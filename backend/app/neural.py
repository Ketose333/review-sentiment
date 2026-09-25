"""Verified, lazy adapters for the two neural models.

Each adapter is called only in its own model worker process. TensorFlow and
PyTorch are never imported into the API or into the same warm worker.
"""

from functools import lru_cache

from backend.app.artifacts import ArtifactUnavailable, verified_directory


@lru_cache(maxsize=1)
def _load_lstm(directory: str, revision: str, manifest_key: tuple):
    from src.models.lstm import LSTMModel, load

    tokenizer, model = load(directory)
    return LSTMModel(tokenizer, model)


@lru_cache(maxsize=1)
def _load_bert(directory: str, revision: str, manifest_key: tuple):
    from src.models.klue_bert import KlueBertModel, load

    tokenizer, model = load(directory)
    return KlueBertModel(tokenizer, model)


def ready(row):
    directory = verified_directory(row)
    loader = {"lstm": _load_lstm, "klue_bert": _load_bert}.get(row.model_id)
    if loader is None:
        raise ArtifactUnavailable()
    try:
        return loader(str(directory), row.artifact_revision, tuple(sorted(row.artifact_manifest.items())))
    except Exception:
        raise ArtifactUnavailable() from None


def predict(row, text: str):
    return ready(row).predict_proba(text)
