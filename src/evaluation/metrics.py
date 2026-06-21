"""Model evaluation metrics and the cross-model comparison table.

load_all_metrics() scans models/*/metrics.json — adding LSTM/KLUE-BERT later only
requires writing a metrics.json in the same shape; no code here needs to change.
"""

import glob
import json
import os

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def compute_metrics(y_true, y_pred) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, average="binary")), 4),
        "recall": round(float(recall_score(y_true, y_pred, average="binary")), 4),
        "f1": round(float(f1_score(y_true, y_pred, average="binary")), 4),
    }


def build_comparison_table(results: dict[str, dict]) -> pd.DataFrame:
    """results = {model_display_name: {"accuracy":..., "precision":..., "recall":..., "f1":...}}."""
    if not results:
        return pd.DataFrame(columns=["Accuracy", "Precision", "Recall", "F1"])

    df = pd.DataFrame(results).T
    df = df.rename(
        columns={
            "accuracy": "Accuracy",
            "precision": "Precision",
            "recall": "Recall",
            "f1": "F1",
        }
    )
    return df[["Accuracy", "Precision", "Recall", "F1"]]


def load_all_metrics(models_dir: str = "models") -> dict[str, dict]:
    """Scans models/*/metrics.json. Model display name comes from a "display_name" key
    inside each metrics.json (falls back to the directory name if absent)."""
    results: dict[str, dict] = {}
    for metrics_path in sorted(glob.glob(os.path.join(models_dir, "*", "metrics.json"))):
        with open(metrics_path, encoding="utf-8") as f:
            data = json.load(f)
        model_dir_name = os.path.basename(os.path.dirname(metrics_path))
        display_name = data.pop("display_name", model_dir_name)
        results[display_name] = data
    return results
