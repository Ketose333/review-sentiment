"""Idempotent periodic retention maintenance."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from backend.app import isolation, ratelimit
from backend.app.analyses import prune_expired, recover_stale
from backend.app.config import (
    analysis_hard_timeout_seconds,
    analysis_timeout_seconds,
    analysis_worker_slots,
    analysis_request_slots,
    analysis_per_client_slots,
    analysis_worker_startup_seconds,
    explanation_timeout_seconds,
    rate_limit_global,
    rate_limit_per_ip,
    rate_limit_salt,
    rate_limit_window_seconds,
    shared_rate_limit_enabled,
    trusted_proxy_hops,
)
from backend.app.db import session_factory
from backend.app.guards import AnalysisAdmission

# Scheduling and the run's own DB writes happen outside the isolated budgets.
STALE_MARGIN_SECONDS = 60
RETENTION_PERIOD_SECONDS = 60 * 60
MIN_COUNTER_PERIOD_SECONDS = 60


def stale_age_seconds() -> float:
    """Never recover a run that a live request could still be working on.

    One request can spend the hard timeout on preprocessing, inference and the
    explanation in turn, so the soft limit alone is no longer an upper bound.
    """
    return max(2 * analysis_timeout_seconds(), isolation.request_worst_case_seconds() + STALE_MARGIN_SECONDS)


def counter_period_seconds() -> int:
    """Prune counters on the window's own cadence, not the hourly retention cadence.

    Hourly pruning would leave an hour of per-minute counters in a table that every
    public request updates, so the retained window count would not be the real retention.
    """
    return max(MIN_COUNTER_PERIOD_SECONDS, ratelimit.RETAINED_WINDOWS * rate_limit_window_seconds())


def maintenance_once() -> None:
    with session_factory()() as session:
        recover_stale(session, max_age_seconds=stale_age_seconds())
        prune_expired(session)


def prune_counters_once() -> None:
    with session_factory()() as session:
        ratelimit.prune_windows(session)
        session.commit()


async def _repeat(work, period_seconds: int, failure_event: str) -> None:
    while True:
        try:
            await asyncio.to_thread(work)
        except Exception:
            # Fixed event code only: DB exceptions may contain sensitive parameters.
            logging.getLogger(__name__).error(failure_event)
        await asyncio.sleep(period_seconds)


async def maintenance_loop() -> None:
    await _repeat(maintenance_once, RETENTION_PERIOD_SECONDS, "analysis_maintenance_failed")


async def counter_loop() -> None:
    await _repeat(prune_counters_once, counter_period_seconds(), "rate_limit_maintenance_failed")


@asynccontextmanager
async def lifespan(_app):
    analysis_timeout_seconds()
    analysis_hard_timeout_seconds()
    analysis_worker_startup_seconds()
    analysis_worker_slots()
    _app.state.analysis_slots = asyncio.Semaphore(analysis_request_slots())
    _app.state.analysis_admission = AnalysisAdmission(analysis_per_client_slots())
    for model_id in ("tfidf_lr", "lstm", "klue_bert"):
        explanation_timeout_seconds(model_id)
    # Prime every setting so a bad value stops startup instead of a later request.
    rate_limit_salt()
    rate_limit_per_ip()
    rate_limit_global()
    rate_limit_window_seconds()
    trusted_proxy_hops()
    if shared_rate_limit_enabled():
        # A salt that differs between processes silently restores the per-process limit,
        # so make the value comparable across logs without revealing it.
        logging.getLogger(__name__).info("rate_limit_salt_fingerprint=%s", ratelimit.salt_fingerprint())
    tasks = [asyncio.create_task(maintenance_loop()), asyncio.create_task(counter_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        # Never leave a worker process behind when the API process stops.
        await asyncio.to_thread(isolation.shutdown)
