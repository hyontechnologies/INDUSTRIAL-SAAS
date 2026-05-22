"""
Piccadily Industrial Historian — Tag Metadata Router
List, search, and upsert tag metadata with alarm threshold management.
"""

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.alarms.engine import evict_threshold_cache
from app.identity.auth import Permission, audit, require_permission, require_plant_access
from app.infra.database import get_db
from app.models import TagMetadataUpdate, UserContext

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


@router.get("")
async def list_tags(
    plant_id: str = Query(...),
    user: UserContext = Depends(require_permission(Permission.METADATA_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        "SELECT tag_name, description, engineering_unit, opc_node_id, data_type, "
        "low_low_limit, low_limit, high_limit, high_high_limit, "
        "deadband, is_active, updated_at "
        "FROM tag_metadata WHERE tenant_id=$1 AND plant_id=$2 ORDER BY tag_name",
        user.tenant_id,
        plant_id,
    )
    return {"count": len(rows), "tags": [dict(r) for r in rows]}


@router.get("/search")
async def search_tags(
    plant_id: str = Query(...),
    q: str = Query(..., min_length=1, description="Tag name / description substring"),
    limit: int = Query(50, le=200),
    user: UserContext = Depends(require_permission(Permission.METADATA_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Full-text search across tag_name and description."""
    rows = await conn.fetch(
        "SELECT tag_name, description, engineering_unit, is_active "
        "FROM tag_metadata WHERE tenant_id=$1 AND plant_id=$2 "
        "AND (tag_name ILIKE $3 OR description ILIKE $3) ORDER BY tag_name LIMIT $4",
        user.tenant_id,
        plant_id,
        f"%{q}%",
        limit,
    )
    return {"count": len(rows), "tags": [dict(r) for r in rows]}


@router.put("/{tag_name}")
async def upsert_tag_metadata(
    tag_name: str,
    plant_id: str = Query(...),
    payload: TagMetadataUpdate = ...,
    user: UserContext = Depends(require_permission(Permission.METADATA_WRITE)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute(
        "INSERT INTO tag_metadata "
        "(tenant_id, plant_id, tag_name, description, engineering_unit, "
        "opc_node_id, data_type, low_low_limit, low_limit, "
        "high_limit, high_high_limit, deadband, is_active) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) "
        "ON CONFLICT (tenant_id, plant_id, tag_name) DO UPDATE SET "
        "description=EXCLUDED.description, engineering_unit=EXCLUDED.engineering_unit, "
        "opc_node_id=EXCLUDED.opc_node_id, data_type=EXCLUDED.data_type, "
        "low_low_limit=EXCLUDED.low_low_limit, low_limit=EXCLUDED.low_limit, "
        "high_limit=EXCLUDED.high_limit, high_high_limit=EXCLUDED.high_high_limit, "
        "deadband=EXCLUDED.deadband, is_active=EXCLUDED.is_active, updated_at=now()",
        user.tenant_id,
        plant_id,
        tag_name,
        payload.description,
        payload.engineering_unit,
        payload.opc_node_id,
        payload.data_type,
        payload.low_low_limit,
        payload.low_limit,
        payload.high_limit,
        payload.high_high_limit,
        payload.deadband,
        payload.is_active,
    )
    await evict_threshold_cache(user.tenant_id, plant_id, tag_name)
    await audit(conn, user, "UPSERT_TAG_METADATA", f"tags/{tag_name}")
    return {"ok": True, "tag_name": tag_name}
