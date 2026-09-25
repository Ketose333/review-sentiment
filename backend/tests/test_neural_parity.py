"""Three-model integrity and execution boundary regressions."""

import hashlib
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app import artifacts, config, isolation
from backend.app.validation import parse_request_shape, validate_text, ValidationProblem


def row(model_id, manifest=None):
    return SimpleNamespace(
        model_id=model_id, enabled=True, artifact_repo=artifacts.EXPECTED_REPO,
        artifact_revision=artifacts.EXPECTED_REVISION,
        artifact_manifest=manifest or artifacts.MODEL_MANIFESTS[model_id],
    )


@pytest.mark.parametrize("model_id", ["tfidf_lr", "lstm", "klue_bert"])
def test_all_models_accept_500_codepoints_and_explanation(model_id):
    payload = parse_request_shape({"text": "가" * 500, "modelId": model_id, "includeExplanation": True})
    validate_text(payload.text)
    assert payload.include_explanation is True
    with pytest.raises(ValidationProblem):
        validate_text("가" * 501)


@pytest.mark.parametrize("model_id", ["lstm", "klue_bert"])
def test_registry_manifest_must_match_audited_files_before_load(monkeypatch, tmp_path, model_id):
    original = artifacts.MODEL_MANIFESTS[model_id]
    contents = {Path(name).name: name.encode() for name in original}
    for name, content in contents.items():
        (tmp_path / name).write_bytes(content)
    audited = {name: hashlib.sha256(contents[Path(name).name]).hexdigest() for name in original}
    monkeypatch.setitem(artifacts.MODEL_MANIFESTS, model_id, audited)
    monkeypatch.setenv(f"{model_id.upper()}_ARTIFACT_DIR", str(tmp_path))
    assert artifacts.is_available(row(model_id, audited))
    (tmp_path / next(iter(contents))).write_bytes(b"changed")
    assert not artifacts.is_available(row(model_id, audited))
    assert not artifacts.is_available(row(model_id, {}))


@pytest.mark.parametrize("line_ending", [b"\n", b"\r\n"])
def test_bert_json_verifies_on_linux_and_windows_checkouts(monkeypatch, tmp_path, line_ending):
    audited = {}
    for relative in artifacts.MODEL_MANIFESTS["klue_bert"]:
        name = Path(relative).name
        canonical = b'{"model": "bert"}\n' if name.endswith(".json") else b"weights"
        (tmp_path / name).write_bytes(canonical.replace(b"\n", line_ending))
        audited[relative] = hashlib.sha256(canonical).hexdigest()
    monkeypatch.setitem(artifacts.MODEL_MANIFESTS, "klue_bert", audited)
    monkeypatch.setenv("KLUE_BERT_ARTIFACT_DIR", str(tmp_path))
    assert artifacts.is_available(row("klue_bert", audited))
    (tmp_path / "config.json").write_bytes(b"changed")
    assert not artifacts.is_available(row("klue_bert", audited))


def test_migration_0008_restores_previous_manifest_on_downgrade(monkeypatch):
    migration = importlib.import_module("backend.migrations.versions.0008_enable_neural_parity")
    calls = []

    class Bind:
        def execute(self, statement, params):
            calls.append((str(statement), params))

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    migration.upgrade()
    assert len(calls) == 2
    for _, params in calls:
        assert json.loads(params["manifest"]) == migration.MANIFESTS[params["model_id"]]
        assert len(json.loads(params["manifest"])) >= 2
    calls.clear()
    migration.downgrade()
    assert len(calls) == 2
    for sql, params in calls:
        assert "enabled = false" in sql
        assert json.loads(params["manifest"]) == migration.PREVIOUS_MANIFESTS[params["model_id"]]


def test_local_neural_support_files_match_pinned_hashes():
    root = Path(__file__).resolve().parents[2]
    for model_id in ("lstm", "klue_bert"):
        for name, expected in artifacts.MODEL_MANIFESTS[model_id].items():
            path = root / name
            if not path.is_file():  # Large weights are intentionally installed separately.
                continue
            source = path.read_bytes()
            # Windows checkout may convert tracked LF text to CRLF; installers
            # normalize these JSON files before verifying the Git blob digest.
            if model_id == "klue_bert" and path.suffix == ".json":
                source = source.replace(b"\r\n", b"\n")
            assert hashlib.sha256(source).hexdigest() == expected


def test_explanation_budget_is_independent_of_prediction_budget(monkeypatch):
    monkeypatch.setattr(isolation, "pool", lambda model_id: SimpleNamespace(run=lambda *args: args))
    result = isolation.explain(row("klue_bert"), "합성 리뷰")
    assert result[-1] == config.explanation_timeout_seconds("klue_bert")
    assert result[-1] > isolation.analysis_hard_timeout_seconds()


def test_model_pools_are_distinct():
    try:
        assert isolation.pool("lstm") is not isolation.pool("klue_bert")
        assert isolation.pool("lstm") is not isolation.pool("tfidf_lr")
    finally:
        isolation.shutdown()


@pytest.mark.parametrize("model_id", ["lstm", "klue_bert"])
def test_real_neural_artifact_if_installed(monkeypatch, model_id):
    directory = os.environ.get(f"TEST_{model_id.upper()}_ARTIFACT_DIR")
    if not directory:
        pytest.skip("requires installed real neural artifact")
    monkeypatch.setenv(f"{model_id.upper()}_ARTIFACT_DIR", directory)
    assert artifacts.is_available(row(model_id))
    label, confidence = isolation.predict(row(model_id), "정말 재미있는 영화였어요")
    assert label in {"긍정", "부정"} and 0 <= confidence <= 1
