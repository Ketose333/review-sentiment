"""Stage A API contract and privacy boundaries."""

from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.app.db import get_session
from backend.app.db import session_factory
from backend.app.main import app
from backend.app.registry import list_models
from backend.app.validation import ValidationProblem, validate_analysis_request


@dataclass
class RegistryRow:
    model_id: str
    display_name: str
    artifact_revision: str = "verified-revision"
    enabled: bool = False
    metrics: dict | None = None
    evaluation_scope: dict | None = None
    explanation_available: bool = False

    def __post_init__(self):
        self.metrics = self.metrics or {"accuracy": 0.8, "precision": 0.8, "recall": 0.8, "f1": 0.8}
        self.evaluation_scope = self.evaluation_scope or {"dataset": "NSMC", "testSet": "test", "testCount": None, "sampleSeed": None}


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self, _statement):
        return self

    def all(self):
        return self.rows


@pytest.fixture
def client():
    rows = [RegistryRow("klue_bert", "KLUE-BERT"), RegistryRow("tfidf_lr", "TF-IDF"), RegistryRow("lstm", "LSTM")]

    def dependency():
        yield FakeSession(rows)

    app.dependency_overrides[get_session] = dependency
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_model_list_has_stable_order_metadata_and_request_id(client):
    response = client.get("/v1/models")
    assert response.status_code == 200
    UUID(response.headers["X-Request-Id"])
    models = response.json()["models"]
    assert [model["modelId"] for model in models] == ["tfidf_lr", "lstm", "klue_bert"]
    assert all(set(model) == {"modelId", "displayName", "version", "available", "metrics", "evaluation", "explanationAvailable"} for model in models)
    assert all(model["available"] is False and model["explanationAvailable"] is False for model in models)
    assert models[0]["evaluation"]["testCount"] is None


def test_registry_missing_row_returns_privacy_safe_503(client):
    app.dependency_overrides[get_session] = lambda: FakeSession([RegistryRow("tfidf_lr", "TF-IDF")])
    response = client.get("/v1/models")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REGISTRY_UNAVAILABLE"
    assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]


def test_registry_connection_failure_returns_503(client):
    class BrokenSession:
        def scalars(self, _statement):
            raise OperationalError("SELECT", {}, Exception("database down"))

    app.dependency_overrides[get_session] = lambda: BrokenSession()
    response = client.get("/v1/models")
    assert response.status_code == 503
    assert "database down" not in response.text


def test_missing_database_configuration_returns_503(client, monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    session_factory.cache_clear()
    response = client.get("/v1/models")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REGISTRY_UNAVAILABLE"
    session_factory.cache_clear()


def test_unknown_path_still_uses_error_envelope(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]


def test_cors_preflight_and_browser_visible_request_id(monkeypatch):
    import importlib
    import backend.app.main as main_module

    try:
        with monkeypatch.context() as env:
            env.setenv("CORS_ORIGINS", "https://web.example")
            importlib.reload(main_module)
            with TestClient(main_module.app) as cors_client:
                preflight = cors_client.options(
                    "/v1/models",
                    headers={"Origin": "https://web.example", "Access-Control-Request-Method": "GET"},
                )
                assert preflight.status_code == 200
                assert preflight.headers["Access-Control-Allow-Origin"] == "https://web.example"
                response = cors_client.get("/missing", headers={"Origin": "https://web.example"})
                assert response.headers["Access-Control-Allow-Origin"] == "https://web.example"
                assert "X-Request-Id" in response.headers["Access-Control-Expose-Headers"]
                assert response.json()["error"]["requestId"] == response.headers["X-Request-Id"]
    finally:
        importlib.reload(main_module)


def test_input_accepts_exactly_500_codepoints_and_preserves_original():
    text = "가" * 499 + "😀"
    result = validate_analysis_request({"text": text, "modelId": "tfidf_lr"})
    assert result.text == text
    assert result.model_id == "tfidf_lr"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"text": "", "modelId": "tfidf_lr"}, "INVALID_TEXT"),
        ({"text": " \t\n", "modelId": "tfidf_lr"}, "INVALID_TEXT"),
        ({"text": "가" * 501, "modelId": "lstm"}, "INVALID_TEXT"),
        ({"text": "비밀 문장", "modelId": "unknown"}, "UNSUPPORTED_MODEL"),
        ({"text": 123, "modelId": "lstm"}, "INVALID_REQUEST"),
        ({"text": "비밀 문장", "modelId": "tfidf_lr", "extra": 1}, "INVALID_REQUEST"),
    ],
)
def test_invalid_input_never_echoes_text(payload, code):
    with pytest.raises(ValidationProblem) as info:
        validate_analysis_request(payload)
    assert info.value.code == code
    assert "비밀 문장" not in str(info.value)
    assert "가" not in str(info.value)


def test_registry_function_rejects_partial_seed():
    with pytest.raises(Exception):
        list_models(FakeSession([RegistryRow("tfidf_lr", "TF-IDF")]))
