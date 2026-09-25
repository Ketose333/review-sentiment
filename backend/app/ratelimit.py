"""Shared fixed-window rate limit so worker count does not multiply the public limit.

The in-process limiter in guards.py bounds one process only: N uvicorn workers or N
instances multiply every limit by N. This module keeps the counters in the PostgreSQL
the API already depends on, so any number of processes enforce one budget. Redis and
queues stay out of scope by design.

Counters are keyed by a salted SHA-256 HMAC of the client address, never the address
itself. Only admitted requests are charged to the global budget, so one client that
floods past its own limit cannot spend everyone else's allowance.
"""

import hashlib
import hmac
import ipaddress
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import (
    rate_limit_global,
    rate_limit_per_ip,
    rate_limit_salt,
    rate_limit_window_seconds,
    shared_rate_limit_enabled,
    trusted_proxy_hops,
)
from backend.app.db import LIMITER_LOCK_TIMEOUT_MS, LIMITER_STATEMENT_TIMEOUT_MS, limiter_session_factory

GLOBAL_BUCKET = "global"
UNKNOWN_CLIENT = "unknown"
# Only the current window is ever read; a couple more absorb clock skew.
RETAINED_WINDOWS = 3
# One budget per /64: a single IPv6 subscriber routinely holds 2**64 addresses, so a
# per-address budget would be no budget at all.
IPV6_CLIENT_PREFIX = 64

# The client row is always counted; the global row only when the client is in budget.
# The client bucket can never equal 'global', so every transaction locks its own client
# row first and the shared row last: one lock order, no deadlock between requests.
_COUNT_STATEMENT = text(
    """
    WITH client AS (
        INSERT INTO rate_limit_counters (bucket, window_start, hits)
        VALUES (:client_bucket, :window_start, 1)
        ON CONFLICT (bucket, window_start) DO UPDATE SET hits = rate_limit_counters.hits + 1
        RETURNING hits
    ), shared AS (
        INSERT INTO rate_limit_counters (bucket, window_start, hits)
        SELECT :global_bucket, :window_start, 1 FROM client WHERE client.hits <= :per_ip
        ON CONFLICT (bucket, window_start) DO UPDATE SET hits = rate_limit_counters.hits + 1
        RETURNING hits
    )
    SELECT (SELECT hits FROM client) AS client_hits, (SELECT hits FROM shared) AS global_hits
    """
)


class SharedLimitUnavailable(Exception):
    """The shared counters cannot be reached, so no request may be admitted."""


def _normalized(candidate: str) -> str | None:
    """Reduce an address to one canonical bucket key, or None if it is not an address.

    Proxies emit several forms for the same client: IPv4-mapped IPv6, bracketed IPv6,
    upper-case hex, and sometimes `address:port`. Left unnormalized, each form would be
    a separate budget, so a proxy that appends the ephemeral port would defeat the
    per-client limit entirely.
    """
    value = candidate.strip()
    if not value:
        return None
    if value.startswith("["):
        value = value[1:].split("]", 1)[0]
    elif value.count(":") == 1 and "." in value:
        value = value.rsplit(":", 1)[0]
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/{IPV6_CLIENT_PREFIX}", strict=False))
    return str(address)


def client_address(request) -> str:
    """Resolve the address to bill, trusting X-Forwarded-For only as far as configured.

    With no trusted hops the peer address is used and any forwarded header is ignored.
    With trusted hops the entry that many positions from the right is the client: those
    entries are appended by proxies we control, so a client cannot shift the index.
    Every forwarded header line is joined first, because a proxy that keeps a
    client-supplied header as its own line would otherwise leave the index inside
    attacker-controlled text. Anything that is not an address becomes one shared
    unidentified bucket rather than a trusted value.
    """
    hops = trusted_proxy_hops()
    if hops == 0:
        peer = request.client.host if request.client else None
        return (peer and _normalized(peer)) or UNKNOWN_CLIENT
    forwarded = [
        part.strip()
        for line in request.headers.getlist("x-forwarded-for")
        for part in line.split(",")
        if part.strip()
    ]
    if len(forwarded) < hops:
        return UNKNOWN_CLIENT
    return _normalized(forwarded[-hops]) or UNKNOWN_CLIENT


