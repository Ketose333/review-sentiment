"""Stage B contract checks that run without PostgreSQL or model weights."""

import hashlib
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi.encoders import jsonable_encoder

from backend.app.analyses import run_response
from backend.app.artifacts import EXPECTED_REPO, EXPECTED_REVISION, ArtifactUnavailable, is_available, verified_directory
from backend.app.db import get_session
from backend.app.main import app
from backend.app.guards import RateLimiter


@pytest.fixture
def client():
    def database_must_not_be_used():
        raise AssertionError("preflight requests must not resolve a DB session")

    app.dependency_overrides[get_session] = database_must_not_be_used
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("payload,code", [
    ({"text": "비밀 문장", "modelId": "unknown"}, "UNSUPPORTED_MODEL"),
    ({"text": 123, "modelId": "tfidf_lr"}, "INVALID_REQUEST"),
    ({"text": "비밀 문장", "modelId": "tfidf_lr", "extra": 1}, "INVALID_REQUEST"),
    ({"text": "비밀 문장", "modelId": "tfidf_lr", "includeExplanation": "true"}, "INVALID_REQUEST"),
])
def test_preflight_errors_need_no_database_and_never_echo_text(client, payload, code):
    response = client.post("/v1/analyses", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]
    assert "analysisId" not in response.json()
    assert "비밀 문장" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("model_id", ["lstm", "klue_bert"])
def test_neural_explanation_passes_preflight_and_needs_database(client, model_id):
    with pytest.raises(AssertionError, match="preflight requests must not resolve"):
        client.post("/v1/analyses", json={"text": "합성 리뷰", "modelId": model_id, "includeExplanation": True})


def test_500_escaped_non_bmp_codepoints_fit_the_body_limit(client):
    # httpx emits ASCII JSON escapes: each emoji can occupy 12 bytes.
    with pytest.raises(AssertionError, match="preflight requests must not resolve"):
        client.post("/v1/analyses", json={"text": "😀" * 500, "modelId": "klue_bert"})


