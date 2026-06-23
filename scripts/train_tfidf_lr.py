"""Trains TF-IDF + LogisticRegression on NSMC and saves model artifacts + metrics.

Usage: python scripts/train_tfidf_lr.py
Acceptance criterion (PRD §12, PR-003): test accuracy >= 0.80.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.load_nsmc import load_nsmc
from src.models.tfidf_lr import evaluate, save, train
from scripts.train_utils import mirror_to_submission

ACCURACY_THRESHOLD = 0.80
MODEL_OUT_DIR = "models/tfidf_lr"


def main():
    print("Loading NSMC dataset...")
    train_df, test_df = load_nsmc(download_if_missing=True)
    print(f"train={len(train_df)} rows, test={len(test_df)} rows")

    print("Training TF-IDF + LogisticRegression...")
    vectorizer, model = train(train_df)

    print("Evaluating on test set...")
    metrics = evaluate(vectorizer, model, test_df)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    assert metrics["accuracy"] >= ACCURACY_THRESHOLD, (
        f"Test accuracy {metrics['accuracy']} below required {ACCURACY_THRESHOLD}"
    )

    save(vectorizer, model, MODEL_OUT_DIR)
    metrics_with_name = {"display_name": "TF-IDF + LogisticRegression", **metrics}
    with open(os.path.join(MODEL_OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics_with_name, f, ensure_ascii=False, indent=2)

    mirror_to_submission(MODEL_OUT_DIR)
    print(f"Saved model artifacts to {MODEL_OUT_DIR}/")


if __name__ == "__main__":
    main()
