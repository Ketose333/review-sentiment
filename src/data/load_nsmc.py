"""NSMC (Naver Sentiment Movie Corpus) dataset loader.

Downloads ratings_train.txt (150k rows) / ratings_test.txt (50k rows) from the
canonical e9t/nsmc source on first use and caches them under dest_dir (gitignored).
"""

import os
import urllib.request

import pandas as pd

_BASE_URL = "https://raw.githubusercontent.com/e9t/nsmc/master"
_FILES = {"train": "ratings_train.txt", "test": "ratings_test.txt"}


def _load_split(dest_dir: str, split: str, download_if_missing: bool) -> pd.DataFrame:
    filename = _FILES[split]
    path = os.path.join(dest_dir, filename)
    if not os.path.exists(path):
        if not download_if_missing:
            raise FileNotFoundError(f"{path} not found and download_if_missing=False")
        os.makedirs(dest_dir, exist_ok=True)
        urllib.request.urlretrieve(f"{_BASE_URL}/{filename}", path)

    df = pd.read_csv(path, sep="\t", encoding="utf-8")
    return df.dropna(subset=["document"]).reset_index(drop=True)


def load_nsmc(dest_dir: str = "data", download_if_missing: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (train_df, test_df), each with columns [id, document, label]."""
    train_df = _load_split(dest_dir, "train", download_if_missing)
    test_df = _load_split(dest_dir, "test", download_if_missing)
    return train_df, test_df
