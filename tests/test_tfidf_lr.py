"""Tests for src/models/tfidf_lr.py — train/evaluate flow and failure-path handling."""

import pandas as pd
import pytest

from src.models.base import EmptyInputError, ModelLoadError
from src.models.tfidf_lr import TfidfLRModel, evaluate, load, train


def _toy_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "document": [
                "정말 재미있는 영화였어요",
                "최고의 영화 강력 추천합니다",
                "너무 재미없고 지루한 영화였다",
                "최악의 영화 시간 낭비였습니다",
            ],
            "label": [1, 1, 0, 0],
        }
    )


def test_train_and_evaluate_returns_metrics_dict():
    df = _toy_df()
    vectorizer, model = train(df)
    metrics = evaluate(vectorizer, model, df)
    assert set(metrics.keys()) == {"accuracy", "precision", "recall", "f1"}
    assert 0.0 <= metrics["accuracy"] <= 1.0


def test_predict_proba_returns_label_and_confidence():
    df = _toy_df()
    vectorizer, model = train(df)
    wrapped = TfidfLRModel(vectorizer, model)
    label, confidence = wrapped.predict_proba("정말 재미있는 영화였어요")
    assert label in {"긍정", "부정"}
    assert 0.0 <= confidence <= 1.0


def test_predict_proba_empty_input_raises_empty_input_error():
    df = _toy_df()
    vectorizer, model = train(df)
    wrapped = TfidfLRModel(vectorizer, model)
    with pytest.raises(EmptyInputError):
        wrapped.predict_proba("!!!@@@")


def test_load_missing_model_dir_raises_model_load_error(tmp_path):
    with pytest.raises(ModelLoadError):
        load(model_dir=str(tmp_path / "does_not_exist"))
