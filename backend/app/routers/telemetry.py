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

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..ingestion import ingest_telemetry_batch
from ..models import TelemetryBatch, UserContext

router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@router.post("/ingest", status_code=202)
async def ingest(
    batch: TelemetryBatch,
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Primary high-throughput ingestion endpoint. Edge agent uses X-API-Key."""
    if len(batch.points) > settings.TELEMETRY_BATCH_MAX:
        raise HTTPException(422, f"Batch exceeds max size {settings.TELEMETRY_BATCH_MAX}")
    result = await ingest_telemetry_batch(conn, batch, user)
    return {"ok": True, **result}


@router.get("/latest")
async def get_latest(
    plant_id: str = Query(...),
    tags: Optional[str] = Query(None, description="Comma-separated tag list"),
    user: UserContext = Depends(get_current_user),
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
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Tag history with time-bucket aggregation. Auto-selects raw or continuous aggregate."""
    valid_aggs = {"avg", "min", "max", "last"}
    if agg not in valid_aggs:
        raise HTTPException(422, f"agg must be one of {valid_aggs}")

    if interval == "raw":
        rows = await conn.fetch(
            "SELECT ts, value, quality FROM telemetry_raw "
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
        span_hours = (end - start).total_seconds() / 3600
        source = (
            "telemetry_1min"
            if span_hours <= 6
            else "telemetry_5min"
            if span_hours <= 48
            else "telemetry_1hour"
            if span_hours <= 720
            else "telemetry_1day"
        )
        agg_col = {"avg": "avg_val", "min": "min_val", "max": "max_val", "last": "last_val"}[agg]
        rows = await conn.fetch(
            f"SELECT bucket AS ts, {agg_col} AS value, sample_count "
            f"FROM {source} WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
            f"AND bucket BETWEEN $4 AND $5 ORDER BY bucket DESC LIMIT $6",
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
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Multi-tag trend correlation. Returns pivot format for React charts."""
    tag_list = [t.strip() for t in tags.split(",")][:10]
    agg_col = {"avg": "avg_val", "min": "min_val", "max": "max_val", "last": "last_val"}.get(agg, "avg_val")
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
    rows = await conn.fetch(
        f"SELECT bucket AS ts, tag_name, {agg_col} AS value FROM {source} "
        f"WHERE tenant_id=$1 AND plant_id=$2 AND tag_name = ANY($3) "
        f"AND bucket BETWEEN $4 AND $5 ORDER BY ts, tag_name LIMIT $6",
        user.tenant_id,
        plant_id,
        tag_list,
        start,
        end,
        limit * len(tag_list),
    )
    pivot = {}
    for r in rows:
        ts_str = r["ts"].isoformat()
        pivot.setdefault(ts_str, {"ts": ts_str})
        pivot[ts_str][r["tag_name"]] = r["value"]
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
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Min/max/avg/stddev/count for a tag over the last N hours."""
    row = await conn.fetchrow(
        "SELECT count(*) AS sample_count, round(avg(value)::numeric, 4) AS avg_val, "
        "round(min(value)::numeric, 4) AS min_val, round(max(value)::numeric, 4) AS max_val, "
        "round(stddev(value)::numeric, 4) AS stddev_val, last(value, ts) AS last_val, "
        "max(ts) AS last_ts FROM telemetry_raw "
        "WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
        "AND ts >= now() - ($4 || ' hours')::interval",
        user.tenant_id,
        plant_id,
        tag_name,
        str(hours),
    )
    return {"tag_name": tag_name, "plant_id": plant_id, "hours": hours, "stats": dict(row)}


@router.get("/stale")
async def get_stale_tags(
    plant_id: str = Query(...),
    stale_minutes: int = Query(None, description="Override default stale threshold"),
    user: UserContext = Depends(get_current_user),
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
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Raw data export. Returns CSV (default) or JSON."""
    rows = await conn.fetch(
        "SELECT ts, value, quality, unit FROM telemetry_raw "
        "WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 "
        "AND ts BETWEEN $4 AND $5 ORDER BY ts ASC LIMIT $6",
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
