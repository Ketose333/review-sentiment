"""Shared rate limit: key privacy, client resolution, and configuration bounds."""

import re
from datetime import datetime, timezone
from types import SimpleNamespace

from starlette.datastructures import Headers

import pytest
from fastapi.testclient import TestClient

from backend.app import config, guards, ratelimit
from backend.app.db import get_session
from backend.app.main import app
from backend.tests.conftest import clear_rate_limit_settings


SALT = "test-salt-with-enough-length"


@pytest.fixture
def shared_enabled(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_SHARED", "true")
    monkeypatch.setenv("RATE_LIMIT_SALT", SALT)
    clear_rate_limit_settings()
    yield
    clear_rate_limit_settings()


def request_with(peer: str | None = "203.0.113.9", forwarded: str | None = None):
    headers = Headers({} if forwarded is None else {"x-forwarded-for": forwarded})
    client = None if peer is None else SimpleNamespace(host=peer)
    return SimpleNamespace(client=client, headers=headers)


@pytest.mark.parametrize("hops,forwarded,expected", [
    (0, None, "203.0.113.9"),
    (0, "198.51.100.7, 10.0.0.1", "203.0.113.9"),
    (1, "198.51.100.7, 10.0.0.1", "10.0.0.1"),
    (2, "198.51.100.7, 10.0.0.1", "198.51.100.7"),
    (2, "10.0.0.1", "unknown"),
    (1, None, "unknown"),
    (1, "   ", "unknown"),
    (1, "198.51.100.7, not-an-address", "unknown"),
    (1, "198.51.100.7, 10.0.0.1:54321", "10.0.0.1"),
    (1, "198.51.100.7, [2001:db8::1]", "2001:db8::/64"),
    (1, "198.51.100.7, 2001:DB8:0:0:1:2:3:4", "2001:db8::/64"),
    (1, "198.51.100.7, ::ffff:203.0.113.5", "203.0.113.5"),
])
def test_client_address_trusts_only_configured_hops(monkeypatch, hops, forwarded, expected):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", str(hops))
    clear_rate_limit_settings()
    assert ratelimit.client_address(request_with(forwarded=forwarded)) == expected


def test_missing_peer_is_not_an_error(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
    clear_rate_limit_settings()
    assert ratelimit.client_address(request_with(peer=None)) == "unknown"


def test_bucket_is_opaque_stable_and_salt_dependent(shared_enabled, monkeypatch):
    address = "203.0.113.9"
    bucket = ratelimit.client_bucket(address)
    # 64 hex characters, so the stored key can never be mistaken for an IPv6 address.
    assert re.fullmatch(r"ip:[0-9a-f]{64}", bucket)
    assert address not in bucket
    assert ratelimit.client_bucket(address) == bucket
    assert ratelimit.client_bucket("203.0.113.10") != bucket
    monkeypatch.setenv("RATE_LIMIT_SALT", "another-salt-long-enough")
    clear_rate_limit_settings()
    assert ratelimit.client_bucket(address) != bucket


@pytest.mark.parametrize("moment,window,expected", [
    ("2026-09-24T05:31:47+00:00", 60, "2026-09-24T05:31:00+00:00"),
    ("2026-09-24T05:31:00+00:00", 60, "2026-09-24T05:31:00+00:00"),
    ("2026-09-24T05:31:47+00:00", 300, "2026-09-24T05:30:00+00:00"),
])
def test_window_start_floors_to_the_window(moment, window, expected):
    computed = ratelimit.window_start(datetime.fromisoformat(moment), window)
    assert computed == datetime.fromisoformat(expected)
    assert computed.tzinfo is timezone.utc


def test_disabled_shared_limit_never_touches_the_database(monkeypatch):
    def unusable():
        raise AssertionError("a disabled shared limit must not open a session")

    monkeypatch.setattr(ratelimit, "limiter_session_factory", unusable)
    assert ratelimit.allow("203.0.113.9") is True


def test_unreachable_counters_are_reported_as_unavailable_not_allowed(shared_enabled, monkeypatch):
    from sqlalchemy.exc import OperationalError

    def broken():
        raise OperationalError("SELECT", {}, Exception("secret dsn"))

    monkeypatch.setattr(ratelimit, "limiter_session_factory", broken)
    with pytest.raises(ratelimit.SharedLimitUnavailable) as failure:
        ratelimit.allow("203.0.113.9")
    assert "secret dsn" not in str(failure.value)


def test_request_is_refused_with_503_when_counters_are_unreachable(monkeypatch):
    def database_must_not_be_used():
        raise AssertionError("the guard must refuse before any DB session is resolved")

    def unavailable(_address):
        raise ratelimit.SharedLimitUnavailable()

    monkeypatch.setattr(guards, "allow_shared", unavailable)
    app.dependency_overrides[get_session] = database_must_not_be_used
    try:
        with TestClient(app) as client:
            response = client.get("/v1/models")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REGISTRY_UNAVAILABLE"


def test_shared_refusal_is_rate_limited_not_an_error(monkeypatch):
    monkeypatch.setattr(guards, "allow_shared", lambda _address: False)
    with TestClient(app) as client:
        response = client.get("/v1/models")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_process_local_limiter_defaults_follow_configuration(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "7")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL", "11")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "30")
    clear_rate_limit_settings()
    limiter = guards.RateLimiter()
    factor = guards.LOCAL_GATE_FACTOR
    assert (limiter.per_ip, limiter.global_limit, limiter.window_seconds) == (7 * factor, 11 * factor, 30)


@pytest.mark.parametrize("name,value", [
    ("RATE_LIMIT_SHARED", "yes"),
    ("RATE_LIMIT_SALT", "too-short"),
    ("RATE_LIMIT_PER_IP", "0"),
    ("RATE_LIMIT_GLOBAL", "0"),
    ("RATE_LIMIT_WINDOW_SECONDS", "0"),
    ("RATE_LIMIT_WINDOW_SECONDS", "3601"),
    ("TRUSTED_PROXY_HOPS", "-1"),
    ("TRUSTED_PROXY_HOPS", "9"),
])
def test_invalid_rate_limit_configuration_prevents_app_start(monkeypatch, name, value):
    monkeypatch.setenv("RATE_LIMIT_SHARED", "true")
    monkeypatch.setenv("RATE_LIMIT_SALT", SALT)
    monkeypatch.setenv(name, value)
    clear_rate_limit_settings()
    try:
        with pytest.raises(ValueError):
            with TestClient(app):
                pass
    finally:
        clear_rate_limit_settings()


def test_global_limit_below_per_ip_is_rejected(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "100")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL", "50")
    clear_rate_limit_settings()
    with pytest.raises(ValueError):
        config.rate_limit_global()


def test_salt_is_not_required_while_the_shared_limit_is_off(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_SHARED", "false")
    monkeypatch.delenv("RATE_LIMIT_SALT", raising=False)
    clear_rate_limit_settings()
    assert config.rate_limit_salt() == ""


def test_every_address_in_one_ipv6_subnet_shares_a_budget(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    clear_rate_limit_settings()
    first = ratelimit.client_address(request_with(forwarded="10.0.0.1, 2001:db8::dead"))
    second = ratelimit.client_address(request_with(forwarded="10.0.0.1, 2001:db8::beef"))
    other = ratelimit.client_address(request_with(forwarded="10.0.0.1, 2001:db9::1"))
    assert first == second == "2001:db8::/64"
    assert other != first


def test_a_second_forwarded_header_line_cannot_shift_the_trusted_index(monkeypatch):
    """A proxy that keeps a client-supplied header as its own line must not be trusted."""
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    clear_rate_limit_settings()
    request = SimpleNamespace(
        client=SimpleNamespace(host="203.0.113.9"),
        headers=Headers(raw=[
            (b"x-forwarded-for", b"9.9.9.9"),
            (b"x-forwarded-for", b"10.0.0.1"),
        ]),
    )
    assert ratelimit.client_address(request) == "10.0.0.1"


def test_naive_moments_are_rejected():
    with pytest.raises(ValueError):
        ratelimit.window_start(datetime(2026, 9, 24, 5, 31), 60)


def test_missing_counts_are_refused_rather_than_admitted(shared_enabled, monkeypatch):
    class Result:
        def __init__(self, row):
            self._row = row

        def one_or_none(self):
            return self._row

    class Session:
        def __init__(self, row):
            self._row = row

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def execute(self, *_args, **_kwargs):
            return Result(self._row)

        def commit(self):
            return None

    rows = (None, SimpleNamespace(client_hits=None, global_hits=1), SimpleNamespace(client_hits=1, global_hits=None))
    for row in rows:
        monkeypatch.setattr(ratelimit, "limiter_session_factory", lambda row=row: (lambda: Session(row)))
        with pytest.raises(ratelimit.SharedLimitUnavailable):
            ratelimit.allow("203.0.113.9")


def test_retry_after_points_at_the_end_of_the_window(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    clear_rate_limit_settings()
    assert ratelimit.retry_after_seconds(datetime(2026, 9, 24, 5, 31, 15, tzinfo=timezone.utc)) == 45
    assert ratelimit.retry_after_seconds(datetime(2026, 9, 24, 5, 31, 0, tzinfo=timezone.utc)) == 60
    assert ratelimit.retry_after_seconds(datetime(2026, 9, 24, 5, 31, 59, tzinfo=timezone.utc)) == 1


def test_refusal_tells_the_client_when_to_retry(monkeypatch):
    monkeypatch.setattr(guards, "allow_shared", lambda _address: False)
    with TestClient(app) as client:
        response = client.get("/v1/models")
    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60


def test_health_endpoint_is_never_rate_limited_and_needs_no_database(monkeypatch):
    def database_must_not_be_used():
        raise AssertionError("the health endpoint must not resolve a DB session")

    def must_not_be_gated(_address):
        raise AssertionError("the health endpoint must not consume the public budget")

    monkeypatch.setattr(guards, "allow_shared", must_not_be_gated)
    app.dependency_overrides[get_session] = database_must_not_be_used
    try:
        with TestClient(app) as client:
            responses = [client.get("/healthz") for _ in range(5)]
    finally:
        app.dependency_overrides.clear()
    assert [response.status_code for response in responses] == [200] * 5
    assert responses[0].json() == {"status": "ok"}


def test_local_gate_is_looser_than_the_shared_budget(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "30")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL", "300")
    clear_rate_limit_settings()
    limiter = guards.RateLimiter()
    assert limiter.per_ip == 30 * guards.LOCAL_GATE_FACTOR
    assert limiter.global_limit == 300 * guards.LOCAL_GATE_FACTOR


def test_a_full_address_map_evicts_instead_of_refusing_a_newcomer():
    limiter = guards.RateLimiter(per_ip=5, global_limit=10000, window_seconds=60, max_ips=2)
    assert limiter.allow("198.51.100.1") is True
    assert limiter.allow("198.51.100.2") is True
    assert limiter.allow("198.51.100.3") is True
    assert len(limiter._by_ip) == 2


def test_salt_fingerprint_is_short_and_does_not_reveal_the_salt(shared_enabled):
    fingerprint = ratelimit.salt_fingerprint()
    assert re.fullmatch(r"[0-9a-f]{8}", fingerprint)
    assert fingerprint not in SALT
