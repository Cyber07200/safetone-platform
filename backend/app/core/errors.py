"""Unified error model: every error response has the shape
{"error": {"code": str, "message": str, "details": any}}.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("safetone.errors")


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None,
                 status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class LiveModeUnavailable(AppError):
    status_code = 409
    code = "LIVE_MODE_UNAVAILABLE"


class ProviderError(AppError):
    """Raised by AI adapters. `retryable` drives the router's retry policy."""
    status_code = 502
    code = "AI_PROVIDER_ERROR"

    def __init__(self, message: str, *, provider: str, retryable: bool = False,
                 http_status: int | None = None, code: str | None = None):
        super().__init__(message, code=code)
        self.provider = provider
        self.retryable = retryable
        self.http_status = http_status


def _payload(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code,
                            content=_payload(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422, content=_payload(
            "VALIDATION_ERROR", "Некорректные входные данные", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE"}.get(
            exc.status_code, "HTTP_ERROR")
        return JSONResponse(status_code=exc.status_code,
                            content=_payload(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content=_payload(
            "INTERNAL_ERROR", "Внутренняя ошибка сервера. Подробности — в серверном журнале."))
