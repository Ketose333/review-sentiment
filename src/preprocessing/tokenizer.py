"""Shared Korean text preprocessing — used identically by training scripts and app.py.

Using the same preprocess_for_vectorizer() at train time (on the training corpus)
and at inference time (on user input) is what guarantees train/inference parity.
"""

import os
import re


def _register_jvm_dll_dir() -> None:
    """Windows: put the JDK's jvm.dll on the DLL search path before konlpy imports jpype.

    `_jpype.pyd` depends on jvm.dll at import time; konlpy/jpype don't register its
    directory, so standalone scripts (e.g. compute_eda.py) fail with
    "DLL load failed while importing _jpype". No-op on Linux/macOS — os.add_dll_directory
    doesn't exist there (Streamlit Cloud installs the JVM via packages.txt instead).
    """
    if not hasattr(os, "add_dll_directory"):
        return
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        return
    for sub in ("bin", os.path.join("bin", "server")):
        candidate = os.path.join(java_home, sub)
        if os.path.isdir(candidate):
            try:
                os.add_dll_directory(candidate)
            except OSError:
                pass


_register_jvm_dll_dir()

from konlpy.tag import Okt

from src.preprocessing.stopwords import KOREAN_STOPWORDS

_HANGUL_PATTERN = re.compile(r"[^ㄱ-ㅎㅏ-ㅣ가-힣\s]")
_okt = Okt()


def clean_text(text: str) -> str:
    """Strips text down to Korean syllables/jamo and whitespace only.

    Removes emoji, special characters, punctuation, digits, and Latin script.
    """
    return _HANGUL_PATTERN.sub("", text or "")


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """Cleans, morphologically tokenizes (Okt, stemmed), and filters stopwords/empties.

    Returns [] for empty/whitespace-only/non-Korean input — callers must handle the
    empty-list case explicitly (PRD §14 edge cases: special chars / emoji-only input).
    """
    cleaned = clean_text(text).strip()
    if not cleaned:
        return []

    morphs = _okt.morphs(cleaned, stem=True)
    tokens = [m for m in morphs if m.strip()]
    if remove_stopwords:
        tokens = [t for t in tokens if t not in KOREAN_STOPWORDS]
    return tokens


def preprocess_for_vectorizer(text: str) -> str:
    """tokenize(text) joined with single spaces — the exact string consumed by
    the TF-IDF vectorizer at both train time and inference time."""
    return " ".join(tokenize(text))
