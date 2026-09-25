"""FastAPI entry point for synchronous analysis."""

import asyncio
import math
import json
import logging
import time
from uuid import UUID
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from backend.app.config import analysis_timeout_seconds, cors_origins
from backend.app.db import RegistryUnavailable, get_session
from backend.app.registry import list_models
from backend.app.analyses import StateConflict, find_unexpired, get_model, receive, run_response, transition
from backend.app.artifacts import ArtifactUnavailable
from backend.app.isolation import WorkerUnavailable, has_analyzable_tokens, predict
from backend.app.validation import AnalysisInput, ValidationProblem, validate_text
from backend.app.maintenance import lifespan
from backend.app.guards import RequestGuardProblem, check_rate_limit, valid_analysis_id, validated_shape
from backend.app.ratelimit import client_address
from backend.app.tables import AnalysisRun
from backend.app.explanation import failed_response as explanation_failed_response, generate as generate_explanation


app = FastAPI(title="Review Sentiment API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    expose_headers=["X-Request-Id"],
)


# Liveness probes run on a fixed interval per instance and carry no diagnostic value.
UNLOGGED_PATHS = frozenset({"/healthz"})


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = str(uuid4())
    started = time.monotonic()
    logged = request.url.path not in UNLOGGED_PATHS
    admitted = False
    claimed = False
    address = None
    analysis_post = request.method == "POST" and request.url.path == "/v1/analyses"
    try:
        if analysis_post:
            try:
                await asyncio.wait_for(request.app.state.analysis_slots.acquire(), timeout=0.05)
            except asyncio.TimeoutError:
                # No analysis row was created; the caller may retry safely.
                response = error_response(request, 503, "SERVICE_BUSY", "잠시 후 다시 시도해 주세요.", retry_after=1)
            else:
                admitted = True
                address = client_address(request)
                if not request.app.state.analysis_admission.claim(address):
                    response = error_response(request, 503, "SERVICE_BUSY", "잠시 후 다시 시도해 주세요.", retry_after=1)
                else:
                    claimed = True
                    response = await call_next(request)
        else:
            response = await call_next(request)
    except Exception:
        if logged:
            _log_request(request, 500, started, "INTERNAL_ERROR")
        raise
    finally:
        if claimed:
            request.app.state.analysis_admission.release(address)
        if admitted:
            request.app.state.analysis_slots.release()
    response.headers["X-Request-Id"] = request.state.request_id
    if logged:
        _log_request(request, response.status_code, started, getattr(request.state, "error_code", None))
    return response


def _log_request(request: Request, status_code: int, started: float, error_code: str | None) -> None:
    route = request.scope.get("route")
    event = {
        "requestId": request.state.request_id,
        "path": getattr(route, "path", "UNMATCHED"),
        "statusCode": status_code,
        "elapsedMs": max(0, int((time.monotonic() - started) * 1000)),
        "modelId": getattr(request.state, "model_id", None),
        "errorCode": error_code,
    }
    logging.getLogger("backend.api").info(json.dumps(event, ensure_ascii=False))


