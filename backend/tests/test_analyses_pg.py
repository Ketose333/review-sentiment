"""Optional real PostgreSQL integration tests (set TEST_DATABASE_URL)."""

import os
import shutil
import logging
import time
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError

from backend.app.analyses import StateConflict, get_model, prune_expired, receive, recover_stale, transition, utc_now
from backend.app.artifacts import ArtifactUnavailable, is_available
from backend.app.db import session_factory
from backend.app.main import app
from backend.app.tables import AnalysisRun, ModelRegistry


pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="requires migrated PostgreSQL")


@pytest.fixture
def pg_client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    session_factory.cache_clear()
    with TestClient(app) as client:
        yield client
    session_factory.cache_clear()


def persisted(analysis_id: str) -> AnalysisRun:
    with session_factory()() as session:
        return session.get(AnalysisRun, UUID(analysis_id))


def test_success_and_get_use_real_verified_model(pg_client, monkeypatch):
    directory = os.environ.get("TEST_TFIDF_ARTIFACT_DIR")
    if not directory:
        pytest.skip("requires preinstalled verified TF-IDF artifacts")
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", directory)
    models = pg_client.get("/v1/models")
    assert models.status_code == 200
    assert models.json()["models"][0]["available"] is True
    for row in models.json()["models"][1:]:
        if not os.environ.get(f"{row['modelId'].upper()}_ARTIFACT_DIR"):
            assert row["available"] is False
    created = pg_client.post("/v1/analyses", json={"text": "정말 재미있는 영화였어요", "modelId": "tfidf_lr"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "SUCCEEDED" and body["label"] in {"긍정", "부정"}
    assert all(body[field].endswith("+00:00") for field in ("createdAt", "completedAt", "expiresAt"))
    assert 0 <= body["confidence"] <= 1
    assert created.headers["Location"] == f"/v1/analyses/{body['analysisId']}"
    assert created.headers["Cache-Control"] == "no-store"
    assert UUID(created.headers["X-Request-Id"])
    result = pg_client.get(created.headers["Location"])
    assert result.status_code == 200 and result.json() == body
    assert result.headers["Cache-Control"] == "no-store"
    row = persisted(body["analysisId"])
    assert row.status == "SUCCEEDED" and row.request_id == UUID(created.headers["X-Request-Id"])
    assert row.expires_at - row.created_at == timedelta(hours=24)
    with session_factory()() as session:
        serialized = session.scalar(text("SELECT row_to_json(a)::text FROM analysis_runs a WHERE analysis_id = :id"), {"id": body["analysisId"]})
        assert "재미있는" not in serialized


@pytest.mark.parametrize("model_id", ["lstm", "klue_bert"])
def test_neural_model_http_inference_with_real_artifact(pg_client, monkeypatch, model_id):
    directory = os.environ.get(f"TEST_{model_id.upper()}_ARTIFACT_DIR")
    if not directory:
        pytest.skip("requires installed neural artifact")
    monkeypatch.setenv(f"{model_id.upper()}_ARTIFACT_DIR", directory)
    listed = pg_client.get("/v1/models")
    entry = next(item for item in listed.json()["models"] if item["modelId"] == model_id)
    assert entry["available"] is True and entry["explanationAvailable"] is True
    created = pg_client.post("/v1/analyses", json={"text": "정말 재미있는 영화였어요", "modelId": model_id})
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["status"] == "SUCCEEDED" and result["label"] in {"긍정", "부정"}
    assert 0 <= result["confidence"] <= 1
    assert pg_client.get(created.headers["Location"]).json() == result
    with session_factory()() as session:
        stored = session.scalar(text("SELECT row_to_json(a)::text FROM analysis_runs a WHERE analysis_id = :id"), {"id": result["analysisId"]})
    assert "재미있는" not in stored


@pytest.mark.parametrize("model_id", ["lstm", "klue_bert"])
@pytest.mark.parametrize("explanation_status", ["SUCCEEDED", "FAILED"])
def test_neural_explanation_is_ephemeral_after_persisted_prediction(pg_client, monkeypatch, model_id, explanation_status):
    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "predict", lambda *_: ("긍정", 0.8))
    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda *_: True)
    if explanation_status == "SUCCEEDED":
        explanation = {"status": "SUCCEEDED", "method": "LIME", "direction": "POSITIVE", "sampleCount": 30, "features": [{"token": "합성", "weight": 0.2}]}
        monkeypatch.setattr(main_module, "generate_explanation", lambda *_: explanation)
    else:
        def fail(*_args):
            raise RuntimeError("private review text")
        monkeypatch.setattr(main_module, "generate_explanation", fail)
    created = pg_client.post("/v1/analyses", json={"text": "합성 리뷰", "modelId": model_id, "includeExplanation": True})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "SUCCEEDED" and body["explanation"]["status"] == explanation_status
    assert persisted(body["analysisId"]).status == "SUCCEEDED"
    retrieved = pg_client.get(created.headers["Location"]).json()
    assert "explanation" not in retrieved
    with session_factory()() as session:
        stored = session.scalar(text("SELECT row_to_json(a)::text FROM analysis_runs a WHERE analysis_id = :id"), {"id": body["analysisId"]})
    assert "합성 리뷰" not in stored and "private review" not in stored


