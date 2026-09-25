"""Keep process-local request limits and rate-limit configuration independent per test."""

import pytest

from backend.app import config, guards


RATE_LIMIT_SETTINGS = (
    config.shared_rate_limit_enabled,
    config.rate_limit_salt,
    config.rate_limit_per_ip,
    config.rate_limit_global,
    config.rate_limit_window_seconds,
    config.trusted_proxy_hops,
)


def clear_rate_limit_settings() -> None:
    for setting in RATE_LIMIT_SETTINGS:
        setting.cache_clear()


@pytest.fixture(autouse=True)
def process_local_rate_limit(monkeypatch):
    """Cases that exercise the shared counters opt in; the rest stay process-local."""
    monkeypatch.setenv("RATE_LIMIT_SHARED", "false")
    clear_rate_limit_settings()
    yield
    clear_rate_limit_settings()


@pytest.fixture(autouse=True)
def fresh_rate_limiter(monkeypatch, process_local_rate_limit):
    monkeypatch.setattr(guards, "limiter", guards.RateLimiter())
