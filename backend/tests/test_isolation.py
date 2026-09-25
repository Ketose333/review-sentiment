"""Hard timeout: a stuck task is killed, and no worker process outlives the pool."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app import isolation
from backend.app.artifacts import ArtifactUnavailable


@pytest.fixture
def fast_deadline(monkeypatch):
    monkeypatch.setattr(isolation, "analysis_hard_timeout_seconds", lambda: 1.0)
    monkeypatch.setattr(isolation, "analysis_worker_startup_seconds", lambda: 120.0)


@pytest.fixture
def pool():
    created = isolation.Pool(1)
    try:
        yield created
    finally:
        created.shutdown()


def test_hard_timeout_kills_the_worker_and_the_next_call_recovers(fast_deadline, pool):
    assert pool.run("sleep", None, "0") is True
    started = time.monotonic()
    with pytest.raises(isolation.WorkerTimeout):
        pool.run("sleep", None, "120")
    elapsed = time.monotonic() - started
    assert elapsed < 10, "the deadline must not wait for the task to finish"
    # A reaped exit code is proof the worker was killed, not merely abandoned.
    assert pool._slots[0].last_exit_code is not None
    assert pool.run("sleep", None, "0") is True


def test_startup_allowance_covers_only_the_first_call_on_a_fresh_worker(monkeypatch, pool):
    # A 3s task only fits a 1.5s budget because the first call adds the spawn allowance.
    monkeypatch.setattr(isolation, "analysis_hard_timeout_seconds", lambda: 1.5)
    monkeypatch.setattr(isolation, "analysis_worker_startup_seconds", lambda: 120.0)
    assert pool.run("sleep", None, "3") is True
    # The same 3s task on the warm worker times out: a 1.5s budget plus a 15s allowance
    # would have been enough, so this fails only because the allowance is not reapplied.
    monkeypatch.setattr(isolation, "analysis_worker_startup_seconds", lambda: 15.0)
    started = time.monotonic()
    with pytest.raises(isolation.WorkerTimeout):
        pool.run("sleep", None, "3")
    assert time.monotonic() - started < 10


def test_all_slots_busy_is_reported_as_unavailable(fast_deadline, pool):
    assert pool._slots[0].lock.acquire(blocking=False)
    try:
        started = time.monotonic()
        with pytest.raises(isolation.WorkerUnavailable):
            pool.run("sleep", None, "0")
        assert time.monotonic() - started < 10
    finally:
        pool._slots[0].lock.release()


def test_concurrent_callers_use_separate_workers(monkeypatch):
    # A wider budget than fast_deadline: the other thread is spawning a worker that
    # imports sklearn and starts a JVM on the same machine.
    monkeypatch.setattr(isolation, "analysis_hard_timeout_seconds", lambda: 5.0)
    monkeypatch.setattr(isolation, "analysis_worker_startup_seconds", lambda: 120.0)
    created = isolation.Pool(2)
    try:
        assert created.run("sleep", None, "0") is True
        gate = threading.Barrier(2, timeout=150)

        def held_call():
            gate.wait()
            return created.run("sleep", None, "0.2")

        with ThreadPoolExecutor(max_workers=2) as threads:
            calls = [threads.submit(held_call) for _ in range(2)]
            assert [call.result(timeout=150) for call in calls] == [True, True]
        assert len({slot._process.pid for slot in created._slots}) == 2
    finally:
        created.shutdown()


def test_task_failure_never_carries_text_back_and_keeps_the_worker(fast_deadline, pool):
    assert pool.run("sleep", None, "0") is True
    with pytest.raises(isolation.TaskFailed) as failure:
        pool.run("sleep", None, "비밀 문장")
    assert "비밀 문장" not in str(failure.value)
    assert failure.value.__cause__ is None and failure.value.args == ()
    assert pool.run("sleep", None, "0") is True


def test_missing_artifacts_surface_as_model_unavailable(fast_deadline, pool, monkeypatch):
    monkeypatch.delenv("TFIDF_ARTIFACT_DIR", raising=False)
    row = {
        "model_id": "tfidf_lr", "enabled": True,
        "artifact_repo": "Ketose333/review-sentiment-assets",
        "artifact_revision": "915d7784e3c81333d6812913b0a80eda37fdbd41",
        "artifact_manifest": {},
    }
    from types import SimpleNamespace

    with pytest.raises(ArtifactUnavailable):
        pool.run("predict", SimpleNamespace(**row), "정말 좋은 영화")


def test_shutdown_leaves_no_worker_process(fast_deadline):
    created = isolation.Pool(1)
    assert created.run("sleep", None, "0") is True
    created.shutdown()
    assert created._slots[0].last_exit_code is not None
    assert created._slots[0]._process is None
    created.shutdown()


def test_shared_pool_is_replaced_after_shutdown(fast_deadline):
    first = isolation.pool()
    try:
        assert isolation.pool() is first
    finally:
        isolation.shutdown()
    second = isolation.pool()
    try:
        assert second is not first
    finally:
        isolation.shutdown()


def test_saturation_near_the_deadline_keeps_the_warm_worker(fast_deadline, pool):
    """P1: winning a slot with no budget left is saturation, not a stuck worker."""
    assert pool.run("sleep", None, "0") is True
    slot = pool._slots[0]
    warm_pid = slot._process.pid
    with pytest.raises(isolation.WorkerUnavailable):
        slot.call("sleep", None, "0", time.monotonic() + 0.01, isolation.min_task_slice_seconds(1.0))
    assert slot._process is not None and slot._process.pid == warm_pid
    assert slot.last_exit_code is None
    assert pool.run("sleep", None, "0") is True


def test_repeated_discard_is_safe_from_several_threads(fast_deadline, pool):
    assert pool.run("sleep", None, "0") is True
    slot = pool._slots[0]
    with ThreadPoolExecutor(max_workers=3) as threads:
        for call in [threads.submit(slot._discard) for _ in range(3)]:
            call.result(timeout=30)
    assert slot._process is None and slot.last_exit_code is not None


def test_shutdown_during_a_stuck_call_does_not_raise(monkeypatch):
    monkeypatch.setattr(isolation, "analysis_hard_timeout_seconds", lambda: 60.0)
    monkeypatch.setattr(isolation, "analysis_worker_startup_seconds", lambda: 120.0)
    created = isolation.Pool(1)
    try:
        assert created.run("sleep", None, "0") is True
        with ThreadPoolExecutor(max_workers=1) as threads:
            stuck = threads.submit(created.run, "sleep", None, "120")
            time.sleep(1)
            created.shutdown()
            with pytest.raises((isolation.WorkerUnavailable, isolation.WorkerTimeout)):
                stuck.result(timeout=60)
        assert created._slots[0]._process is None
    finally:
        created.shutdown()


def test_explanations_cannot_take_the_slot_reserved_for_predictions(fast_deadline):
    created = isolation.Pool(2)
    assert created._slots[0].lock.acquire(blocking=False)
    try:
        started = time.monotonic()
        with pytest.raises(isolation.WorkerUnavailable):
            created.run("explain", None, "합성 리뷰")
        assert time.monotonic() - started < 10
        assert created.run("sleep", None, "0") is True
    finally:
        created._slots[0].lock.release()
        created.shutdown()


def test_a_single_slot_still_allows_explanations():
    created = isolation.Pool(1)
    try:
        assert created._candidates("explain") == created._slots
    finally:
        created.shutdown()


def test_request_worst_case_covers_three_killed_tasks(monkeypatch):
    monkeypatch.setattr(isolation, "analysis_hard_timeout_seconds", lambda: 20.0)
    monkeypatch.setattr(isolation, "analysis_worker_startup_seconds", lambda: 60.0)
    from backend.app.config import explanation_timeout_seconds
    expected = 2 * (20.0 + 60.0 + 2 * isolation.TERMINATE_GRACE_SECONDS) + max(
        explanation_timeout_seconds(model_id) for model_id in ("tfidf_lr", "lstm", "klue_bert")
    ) + 60.0 + 2 * isolation.TERMINATE_GRACE_SECONDS
    assert isolation.request_worst_case_seconds() == expected


def test_minimum_slice_never_eats_the_whole_budget():
    assert isolation.min_task_slice_seconds(20.0) == 1.0
    assert isolation.min_task_slice_seconds(1.0) == 0.25
    assert isolation.min_task_slice_seconds(2.0) == 0.5
