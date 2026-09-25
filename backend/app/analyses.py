"""Metadata-only analysis persistence and atomic state transitions."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from backend.app.tables import AnalysisRun, ModelRegistry


class StateConflict(Exception):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_model(session: Session, model_id: str) -> ModelRegistry | None:
    return session.get(ModelRegistry, model_id)


def receive(session: Session, model: ModelRegistry, request_id: str) -> AnalysisRun:
    created_at = utc_now()
    run = AnalysisRun(
        analysis_id=uuid4(), model_id=model.model_id, model_version=model.artifact_revision,
        status="RECEIVED", label=None, confidence=None,
        explanation_available=model.explanation_available, duration_ms=None, error_code=None,
        request_id=UUID(request_id), created_at=created_at, completed_at=None,
        expires_at=created_at + timedelta(hours=24),
    )
    session.add(run)
    session.commit()
    return run


def transition(session: Session, run: AnalysisRun, expected: str, status: str, **changes) -> None:
    values = {"status": status, **changes}
    if status in {"SUCCEEDED", "FAILED", "REJECTED"}:
        values["completed_at"] = utc_now()
    result = session.execute(
        update(AnalysisRun)
        .where(AnalysisRun.analysis_id == run.analysis_id, AnalysisRun.status == expected)
        .values(**values)
    )
    if result.rowcount != 1:
        session.rollback()
        raise StateConflict()
    session.commit()
    for key, value in values.items():
        setattr(run, key, value)


def find_unexpired(session: Session, analysis_id: UUID) -> AnalysisRun | None:
    return session.scalar(
        select(AnalysisRun).where(
            AnalysisRun.analysis_id == analysis_id,
            AnalysisRun.expires_at > utc_now(),
        )
    )


def prune_expired(session: Session) -> int:
    result = session.execute(delete(AnalysisRun).where(AnalysisRun.expires_at <= utc_now()))
    session.commit()
    return result.rowcount


def recover_stale(session: Session, max_age_seconds: float) -> int:
    """Recover interrupted runs only after twice the configured soft budget."""
    now = utc_now()
    result = session.execute(
        update(AnalysisRun)
        .where(AnalysisRun.status == "RUNNING", AnalysisRun.created_at <= now - timedelta(seconds=max_age_seconds))
        .values(status="FAILED", error_code="INFERENCE_FAILED", completed_at=now)
    )
    session.commit()
    return result.rowcount


def run_response(run: AnalysisRun) -> dict:
    data = {
        "analysisId": str(run.analysis_id), "status": run.status,
        "modelId": run.model_id, "modelVersion": run.model_version,
        "createdAt": run.created_at.astimezone(timezone.utc),
        "completedAt": run.completed_at.astimezone(timezone.utc) if run.completed_at else None,
        "expiresAt": run.expires_at.astimezone(timezone.utc),
    }
    if run.status == "SUCCEEDED":
        data.update(label=run.label, confidence=run.confidence,
                    durationMs=run.duration_ms,
                    explanationAvailable=run.explanation_available)
    elif run.status in {"FAILED", "REJECTED"}:
        data["errorCode"] = run.error_code
    return data