def error_response(request: Request, status: int, code: str, message: str, analysis_id: str | None = None, retry_after: int | None = None) -> JSONResponse:
    request.state.error_code = code
    content = {"error": {"code": code, "message": message, "requestId": request.state.request_id}}
    if analysis_id is not None:
        content["analysisId"] = analysis_id
    headers = {"X-Request-Id": request.state.request_id, "Cache-Control": "no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status, content=content, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, _exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default detail can include the rejected input; use a fixed response.
    return error_response(request, 422, "INVALID_REQUEST", "요청 형식을 확인해 주세요.")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return error_response(request, 404, "NOT_FOUND", "요청한 경로를 찾을 수 없습니다.")
    return error_response(request, exc.status_code, "HTTP_ERROR", "요청을 처리하지 못했습니다.")


@app.exception_handler(RegistryUnavailable)
async def registry_error(request: Request, _exc: RegistryUnavailable) -> JSONResponse:
    return error_response(request, 503, "REGISTRY_UNAVAILABLE", "모델 목록을 불러올 수 없습니다.")


@app.exception_handler(RequestGuardProblem)
async def guard_error(request: Request, exc: RequestGuardProblem) -> JSONResponse:
    return error_response(request, exc.status, exc.code, exc.message, retry_after=exc.retry_after)


@app.exception_handler(Exception)
async def internal_error(request: Request, _exc: Exception) -> JSONResponse:
    # Deliberately avoid exception text: it may contain submitted text or paths.
    return error_response(request, 500, "INTERNAL_ERROR", "요청을 처리하지 못했습니다.")


@app.get("/healthz")
def healthz(_request: Request):
    """Liveness only: never rate limited, never touches the database.

    A readiness probe billed against the public budget would be refused exactly when
    the service is busiest, and the limiter itself would start triggering restarts.
    """
    return JSONResponse(content={"status": "ok"}, headers={"Cache-Control": "no-store"})


@app.get("/v1/models")
def get_models(request: Request, _rate: None = Depends(check_rate_limit), session: Session = Depends(get_session)):
    try:
        return {"models": list_models(session)}
    except (SQLAlchemyError, RegistryUnavailable):
        return error_response(request, 503, "REGISTRY_UNAVAILABLE", "모델 목록을 불러올 수 없습니다.")


def _failure(request: Request, session: Session, run, code: str, status: int, message: str) -> JSONResponse:
    transition(session, run, "RUNNING", "FAILED", error_code=code)
    return error_response(request, status, code, message, str(run.analysis_id))


def _storage_or_recovered_failure(request: Request, session: Session, run) -> JSONResponse:
    session.rollback()
    try:
        session.expire_all()
        current = session.get(AnalysisRun, run.analysis_id)
        if current is not None and current.status == "FAILED" and current.error_code == "INFERENCE_FAILED":
            return error_response(request, 500, "INFERENCE_FAILED", "분석에 실패했습니다.", str(run.analysis_id))
    except SQLAlchemyError:
        session.rollback()
    return error_response(request, 503, "REGISTRY_UNAVAILABLE", "분석을 저장하지 못했습니다.", str(run.analysis_id))


@app.post("/v1/analyses")
def create_analysis(request: Request, _rate: None = Depends(check_rate_limit), supplied: AnalysisInput = Depends(validated_shape), session: Session = Depends(get_session)):
    try:
        model = get_model(session, supplied.model_id)
    except SQLAlchemyError:
        return error_response(request, 503, "REGISTRY_UNAVAILABLE", "모델 목록을 불러올 수 없습니다.")
    if model is None:
        return error_response(request, 503, "REGISTRY_UNAVAILABLE", "모델 목록을 불러올 수 없습니다.")
    if supplied.include_explanation and not model.explanation_available:
        return error_response(request, 422, "EXPLANATION_UNSUPPORTED", "이 모델은 설명을 지원하지 않습니다.")
    try:
        run = receive(session, model, request.state.request_id)
    except SQLAlchemyError:
        session.rollback()
        return error_response(request, 503, "REGISTRY_UNAVAILABLE", "분석을 저장하지 못했습니다.")
    try:
        validate_text(supplied.text)
        if model.model_id in {"tfidf_lr", "lstm"} and has_analyzable_tokens(supplied.text) is False:
            raise ValidationProblem("INVALID_TEXT")
    except ValidationProblem:
        try:
            transition(session, run, "RECEIVED", "REJECTED", error_code="INVALID_TEXT")
        except (SQLAlchemyError, StateConflict):
            return _storage_or_recovered_failure(request, session, run)
        return error_response(request, 422, "INVALID_TEXT", "입력 텍스트를 확인해 주세요.", str(run.analysis_id))
    except Exception:
        # Tokenizer dependencies can fail before RUNNING; record a terminal model failure.
        try:
            transition(session, run, "RECEIVED", "RUNNING")
            return _failure(request, session, run, "MODEL_UNAVAILABLE", 503, "모델을 사용할 수 없습니다.")
        except (SQLAlchemyError, StateConflict):
            return _storage_or_recovered_failure(request, session, run)

    try:
        transition(session, run, "RECEIVED", "RUNNING")
    except (SQLAlchemyError, StateConflict):
        return _storage_or_recovered_failure(request, session, run)
    started = time.monotonic()
    if not model.enabled:
        try:
            return _failure(request, session, run, "MODEL_UNAVAILABLE", 503, "모델을 사용할 수 없습니다.")
        except (SQLAlchemyError, StateConflict):
            return _storage_or_recovered_failure(request, session, run)
    try:
        label, confidence = predict(model, supplied.text)
    except (ArtifactUnavailable, WorkerUnavailable):
        code, status, message = "MODEL_UNAVAILABLE", 503, "모델을 사용할 수 없습니다."
    except Exception:
        code, status, message = "INFERENCE_FAILED", 500, "분석에 실패했습니다."
    else:
        if time.monotonic() - started >= analysis_timeout_seconds() or type(label) is not str or label not in {"긍정", "부정"} or type(confidence) not in (float, int) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            code, status, message = "INFERENCE_FAILED", 500, "분석에 실패했습니다."
        else:
            # Persist the prediction before optional LIME work. A terminated or
            # slow explanation must never turn a successful prediction into FAILED.
            duration_ms = max(0, int((time.monotonic() - started) * 1000))
            try:
                transition(session, run, "RUNNING", "SUCCEEDED", label=label, confidence=float(confidence), duration_ms=duration_ms)
            except (SQLAlchemyError, StateConflict):
                return _storage_or_recovered_failure(request, session, run)
            body = run_response(run)
            if supplied.include_explanation:
                try:
                    explanation = generate_explanation(model, supplied.text)
                except Exception:
                    # LIME errors can include snippets of the submitted text.
                    explanation = explanation_failed_response()
                body["explanation"] = explanation
                if explanation["status"] == "FAILED":
                    request.state.error_code = "EXPLANATION_FAILED"
            return JSONResponse(
                status_code=201, content=jsonable_encoder(body),
                headers={"Location": f"/v1/analyses/{run.analysis_id}", "Cache-Control": "no-store"},
            )
    try:
        return _failure(request, session, run, code, status, message)
    except (SQLAlchemyError, StateConflict):
        return _storage_or_recovered_failure(request, session, run)


@app.get("/v1/analyses/{analysis_id}")
def get_analysis(request: Request, _rate: None = Depends(check_rate_limit), parsed: UUID = Depends(valid_analysis_id), session: Session = Depends(get_session)):
    try:
        run = find_unexpired(session, parsed)
    except SQLAlchemyError:
        return error_response(request, 503, "REGISTRY_UNAVAILABLE", "분석 결과를 불러올 수 없습니다.")
    if run is None:
        return error_response(request, 404, "ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.")
    request.state.model_id = run.model_id
    return JSONResponse(content=jsonable_encoder(run_response(run)), headers={"Cache-Control": "no-store"})
