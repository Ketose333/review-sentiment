"""Bound public analysis requests before JSON parsing or DB access."""

import json
import time
from collections import deque
from threading import Lock
from typing import Any
from uuid import UUID

from fastapi import Depends, Request

from backend.app.config import analysis_per_client_slots, rate_limit_global, rate_limit_per_ip, rate_limit_window_seconds
from backend.app.ratelimit import SharedLimitUnavailable, allow as allow_shared, client_address, retry_after_seconds
from backend.app.validation import AnalysisInput, ValidationProblem, parse_request_shape


MAX_BODY_BYTES = 8192  # 500 escaped non-BMP code points can occupy 6000 JSON bytes.
# The in-process gate only shields the shared counters from obvious floods, so it is
# deliberately looser than the authoritative budget. Matching it would make the limit a
# sliding window per worker, and which worker served a request would decide the answer.
LOCAL_GATE_FACTOR = 4


class RequestGuardProblem(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
        super().__init__(code)


class RateLimiter:
    """First gate inside one process: keeps obvious floods off the shared counters."""

    def __init__(self, per_ip: int | None = None, global_limit: int | None = None, window_seconds: int | None = None, max_ips: int = 1024):
        self.per_ip = rate_limit_per_ip() * LOCAL_GATE_FACTOR if per_ip is None else per_ip
        self.global_limit = rate_limit_global() * LOCAL_GATE_FACTOR if global_limit is None else global_limit
        self.window_seconds = rate_limit_window_seconds() if window_seconds is None else window_seconds
        self.max_ips = max_ips
        self._global: deque[float] = deque()
        self._by_ip: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            while self._global and self._global[0] <= cutoff:
                self._global.popleft()
            for known_ip, entries in list(self._by_ip.items()):
                while entries and entries[0] <= cutoff:
                    entries.popleft()
                if not entries:
                    del self._by_ip[known_ip]
            entries = self._by_ip.get(ip)
            if len(self._global) >= self.global_limit or (entries is not None and len(entries) >= self.per_ip):
                return False
            if entries is None:
                if len(self._by_ip) >= self.max_ips:
                    # Drop the address tracked longest rather than refuse a newcomer:
                    # otherwise filling this map denies every client we have not seen yet.
                    # Eviction order is insertion, not recency, which is acceptable because
                    # the shared counters stay authoritative for anyone evicted early.
                    self._by_ip.pop(next(iter(self._by_ip)), None)
                entries = self._by_ip[ip] = deque()
            entries.append(now)
            self._global.append(now)
            return True


limiter = RateLimiter()


class AnalysisAdmission:
    """Keep one client from occupying every long-running POST slot."""

    def __init__(self, per_client: int | None = None):
        self.per_client = analysis_per_client_slots() if per_client is None else per_client
        self._active: dict[str, int] = {}
        self._lock = Lock()

    def claim(self, address: str) -> bool:
        with self._lock:
            count = self._active.get(address, 0)
            if count >= self.per_client:
                return False
            self._active[address] = count + 1
            return True

    def release(self, address: str) -> None:
        with self._lock:
            count = self._active[address] - 1
            if count:
                self._active[address] = count
            else:
                del self._active[address]


def check_rate_limit(request: Request) -> None:
    address = client_address(request)
    if not limiter.allow(address):
        raise RequestGuardProblem(429, "RATE_LIMITED", "잠시 후 다시 시도해 주세요.", retry_after_seconds())
    try:
        admitted = allow_shared(address)
    except SharedLimitUnavailable:
        # The shared budget is unknown, so admitting the request could exceed it.
        raise RequestGuardProblem(503, "REGISTRY_UNAVAILABLE", "요청을 처리하지 못했습니다.") from None
    if not admitted:
        raise RequestGuardProblem(429, "RATE_LIMITED", "잠시 후 다시 시도해 주세요.", retry_after_seconds())


async def bounded_json(request: Request) -> Any:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise RequestGuardProblem(422, "INVALID_REQUEST", "요청 형식을 확인해 주세요.")
    pieces = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            raise RequestGuardProblem(413, "PAYLOAD_TOO_LARGE", "요청 크기를 줄여 주세요.")
        pieces.append(chunk)
    try:
        return json.loads(b"".join(pieces).decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise RequestGuardProblem(422, "INVALID_REQUEST", "요청 형식을 확인해 주세요.") from None


def validated_shape(request: Request, payload: Any = Depends(bounded_json)) -> AnalysisInput:
    try:
        supplied = parse_request_shape(payload)
        request.state.model_id = supplied.model_id
        return supplied
    except ValidationProblem as exc:
        message = {
            "UNSUPPORTED_MODEL": "지원하지 않는 모델입니다.",
            "EXPLANATION_UNSUPPORTED": "이 모델은 설명을 지원하지 않습니다.",
        }.get(exc.code, "요청 형식을 확인해 주세요.")
        raise RequestGuardProblem(422, exc.code, message) from None


def valid_analysis_id(analysis_id: str) -> UUID:
    try:
        return UUID(analysis_id)
    except (ValueError, AttributeError):
        raise RequestGuardProblem(404, "ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.") from None
