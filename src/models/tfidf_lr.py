"""TF-IDF + LogisticRegression sentiment model: train/evaluate/save/load + inference wrapper."""

import os

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer

from src.evaluation.metrics import compute_metrics
from src.models.base import EmptyInputError, ModelLoadError
from src.preprocessing.tokenizer import preprocess_for_vectorizer

LABEL_MAP = {0: "부정", 1: "긍정"}


def build_vectorizer(max_features: int = 10000) -> TfidfVectorizer:
    """Vectorizer expects already space-joined tokens from preprocess_for_vectorizer."""
    return TfidfVectorizer(max_features=max_features, analyzer="word", token_pattern=r"\S+")


def train(train_df: pd.DataFrame) -> tuple[TfidfVectorizer, LogisticRegression]:
    corpus = train_df["document"].map(preprocess_for_vectorizer)
    vectorizer = build_vectorizer()
    X_train = vectorizer.fit_transform(corpus)

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train, train_df["label"])

    return vectorizer, model


def evaluate(vectorizer: TfidfVectorizer, model: LogisticRegression, test_df: pd.DataFrame) -> dict:
    corpus = test_df["document"].map(preprocess_for_vectorizer)
    X_test = vectorizer.transform(corpus)
    y_pred = model.predict(X_test)
    return compute_metrics(test_df["label"], y_pred)


def save(vectorizer: TfidfVectorizer, model: LogisticRegression, out_dir: str = "models/tfidf_lr") -> None:
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(vectorizer, os.path.join(out_dir, "vectorizer.pkl"))
    joblib.dump(model, os.path.join(out_dir, "model.pkl"))


def load(model_dir: str = "models/tfidf_lr") -> tuple[TfidfVectorizer, LogisticRegression]:
    vectorizer_path = os.path.join(model_dir, "vectorizer.pkl")
    model_path = os.path.join(model_dir, "model.pkl")
    if not os.path.exists(vectorizer_path) or not os.path.exists(model_path):
        raise ModelLoadError(f"TF-IDF model artifacts not found in {model_dir}")
    vectorizer = joblib.load(vectorizer_path)
    model = joblib.load(model_path)
    return vectorizer, model


class TfidfLRModel:
    def __init__(self, vectorizer: TfidfVectorizer, model: LogisticRegression):
        self.vectorizer = vectorizer
        self.model = model

    def predict_proba(self, raw_text: str) -> tuple[str, float]:
        processed = preprocess_for_vectorizer(raw_text)
        if not processed:
            raise EmptyInputError("No tokens remain after preprocessing")

        X = self.vectorizer.transform([processed])
        probabilities = self.model.predict_proba(X)[0]
        predicted_class = probabilities.argmax()
        label = LABEL_MAP[predicted_class]
        confidence = float(probabilities[predicted_class])
        return label, confidence
