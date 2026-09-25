"""The web app bundles a copy of the EDA stats; it must not drift from the source."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "models" / "eda" / "stats.json"
BUNDLED = ROOT / "frontend" / "src" / "data" / "eda-stats.json"


def test_bundled_stats_match_the_generated_source():
    assert SOURCE.is_file() and BUNDLED.is_file()
    assert json.loads(BUNDLED.read_text(encoding="utf-8")) == json.loads(SOURCE.read_text(encoding="utf-8"))


def test_bundled_stats_keep_the_shape_the_web_reads():
    stats = json.loads(BUNDLED.read_text(encoding="utf-8"))
    assert set(stats) == {"label_counts", "length_histogram", "top_words_by_label", "word_tokenizer"}
    assert set(stats["label_counts"]) == {"긍정", "부정"}
    histogram = stats["length_histogram"]
    assert len(histogram["bin_edges"]) == len(histogram["counts"]) + 1
    for label in ("긍정", "부정"):
        rows = stats["top_words_by_label"][label]
        assert rows and all(len(row) == 2 and isinstance(row[0], str) and isinstance(row[1], int) for row in rows)
