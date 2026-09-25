"""Run model work in killable worker processes so a stuck call cannot outlive its deadline.

The soft budget can only be observed after inference returns. Neither LIME nor the
Java tokenizer can be interrupted from a Python thread, so the API runs both in
separate processes and kills the process once its deadline passes. Workers stay
warm between requests: a spawned worker pays the framework import and JVM start
cost once, so only the first call on a fresh worker gets the startup allowance.
"""

import multiprocessing
import time
from contextlib import suppress
from threading import Lock
from types import SimpleNamespace

from backend.app.artifacts import ArtifactUnavailable
from backend.app.config import (
    analysis_hard_timeout_seconds,
    analysis_worker_slots,
    analysis_worker_startup_seconds,
)

TERMINATE_GRACE_SECONDS = 2.0
ACQUIRE_POLL_SECONDS = 0.05
EXPLANATION_ACQUIRE_SECONDS = 0.05
# Least budget worth committing to a worker. Winning a slot with less left than this
# means the process is saturated, not that the worker is stuck: report it as such
# instead of sending work the deadline will immediately kill. Kept a share of the
# budget as well as an absolute cap, so a small configured deadline is not spent
# entirely on this check (time.monotonic() resolution is ~16ms on Windows).
MIN_TASK_SLICE_CAP_SECONDS = 1.0
MIN_TASK_SLICE_SHARE = 0.25
# Slots held back from optional explanations so LIME cannot starve the mandatory path.
SLOTS_RESERVED_FOR_PREDICTION = 1
# Isolated calls one request can make in turn: main.py's tokens and predict, and
# explanation.py's explain. Adding a fourth would invalidate request_worst_case_seconds.
TASKS_PER_REQUEST = 3
ROW_FIELDS = ("model_id", "enabled", "artifact_repo", "artifact_revision", "artifact_manifest")


class WorkerUnavailable(Exception):
    """No worker ran the task: spawn failed, the transport broke, or every slot was busy."""


class WorkerTimeout(Exception):
    """The worker missed its deadline and was killed."""


class TaskFailed(Exception):
    """The task raised inside the worker; the reason is deliberately not carried across."""


def _task_predict(row, text: str):
    if row.model_id == "tfidf_lr":
        from backend.app.tfidf import predict
    else:
        from backend.app.neural import predict
    return predict(row, text)


def _task_tokens(_row, text: str):
    from backend.app.tfidf import has_analyzable_tokens

    return has_analyzable_tokens(text)


def _task_explain(row, text: str):
    from src.explainability.lime_explainer import explain

    from backend.app.explanation import MAX_FEATURES, SAMPLE_COUNT
    if row.model_id == "tfidf_lr":
        from backend.app.tfidf import ready
    else:
        from backend.app.neural import ready
    samples = {"tfidf_lr": SAMPLE_COUNT, "lstm": 30, "klue_bert": 30}[row.model_id]
    return explain(ready(row), text, num_samples=samples, num_features=MAX_FEATURES)


def _task_sleep(_row, text: str):
    """Self-check task for the hard-timeout tests; no HTTP path reaches it.

    It has to live in this registry rather than be injected by a test: under "spawn"
    the worker re-imports this module, so a task patched into the parent's dict
    would not exist in the child.
    """
    time.sleep(float(text))
    return True


TASKS = {"predict": _task_predict, "tokens": _task_tokens, "explain": _task_explain, "sleep": _task_sleep}


def min_task_slice_seconds(budget: float) -> float:
    return min(MIN_TASK_SLICE_CAP_SECONDS, budget * MIN_TASK_SLICE_SHARE)


def _describe(row) -> dict | None:
    """Send only the registry fields the worker verifies; ORM instances stay in the parent."""
    if row is None:
        return None
    return {name: getattr(row, name) for name in ROW_FIELDS}


def _restore(described: dict | None):
    return None if described is None else SimpleNamespace(**described)


def _worker(connection) -> None:
    while True:
        try:
            message = connection.recv()
        except (EOFError, OSError, ValueError):
            return
        if message is None:
            return
        name, described, text = message
        try:
            value = TASKS[name](_restore(described), text)
        except ArtifactUnavailable:
            reply = ("unavailable", None)
        except Exception:
            # Exception text can quote the submitted review; never send it back.
            reply = ("failed", None)
        else:
            reply = ("ok", value)
        try:
            connection.send(reply)
        except (OSError, ValueError):
            return


