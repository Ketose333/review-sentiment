"""Ephemeral LIME result; never persist features or submitted text."""

import math

from backend.app.artifacts import ArtifactUnavailable
from backend.app.isolation import TaskFailed, WorkerTimeout, WorkerUnavailable, explain


SAMPLE_COUNT = 300
MAX_FEATURES = 8


class ExplanationUnavailable(Exception):
    pass


def generate(row, text: str) -> dict:
    # LIME runs in a killable worker: a busy, stuck, or failed run never holds the API.
    try:
        features = explain(row, text)
    except (ArtifactUnavailable, WorkerUnavailable, WorkerTimeout, TaskFailed):
        raise ExplanationUnavailable() from None
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise ExplanationUnavailable()
    encoded = []
    for feature in features:
        if not isinstance(feature, tuple) or len(feature) != 2:
            raise ExplanationUnavailable()
        token, weight = feature
        if not isinstance(token, str) or not token or type(weight) not in (int, float) or not math.isfinite(weight):
            raise ExplanationUnavailable()
        encoded.append({"token": str(token), "weight": float(weight)})
    return {
        "status": "SUCCEEDED", "method": "LIME", "direction": "POSITIVE",
        "sampleCount": SAMPLE_COUNT if row.model_id == "tfidf_lr" else 30, "features": encoded,
    }


def failed_response() -> dict:
    return {"status": "FAILED", "method": "LIME", "errorCode": "EXPLANATION_FAILED"}
