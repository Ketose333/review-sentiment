"""Common interface every sentiment model wrapper implements.

TF-IDF+LogisticRegression implements this now; LSTM/KLUE-BERT implement it later
without requiring any change to app.py or the model registry's lookup logic.
"""

from typing import Protocol


class SentimentModel(Protocol):
    def predict_proba(self, raw_text: str) -> tuple[str, float]:
        """Returns (label, confidence) where label in {'긍정', '부정'} and confidence in [0, 1]."""
        ...


class ModelLoadError(Exception):
    """Raised when a model's artifacts cannot be loaded (missing/corrupt files)."""


class EmptyInputError(Exception):
    """Raised when preprocessing yields no tokens for the given input (PRD §14 edge case)."""