def client_bucket(address: str) -> str:
    """Salted HMAC: the counters identify a client without storing one.

    The full digest is kept so a stored key cannot be confused with any raw address
    form — a 128-bit IPv6 address is exactly 32 hex characters, a digest is 64.
    """
    digest = hmac.new(rate_limit_salt().encode("utf-8"), address.encode("utf-8"), hashlib.sha256)
    return f"ip:{digest.hexdigest()}"


def salt_fingerprint() -> str:
    """Non-reversible marker so a salt that differs between processes becomes visible."""
    digest = hmac.new(rate_limit_salt().encode("utf-8"), b"fingerprint", hashlib.sha256)
    return digest.hexdigest()[:8]


def window_start(moment: datetime, window_seconds: int) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("window_start requires an aware datetime")
    epoch = int(moment.timestamp())
    return datetime.fromtimestamp(epoch - epoch % window_seconds, tz=timezone.utc)


def allow(address: str, moment: datetime | None = None) -> bool:
    """Count this request in the shared window and report whether it stays in budget.

    Counting before checking is deliberate: a fixed window records attempts, so a
    client that keeps pushing past the limit does not earn a fresh allowance by racing.
    """
    if not shared_rate_limit_enabled():
        return True
    window = window_start(moment or datetime.now(timezone.utc), rate_limit_window_seconds())
    per_ip = rate_limit_per_ip()
    try:
        with limiter_session_factory()() as session:
            # Neon pooled connections use transaction pooling and reject these as
            # startup options. SET LOCAL stays scoped to this transaction and is
            # supported without leaking settings to a reused backend connection.
            session.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": f"{LIMITER_STATEMENT_TIMEOUT_MS}ms"},
            )
            session.execute(
                text("SELECT set_config('lock_timeout', :timeout, true)"),
                {"timeout": f"{LIMITER_LOCK_TIMEOUT_MS}ms"},
            )
            counted = session.execute(_COUNT_STATEMENT, {
                "client_bucket": client_bucket(address),
                "global_bucket": GLOBAL_BUCKET,
                "window_start": window,
                "per_ip": per_ip,
            }).one_or_none()
            session.commit()
    except (SQLAlchemyError, OSError):
        # Never fail open, and never carry the driver's message: it can hold the DSN.
        raise SharedLimitUnavailable() from None
    if counted is None or counted.client_hits is None:
        # The client row is always written, so a missing count means a broken assumption
        # rather than an empty budget; refusing is the only safe reading.
        raise SharedLimitUnavailable()
    if counted.client_hits > per_ip:
        return False
    if counted.global_hits is None:
        raise SharedLimitUnavailable()
    return counted.global_hits <= rate_limit_global()


def retry_after_seconds(moment: datetime | None = None) -> int:
    """Seconds until the current fixed window ends, so a refusal can say when to retry."""
    window_seconds = rate_limit_window_seconds()
    now = moment or datetime.now(timezone.utc)
    elapsed = (now - window_start(now, window_seconds)).total_seconds()
    return max(1, int(window_seconds - elapsed))


def prune_windows(session, moment: datetime | None = None) -> int:
    """Drop counters no live window can read. The caller owns the transaction."""
    window_seconds = rate_limit_window_seconds()
    cutoff = window_start(moment or datetime.now(timezone.utc), window_seconds) - timedelta(
        seconds=RETAINED_WINDOWS * window_seconds
    )
    deleted = session.execute(
        text("DELETE FROM rate_limit_counters WHERE window_start < :cutoff"), {"cutoff": cutoff}
    ).rowcount
    return deleted or 0
