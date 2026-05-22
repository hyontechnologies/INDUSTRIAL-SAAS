"""
Piccadily Industrial Historian — Telemetry Router
High-throughput ingestion, latest values, history, multi-history, stats, stale detection, export.
"""

import csv
import io
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import StreamingResponse

from ..auth import Permission, require_permission, require_plant_access
from ..config import settings
from ..database import get_db
from ..ingestion import ingest_telemetry_batch
from ..models import TelemetryBatch, UserContext
from ..tag_router import TagRouter

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])
tag_router = TagRouter()


@router.post("/ingest", status_code=202)
async def ingest(
    batch: TelemetryBatch,
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_WRITE)),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Primary high-throughput ingestion endpoint. Edge agent uses X-API-Key."""
    # Enforce plant access if not edge
    if not user.is_edge and user.plant_ids and batch.plant_id not in user.plant_ids:
        raise HTTPException(status_code=403, detail=f"Access denied to plant '{batch.plant_id}'")
    if len(batch.points) > settings.TELEMETRY_BATCH_MAX:
        raise HTTPException(422, f"Batch exceeds max size {settings.TELEMETRY_BATCH_MAX}")
    result = await ingest_telemetry_batch(conn, batch, user)
    return {"ok": True, **result}


@router.get("/latest")
async def get_latest(
    plant_id: str = Query(...),
    tags: Optional[str] = Query(None, description="Comma-separated tag list"),
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Latest value for all (or specified) tags in a plant. O(1) per tag."""
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    if tag_list:
        rows = await conn.fetch(
            "SELECT tag_name, value, quality, ts, unit FROM telemetry_latest "
            "WHERE tenant_id=$1 AND plant_id=$2 AND tag_name = ANY($3) ORDER BY tag_name",
            user.tenant_id,
            plant_id,
            tag_list,
        )
    else:
        rows = await conn.fetch(
            "SELECT tag_name, value, quality, ts, unit FROM telemetry_latest "
            "WHERE tenant_id=$1 AND plant_id=$2 ORDER BY tag_name",
            user.tenant_id,
            plant_id,
        )
    return {"plant_id": plant_id, "count": len(rows), "data": [dict(r) for r in rows]}


