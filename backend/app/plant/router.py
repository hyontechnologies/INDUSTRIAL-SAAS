"""
Piccadily Industrial Historian — Plant Management Router
CRUD operations for plants with tenant isolation.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.identity.auth import Permission, audit, require_permission, require_plant_access
from app.infra.database import get_db
from app.models import PlantCreate
from app.models import UserContext
from app.core.pagination import PaginationParams, PaginatedResponse, build_paginated_response

router = APIRouter(prefix="/api/v1/plants", tags=["plants"])


@router.get("", response_model=PaginatedResponse[dict])
async def list_plants(
    pagination: PaginationParams = Depends(),
    user: UserContext = Depends(require_permission(Permission.METADATA_READ)),
    conn: asyncpg.Connection = Depends(get_db),
):
    query = (
        "SELECT plant_id, name, location, plant_type, timezone, is_active, created_at FROM plants WHERE tenant_id=$1"
    )
    params: list[Any] = [user.tenant_id]

    if user.plant_ids:
        query += " AND plant_id = ANY($2)"
        params.append(user.plant_ids)

    if pagination.cursor:
        query += f" AND created_at < ${len(params) + 1}"
        params.append(datetime.fromisoformat(pagination.cursor))

    query += f" ORDER BY created_at DESC LIMIT ${len(params) + 1}"
    params.append(pagination.limit + 1)

    rows = await conn.fetch(query, *params)
    return build_paginated_response(list(rows), limit=pagination.limit, cursor_field="created_at")


@router.get("/{plant_id}")
async def get_plant(
    plant_id: str,
    user: UserContext = Depends(require_permission(Permission.METADATA_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        "SELECT plant_id, name, location, plant_type, timezone, is_active, config, created_at "
        "FROM plants WHERE tenant_id=$1 AND plant_id=$2",
        user.tenant_id,
        plant_id,
    )
    if not row:
        raise HTTPException(404, "Plant not found")
    return dict(row)


@router.post("", status_code=201)
async def create_plant(
    payload: PlantCreate,
    user: UserContext = Depends(require_permission(Permission.METADATA_WRITE)),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute(
        "INSERT INTO plants (tenant_id, plant_id, name, location, plant_type, timezone, config) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (tenant_id, plant_id) "
        "DO UPDATE SET name=$3, location=$4, plant_type=$5, timezone=$6, config=$7",
        user.tenant_id,
        payload.plant_id,
        payload.name,
        payload.location,
        payload.plant_type,
        payload.timezone,
        json.dumps(payload.config or {}),
    )
    await audit(conn, user, "CREATE_PLANT", f"plants/{payload.plant_id}")
    return {"ok": True, "plant_id": payload.plant_id}


@router.delete("/{plant_id}")
async def deactivate_plant(
    plant_id: str,
    user: UserContext = Depends(require_permission(Permission.METADATA_WRITE)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Soft-delete (sets is_active=false). Data is retained."""
    result = await conn.execute(
        "UPDATE plants SET is_active=false WHERE tenant_id=$1 AND plant_id=$2",
        user.tenant_id,
        plant_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Plant not found")
    await audit(conn, user, "DEACTIVATE_PLANT", f"plants/{plant_id}")
    return {"ok": True, "plant_id": plant_id}


@router.get("/{plant_id}/summary")
async def plant_summary(
    plant_id: str,
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Dashboard KPI summary — tag counts + alarm counts in one round-trip."""
    latest_count, active_alarms, critical_alarms = await asyncio.gather(
        conn.fetchval(
            "SELECT count(*) FROM telemetry_latest WHERE tenant_id=$1 AND plant_id=$2",
            user.tenant_id,
            plant_id,
        ),
        conn.fetchval(
            "SELECT count(*) FROM alarms WHERE tenant_id=$1 AND plant_id=$2 AND alarm_state='ACTIVE'",
            user.tenant_id,
            plant_id,
        ),
        conn.fetchval(
            "SELECT count(*) FROM alarms WHERE tenant_id=$1 AND plant_id=$2 "
            "AND alarm_state='ACTIVE' AND severity IN ('CRITICAL','ALARM')",
            user.tenant_id,
            plant_id,
        ),
    )
    return {
        "plant_id": plant_id,
        "active_tags": latest_count,
        "active_alarms": active_alarms,
        "critical_alarms": critical_alarms,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
