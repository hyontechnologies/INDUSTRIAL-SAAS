"""
Piccadily Industrial Historian — Grafana SimpleJSON-Compatible Router
Tag search and time-series query endpoints for Grafana datasource integration.
"""

from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Request

from ..auth import Permission, require_permission
from ..database import get_db
from ..models import UserContext

router = APIRouter(prefix="/grafana", tags=["grafana"], include_in_schema=False)


@router.get("/")
async def grafana_health():
    return {"status": "ok"}


@router.post("/search")
async def grafana_search(
    request: Request,
    user: UserContext = Depends(require_permission(Permission.METADATA_READ)),
    conn: asyncpg.Connection = Depends(get_db),
):
    body = await request.json()
    target = body.get("target", "")
    rows = await conn.fetch(
        "SELECT DISTINCT tag_name FROM tag_metadata WHERE tenant_id=$1 AND tag_name ILIKE $2 LIMIT 200",
        user.tenant_id,
        f"%{target}%",
    )
    return [r["tag_name"] for r in rows]


@router.post("/query")
async def grafana_query(
    request: Request,
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Grafana SimpleJSON time-series query using continuous aggregates."""
    body = await request.json()
    fr = body.get("range", {})
    start = datetime.fromisoformat(fr.get("from", "").replace("Z", "+00:00"))
    end = datetime.fromisoformat(fr.get("to", "").replace("Z", "+00:00"))
    span_h = (end - start).total_seconds() / 3600

    source = (
        "telemetry_1min"
        if span_h <= 6
        else "telemetry_5min"
        if span_h <= 48
        else "telemetry_1hour"
        if span_h <= 720
        else "telemetry_1day"
    )

    result = []
    for t in body.get("targets", []):
        tag = t.get("target", "")
        rows = await conn.fetch(
            f"SELECT bucket AS ts, avg_val AS value FROM {source} "
            f"WHERE tenant_id=$1 AND tag_name=$2 AND bucket BETWEEN $3 AND $4 ORDER BY bucket LIMIT 2000",
            user.tenant_id,
            tag,
            start,
            end,
        )
        result.append(
            {
                "target": tag,
                "datapoints": [[r["value"], int(r["ts"].timestamp() * 1000)] for r in rows if r["value"] is not None],
            }
        )
    return result
