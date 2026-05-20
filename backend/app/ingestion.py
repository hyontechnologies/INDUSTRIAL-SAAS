"""
Piccadily Industrial Historian — Telemetry Ingestion Pipeline
High-throughput ingestion using asyncpg COPY for raw rows + bulk upsert for latest.
"""

import asyncio
from datetime import datetime, timezone
from typing import List

import asyncpg
import structlog
from fastapi import HTTPException

from .alarms import evaluate_alarms_for_batch, insert_alarms
from .broadcaster import ws_manager
from .config import settings
from .metrics import metrics, rate_limiter
from .models import TelemetryBatch, TelemetryPoint, UserContext

log = structlog.get_logger("historian.ingestion")


async def _insert_raw_copy(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    points: List[TelemetryPoint],
) -> None:
    """
    Insert raw telemetry via asyncpg COPY protocol (fastest path).
    Falls back to executemany with ON CONFLICT DO NOTHING if COPY fails.
    """
    rows = [
        (
            tenant_id,
            plant_id,
            pt.tag_name,
            pt.value,
            pt.quality.value,
            pt.timestamp or datetime.now(timezone.utc),
            pt.unit,
            pt.source_id,
        )
        for pt in points
    ]
    try:
        await conn.copy_records_to_table(
            "telemetry_raw",
            records=rows,
            columns=["tenant_id", "plant_id", "tag_name", "value", "quality", "ts", "unit", "source_id"],
        )
    except asyncpg.UniqueViolationError:
        pass  # Tolerate duplicate ts+tag rows
    except Exception as exc:
        log.warning("copy_failed_fallback_to_executemany", error=str(exc))
        await conn.executemany(
            """
            INSERT INTO telemetry_raw
                (tenant_id, plant_id, tag_name, value, quality, ts, unit, source_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT DO NOTHING
            """,
            rows,
        )


async def _upsert_latest(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    points: List[TelemetryPoint],
) -> None:
    """
    Upsert latest value per tag. Only updates when incoming timestamp is newer.
    """
    await conn.executemany(
        """
        INSERT INTO telemetry_latest
            (tenant_id, plant_id, tag_name, value, quality, ts, unit)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT (tenant_id, plant_id, tag_name)
        DO UPDATE SET
            value   = EXCLUDED.value,
            quality = EXCLUDED.quality,
            ts      = EXCLUDED.ts,
            unit    = EXCLUDED.unit
        WHERE telemetry_latest.ts < EXCLUDED.ts
        """,
        [
            (
                tenant_id,
                plant_id,
                pt.tag_name,
                pt.value,
                pt.quality.value,
                pt.timestamp or datetime.now(timezone.utc),
                pt.unit,
            )
            for pt in points
        ],
    )


async def ingest_telemetry_batch(
    conn: asyncpg.Connection,
    batch: TelemetryBatch,
    user: UserContext,
) -> dict:
    """
    Main ingestion pipeline (hot path):
      1. Tenant isolation check
      2. Rate-limit check
      3. COPY bulk insert → telemetry_raw
      4. Upsert → telemetry_latest
      5. Alarm evaluation (DB-driven thresholds + cooldown)
      6. Alarm insert
      7. Metrics update
      8. WS broadcast (fire-and-forget asyncio.Task)
    """
    if not batch.points:
        return {"inserted": 0, "alarms": 0}

    # Edge agents carry their tenant in the key; human users must match
    if not user.is_edge and user.tenant_id != batch.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    if not rate_limiter.check(batch.tenant_id, len(batch.points)):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: >{settings.RATE_LIMIT_POINTS_PER_MIN} points/min",
        )

    await _insert_raw_copy(conn, batch.tenant_id, batch.plant_id, batch.points)
    await _upsert_latest(conn, batch.tenant_id, batch.plant_id, batch.points)

    alarms = await evaluate_alarms_for_batch(conn, batch.tenant_id, batch.plant_id, batch.points)
    await insert_alarms(conn, alarms)

    metrics.record_batch(batch.tenant_id, len(batch.points), len(alarms))

    # WebSocket broadcast — never blocks ingestion
    asyncio.create_task(
        ws_manager.broadcast(
            batch.tenant_id,
            batch.plant_id,
            {
                "type": "telemetry",
                "plant_id": batch.plant_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "count": len(batch.points),
                "alarms": len(alarms),
                "data": {
                    pt.tag_name: {
                        "v": pt.value,
                        "q": pt.quality.value,
                        "t": pt.timestamp.isoformat() if pt.timestamp else None,
                    }
                    for pt in batch.points[:50]  # cap payload size
                },
                "alarm_events": [
                    {"tag": a["tag_name"], "severity": a["severity"], "msg": a["message"], "val": a["trigger_value"]}
                    for a in alarms
                ],
            },
        )
    )

    return {"inserted": len(batch.points), "alarms": len(alarms)}
