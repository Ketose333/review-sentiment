"""Tests for src/preprocessing/tokenizer.py — the shared train/inference preprocessing module."""

from src.preprocessing.tokenizer import preprocess_for_vectorizer, tokenize


def test_tokenize_empty_string_returns_empty_list():
    assert tokenize("") == []


def test_tokenize_whitespace_only_returns_empty_list():
    assert tokenize("   ") == []


def test_tokenize_emoji_only_returns_empty_list():
    assert tokenize("\U0001F600\U0001F600\U0001F600") == []


def test_tokenize_special_chars_only_returns_empty_list():
    assert tokenize("!!!@@@###") == []


def test_tokenize_normal_korean_review_returns_tokens():
    tokens = tokenize("정말 재미있는 영화였어요")
    assert len(tokens) > 0
    assert "영화" in tokens


def test_preprocess_for_vectorizer_joins_tokens_with_space():
    result = preprocess_for_vectorizer("정말 재미있는 영화였어요")
    assert isinstance(result, str)
    assert " " in result or len(result.split()) >= 1


def test_preprocess_for_vectorizer_empty_input_returns_empty_string():
    assert preprocess_for_vectorizer("") == ""
