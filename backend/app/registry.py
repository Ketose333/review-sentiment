"""Read model metadata without loading model weights."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db import RegistryUnavailable
from backend.app.tables import ModelRegistry
from backend.app.validation import MODEL_IDS
from backend.app.artifacts import is_available


def list_models(session: Session) -> list[dict]:
    rows = session.scalars(select(ModelRegistry).where(ModelRegistry.model_id.in_(MODEL_IDS))).all()
    by_id = {row.model_id: row for row in rows}
    if set(by_id) != set(MODEL_IDS):
        raise RegistryUnavailable()
    models = []
    for model_id in MODEL_IDS:
        row = by_id[model_id]
        available = is_available(row)
        models.append({
            "modelId": row.model_id,
            "displayName": row.display_name,
            "version": row.artifact_revision,
            "available": available,
            "metrics": row.metrics,
            "evaluation": row.evaluation_scope,
            "explanationAvailable": row.explanation_available and available,
        })
    return models
