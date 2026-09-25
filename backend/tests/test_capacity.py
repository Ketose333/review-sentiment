"""Bound long analysis requests without stalling reads or other predictions."""

import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app import artifacts, config, guards, isolation, main
from backend.app.db import get_session


def test_busy_post_is_rejected_before_db_and_get_stays_responsive(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setenv("ANALYSIS_REQUEST_SLOTS", "1")
    config.analysis_request_slots.cache_clear()
    monkeypatch.setattr(main, "list_models", lambda _session: [])

    def blocked_model(_session, _id):
        entered.set()
        assert release.wait(5)
        return None

    monkeypatch.setattr(main, "get_model", blocked_model)
    main.app.dependency_overrides[get_session] = lambda: object()
    try:
        with TestClient(main.app) as client, ThreadPoolExecutor(max_workers=1) as threads:
            first = threads.submit(client.post, "/v1/analyses", json={"text": "합성", "modelId": "tfidf_lr"})
            assert entered.wait(3)
            started = time.monotonic()
            busy = client.post("/v1/analyses", json={"text": "합성", "modelId": "tfidf_lr"})
            assert time.monotonic() - started < 1
            assert busy.status_code == 503 and busy.json()["error"]["code"] == "SERVICE_BUSY"
            assert "analysisId" not in busy.json() and busy.headers["Retry-After"] == "1"
            assert client.get("/v1/models").status_code == 200
            assert client.get("/healthz").status_code == 200
            release.set()
            assert first.result(timeout=5).status_code == 503
    finally:
        release.set()
        main.app.dependency_overrides.clear()
        config.analysis_request_slots.cache_clear()


def test_get_analysis_uses_shared_limit_before_database(monkeypatch):
    monkeypatch.setattr(guards, "allow_shared", lambda _address: False)

    def database_must_not_be_used():
        raise AssertionError("GET was not rate limited")

    main.app.dependency_overrides[get_session] = database_must_not_be_used
    try:
        with TestClient(main.app) as client:
            response = client.get(f"/v1/analyses/{uuid4()}")
        assert response.status_code == 429 and response.json()["error"]["code"] == "RATE_LIMITED"
    finally:
        main.app.dependency_overrides.clear()


def test_optional_explanation_has_short_slot_wait_and_prediction_slot_survives():
    created = isolation.Pool(2)
    assert created._slots[0].lock.acquire(blocking=False)
    try:
        started = time.monotonic()
        with pytest.raises(isolation.WorkerUnavailable):
            created.run("explain", None, "합성", budget=180)
        assert time.monotonic() - started < 0.5
        assert created.run("sleep", None, "0") is True
    finally:
        created._slots[0].lock.release()
        created.shutdown()


def test_active_client_slots_preserve_capacity_for_other_clients():
    admission = guards.AnalysisAdmission(per_client=1)
    assert admission.claim("198.51.100.1")
    assert not admission.claim("198.51.100.1")
    assert admission.claim("198.51.100.2")
    admission.release("198.51.100.1")
    assert admission.claim("198.51.100.1")
    admission.release("198.51.100.1")
    admission.release("198.51.100.2")
    assert admission._active == {}


def test_long_bert_request_does_not_hold_other_clients_or_models(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setenv("ANALYSIS_REQUEST_SLOTS", "2")
    config.analysis_request_slots.cache_clear()
    config.analysis_per_client_slots.cache_clear()
    monkeypatch.setattr(main, "client_address", lambda request: request.headers["X-Test-Client"])

    def model(_session, model_id):
        if model_id == "klue_bert":
            entered.set()
            assert release.wait(5)
        return None

    monkeypatch.setattr(main, "get_model", model)
    main.app.dependency_overrides[get_session] = lambda: object()
    try:
        with TestClient(main.app) as client, ThreadPoolExecutor(max_workers=1) as threads:
            first = threads.submit(client.post, "/v1/analyses",
                                   json={"text": "합성", "modelId": "klue_bert"},
                                   headers={"X-Test-Client": "198.51.100.1"})
            assert entered.wait(3)
            started = time.monotonic()
            other = client.post("/v1/analyses", json={"text": "합성", "modelId": "tfidf_lr"},
                                headers={"X-Test-Client": "198.51.100.2"})
            assert time.monotonic() - started < 1
            assert other.status_code == 503 and other.json()["error"]["code"] == "REGISTRY_UNAVAILABLE"
            release.set()
            assert first.result(timeout=5).status_code == 503
    finally:
        release.set()
        main.app.dependency_overrides.clear()
        config.analysis_request_slots.cache_clear()
        config.analysis_per_client_slots.cache_clear()


def test_immutable_artifact_identity_avoids_rehash_and_detects_change(monkeypatch, tmp_path):
    contents = {"model.pkl": b"model", "vectorizer.pkl": b"vectorizer"}
    manifest = {f"models/tfidf_lr/{name}": hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    for name, data in contents.items():
        (tmp_path / name).write_bytes(data)
    monkeypatch.setattr(artifacts, "EXPECTED_MANIFEST", manifest)
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", str(tmp_path))
    row = SimpleNamespace(model_id="tfidf_lr", enabled=True, artifact_repo=artifacts.EXPECTED_REPO,
                          artifact_revision=artifacts.EXPECTED_REVISION, artifact_manifest=manifest)
    artifacts._digest_file.cache_clear()
    assert artifacts.is_available(row) and artifacts.is_available(row)
    assert artifacts._digest_file.cache_info().misses == 2
    (tmp_path / "model.pkl").write_bytes(b"other")  # Same size, different content.
    assert not artifacts.is_available(row)
    assert artifacts._digest_file.cache_info().misses == 3
    artifacts._digest_file.cache_clear()


def test_same_size_overwrite_with_restored_mtime_invalidates_digest(monkeypatch, tmp_path):
    contents = {"model.pkl": b"model", "vectorizer.pkl": b"vectorizer"}
    manifest = {f"models/tfidf_lr/{name}": hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    for name, data in contents.items():
        (tmp_path / name).write_bytes(data)
    monkeypatch.setattr(artifacts, "EXPECTED_MANIFEST", manifest)
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", str(tmp_path))
    row = SimpleNamespace(model_id="tfidf_lr", enabled=True, artifact_repo=artifacts.EXPECTED_REPO,
                          artifact_revision=artifacts.EXPECTED_REVISION, artifact_manifest=manifest)
    artifacts._digest_file.cache_clear()
    assert artifacts.is_available(row)
    target = tmp_path / "model.pkl"
    before = target.stat()
    prior_change_time = artifacts._windows_change_time(target) if os.name == "nt" else before.st_ctime_ns
    time.sleep(0.02)
    target.write_bytes(b"other")
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert target.stat().st_size == before.st_size
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    if os.name == "nt" and prior_change_time:
        assert artifacts._windows_change_time(target) != prior_change_time
    assert not artifacts.is_available(row)
    artifacts._digest_file.cache_clear()


@pytest.mark.skipif(os.name != "nt", reason="Windows provider fallback")
@pytest.mark.parametrize("query_fails", [False, True])
def test_windows_provider_without_change_time_never_caches(monkeypatch, tmp_path, query_fails):
    contents = {"model.pkl": b"model", "vectorizer.pkl": b"vectorizer"}
    manifest = {f"models/tfidf_lr/{name}": hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    for name, data in contents.items():
        (tmp_path / name).write_bytes(data)
    monkeypatch.setattr(artifacts, "EXPECTED_MANIFEST", manifest)
    def change_time(_path):
        if query_fails:
            raise OSError("unsupported FileBasicInfo")
        return 0

    monkeypatch.setattr(artifacts, "_windows_change_time", change_time)
    monkeypatch.setenv("TFIDF_ARTIFACT_DIR", str(tmp_path))
    row = SimpleNamespace(model_id="tfidf_lr", enabled=True, artifact_repo=artifacts.EXPECTED_REPO,
                          artifact_revision=artifacts.EXPECTED_REVISION, artifact_manifest=manifest)
    artifacts._digest_file.cache_clear()
    assert artifacts.is_available(row) and artifacts.is_available(row)
    assert artifacts._digest_file.cache_info().misses == 0
    (tmp_path / "model.pkl").write_bytes(b"other")
    assert not artifacts.is_available(row)


@pytest.mark.parametrize("name,value", [
    ("ANALYSIS_REQUEST_SLOTS", "0"),
    ("ANALYSIS_REQUEST_SLOTS", "17"),
    ("ANALYSIS_PER_CLIENT_SLOTS", "0"),
    ("ANALYSIS_PER_CLIENT_SLOTS", "5"),
])
def test_invalid_admission_configuration_fails_startup(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    config.analysis_request_slots.cache_clear()
    config.analysis_per_client_slots.cache_clear()
    try:
        with pytest.raises(ValueError):
            with TestClient(main.app):
                pass
    finally:
        config.analysis_request_slots.cache_clear()
        config.analysis_per_client_slots.cache_clear()
