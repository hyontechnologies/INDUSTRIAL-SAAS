"""
Piccadily Industrial Historian — Authentication & Authorization
Dual-auth: Supabase JWT (human users) + API Key (edge agents).
RBAC role hierarchy with require_role() dependency factory.
"""

import hashlib
from typing import Optional

import asyncpg
import structlog
from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt

from .config import settings
from .database import get_pool
from .models import UserContext

log = structlog.get_logger("historian.auth")


def _hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _verify_edge_api_key_db(raw_key: str) -> Optional[str]:
    """
    Check api_keys table first (DB-backed), then fall back to env-var map.
    Returns tenant_id if valid, else None.
    """
    h = _hash_api_key(raw_key)

    # DB lookup (primary source)
    pool = get_pool()
    if pool:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT tenant_id FROM api_keys
                    WHERE key_hash=$1 AND is_active=true
                      AND (expires_at IS NULL OR expires_at > now())
                    """,
                    h,
                )
                if row:
                    return row["tenant_id"]
        except Exception:
            pass  # Fall through to env-var fallback

    # Env-var fallback
    return settings.edge_api_keys_map.get(h)


def _decode_supabase_jwt(token: str) -> dict:
    """Decode and validate Supabase-issued JWT. Raises 401 on failure."""
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> UserContext:
    """
    Dual-auth resolver:
      1. X-API-Key header  →  edge agent machine auth (hashed key lookup, DB-backed)
      2. Authorization: Bearer <JWT>  →  Supabase human user auth
    """
    # Extract header values if they are strings (FastAPI passes string or None, direct tests might pass default Header objects)
    api_key = x_api_key if isinstance(x_api_key, str) else None
    auth_header = authorization if isinstance(authorization, str) else None

    if api_key:
        tenant_id = await _verify_edge_api_key_db(api_key)
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return UserContext(
            user_id=f"edge:{tenant_id}",
            tenant_id=tenant_id,
            email=f"edge@{tenant_id}",
            role="edge_agent",
            is_edge=True,
        )

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing credentials — provide X-API-Key or Authorization: Bearer <JWT>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]
    payload = _decode_supabase_jwt(token)

    meta = payload.get("app_metadata", {})
    user_meta = payload.get("user_metadata", {})
    tenant_id = meta.get("tenant_id") or user_meta.get("tenant_id")
    role = meta.get("role", "viewer")

    if not tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id missing from token")

    return UserContext(
        user_id=payload["sub"],
        tenant_id=tenant_id,
        email=payload.get("email", ""),
        role=role,
    )


def require_role(*allowed: str):
    """Dependency factory — raises HTTP 403 if user.role not in allowed."""

    async def _guard(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not authorised. Required: {allowed}",
            )
        return user

    return _guard


async def audit(
    conn: asyncpg.Connection,
    user: UserContext,
    action: str,
    resource: str,
    detail: Optional[dict] = None,
) -> None:
    """Write an entry to the audit_logs hypertable."""
    import json

    await conn.execute(
        """
        INSERT INTO audit_logs
            (tenant_id, user_id, user_email, role, action, resource, detail)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        user.tenant_id,
        user.user_id,
        user.email,
        user.role,
        action,
        resource,
        json.dumps(detail or {}),
    )