@router.get("/history")
async def get_history(
    plant_id: str = Query(...),
    tag_name: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    interval: str = Query("1m", description="Time bucket: 1m 5m 15m 1h 1d raw"),
    agg: str = Query("avg", description="avg | min | max | last"),
    limit: int = Query(2000, le=10000),
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Tag history with time-bucket aggregation. Auto-selects raw or continuous aggregate."""
    valid_aggs = {"avg", "min", "max", "last", "first"}
    if agg not in valid_aggs:
        raise HTTPException(422, f"agg must be one of {valid_aggs}")

    valid_intervals = {"1m", "5m", "15m", "1h", "1d", "raw"}
    if interval not in valid_intervals:
        raise HTTPException(422, f"interval must be one of {valid_intervals}")

    if interval == "raw":
        rows = await conn.fetch(
            "SELECT ts, value, quality FROM telemetry_all "
            "WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
            "AND ts BETWEEN $4 AND $5 ORDER BY ts DESC LIMIT $6",
            user.tenant_id,
            plant_id,
            tag_name,
            start,
            end,
            limit,
        )
    else:
        pg_interval = {"1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes", "1h": "1 hour", "1d": "1 day"}.get(
            interval, "1 minute"
        )
        if agg == "last":
            agg_sql = "last(value, ts)"
        elif agg == "first":
            agg_sql = "first(value, ts)"
        else:
            agg_sql = f"{agg}(value)"

        rows = await conn.fetch(
            f"SELECT time_bucket('{pg_interval}', ts) AS ts, {agg_sql} AS value, count(value) AS sample_count "
            f"FROM telemetry_all WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
            f"AND ts BETWEEN $4 AND $5 "
            f"GROUP BY ts ORDER BY ts DESC LIMIT $6",
            user.tenant_id,
            plant_id,
            tag_name,
            start,
            end,
            limit,
        )

    return {
        "tag_name": tag_name,
        "plant_id": plant_id,
        "interval": interval,
        "count": len(rows),
        "data": [dict(r) for r in rows],
    }


@router.get("/multi-history")
async def get_multi_history(
    plant_id: str = Query(...),
    tags: str = Query(..., description="Comma-separated, max 10 tags"),
    start: datetime = Query(...),
    end: datetime = Query(...),
    interval: str = Query("5m"),
    agg: str = Query("avg"),
    limit: int = Query(1000, le=5000),
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Multi-tag trend correlation. Returns pivot format for React charts."""
    tag_list = [t.strip() for t in tags.split(",")][:10]

    valid_aggs = {"avg", "min", "max", "last", "first"}
    if agg not in valid_aggs:
        raise HTTPException(422, f"agg must be one of {valid_aggs}")

    valid_intervals = {"1m", "5m", "15m", "1h", "1d"}
    if interval not in valid_intervals:
        raise HTTPException(422, f"interval must be one of {valid_intervals}")

    pg_interval = {"1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes", "1h": "1 hour", "1d": "1 day"}.get(
        interval, "5 minutes"
    )

    if agg == "last":
        agg_sql = "last(value, ts)"
    elif agg == "first":
        agg_sql = "first(value, ts)"
    else:
        agg_sql = f"{agg}(value)"

    pivot = {}

    for tag_name in tag_list:
        rows = await conn.fetch(
            f"SELECT time_bucket('{pg_interval}', ts) AS ts, {agg_sql} AS value "
            f"FROM telemetry_all WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
            f"AND ts BETWEEN $4 AND $5 GROUP BY ts ORDER BY ts DESC LIMIT $6",
            user.tenant_id,
            plant_id,
            tag_name,
            start,
            end,
            limit,
        )
        for r in rows:
            ts_str = r["ts"].isoformat()
            pivot.setdefault(ts_str, {"ts": ts_str})
            pivot[ts_str][tag_name] = r["value"]

    return {
        "plant_id": plant_id,
        "tags": tag_list,
        "interval": interval,
        "count": len(pivot),
        "data": sorted(pivot.values(), key=lambda x: x["ts"], reverse=True),
    }


@router.get("/stats")
async def get_tag_stats(
    plant_id: str = Query(...),
    tag_name: str = Query(...),
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Min/max/avg/stddev/count for a tag over the last N hours."""
    tag_meta = await conn.fetchrow(
        "SELECT tag_group FROM tag_metadata WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3",
        user.tenant_id,
        plant_id,
        tag_name,
    )
    group = tag_meta["tag_group"] if tag_meta else None
    hypertable = await tag_router.route_tag(conn, user.tenant_id, tag_name, group)

    row = await conn.fetchrow(
        f"SELECT count(*) AS sample_count, round(avg(value)::numeric, 4) AS avg_val, "
        f"round(min(value)::numeric, 4) AS min_val, round(max(value)::numeric, 4) AS max_val, "
        f"round(stddev(value)::numeric, 4) AS std_val "
        f"FROM {hypertable} "
        f"WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
        f"AND ts >= now() - interval '1 hour' * $4",
        user.tenant_id,
        plant_id,
        tag_name,
        hours,
    )
    return {"tag_name": tag_name, "plant_id": plant_id, "hours": hours, "stats": dict(row)}


@router.get("/stale")
async def get_stale_tags(
    plant_id: str = Query(...),
    stale_minutes: int = Query(None, description="Override default stale threshold"),
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Tags whose last update is older than stale_minutes."""
    threshold = stale_minutes or settings.STALE_TAG_MINUTES
    rows = await conn.fetch(
        "SELECT tag_name, value, quality, ts, unit, "
        "EXTRACT(EPOCH FROM (now() - ts)) / 60 AS stale_minutes "
        "FROM telemetry_latest WHERE tenant_id=$1 AND plant_id=$2 "
        "AND ts < now() - ($3 || ' minutes')::interval ORDER BY ts ASC",
        user.tenant_id,
        plant_id,
        str(threshold),
    )
    return {
        "plant_id": plant_id,
        "stale_threshold_minutes": threshold,
        "stale_count": len(rows),
        "stale_tags": [dict(r) for r in rows],
    }


@router.get("/export")
async def export_telemetry(
    plant_id: str = Query(...),
    tag_name: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    fmt: str = Query("csv", description="csv | json"),
    limit: int = Query(50000, le=100000),
    user: UserContext = Depends(require_permission(Permission.TELEMETRY_READ)),
    _=Depends(require_plant_access),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Raw data export. Returns CSV (default) or JSON."""
    tag_meta = await conn.fetchrow(
        "SELECT tag_group FROM tag_metadata WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3",
        user.tenant_id,
        plant_id,
        tag_name,
    )
    group = tag_meta["tag_group"] if tag_meta else None
    hypertable = await tag_router.route_tag(conn, user.tenant_id, tag_name, group)

    rows = await conn.fetch(
        f"SELECT ts, value, quality FROM {hypertable} "
        f"WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
        f"AND ts BETWEEN $4 AND $5 ORDER BY ts ASC LIMIT $6",
        user.tenant_id,
        plant_id,
        tag_name,
        start,
        end,
        limit,
    )
    if fmt == "json":
        return {"tag_name": tag_name, "plant_id": plant_id, "count": len(rows), "data": [dict(r) for r in rows]}

    def generate_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["timestamp", "value", "quality", "unit"])
        for r in rows:
            writer.writerow([r["ts"].isoformat() if r["ts"] else "", r["value"], r["quality"], r["unit"] or ""])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    filename = f"{tag_name}_{start.date()}_{end.date()}.csv".replace(" ", "_")
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