class _Slot:
    """One warm worker process, held by exactly one caller at a time."""

    def __init__(self):
        self.lock = Lock()
        # Exit code of the worker this slot last discarded; None until one is reaped.
        self.last_exit_code = None
        # Serializes worker teardown: a stuck caller and shutdown can both reach it.
        self._lifecycle = Lock()
        self._process = None
        self._connection = None

    def call(self, name: str, row, text: str, deadline: float, min_slice: float):
        if deadline - time.monotonic() < min_slice:
            raise WorkerUnavailable()
        if self._process is None or not self._process.is_alive():
            self._discard()
            self._start()
            deadline += analysis_worker_startup_seconds()
        # Keep a local handle: shutdown may drop the slot's connection while this call runs.
        connection = self._connection
        try:
            connection.send((name, _describe(row), text))
        except (OSError, ValueError, AttributeError):
            self._discard()
            raise WorkerUnavailable() from None
        remaining = deadline - time.monotonic()
        try:
            arrived = remaining > 0 and connection.poll(remaining)
        except (OSError, ValueError):
            self._discard()
            raise WorkerUnavailable() from None
        if not arrived:
            self._discard()
            raise WorkerTimeout()
        try:
            kind, value = connection.recv()
        except (EOFError, OSError, ValueError):
            self._discard()
            raise WorkerUnavailable() from None
        if kind == "unavailable":
            raise ArtifactUnavailable()
        if kind != "ok":
            raise TaskFailed()
        return value

    # poll() respects the deadline; the recv() that follows does not. That is safe only
    # because a reply is small enough to arrive in one pipe write (a status pair, or at
    # most MAX_FEATURES token/weight pairs), and a worker killed mid-write surfaces as
    # EOFError. A larger reply payload would have to bound the read itself.

    def _start(self) -> None:
        context = multiprocessing.get_context("spawn")
        parent_end, child_end = context.Pipe()
        process = context.Process(target=_worker, args=(child_end,), daemon=True)
        try:
            process.start()
        except Exception:
            parent_end.close()
            child_end.close()
            raise WorkerUnavailable() from None
        # Close the parent's copy of the child end so a dead worker surfaces as EOF.
        child_end.close()
        self._process, self._connection = process, parent_end

    def _discard(self, close_connection: bool = True) -> None:
        with self._lifecycle:
            self._teardown(close_connection)

    def _teardown(self, close_connection: bool) -> None:
        """Kill the worker; only the thread that owns the slot may close the pipe.

        On Windows, closing a Connection while another thread sits in poll() destroys
        an Overlapped object with I/O in flight. Killing the worker is enough to wake
        that thread with EOF, and it then closes the pipe itself.
        """
        process, connection = self._process, self._connection
        self._process = None
        if close_connection:
            self._connection = None
        if connection is not None and close_connection:
            with suppress(OSError):
                connection.close()
        if process is None:
            return
        if process.is_alive():
            process.terminate()
            process.join(TERMINATE_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join(TERMINATE_GRACE_SECONDS)
        self.last_exit_code = process.exitcode
        with suppress(ValueError, OSError):
            process.close()


class Pool:
    def __init__(self, size: int):
        self._slots = [_Slot() for _ in range(size)]
        self._closed = False

    def run(self, name: str, row, text: str, budget: float | None = None):
        """Bound one task by the hard timeout, including the wait for a free worker."""
        budget = analysis_hard_timeout_seconds() if budget is None else budget
        deadline = time.monotonic() + budget
        acquire_deadline = min(deadline, time.monotonic() + EXPLANATION_ACQUIRE_SECONDS) if name == "explain" else deadline
        slot = self._acquire(acquire_deadline, self._candidates(name))
        try:
            if self._closed:
                raise WorkerUnavailable()
            return slot.call(name, row, text, deadline, min_task_slice_seconds(budget))
        finally:
            slot.lock.release()

    def _candidates(self, name: str) -> list:
        """Optional explanations skip the reserved slot; predictions take it first."""
        if name != "explain" or len(self._slots) <= SLOTS_RESERVED_FOR_PREDICTION:
            return list(reversed(self._slots))
        return self._slots[:-SLOTS_RESERVED_FOR_PREDICTION]

    def _acquire(self, deadline: float, candidates: list) -> _Slot:
        while True:
            if self._closed:
                raise WorkerUnavailable()
            for slot in candidates:
                if slot.lock.acquire(blocking=False):
                    return slot
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerUnavailable()
            time.sleep(min(ACQUIRE_POLL_SECONDS, remaining))

    def shutdown(self) -> None:
        """Leave no worker process behind, even if a slot is still held by a stuck call."""
        self._closed = True
        for slot in self._slots:
            acquired = slot.lock.acquire(timeout=TERMINATE_GRACE_SECONDS)
            try:
                slot._discard(close_connection=acquired)
            finally:
                if acquired:
                    slot.lock.release()


_pool_lock = Lock()
_pools: dict[str, Pool] = {}


def pool(model_id: str = "tfidf_lr") -> Pool:
    with _pool_lock:
        if model_id not in _pools:
            _pools[model_id] = Pool(analysis_worker_slots())
        return _pools[model_id]


def shutdown() -> None:
    with _pool_lock:
        current = list(_pools.values())
        _pools.clear()
    for item in current:
        item.shutdown()


def request_worst_case_seconds() -> float:
    """Upper bound on one request's isolated work: three tasks, each able to spawn and be killed."""
    per_task = analysis_hard_timeout_seconds() + analysis_worker_startup_seconds() + 2 * TERMINATE_GRACE_SECONDS
    from backend.app.config import explanation_timeout_seconds
    explanation = max(explanation_timeout_seconds(model_id) for model_id in ("tfidf_lr", "lstm", "klue_bert"))
    return 2 * per_task + explanation + analysis_worker_startup_seconds() + 2 * TERMINATE_GRACE_SECONDS


def predict(row, text: str) -> tuple[str, float]:
    selected = pool() if row.model_id == "tfidf_lr" else pool(row.model_id)
    return selected.run("predict", row, text)


def has_analyzable_tokens(text: str) -> bool:
    return pool().run("tokens", None, text) is True


def explain(row, text: str):
    from backend.app.config import explanation_timeout_seconds
    if row.model_id == "tfidf_lr":
        return pool().run("explain", row, text)
    return pool(row.model_id).run("explain", row, text, explanation_timeout_seconds(row.model_id))
