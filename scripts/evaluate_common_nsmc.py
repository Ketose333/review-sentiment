"""Evaluate the three saved models on one pinned NSMC test sample.

Run from this checkout with:
    python scripts/evaluate_common_nsmc.py --all --models-root E:/CAREER/repos/review-sentiment/models

Raw review text stays in the ignored data cache and in process memory. The JSON
result contains hashes, counts, versions and aggregate metrics only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "ratings_test.txt"
RESULT_PATH = ROOT / "reports" / "common_nsmc_5000.json"
DATA_URL = (
    "https://raw.githubusercontent.com/e9t/nsmc/"
    "eafdd77e310f399a4d0083a58ade40b55a5a308d/ratings_test.txt"
)
DATA_SHA256 = "8ac9f64052f11dbf6ae0acb5e038f03d90a76f0eda7820cfb3a92d02edfcebda"
SAMPLE_SIZE = 5000
SAMPLE_SEED = 42
MODEL_FILES = {
    "tfidf_lr": {
        "vectorizer.pkl": "69df406990335fa9ba1e2d1411ad2a56a41ecba40abded1781cafff404727118",
        "model.pkl": "8eb8571babaf37d452b3b894281fde6997c6b2aaf8533efdfb85aa6f28bbe611",
    },
    "lstm": {
        "model.h5": "aa87bac234a46daebda568a79000cb656dc781df39cbe28152200935a2f9f60b",
        "tokenizer.json": "ec62e121240daf19b5b206db0e91c4f108b740a7dd041173d5bfaa46c79da451",
    },
    "klue_bert": {
        "model.safetensors": "8a2e7480a194c64ffe0b22a35a3a0ecd9e4cc5cd5e68cb73436b399956f28423",
        "tokenizer.json": "c31fcbfa68647c3674ebde12c390b637f85c855f43b292264b4ac9b3ef8c03f3",
        "config.json": "603b8940a2e8550d2b250a8bcf64e55fd4a221868579a88e83b826a2b2f88c0b",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_model_files(models_root: Path, model_id: str) -> dict[str, str]:
    actual = {}
    for filename, expected in MODEL_FILES[model_id].items():
        path = models_root / model_id / filename
        if not path.is_file():
            raise RuntimeError(f"Missing model artifact: {model_id}/{filename}")
        actual[filename] = sha256_file(path)
        if actual[filename] != expected:
            raise RuntimeError(f"Artifact SHA-256 mismatch: {model_id}/{filename}")
    return actual


def checked_data() -> tuple[pd.DataFrame, str, int]:
    if not DATA_PATH.exists():
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(DATA_URL, DATA_PATH)
    if sha256_file(DATA_PATH) != DATA_SHA256:
        raise RuntimeError("NSMC test data SHA-256 mismatch")

    frame = pd.read_csv(DATA_PATH, sep="\t", encoding="utf-8")
    frame = frame.dropna(subset=["document"]).reset_index(drop=True)
    if len(frame) < SAMPLE_SIZE:
        raise RuntimeError("NSMC test data has fewer rows than the requested sample")
    sample = frame.sample(n=SAMPLE_SIZE, random_state=SAMPLE_SEED).reset_index(drop=True)
    # Canonical UTF-8 JSONL fingerprint includes row order, id, text, and label.
    # Only the digest is persisted; no review text appears in reports or logs.
    digest = hashlib.sha256()
    for row in sample.itertuples(index=False):
        canonical = json.dumps(
            [int(row.id), row.document, int(row.label)], ensure_ascii=False, separators=(",", ":")
        )
        digest.update(canonical.encode("utf-8") + b"\n")
    return sample, digest.hexdigest(), len(frame)


def versions() -> dict[str, str]:
    names = ["pandas", "numpy", "scikit-learn", "joblib", "konlpy", "JPype1", "tensorflow", "torch", "transformers"]
    result = {"python": platform.python_version(), "platform": platform.platform()}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not installed"
    return result


def evaluate_model(model_id: str, models_root: Path) -> dict:
    # Check files before importing potentially unsafe model loaders.
    hashes = checked_model_files(models_root, model_id)
    sample, sample_hash, filtered_count = checked_data()
    sys.path.insert(0, str(ROOT))
    started = time.monotonic()
    if model_id == "tfidf_lr":
        from src.models.tfidf_lr import evaluate, load

        vectorizer, model = load(str(models_root / model_id))
        metrics = evaluate(vectorizer, model, sample)
    elif model_id == "lstm":
        from src.models.lstm import evaluate, load

        tokenizer, model = load(str(models_root / model_id))
        metrics, _ = evaluate(tokenizer, model, sample)
    else:
        from src.models.klue_bert import evaluate, load

        tokenizer, model = load(str(models_root / model_id))
        metrics = evaluate(tokenizer, model, sample)
    return {
        "modelId": model_id,
        "metrics": metrics,
        "sampleSha256": sample_hash,
        "filteredTestRows": filtered_count,
        "modelSha256": hashes,
        "durationSeconds": round(time.monotonic() - started, 2),
        "environment": versions(),
    }


def run_all(models_root: Path, timeout_seconds: int) -> int:
    # Pin artifact checks before any evaluator starts.
    for model_id in MODEL_FILES:
        checked_model_files(models_root, model_id)
    _, sample_hash, filtered_count = checked_data()
    result = {
        "evaluatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "dataSource": DATA_URL,
        "dataSha256": DATA_SHA256,
        "filteredTestRows": filtered_count,
        "sampleMethod": "dropna(document), reset_index(drop=True), sample(n=5000, random_state=42), reset_index(drop=True)",
        "sampleSize": SAMPLE_SIZE,
        "sampleSeed": SAMPLE_SEED,
        "sampleSha256": sample_hash,
        "metricDefinition": "sklearn binary precision/recall/F1 with positive label 1; four decimal places",
        "models": {},
    }
    RESULT_PATH.parent.mkdir(exist_ok=True)
    for model_id in MODEL_FILES:
        print(f"Starting {model_id} evaluation", flush=True)
        started = time.monotonic()
        command = [sys.executable, str(Path(__file__).resolve()), "--model", model_id, "--models-root", str(models_root)]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, cwd=ROOT)
        except subprocess.TimeoutExpired:
            result["models"][model_id] = {"status": "timed_out", "timeoutSeconds": timeout_seconds}
            print(f"{model_id} timed out after {timeout_seconds}s", flush=True)
            break
        if process.returncode:
            # Do not echo child stderr: third-party exceptions may contain input data.
            result["models"][model_id] = {"status": "failed", "exitCode": process.returncode}
            print(f"{model_id} failed (exit {process.returncode}); child output suppressed", flush=True)
            break
        model_result = json.loads(process.stdout)
        if model_result["sampleSha256"] != sample_hash:
            raise RuntimeError(f"Sample mismatch for {model_id}")
        result["models"][model_id] = {"status": "succeeded", **model_result}
        print(f"{model_id} completed in {time.monotonic() - started:.1f}s", flush=True)
        RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if len(result["models"]) == 3 and all(row["status"] == "succeeded" for row in result["models"].values()) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--model", choices=MODEL_FILES)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    if args.all:
        return run_all(args.models_root.resolve(), args.timeout_seconds)
    print(json.dumps(evaluate_model(args.model, args.models_root.resolve()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
