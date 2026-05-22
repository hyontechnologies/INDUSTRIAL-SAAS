"""
Industrial Operations Cloud — Domain Exception Hierarchy

Structured exceptions for clean error handling across bounded contexts.
All exceptions carry HTTP status codes for automatic FastAPI translation.
"""

from typing import Any, Optional


class DomainException(Exception):
    """Base exception for all domain-level errors."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: Optional[str] = None, context: Optional[dict[str, Any]] = None):
        self.detail = detail or self.__class__.detail
        self.context = context or {}
        super().__init__(self.detail)


# ── Identity Context ─────────────────────────────────────────────────────────


class AuthenticationError(DomainException):
    status_code = 401
    detail = "Authentication required"


class AuthorizationError(DomainException):
    status_code = 403
    detail = "Insufficient permissions"


class TenantAccessDenied(AuthorizationError):
    detail = "Access denied to this tenant"


class PlantAccessDenied(AuthorizationError):
    detail = "Access denied to this plant"


class SessionRevoked(AuthenticationError):
    detail = "Session has been revoked"


# ── Plant Context ─────────────────────────────────────────────────────────────


class PlantNotFound(DomainException):
    status_code = 404
    detail = "Plant not found"


# ── Telemetry Context ─────────────────────────────────────────────────────────


class RateLimitExceeded(DomainException):
    status_code = 429
    detail = "Rate limit exceeded"


class InvalidTelemetryBatch(DomainException):
    status_code = 422
    detail = "Invalid telemetry batch"


class HypertableNotFound(DomainException):
    status_code = 500
    detail = "Could not determine target hypertable for tag"


# ── Alarm Context ─────────────────────────────────────────────────────────────


class AlarmNotFound(DomainException):
    status_code = 404
    detail = "Alarm not found"


class AlarmStateConflict(DomainException):
    status_code = 409
    detail = "Alarm already acknowledged or cleared"


# ── Infrastructure ────────────────────────────────────────────────────────────


class RedisUnavailable(DomainException):
    status_code = 503
    detail = "Redis service unavailable"


class DatabaseUnavailable(DomainException):
    status_code = 503
    detail = "Database service unavailable"