@pytest.mark.parametrize("payload,code,record", [
    ({"text": 123, "modelId": "tfidf_lr"}, "INVALID_REQUEST", False),
    ({"text": "민감한 문장", "modelId": "unknown"}, "UNSUPPORTED_MODEL", False),
    ({"text": "민감한 문장" + "가" * 500, "modelId": "tfidf_lr"}, "INVALID_TEXT", True),
    ({"text": "😀!!!", "modelId": "tfidf_lr"}, "INVALID_TEXT", True),
])
def test_rejection_privacy_and_record_shape(pg_client, monkeypatch, payload, code, record):
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", os.environ.get("TEST_TFIDF_ARTIFACT_DIR", ""))
    response = pg_client.post("/v1/analyses", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == code
    assert body["error"]["requestId"] == response.headers["X-Request-Id"]
    assert "민감한" not in response.text and "😀" not in response.text
    assert ("analysisId" in body) is record
    if record:
        row = persisted(body["analysisId"])
        assert row.status == "REJECTED" and row.error_code == "INVALID_TEXT"
        assert row.label is None and row.confidence is None
        result = pg_client.get(f"/v1/analyses/{body['analysisId']}")
        assert result.json()["status"] == "REJECTED"


def test_model_unavailable_and_inference_failure_are_distinct(pg_client, monkeypatch):
    unavailable = pg_client.post("/v1/analyses", json={"text": "좋은 영화", "modelId": "lstm"})
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert persisted(unavailable.json()["analysisId"]).status == "FAILED"

    import backend.app.main as main_module
    monkeypatch.setattr(main_module, "predict", lambda *_: (_ for _ in ()).throw(RuntimeError("hidden source text")))
    failed = pg_client.post("/v1/analyses", json={"text": "슬픈 영화", "modelId": "tfidf_lr"})
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "INFERENCE_FAILED"
    assert "hidden source text" not in failed.text
    assert persisted(failed.json()["analysisId"]).status == "FAILED"


def test_expired_is_404_before_prune_and_then_deleted(pg_client):
    created = pg_client.post("/v1/analyses", json={"text": "", "modelId": "tfidf_lr"})
    analysis_id = created.json()["analysisId"]
    with session_factory()() as session:
        old = utc_now() - timedelta(hours=25)
        session.execute(update(AnalysisRun).where(AnalysisRun.analysis_id == UUID(analysis_id)).values(created_at=old, expires_at=old + timedelta(hours=24)))
        session.commit()
    missing = pg_client.get(f"/v1/analyses/{analysis_id}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
    assert pg_client.get("/v1/analyses/not-a-uuid").status_code == 404
    with session_factory()() as session:
        assert prune_expired(session) >= 1
    assert persisted(analysis_id) is None


def test_terminal_transition_cannot_be_repeated(pg_client):
    created = pg_client.post("/v1/analyses", json={"text": "", "modelId": "tfidf_lr"})
    row = persisted(created.json()["analysisId"])
    with session_factory()() as session:
        with pytest.raises(StateConflict):
            transition(session, row, "RECEIVED", "RUNNING")
    assert persisted(created.json()["analysisId"]).status == "REJECTED"


def test_success_write_failure_does_not_return_success(pg_client, monkeypatch):
    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)
    monkeypatch.setattr(main_module, "predict", lambda *_: ("긍정", 0.9))
    original = main_module.transition
    seen = {}

    def fail_success(session, row, expected, status, **changes):
        seen["id"] = row.analysis_id
        if status == "SUCCEEDED":
            raise OperationalError("UPDATE", {}, Exception("secret database failure"))
        return original(session, row, expected, status, **changes)

    monkeypatch.setattr(main_module, "transition", fail_success)
    response = pg_client.post("/v1/analyses", json={"text": "성공 저장 실패", "modelId": "tfidf_lr"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "REGISTRY_UNAVAILABLE"
    assert "secret database failure" not in response.text
    assert persisted(str(seen["id"])).status == "RUNNING"


@pytest.mark.parametrize("label", [[], {}, 3])
def test_invalid_label_type_is_recorded_as_inference_failure(pg_client, monkeypatch, label):
    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)
    monkeypatch.setattr(main_module, "predict", lambda *_: (label, 0.9))
    response = pg_client.post("/v1/analyses", json={"text": "유효한 한국어 리뷰", "modelId": "tfidf_lr"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INFERENCE_FAILED"
    row = persisted(response.json()["analysisId"])
    assert row.status == "FAILED" and row.error_code == "INFERENCE_FAILED"
    assert row.label is None and row.confidence is None


def test_soft_timeout_returns_failed_record(pg_client, monkeypatch):
    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)
    monkeypatch.setattr(main_module, "predict", lambda *_: ("긍정", 0.9))
    monkeypatch.setattr(main_module, "analysis_timeout_seconds", lambda: 0)
    response = pg_client.post("/v1/analyses", json={"text": "시간 초과 영화", "modelId": "tfidf_lr"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INFERENCE_FAILED"
    assert persisted(response.json()["analysisId"]).status == "FAILED"


def test_hard_timeout_during_inference_is_recorded_as_inference_failure(pg_client, monkeypatch):
    import backend.app.main as main_module
    from backend.app.isolation import WorkerTimeout

    def killed(*_args):
        raise WorkerTimeout()

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)
    monkeypatch.setattr(main_module, "predict", killed)
    response = pg_client.post("/v1/analyses", json={"text": "멈춘 추론", "modelId": "tfidf_lr"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INFERENCE_FAILED"
    row = persisted(response.json()["analysisId"])
    assert row.status == "FAILED" and row.error_code == "INFERENCE_FAILED"
    assert row.label is None and row.confidence is None


def test_no_free_worker_is_recorded_as_model_unavailable(pg_client, monkeypatch):
    import backend.app.main as main_module
    from backend.app.isolation import WorkerUnavailable

    def busy(*_args):
        raise WorkerUnavailable()

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)
    monkeypatch.setattr(main_module, "predict", busy)
    response = pg_client.post("/v1/analyses", json={"text": "워커 없음", "modelId": "tfidf_lr"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert persisted(response.json()["analysisId"]).status == "FAILED"


def test_hard_timeout_in_the_tokenizer_is_recorded_as_model_unavailable(pg_client, monkeypatch):
    import backend.app.main as main_module
    from backend.app.isolation import WorkerTimeout

    def killed(_text):
        raise WorkerTimeout()

    monkeypatch.setattr(main_module, "has_analyzable_tokens", killed)
    response = pg_client.post("/v1/analyses", json={"text": "토크나이저 정지", "modelId": "tfidf_lr"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    row = persisted(response.json()["analysisId"])
    assert row.status == "FAILED" and row.error_code == "MODEL_UNAVAILABLE"


def test_explanation_hard_timeout_keeps_the_prediction(pg_client, monkeypatch):
    directory = os.environ.get("TEST_TFIDF_ARTIFACT_DIR")
    if not directory:
        pytest.skip("requires preinstalled verified TF-IDF artifacts")
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", directory)
    import backend.app.explanation as explanation_module
    from backend.app.isolation import WorkerTimeout

    def killed(*_args):
        raise WorkerTimeout()

    monkeypatch.setattr(explanation_module, "explain", killed)
    response = pg_client.post("/v1/analyses", json={"text": "정말 좋은 영화", "modelId": "tfidf_lr", "includeExplanation": True})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["explanation"] == {"status": "FAILED", "method": "LIME", "errorCode": "EXPLANATION_FAILED"}
    row = persisted(body["analysisId"])
    assert row.status == "SUCCEEDED" and row.label in {"긍정", "부정"}


def test_stale_recovery_and_success_race_returns_persisted_failure(pg_client, monkeypatch):
    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)

    def recovered_during_inference(*_args):
        with session_factory()() as session:
            row = session.scalar(select(AnalysisRun).where(AnalysisRun.status == "RUNNING").order_by(AnalysisRun.created_at.desc()))
            transition(session, row, "RUNNING", "FAILED", error_code="INFERENCE_FAILED")
        return "긍정", 0.9

    monkeypatch.setattr(main_module, "predict", recovered_during_inference)
    response = pg_client.post("/v1/analyses", json={"text": "경합 테스트", "modelId": "tfidf_lr"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INFERENCE_FAILED"
    assert persisted(response.json()["analysisId"]).status == "FAILED"

    # Recovery leaves a fresh in-flight run untouched and closes an old one.
    with session_factory()() as session:
        row = receive(session, get_model(session, "tfidf_lr"), str(uuid4()))
        transition(session, row, "RECEIVED", "RUNNING")
        # Scoped to this row: unrelated runs left by other tests must not decide the result.
        recover_stale(session, max_age_seconds=240)
        assert session.get(AnalysisRun, row.analysis_id).status == "RUNNING"
        old = utc_now() - timedelta(seconds=300)
        session.execute(update(AnalysisRun).where(AnalysisRun.analysis_id == row.analysis_id).values(
            created_at=old, expires_at=old + timedelta(hours=24),
        ))
        session.commit()
        assert recover_stale(session, max_age_seconds=240) >= 1
    assert persisted(str(row.analysis_id)).status == "FAILED"


def test_tampered_pickle_is_rejected_before_loading(pg_client, monkeypatch, tmp_path):
    source = os.environ.get("TEST_TFIDF_ARTIFACT_DIR")
    if not source:
        pytest.skip("requires preinstalled verified TF-IDF artifacts")
    for name in ("model.pkl", "vectorizer.pkl"):
        shutil.copyfile(os.path.join(source, name), tmp_path / name)
    with (tmp_path / "model.pkl").open("ab") as stream:
        stream.write(b"tampered")
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", str(tmp_path))
    with session_factory()() as session:
        row = session.get(ModelRegistry, "tfidf_lr")
        assert is_available(row) is False
    response = pg_client.post("/v1/analyses", json={"text": "정말 좋은 영화", "modelId": "tfidf_lr"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"
    assert persisted(response.json()["analysisId"]).status == "FAILED"


def test_opt_in_lime_is_one_time_and_not_persisted(pg_client, monkeypatch):
    directory = os.environ.get("TEST_TFIDF_ARTIFACT_DIR")
    if not directory:
        pytest.skip("requires preinstalled verified TF-IDF artifacts")
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", directory)
    models = pg_client.get("/v1/models")
    assert models.status_code == 200
    assert models.json()["models"][0]["explanationAvailable"] is True
    assert all(model["explanationAvailable"] == model["available"] for model in models.json()["models"][1:])
    created = pg_client.post("/v1/analyses", json={
        "text": "정말 재미있는 영화였어요", "modelId": "tfidf_lr", "includeExplanation": True,
    })
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "SUCCEEDED" and body["explanationAvailable"] is True
    explanation = body["explanation"]
    assert explanation["status"] == "SUCCEEDED"
    assert explanation["method"] == "LIME" and explanation["direction"] == "POSITIVE"
    assert explanation["sampleCount"] == 300
    assert len(explanation["features"]) <= 8
    assert all(set(item) == {"token", "weight"} for item in explanation["features"])
    assert created.headers["Cache-Control"] == "no-store"
    retrieved = pg_client.get(created.headers["Location"])
    assert retrieved.status_code == 200
    assert "explanation" not in retrieved.json()
    assert retrieved.json()["status"] == "SUCCEEDED"
    with session_factory()() as session:
        stored = session.scalar(text("SELECT row_to_json(a)::text FROM analysis_runs a WHERE analysis_id = :id"), {"id": body["analysisId"]})
    assert "features" not in stored and "재미있는" not in stored
    assert all(item["token"] not in stored for item in explanation["features"])


def test_lime_failure_keeps_prediction_success_without_leaking_input(pg_client, monkeypatch, caplog):
    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)
    monkeypatch.setattr(main_module, "predict", lambda *_: ("긍정", 0.93))

    def fail_explanation(*_args):
        raise RuntimeError("secret review text and partial LIME tokens")

    monkeypatch.setattr(main_module, "generate_explanation", fail_explanation)
    with caplog.at_level(logging.INFO, logger="backend.api"):
        response = pg_client.post("/v1/analyses", json={
            "text": "비밀 리뷰 문장", "modelId": "tfidf_lr", "includeExplanation": True,
        })
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "SUCCEEDED"
    assert body["explanation"] == {"status": "FAILED", "method": "LIME", "errorCode": "EXPLANATION_FAILED"}
    assert "비밀 리뷰 문장" not in response.text and "partial LIME tokens" not in response.text
    safe_records = [record.message for record in caplog.records if record.name == "backend.api"]
    assert len(safe_records) == 1
    assert '"errorCode": "EXPLANATION_FAILED"' in safe_records[0]
    assert '"modelId": "tfidf_lr"' in safe_records[0]
    assert "비밀 리뷰 문장" not in safe_records[0] and "partial LIME tokens" not in safe_records[0]
    row = persisted(body["analysisId"])
    assert row.status == "SUCCEEDED" and row.error_code is None
    assert "explanation" not in pg_client.get(response.headers["Location"]).json()


def test_slow_lime_cannot_be_recovered_as_failed_after_prediction_commits(pg_client, monkeypatch):
    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "has_analyzable_tokens", lambda _: True)
    monkeypatch.setattr(main_module, "predict", lambda *_: ("긍정", 0.91))
    original_transition = main_module.transition
    succeeded_id = {}

    def record_success(session, run, expected, status, **changes):
        result = original_transition(session, run, expected, status, **changes)
        if status == "SUCCEEDED":
            succeeded_id["id"] = run.analysis_id
        return result

    def slow_explanation(*_args):
        analysis_id = succeeded_id["id"]  # Fails if LIME ran before prediction persistence.
        with session_factory()() as session:
            old = utc_now() - timedelta(seconds=300)
            session.execute(update(AnalysisRun).where(AnalysisRun.analysis_id == analysis_id).values(
                created_at=old, expires_at=old + timedelta(hours=24),
            ))
            session.commit()
            recover_stale(session, max_age_seconds=240)
            assert session.get(AnalysisRun, analysis_id).status == "SUCCEEDED"
        time.sleep(0.05)
        return {"status": "SUCCEEDED", "method": "LIME", "direction": "POSITIVE", "sampleCount": 300, "features": []}

    monkeypatch.setattr(main_module, "transition", record_success)
    monkeypatch.setattr(main_module, "generate_explanation", slow_explanation)
    response = pg_client.post("/v1/analyses", json={
        "text": "합성 리뷰 문장", "modelId": "tfidf_lr", "includeExplanation": True,
    })
    assert response.status_code == 201
    assert response.json()["status"] == "SUCCEEDED"
    assert response.json()["explanation"]["status"] == "SUCCEEDED"
    assert persisted(response.json()["analysisId"]).status == "SUCCEEDED"
    retrieved = pg_client.get(response.headers["Location"]).json()
    assert retrieved["durationMs"] == response.json()["durationMs"]
    assert "explanation" not in retrieved
