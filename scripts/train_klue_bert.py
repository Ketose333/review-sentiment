"""Fine-tunes KLUE-BERT on an NSMC subset (CPU-only environment) and saves metrics.

Usage: python scripts/train_klue_bert.py
Full-data GPU fine-tuning is the PRD target (Acc >= 0.88); this CPU-subset run is a
documented fallback (docs/STATUS.md) since no GPU is available locally.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.load_nsmc import load_nsmc
from src.models.klue_bert import evaluate, save, train

TRAIN_SUBSET = 18000
TEST_SUBSET = 5000
MODEL_OUT_DIR = "models/klue_bert"


def main():
    print("Loading NSMC dataset...")
    train_df, test_df = load_nsmc(download_if_missing=True)

    train_subset = train_df.sample(n=TRAIN_SUBSET, random_state=42).reset_index(drop=True)
    test_subset = test_df.sample(n=TEST_SUBSET, random_state=42).reset_index(drop=True)
    print(f"CPU subset: train={len(train_subset)} rows, test={len(test_subset)} rows")

    print("Fine-tuning KLUE-BERT...")
    tokenizer, model = train(train_subset)

    print("Evaluating on test subset...")
    metrics = evaluate(tokenizer, model, test_subset)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    save(tokenizer, model, MODEL_OUT_DIR)
    metrics_with_name = {
        "display_name": "KLUE-BERT",
        "note": f"CPU subset fine-tune (train={TRAIN_SUBSET}, test={TEST_SUBSET}); GPU full-data run is PRD target",
        **metrics,
    }
    with open(os.path.join(MODEL_OUT_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics_with_name, f, ensure_ascii=False, indent=2)

    print(f"Saved model artifacts to {MODEL_OUT_DIR}/")


if __name__ == "__main__":
    main()
