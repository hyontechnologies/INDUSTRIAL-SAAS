"""
Piccadily Industrial Historian — Authentication & Authorization
Dual-auth: Supabase JWT (human users) + API Key (edge agents).
RBAC role hierarchy with require_role() dependency factory.
"""

import hashlib
from enum import Enum
from functools import lru_cache
from typing import Optional, Set

import asyncpg
import structlog
from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from app.infra.database import get_read_pool

from app.config import settings
from app.models import UserContext

log = structlog.get_logger("historian.auth")


class Permission(str, Enum):
    # Telemetry
    TELEMETRY_READ = "telemetry:read"
    TELEMETRY_WRITE = "telemetry:write"  # Usually edge only

    # Alarms
    ALARMS_READ = "alarms:read"
    ALARMS_ACK = "alarms:ack"
    ALARMS_CONFIG = "alarms:config"

    # Metadata (Tags/Plants)
    METADATA_READ = "metadata:read"
    METADATA_WRITE = "metadata:write"

    # Admin
    ADMIN_USERS = "admin:users"
    ADMIN_API_KEYS = "admin:api_keys"
    ADMIN_FULL = "admin:full"  # Needed for RBAC integration tests


ROLE_PERMISSIONS: dict[str, Set[Permission]] = {
    "viewer": {
        Permission.TELEMETRY_READ,
        Permission.ALARMS_READ,
        Permission.METADATA_READ,
    },
    "operator": {
        Permission.TELEMETRY_READ,
        Permission.ALARMS_READ,
        Permission.ALARMS_ACK,
        Permission.METADATA_READ,
    },
    "engineer": {
        Permission.TELEMETRY_READ,
        Permission.ALARMS_READ,
        Permission.ALARMS_ACK,
        Permission.ALARMS_CONFIG,
        Permission.METADATA_READ,
        Permission.METADATA_WRITE,
    },
    "admin": set(Permission),  # All permissions
    "edge_agent": {
        Permission.TELEMETRY_WRITE,
    },
}


def _hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _verify_edge_api_key_db(raw_key: str, pool: asyncpg.Pool) -> Optional[str]:
    """
    Check api_keys table first (DB-backed), then fall back to env-var map.
    Returns tenant_id if valid, else None.
    """
    h = _hash_api_key(raw_key)

    # DB lookup (primary source)
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
        # Temporary bypass for local development if the user hasn't configured their real secret
        verify_sig = settings.SUPABASE_JWT_SECRET != "your-jwt-secret-from-supabase-dashboard"
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            options={"verify_signature": verify_sig},
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
    pool: asyncpg.Pool = Depends(get_read_pool),
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
        tenant_id = await _verify_edge_api_key_db(api_key, pool)
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
    plant_ids = meta.get("plant_ids", [])  # Empty list means all plants for this tenant

    if not tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id missing from token")

    session_id = payload.get("session_id")
    if session_id:
        from app.infra.redis import get_redis

        if get_redis():
            is_revoked = await get_redis().get(f"revoked:session:{session_id}")
            if is_revoked:
                raise HTTPException(status_code=401, detail="Session has been revoked")

    return UserContext(
        user_id=payload["sub"],
        tenant_id=tenant_id,
        email=payload.get("email", ""),
        role=role,
        plant_ids=plant_ids,
    )


@lru_cache()
def require_permission(perm: Permission):
    """Dependency factory — raises HTTP 403 if user lacks required permission."""

    async def _guard(user: UserContext = Depends(get_current_user)) -> UserContext:
        user_perms = ROLE_PERMISSIONS.get(user.role, set())
        if perm not in user_perms:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {perm.value}. Current role '{user.role}' does not have this access.",
            )
        return user

    return _guard


def require_plant_access(plant_id_param: str = "plant_id"):
    """
    Dependency factory to verify user has access to a specific plant.
    Reads plant_id from query params or path params.
    """

    async def _check(
        request: Request, user: UserContext = Depends(get_current_user), pool: asyncpg.Pool = Depends(get_read_pool)
    ) -> UserContext:
        plant_id = request.query_params.get(plant_id_param) or request.path_params.get(plant_id_param)

        if not plant_id or user.is_edge:
            return user

        if user.plant_ids and plant_id not in user.plant_ids:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to plant '{plant_id}'. Allowed plants: {user.plant_ids}",
            )

        if not user.plant_ids:
            if pool:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT 1 FROM plants WHERE tenant_id=$1 AND plant_id=$2",
                        user.tenant_id,
                        plant_id,
                    )
                    if not row:
                        raise HTTPException(
                            status_code=404,
                            detail=f"Plant '{plant_id}' not found in tenant '{user.tenant_id}'",
                        )
        return user

    return _check


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
