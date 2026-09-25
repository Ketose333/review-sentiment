"""Optional real PostgreSQL checks for the shared rate limit (set TEST_DATABASE_URL)."""

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.app import guards, ratelimit
from backend.app.db import session_factory
from backend.app.main import app
from backend.tests.conftest import clear_rate_limit_settings


pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="requires migrated PostgreSQL")

SALT = "integration-salt-long-enough"
WINDOW = datetime(2026, 9, 24, 5, 31, tzinfo=timezone.utc)


@pytest.fixture
def shared_counters(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("RATE_LIMIT_SHARED", "true")
    monkeypatch.setenv("RATE_LIMIT_SALT", SALT)
    session_factory.cache_clear()
    clear_rate_limit_settings()
    _clear_counters()
    yield
    _clear_counters()
    clear_rate_limit_settings()
    session_factory.cache_clear()


def _clear_counters() -> None:
    with session_factory()() as session:
        session.execute(text("DELETE FROM rate_limit_counters"))
        session.commit()


def _rows() -> list[tuple[str, int]]:
    with session_factory()() as session:
        return [(bucket, hits) for bucket, hits in session.execute(
            text("SELECT bucket, hits FROM rate_limit_counters ORDER BY bucket")
        ).all()]


def test_per_client_budget_survives_a_fresh_in_process_limiter(shared_counters, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "3")
    clear_rate_limit_settings()
    address = "198.51.100.23"
    assert [ratelimit.allow(address, WINDOW) for _ in range(3)] == [True, True, True]
    # A brand-new in-process limiter proves the refusal comes from the shared counters.
    monkeypatch.setattr(guards, "limiter", guards.RateLimiter())
    assert ratelimit.allow(address, WINDOW) is False
    assert ratelimit.allow("198.51.100.24", WINDOW) is True


def test_global_budget_is_shared_between_different_clients(shared_counters, monkeypatch):
    # One request per address, so only the shared global budget can refuse anyone.
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "2")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL", "4")
    clear_rate_limit_settings()
    assert [ratelimit.allow(f"198.51.100.{index}", WINDOW) for index in range(4)] == [True] * 4
    assert ratelimit.allow("198.51.100.200", WINDOW) is False


def test_a_new_window_restores_the_budget(shared_counters, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "1")
    clear_rate_limit_settings()
    address = "198.51.100.31"
    assert ratelimit.allow(address, WINDOW) is True
    assert ratelimit.allow(address, WINDOW + timedelta(seconds=30)) is False
    assert ratelimit.allow(address, WINDOW + timedelta(seconds=60)) is True


def test_counters_never_hold_the_client_address(shared_counters):
    address = "198.51.100.42"
    assert ratelimit.allow(address, WINDOW) is True
    buckets = [bucket for bucket, _hits in _rows()]
    assert sorted(buckets) == sorted(["global", ratelimit.client_bucket(address)])
    with session_factory()() as session:
        dumped = session.scalar(text("SELECT string_agg(row_to_json(r)::text, ' ') FROM rate_limit_counters r"))
    assert address not in dumped and SALT not in dumped


def test_the_table_refuses_a_raw_address_as_a_bucket(shared_counters):
    # A dotted quad and a bare IPv6 address (exactly 32 hex characters) must both fail.
    for raw in ("198.51.100.42", "20010db8000000000000000000000001", "ip:20010db8000000000000000000000001"):
        with session_factory()() as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    text("INSERT INTO rate_limit_counters (bucket, window_start, hits) VALUES (:b, :w, 1)"),
                    {"b": raw, "w": WINDOW},
                )
                session.commit()


def test_pruning_keeps_live_windows_only(shared_counters):
    assert ratelimit.allow("198.51.100.51", WINDOW) is True
    with session_factory()() as session:
        # prune_windows leaves the transaction to the caller, so nothing is visible yet.
        assert ratelimit.prune_windows(session, WINDOW) == 0
        session.commit()
        assert len(_rows()) == 2
        later = WINDOW + timedelta(seconds=60 * (ratelimit.RETAINED_WINDOWS + 1))
        assert ratelimit.prune_windows(session, later) == 2
        session.commit()
    assert _rows() == []


