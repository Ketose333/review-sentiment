"""Environment configuration for the API."""

import os
from functools import lru_cache


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    return url


def cors_origins() -> list[str]:
    return [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin.strip()]


@lru_cache
def analysis_timeout_seconds() -> int:
    """Soft synchronous processing budget; inference is checked after it returns."""
    value = int(os.environ.get("ANALYSIS_TIMEOUT_SECONDS", "120"))
    if not 1 <= value <= 3600:
        raise ValueError("ANALYSIS_TIMEOUT_SECONDS must be between 1 and 3600")
    return value


@lru_cache
def analysis_hard_timeout_seconds() -> float:
    """Wall-clock deadline for one isolated task, including the wait for a free worker."""
    value = float(os.environ.get("ANALYSIS_HARD_TIMEOUT_SECONDS", "20"))
    if not 1 <= value <= 600:
        raise ValueError("ANALYSIS_HARD_TIMEOUT_SECONDS must be between 1 and 600")
    if value > analysis_timeout_seconds():
        # A task the hard deadline lets run would be force-failed by the soft check anyway.
        raise ValueError("ANALYSIS_HARD_TIMEOUT_SECONDS must not exceed ANALYSIS_TIMEOUT_SECONDS")
    return value


@lru_cache
def analysis_worker_startup_seconds() -> float:
    """Extra allowance for the first call on a freshly spawned worker (imports, JVM start)."""
    value = float(os.environ.get("ANALYSIS_WORKER_STARTUP_SECONDS", "60"))
    # A measured cold start is 9-11s: a lower allowance would kill every fresh worker.
    if not 15 <= value <= 600:
        raise ValueError("ANALYSIS_WORKER_STARTUP_SECONDS must be between 15 and 600")
    return value


@lru_cache
def analysis_worker_slots() -> int:
    """Concurrent isolated tasks per API process; each warm worker holds its own model copy."""
    value = int(os.environ.get("ANALYSIS_WORKER_SLOTS", "2"))
    if not 1 <= value <= 8:
        raise ValueError("ANALYSIS_WORKER_SLOTS must be between 1 and 8")
    return value


@lru_cache
def shared_rate_limit_enabled() -> bool:
    """Shared counters are the default: a per-process limit is not a public limit."""
    value = os.environ.get("RATE_LIMIT_SHARED", "true").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError("RATE_LIMIT_SHARED must be 'true' or 'false'")
    return value == "true"


@lru_cache
def rate_limit_salt() -> str:
    """Secret that turns a client address into a counter key. Shared by every process."""
    value = os.environ.get("RATE_LIMIT_SALT", "")
    if not shared_rate_limit_enabled():
        return value
    if len(value) < 16:
        raise ValueError("RATE_LIMIT_SALT must be at least 16 characters when RATE_LIMIT_SHARED is true")
    return value


@lru_cache
def analysis_request_slots() -> int:
    """Maximum concurrent POST analyses per API process, including LIME."""
    value = int(os.environ.get("ANALYSIS_REQUEST_SLOTS", "4"))
    if not 1 <= value <= 16:
        raise ValueError("ANALYSIS_REQUEST_SLOTS must be between 1 and 16")
    return value


@lru_cache
def analysis_per_client_slots() -> int:
    value = int(os.environ.get("ANALYSIS_PER_CLIENT_SLOTS", "1"))
    if not 1 <= value <= analysis_request_slots():
        raise ValueError("ANALYSIS_PER_CLIENT_SLOTS must be between 1 and ANALYSIS_REQUEST_SLOTS")
    return value


@lru_cache
def explanation_timeout_seconds(model_id: str) -> float:
    """Independent LIME wall-clock budget after prediction has been committed."""
    defaults = {"tfidf_lr": "20", "lstm": "45", "klue_bert": "180"}
    if model_id not in defaults:
        raise ValueError("unsupported model")
    value = float(os.environ.get(f"{model_id.upper()}_EXPLANATION_TIMEOUT_SECONDS", defaults[model_id]))
    if not 1 <= value <= 600:
        raise ValueError("explanation timeout must be between 1 and 600")
    return value


@lru_cache
def rate_limit_per_ip() -> int:
    value = int(os.environ.get("RATE_LIMIT_PER_IP", "30"))
    if not 1 <= value <= 10000:
        raise ValueError("RATE_LIMIT_PER_IP must be between 1 and 10000")
    return value


@lru_cache
def rate_limit_global() -> int:
    value = int(os.environ.get("RATE_LIMIT_GLOBAL", "300"))
    if not 1 <= value <= 100000:
        raise ValueError("RATE_LIMIT_GLOBAL must be between 1 and 100000")
    if value < rate_limit_per_ip():
        raise ValueError("RATE_LIMIT_GLOBAL must not be below RATE_LIMIT_PER_IP")
    return value


@lru_cache
def rate_limit_window_seconds() -> int:
    value = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
    if not 1 <= value <= 3600:
        raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be between 1 and 3600")
    return value


@lru_cache
def trusted_proxy_hops() -> int:
    """How many trailing X-Forwarded-For entries are added by proxies we control.

    0 means the header is ignored and the peer address is billed. Behind a proxy this
    must be set, or every client shares the proxy's address and one budget.
    """
    value = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
    if not 0 <= value <= 8:
        raise ValueError("TRUSTED_PROXY_HOPS must be between 0 and 8")
    return value
