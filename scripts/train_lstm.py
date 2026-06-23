"""Trains an Embedding->LSTM->Dense model on NSMC and saves artifacts + metrics.

Usage: python scripts/train_lstm.py
Target (docs/STATUS.md P1, PR-004): test accuracy >= 0.85.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.load_nsmc import load_nsmc
from src.models.lstm import evaluate, save, train

ACCURACY_THRESHOLD = 0.85
MODEL_OUT_DIR = "models/lstm"


def main():
    print("Loading NSMC dataset...")
    train_df, test_df = load_nsmc(download_if_missing=True)
    print(f"train={len(train_df)} rows, test={len(test_df)} rows")

    print("Training LSTM (Embedding -> LSTM -> Dense)...")
    tokenizer, model, _history = train(train_df)

    print("Evaluating on test set...")
    metrics, _y_pred = evaluate(tokenizer, model, test_df)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    if metrics["accuracy"] < ACCURACY_THRESHOLD:
        print(f"WARNING: test accuracy {metrics['accuracy']} below target {ACCURACY_THRESHOLD}")

    save(tokenizer, model, MODEL_OUT_DIR)
    metrics_with_name = {"display_name": "LSTM", **metrics}
    with open(os.path.join(MODEL_OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics_with_name, f, ensure_ascii=False, indent=2)

    print(f"Saved model artifacts to {MODEL_OUT_DIR}/")


if __name__ == "__main__":
    main()