def test_requests_are_refused_once_the_shared_budget_is_spent(shared_counters, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "2")
    clear_rate_limit_settings()
    # Pin the window so three requests cannot straddle a real minute boundary.
    monkeypatch.setattr(ratelimit, "window_start", lambda _moment, _seconds: WINDOW)
    with TestClient(app) as client:
        first = client.get("/v1/models")
        monkeypatch.setattr(guards, "limiter", guards.RateLimiter())
        second = client.get("/v1/models")
        monkeypatch.setattr(guards, "limiter", guards.RateLimiter())
        third = client.get("/v1/models")
    assert first.status_code == 200 and second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "RATE_LIMITED"
    assert third.headers["X-Request-Id"] == third.json()["error"]["requestId"]


def _allow_in_child(database_url, salt, per_ip, address, moment, attempts):
    """Runs in a separate interpreter: only the database can carry the budget across."""
    import os as child_os
    from datetime import datetime as child_datetime

    child_os.environ.update({
        "DATABASE_URL": database_url,
        "RATE_LIMIT_SHARED": "true",
        "RATE_LIMIT_SALT": salt,
        "RATE_LIMIT_PER_IP": per_ip,
    })
    from backend.app import ratelimit as child_ratelimit

    when = child_datetime.fromisoformat(moment)
    return [child_ratelimit.allow(address, when) for _ in range(attempts)]


def test_an_over_budget_client_cannot_spend_the_global_budget(shared_counters, monkeypatch):
    """One flooding client must not turn the shared global limit into a public outage."""
    monkeypatch.setenv("RATE_LIMIT_PER_IP", "2")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL", "4")
    clear_rate_limit_settings()
    flooder = "198.51.100.77"
    assert [ratelimit.allow(flooder, WINDOW) for _ in range(2)] == [True, True]
    assert [ratelimit.allow(flooder, WINDOW) for _ in range(20)] == [False] * 20
    counted = dict(_rows())
    assert counted["global"] == 2, "refused requests must not be charged to the global budget"
    assert counted[ratelimit.client_bucket(flooder)] == 22
    assert [ratelimit.allow(f"198.51.100.{index}", WINDOW) for index in (81, 82)] == [True, True]


def test_the_shared_budget_holds_across_separate_os_processes(shared_counters, monkeypatch):
    import multiprocessing

    monkeypatch.setenv("RATE_LIMIT_PER_IP", "4")
    clear_rate_limit_settings()
    address = "198.51.100.91"
    assert ratelimit.allow(address, WINDOW) is True
    context = multiprocessing.get_context("spawn")
    with context.Pool(1) as pool:
        verdicts = pool.apply(
            _allow_in_child,
            (os.environ["TEST_DATABASE_URL"], SALT, "4", address, WINDOW.isoformat(), 4),
        )
    # One request was spent in this process, so the child sees only three of the four.
    assert verdicts == [True, True, True, False]


def test_counters_are_pruned_on_the_window_cadence(shared_counters):
    from backend.app import maintenance

    assert maintenance.counter_period_seconds() == max(60, ratelimit.RETAINED_WINDOWS * 60)
    assert maintenance.counter_period_seconds() < maintenance.RETENTION_PERIOD_SECONDS
    # A pinned past window is already stale; the live window must survive the same sweep.
    assert ratelimit.allow("198.51.100.61", WINDOW) is True
    assert ratelimit.allow("198.51.100.62") is True
    maintenance.prune_counters_once()
    surviving = dict(_rows())
    assert ratelimit.client_bucket("198.51.100.62") in surviving
    assert ratelimit.client_bucket("198.51.100.61") not in surviving


def test_concurrent_requests_do_not_lose_or_inflate_counts(shared_counters, monkeypatch):
    """Concurrency must not lose increments, deadlock, or trip the limiter's lock timeout."""
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("RATE_LIMIT_PER_IP", "4")
    monkeypatch.setenv("RATE_LIMIT_GLOBAL", "24")
    clear_rate_limit_settings()
    addresses = [f"198.51.100.{index}" for index in range(101, 107)] * 4
    with ThreadPoolExecutor(max_workers=8) as threads:
        verdicts = list(threads.map(lambda address: ratelimit.allow(address, WINDOW), addresses))
    counted = dict(_rows())
    assert all(verdicts), "6 clients x 4 requests are all inside a 4 per-client, 24 global budget"
    assert counted["global"] == sum(verdicts), "the global counter must match the admitted requests"
    assert sum(hits for bucket, hits in counted.items() if bucket != "global") == len(addresses)
    assert all(counted[ratelimit.client_bucket(address)] == 4 for address in set(addresses))
