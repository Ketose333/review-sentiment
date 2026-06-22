"""Precomputes EDA stats (label distribution, review length histogram, top words by
label) and saves them to models/eda/stats.json so app.py can render them without
re-tokenizing the full corpus on every page load.

Usage: python scripts/compute_eda.py
"""

import json
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.load_nsmc import load_nsmc
from src.preprocessing.tokenizer import tokenize

OUT_DIR = "models/eda"
WORD_SAMPLE_PER_LABEL = 15000
TOP_N_WORDS = 20
LENGTH_BINS = 20


def _top_words(documents, top_n: int) -> list[list]:
    counter = Counter()
    for doc in documents:
        counter.update(tokenize(doc))
    return [[word, count] for word, count in counter.most_common(top_n)]


def main():
    print("Loading NSMC dataset...")
    train_df, test_df = load_nsmc(download_if_missing=True)
    full_df = train_df  # train split alone is representative and large enough for EDA

    label_counts = full_df["label"].value_counts().sort_index().to_dict()

    lengths = full_df["document"].str.len().to_numpy()
    counts, bin_edges = np.histogram(lengths, bins=LENGTH_BINS)
    length_histogram = {
        "bin_edges": [round(float(e), 1) for e in bin_edges],
        "counts": [int(c) for c in counts],
    }

    print(f"Sampling {WORD_SAMPLE_PER_LABEL} reviews per label and tokenizing for word frequency...")
    top_words_by_label = {}
    for label, name in ((0, "부정"), (1, "긍정")):
        subset = full_df[full_df["label"] == label]["document"]
        sample = subset.sample(n=min(WORD_SAMPLE_PER_LABEL, len(subset)), random_state=42)
        top_words_by_label[name] = _top_words(sample, TOP_N_WORDS)
        print(f"  {name}: top word = {top_words_by_label[name][0]}")

    stats = {
        "label_counts": {"부정": int(label_counts.get(0, 0)), "긍정": int(label_counts.get(1, 0))},
        "length_histogram": length_histogram,
        "top_words_by_label": top_words_by_label,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "stats.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Saved EDA stats to {out_path}")


if __name__ == "__main__":
    main()
