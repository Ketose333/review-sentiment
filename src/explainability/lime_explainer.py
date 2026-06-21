"""LIME-based word-level explanation for sentiment predictions.

Drives any SentimentModel through its predict_proba(str) -> (label, confidence)
interface only, so this works unchanged for LSTM/KLUE-BERT once those land (PR-008).
"""

import numpy as np
from lime.lime_text import LimeTextExplainer

from src.models.base import EmptyInputError

_CLASS_NAMES = ["부정", "긍정"]
_LABEL_TO_INDEX = {"부정": 0, "긍정": 1}


def _make_classifier_fn(model):
    def classifier_fn(texts: list[str]) -> np.ndarray:
        probs = np.full((len(texts), 2), 0.5)
        for i, text in enumerate(texts):
            try:
                label, confidence = model.predict_proba(text)
            except EmptyInputError:
                continue
            idx = _LABEL_TO_INDEX[label]
            probs[i, idx] = confidence
            probs[i, 1 - idx] = 1 - confidence
        return probs

    return classifier_fn


def explain(model, text: str, num_features: int = 8, num_samples: int = 300) -> list[tuple[str, float]]:
    """Returns [(word, weight), ...] for the predicted-긍정 direction.

    Positive weight pushes the prediction toward 긍정, negative toward 부정.
    """
    explainer = LimeTextExplainer(class_names=_CLASS_NAMES)
    exp = explainer.explain_instance(
        text,
        _make_classifier_fn(model),
        num_features=num_features,
        num_samples=num_samples,
        labels=(1,),
    )
    return exp.as_list(label=1)
