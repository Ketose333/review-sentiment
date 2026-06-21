"""LSTM(Embedding→LSTM→Dense) sentiment model: train/evaluate/save/load + inference wrapper.

Reuses the same Okt-based tokenize() as TF-IDF so train/inference preprocessing stays
identical; only the vectorization (word-index sequence vs TF-IDF) differs.
"""

import os

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.layers import LSTM, Dense, Embedding
from tensorflow.keras.models import Sequential
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.preprocessing.text import Tokenizer

from src.evaluation.metrics import compute_metrics
from src.models.base import EmptyInputError, ModelLoadError
from src.preprocessing.tokenizer import preprocess_for_vectorizer

LABEL_MAP = {0: "부정", 1: "긍정"}
MAX_LEN = 40
VOCAB_SIZE = 20000


def build_tokenizer(corpus: pd.Series) -> Tokenizer:
    tokenizer = Tokenizer(num_words=VOCAB_SIZE, oov_token="<OOV>")
    tokenizer.fit_on_texts(corpus)
    return tokenizer


def _to_sequences(tokenizer: Tokenizer, corpus: pd.Series) -> np.ndarray:
    sequences = tokenizer.texts_to_sequences(corpus)
    return pad_sequences(sequences, maxlen=MAX_LEN, padding="post", truncating="post")


def build_model() -> Sequential:
    model = Sequential(
        [
            Embedding(VOCAB_SIZE, 64, input_length=MAX_LEN),
            LSTM(64),
            Dense(1, activation="sigmoid"),
        ]
    )
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    return model


def train(train_df: pd.DataFrame, epochs: int = 5, batch_size: int = 256) -> tuple[Tokenizer, Sequential]:
    corpus = train_df["document"].map(preprocess_for_vectorizer)
    tokenizer = build_tokenizer(corpus)
    X_train = _to_sequences(tokenizer, corpus)

    model = build_model()
    model.fit(X_train, train_df["label"].to_numpy(), epochs=epochs, batch_size=batch_size, verbose=2)

    return tokenizer, model


def evaluate(tokenizer: Tokenizer, model: Sequential, test_df: pd.DataFrame) -> dict:
    corpus = test_df["document"].map(preprocess_for_vectorizer)
    X_test = _to_sequences(tokenizer, corpus)
    y_pred = (model.predict(X_test, verbose=0).ravel() >= 0.5).astype(int)
    return compute_metrics(test_df["label"], y_pred)


def save(tokenizer: Tokenizer, model: Sequential, out_dir: str = "models/lstm") -> None:
    os.makedirs(out_dir, exist_ok=True)
    model.save(os.path.join(out_dir, "model.h5"))
    with open(os.path.join(out_dir, "tokenizer.json"), "w", encoding="utf-8") as f:
        f.write(tokenizer.to_json())


def load(model_dir: str = "models/lstm") -> tuple[Tokenizer, Sequential]:
    model_path = os.path.join(model_dir, "model.h5")
    tokenizer_path = os.path.join(model_dir, "tokenizer.json")
    if not os.path.exists(model_path) or not os.path.exists(tokenizer_path):
        raise ModelLoadError(f"LSTM model artifacts not found in {model_dir}")
    model = tf.keras.models.load_model(model_path)
    with open(tokenizer_path, encoding="utf-8") as f:
        tokenizer = tf.keras.preprocessing.text.tokenizer_from_json(f.read())
    return tokenizer, model


class LSTMModel:
    def __init__(self, tokenizer: Tokenizer, model: Sequential):
        self.tokenizer = tokenizer
        self.model = model

    def predict_proba(self, raw_text: str) -> tuple[str, float]:
        processed = preprocess_for_vectorizer(raw_text)
        if not processed:
            raise EmptyInputError("No tokens remain after preprocessing")

        X = _to_sequences(self.tokenizer, pd.Series([processed]))
        positive_proba = float(self.model.predict(X, verbose=0).ravel()[0])
        predicted_class = 1 if positive_proba >= 0.5 else 0
        confidence = positive_proba if predicted_class == 1 else 1 - positive_proba
        return LABEL_MAP[predicted_class], confidence
