"""
Piccadily Industrial Historian — Grafana SimpleJSON-Compatible Router
Tag search and time-series query endpoints for Grafana datasource integration.
"""

from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Request

from ..database import get_db

router = APIRouter(prefix="/grafana", tags=["grafana"], include_in_schema=False)


@router.get("/")
async def grafana_health():
    return {"status": "ok"}


@router.post("/search")
async def grafana_search(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    body = await request.json()
    target = body.get("target", "")
    rows = await conn.fetch(
        "SELECT DISTINCT tag_name FROM tag_metadata WHERE tag_name ILIKE $1 LIMIT 200",
        f"%{target}%",
    )
    return [r["tag_name"] for r in rows]


@router.post("/query")
async def grafana_query(
    request: Request,
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
            f"WHERE tag_name=$1 AND bucket BETWEEN $2 AND $3 ORDER BY bucket LIMIT 2000",
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
