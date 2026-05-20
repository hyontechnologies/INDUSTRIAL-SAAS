"""
Piccadily Industrial Historian — Admin Router
Tenant management, audit log, ingestion stats, API key CRUD.
"""

import secrets
import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import audit, require_role, _hash_api_key
from ..broadcaster import ws_manager
from ..database import get_db
from ..metrics import metrics
from ..config import settings
from ..models import ApiKeyCreate, UserContext

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/tenants")
async def list_tenants(
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch("SELECT tenant_id, name, plan, is_active, created_at FROM tenants ORDER BY name")
    return {"count": len(rows), "tenants": [dict(r) for r in rows]}


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(200, le=1000),
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        "SELECT id, tenant_id, user_email, role, action, resource, detail, created_at "
        "FROM audit_logs WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT $2",
        user.tenant_id,
        limit,
    )
    return {"count": len(rows), "logs": [dict(r) for r in rows]}


@router.get("/ingestion-stats")
async def ingestion_stats(
    user: UserContext = Depends(require_role("admin")),
):
    """Live ingestion counters — no DB query needed."""
    return {
        "points_total": metrics.points_total,
        "batches_total": metrics.batches_total,
        "alarms_total": metrics.alarms_total,
        "errors_total": metrics.errors_total,
        "uptime_seconds": metrics.uptime_seconds,
        "ws_connections": ws_manager.connection_count,
        "rate_limit_pts_per_min": settings.RATE_LIMIT_POINTS_PER_MIN,
        "tenant_point_counts": dict(metrics._tenant_counts),
    }


@router.get("/api-keys")
async def list_api_keys(
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """List all API keys for the tenant (hashes only)."""
    rows = await conn.fetch(
        "SELECT key_id, label, tenant_id, is_active, created_at, expires_at, last_used_at "
        "FROM api_keys WHERE tenant_id=$1 ORDER BY created_at DESC",
        user.tenant_id,
    )
    return {"count": len(rows), "keys": [dict(r) for r in rows]}


@router.post("/api-keys", status_code=201)
async def create_api_key(
    payload: ApiKeyCreate,
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Provision a new API key for an edge agent. Returns raw key ONCE."""
    raw_key = secrets.token_urlsafe(32)
    key_hash = _hash_api_key(raw_key)
    key_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO api_keys (key_id, label, tenant_id, key_hash) VALUES ($1,$2,$3,$4)",
        key_id,
        payload.label,
        payload.tenant_id,
        key_hash,
    )
    await audit(
        conn, user, "CREATE_API_KEY", f"api_keys/{key_id}", {"label": payload.label, "tenant": payload.tenant_id}
    )
    return {
        "ok": True,
        "key_id": key_id,
        "raw_key": raw_key,
        "label": payload.label,
        "warning": "Save this key immediately. It will not be shown again.",
    }


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    result = await conn.execute(
        "UPDATE api_keys SET is_active=false WHERE key_id=$1 AND tenant_id=$2",
        key_id,
        user.tenant_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "API key not found")
    await audit(conn, user, "REVOKE_API_KEY", f"api_keys/{key_id}")
    return {"ok": True, "key_id": key_id}