def test_malformed_json_does_not_echo_input(client):
    response = client.post("/v1/analyses", content='{"text":"비밀 문장",', headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "비밀 문장" not in response.text


def test_deeply_nested_json_is_safe_format_error(client):
    response = client.post(
        "/v1/analyses", content="[" * 1100 + "0" + "]" * 1100,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "analysisId" not in response.json()
    assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]


def test_structured_log_contains_only_safe_fields(client, caplog):
    with caplog.at_level(logging.INFO, logger="backend.api"):
        response = client.post("/v1/analyses", json={"text": "비밀 리뷰 문장", "modelId": "unknown"})
    records = [record for record in caplog.records if record.name == "backend.api"]
    assert len(records) == 1
    event = json.loads(records[0].message)
    assert set(event) == {"requestId", "path", "statusCode", "elapsedMs", "modelId", "errorCode"}
    assert event["requestId"] == response.headers["X-Request-Id"]
    assert event["path"] == "/v1/analyses"
    assert event["statusCode"] == 422 and event["errorCode"] == "UNSUPPORTED_MODEL"
    assert event["modelId"] is None
    assert "비밀 리뷰 문장" not in records[0].message


def test_invalid_analysis_id_is_404_without_database(client):
    response = client.get("/v1/analyses/not-a-uuid")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
    assert response.headers["Cache-Control"] == "no-store"


def test_oversized_body_is_rejected_before_json_parse_or_database(client):
    response = client.post(
        "/v1/analyses", content='{"text":"' + "가" * 3000 + '","modelId":"tfidf_lr"}',
        headers={"Content-Type": "application/json", "Content-Length": "10"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "analysisId" not in response.json()
    assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]
    assert "가" not in response.text


def test_rate_limit_is_applied_before_database_and_body_parsing(client, monkeypatch):
    import backend.app.guards as guards

    monkeypatch.setattr(guards, "limiter", RateLimiter(per_ip=1, global_limit=1))
    first = client.post("/v1/analyses", json={"text": "비밀", "modelId": "unknown"})
    second = client.post("/v1/analyses", content="{invalid", headers={"Content-Type": "application/json"})
    assert first.status_code == 422
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"
    assert "analysisId" not in second.json()
    assert second.json()["error"]["requestId"] == second.headers["X-Request-Id"]


def test_model_list_rate_limit_precedes_database_and_artifact_check(client, monkeypatch):
    import backend.app.guards as guards

    monkeypatch.setattr(guards, "limiter", RateLimiter(per_ip=0, global_limit=0))
    response = client.get("/v1/models")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]
    assert "analysisId" not in response.json()


def test_rate_limiter_bounds_ip_keys_and_global_requests(monkeypatch):
    import backend.app.guards as guards

    clock = [100.0]
    monkeypatch.setattr(guards.time, "monotonic", lambda: clock[0])
    limiter = RateLimiter(per_ip=2, global_limit=3, window_seconds=60, max_ips=2)
    assert limiter.allow("one") and limiter.allow("one")
    assert limiter.allow("two")
    assert not limiter.allow("one") and not limiter.allow("three")
    clock[0] += 61
    assert limiter.allow("three")


def test_invalid_timeout_configuration_prevents_app_start(monkeypatch):
    from backend.app.config import analysis_timeout_seconds

    monkeypatch.setenv("ANALYSIS_TIMEOUT_SECONDS", "0")
    analysis_timeout_seconds.cache_clear()
    try:
        with pytest.raises(ValueError):
            with TestClient(app):
                pass
    finally:
        analysis_timeout_seconds.cache_clear()


@pytest.mark.parametrize("name,value", [
    ("ANALYSIS_HARD_TIMEOUT_SECONDS", "0"),
    ("ANALYSIS_HARD_TIMEOUT_SECONDS", "601"),
    ("ANALYSIS_HARD_TIMEOUT_SECONDS", "121"),
    ("ANALYSIS_WORKER_STARTUP_SECONDS", "0"),
    ("ANALYSIS_WORKER_STARTUP_SECONDS", "14"),
    ("ANALYSIS_WORKER_SLOTS", "0"),
    ("ANALYSIS_WORKER_SLOTS", "9"),
])
def test_invalid_hard_timeout_configuration_prevents_app_start(monkeypatch, name, value):
    from backend.app.config import (
        analysis_hard_timeout_seconds,
        analysis_timeout_seconds,
        analysis_worker_slots,
        analysis_worker_startup_seconds,
    )

    # The soft limit is cached too, and the hard limit is validated against it.
    cached = (analysis_timeout_seconds, analysis_hard_timeout_seconds,
              analysis_worker_startup_seconds, analysis_worker_slots)
    monkeypatch.setenv(name, value)
    for entry in cached:
        entry.cache_clear()
    try:
        with pytest.raises(ValueError):
            with TestClient(app):
                pass
    finally:
        for entry in cached:
            entry.cache_clear()


def test_stale_recovery_window_exceeds_the_isolated_request_worst_case(monkeypatch):
    from backend.app import isolation, maintenance
    from backend.app.config import analysis_timeout_seconds

    class NoSession:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    captured = {}
    monkeypatch.setattr(maintenance, "session_factory", lambda: NoSession)
    monkeypatch.setattr(maintenance, "recover_stale", lambda _session, max_age_seconds: captured.setdefault("age", max_age_seconds))
    monkeypatch.setattr(maintenance, "prune_expired", lambda _session: None)
    monkeypatch.setattr(maintenance.ratelimit, "prune_windows", lambda _session: 0)
    maintenance.maintenance_once()
    # A run must never be recovered while a live request could still be working on it.
    assert captured["age"] > isolation.request_worst_case_seconds()
    assert captured["age"] >= 2 * analysis_timeout_seconds()


def test_lifespan_shuts_down_worker_processes(monkeypatch):
    from backend.app import maintenance

    stopped = []
    monkeypatch.setattr(maintenance.isolation, "shutdown", lambda: stopped.append(True))
    with TestClient(app):
        pass
    assert stopped == [True]


def test_maintenance_failure_logs_only_fixed_event_and_retries(monkeypatch, caplog):
    import backend.app.maintenance as maintenance

    def fail():
        raise RuntimeError("secret review text")

    class StopLoop(Exception):
        pass

    async def stop_after_first_attempt(_seconds):
        raise StopLoop()

    monkeypatch.setattr(maintenance, "maintenance_once", fail)
    monkeypatch.setattr(maintenance.asyncio, "sleep", stop_after_first_attempt)
    with caplog.at_level("ERROR"):
        with pytest.raises(StopLoop):
            asyncio.run(maintenance.maintenance_loop())
    assert "analysis_maintenance_failed" in caplog.text
    assert "secret review text" not in caplog.text


@pytest.mark.parametrize("status,expected_keys", [
    ("SUCCEEDED", {"label", "confidence", "durationMs", "explanationAvailable"}),
    ("FAILED", {"errorCode"}),
    ("REJECTED", {"errorCode"}),
])
def test_response_mapping_exposes_only_state_appropriate_fields(status, expected_keys):
    now = datetime.now(timezone.utc)
    run = SimpleNamespace(
        analysis_id=uuid4(), status=status, model_id="tfidf_lr", model_version="revision",
        created_at=now, completed_at=now, expires_at=now,
        label="긍정" if status == "SUCCEEDED" else None,
        confidence=0.8 if status == "SUCCEEDED" else None,
        duration_ms=10 if status == "SUCCEEDED" else None,
        explanation_available=False,
        error_code="INFERENCE_FAILED" if status != "SUCCEEDED" else None,
    )
    body = run_response(run)
    assert expected_keys.issubset(body)
    assert body["status"] == status
    assert "text" not in body and "requestId" not in body
    if status != "SUCCEEDED":
        assert "label" not in body and "confidence" not in body
    else:
        assert "errorCode" not in body


def test_response_timestamps_are_utc_even_when_database_returns_kst():
    kst = timezone(timedelta(hours=9))
    created = datetime(2026, 9, 24, 9, 0, tzinfo=kst)
    run = SimpleNamespace(
        analysis_id=uuid4(), status="SUCCEEDED", model_id="tfidf_lr",
        model_version="revision", created_at=created,
        completed_at=created + timedelta(seconds=2),
        expires_at=created + timedelta(hours=24),
        label="긍정", confidence=0.8, duration_ms=2,
        explanation_available=False, error_code=None,
    )
    response = jsonable_encoder(run_response(run))
    assert response["createdAt"] == "2026-09-24T00:00:00+00:00"
    assert response["completedAt"] == "2026-09-24T00:00:02+00:00"
    assert response["expiresAt"] == "2026-09-25T00:00:00+00:00"


def test_include_explanation_defaults_false_and_false_is_accepted():
    from backend.app.validation import parse_request_shape

    basic = parse_request_shape({"text": "좋은 영화", "modelId": "tfidf_lr"})
    explicit_false = parse_request_shape({"text": "좋은 영화", "modelId": "tfidf_lr", "includeExplanation": False})
    requested = parse_request_shape({"text": "좋은 영화", "modelId": "tfidf_lr", "includeExplanation": True})
    assert basic.include_explanation is False
    assert explicit_false.include_explanation is False
    assert requested.include_explanation is True


@pytest.mark.parametrize("failure", ["WorkerUnavailable", "WorkerTimeout", "TaskFailed"])
def test_every_isolated_explanation_failure_is_reported_as_unavailable(monkeypatch, failure):
    import backend.app.explanation as explanation
    from backend.app import isolation

    def raise_failure(*_args):
        raise getattr(isolation, failure)()

    monkeypatch.setattr(explanation, "explain", raise_failure)
    with pytest.raises(explanation.ExplanationUnavailable):
        explanation.generate(object(), "비밀 문장")
    assert explanation.failed_response() == {
        "status": "FAILED", "method": "LIME", "errorCode": "EXPLANATION_FAILED",
    }


@pytest.mark.parametrize("features", [
    "not a list",
    [("좋다", 0.1)] * 9,
    [["좋다", 0.1]],
    [("좋다", 0.1, 2)],
    [("", 0.1)],
    [("좋다", float("nan"))],
    [("좋다", "0.1")],
])
def test_malformed_isolated_features_never_return_partial_output(monkeypatch, features):
    import backend.app.explanation as explanation

    monkeypatch.setattr(explanation, "explain", lambda *_args: features)
    with pytest.raises(explanation.ExplanationUnavailable):
        explanation.generate(object(), "비밀 문장")


def test_explanation_uses_the_killable_worker_pool(monkeypatch):
    import backend.app.explanation as explanation
    from backend.app import isolation

    seen = {}

    def record(name, row, text):
        seen.update(task=name, row=row, text=text)
        return [("재미", 0.2)]

    monkeypatch.setattr(isolation, "pool", lambda: SimpleNamespace(run=record))
    row = SimpleNamespace(model_id="tfidf_lr")
    result = explanation.generate(row, "합성 리뷰")
    assert seen == {"task": "explain", "row": row, "text": "합성 리뷰"}
    assert result["status"] == "SUCCEEDED" and result["features"] == [{"token": "재미", "weight": 0.2}]


def test_availability_checks_both_hashes_without_deserializing(monkeypatch, tmp_path):
    import backend.app.artifacts as artifact_module
    from backend.app import tfidf

    def fail_if_loaded(*_args):
        raise AssertionError("model deserialization must not run for list availability")

    monkeypatch.setattr(tfidf, "_load_verified", fail_if_loaded)
    contents = {"model.pkl": b"model", "vectorizer.pkl": b"vectorizer"}
    for name, content in contents.items():
        (tmp_path / name).write_bytes(content)
    row = SimpleNamespace(
        model_id="tfidf_lr", enabled=True, artifact_repo=EXPECTED_REPO,
        artifact_revision=EXPECTED_REVISION,
        artifact_manifest={f"models/tfidf_lr/{name}": hashlib.sha256(content).hexdigest() for name, content in contents.items()},
    )
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", str(tmp_path))
    # A self-consistent DB manifest is still untrusted unless it matches the audited revision.
    assert is_available(row) is False
    with pytest.raises(ArtifactUnavailable):
        verified_directory(row)
    monkeypatch.setattr(artifact_module, "EXPECTED_MANIFEST", row.artifact_manifest)
    assert verified_directory(row) == tmp_path.resolve()
    assert is_available(row) is True
    (tmp_path / "vectorizer.pkl").write_bytes(b"tampered")
    assert is_available(row) is False
    with pytest.raises(ArtifactUnavailable):
        verified_directory(row)
