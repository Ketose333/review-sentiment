"""Verified adapter around the existing TF-IDF model implementation."""

from backend.app.artifacts import ArtifactUnavailable, verified_directory
from backend.app.tables import ModelRegistry
from functools import lru_cache


@lru_cache(maxsize=2)
def _load_verified(directory: str, revision: str, model_hash: str, vectorizer_hash: str):
    from src.models.tfidf_lr import TfidfLRModel, load

    vectorizer, model = load(directory)
    return TfidfLRModel(vectorizer, model)


def predict(row: ModelRegistry, text: str) -> tuple[str, float]:
    model = ready(row)
    return model.predict_proba(text)


def ready(row: ModelRegistry):
    directory = verified_directory(row)
    try:
        model = _load_verified(
            str(directory), row.artifact_revision,
            row.artifact_manifest["models/tfidf_lr/model.pkl"],
            row.artifact_manifest["models/tfidf_lr/vectorizer.pkl"],
        )
    except Exception as exc:
        raise ArtifactUnavailable() from exc
    return model


def has_analyzable_tokens(text: str) -> bool:
    from src.preprocessing.tokenizer import preprocess_for_vectorizer

    return bool(preprocess_for_vectorizer(text))
