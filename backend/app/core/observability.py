"""
Industrial Operations Cloud — Observability Module

Centralized error recording, structured logging configuration, and future
OpenTelemetry integration point.
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .exceptions import DomainException

log = structlog.get_logger("historian.observability")


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for domain exceptions.
    Prevents raw stack traces from leaking to clients.
    """

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        log.warning(
            "domain.exception",
            status_code=exc.status_code,
            detail=exc.detail,
            context=exc.context,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "detail": exc.detail,
                "context": exc.context if exc.context else None,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled.exception",
            error=str(exc),
            type=type(exc).__name__,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "detail": "An unexpected error occurred",
            },
        )
