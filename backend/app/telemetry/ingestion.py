"""
Piccadily Industrial Historian — Telemetry Ingestion Pipeline
High-throughput ingestion using asyncpg COPY for raw rows + bulk upsert for latest.
"""

import asyncio
from datetime import datetime, timezone

import asyncpg
import structlog
from fastapi import HTTPException

from app.telemetry.stream_writer import publish_batch_to_stream
from app.models import TelemetryBatch, UserContext
from app.config import settings
from app.infra.metrics import metrics, rate_limiter
from app.realtime.broadcaster import ws_manager

log = structlog.get_logger("historian.ingestion")


async def ingest_telemetry_batch(
    conn: asyncpg.Connection,  # Kept for signature compatibility if needed, though unused now
    batch: TelemetryBatch,
    user: UserContext,
) -> dict:
    """
    Main ingestion pipeline (hot path) - v4.0 Redis Streams:
      1. Tenant isolation check
      2. Rate-limit check
      3. XADD to Redis Stream (fire-and-forget async pipeline)
      4. Metrics update
      5. WS broadcast (fire-and-forget asyncio.Task)
    """
    if not batch.points:
        return {"inserted": 0, "alarms": 0}

    # Edge agents carry their tenant in the key; human users must match
    if not user.is_edge and user.tenant_id != batch.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    if not await rate_limiter.check(batch.tenant_id, len(batch.points)):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: >{settings.RATE_LIMIT_POINTS_PER_MIN} points/min",
        )

    # 3. Publish to Redis Stream for asynchronous workers
    await publish_batch_to_stream(batch.tenant_id, batch.plant_id, batch.points)

    # Note: Alarms are now evaluated by the alarm consumer asynchronously.
    # The response here just indicates points accepted into the buffer.
    metrics.record_batch(batch.tenant_id, len(batch.points), 0)

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
                "alarms": 0,  # Evaluated async now
                "data": {
                    pt.tag_name: {
                        "v": pt.value,
                        "q": pt.quality.value,
                        "t": pt.timestamp.isoformat() if pt.timestamp else None,
                    }
                    for pt in batch.points[:50]  # cap payload size
                },
                "alarm_events": [],  # Emitted by alarm consumer now
            },
        )
    )

    return {"inserted": len(batch.points), "status": "buffered_to_stream"}
