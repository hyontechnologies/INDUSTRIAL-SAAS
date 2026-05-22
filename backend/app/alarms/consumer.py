"""
Piccadily Industrial Historian v4.0 — Redis Alarm Consumer
Reads telemetry from Redis Streams and evaluates DB-driven alarm thresholds.
Operates on a separate consumer group from the DB writers.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any

import structlog

from .config import settings
from app.infra.database import get_write_pool
from app.telemetry.stream_writer import redis_client
from .models import TelemetryPoint, TagQuality
from app.alarms.engine import evaluate_alarms_for_batch, insert_alarms

log = structlog.get_logger("historian.alarm_consumer")

ALARM_CONSUMER_GROUP = "historian-alarms"


async def setup_alarm_consumer_group(stream_key: str):
    """Ensure the alarm consumer group exists for a stream."""
    try:
        await redis_client.xgroup_create(
            name=stream_key,
            groupname=ALARM_CONSUMER_GROUP,
            id="$",  # Start from newest messages
            mkstream=True,
        )
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            log.error("redis.alarm_group_error", error=str(e), stream=stream_key)


async def get_active_streams() -> List[str]:
    """Scan Redis for all telemetry streams."""
    streams = []
    pattern = f"{settings.REDIS_STREAM_PREFIX}*"
    async for key in redis_client.scan_iter(match=pattern):
        streams.append(key)
    return streams


async def process_alarms(batch_data: List[Dict[str, Any]]):
    """Convert stream dicts to TelemetryPoints and evaluate alarms."""
    if not batch_data:
        return

    # Group by tenant and plant
    groups = {}

    for row in batch_data:
        tenant_id = row["tenant_id"]
        plant_id = row["plant_id"]
        key = (tenant_id, plant_id)

        if key not in groups:
            groups[key] = []

        try:
            val = float(row["value"])
            ts_str = row.get("ts")
            ts = datetime.fromisoformat(ts_str) if ts_str else None
            quality = TagQuality(row.get("quality", "GOOD"))

            pt = TelemetryPoint(
                tag_name=row["tag_name"], value=val, quality=quality, timestamp=ts, unit=row.get("unit")
            )
            groups[key].append(pt)
        except (ValueError, TypeError):
            continue

    pool = get_write_pool()
    async with pool.acquire() as conn:
        all_alarms = []
        for (tid, pid), pts in groups.items():
            sweep_alarms = await evaluate_alarms_for_batch(conn, tid, pid, pts)
            all_alarms.extend(sweep_alarms)

        if all_alarms:
            await insert_alarms(conn, all_alarms)
            log.info("alarm_sweep.alarms_fired", count=len(all_alarms))


async def alarm_consumer_worker(worker_id: int):
    """
    Background worker that reads from Redis Streams and evaluates alarms.
    Runs completely decoupled from the TimescaleDB writer workers.
    """
    log.info("alarm_worker.started", worker_id=worker_id, group=ALARM_CONSUMER_GROUP)
    consumer_name = f"alarm-worker-{worker_id}"

    await asyncio.sleep(3)

    while True:
        try:
            streams = await get_active_streams()
            if not streams:
                await asyncio.sleep(5)
                continue

            for s in streams:
                await setup_alarm_consumer_group(s)

            streams_dict = {s: ">" for s in streams}

            messages = await redis_client.xreadgroup(
                groupname=ALARM_CONSUMER_GROUP,
                consumername=consumer_name,
                streams=streams_dict,
                count=settings.REDIS_CONSUMER_BATCH_SIZE,
                block=settings.REDIS_BLOCK_MS,
            )

            if not messages:
                continue

            for stream_name, stream_messages in messages:
                if not stream_messages:
                    continue

                batch_data = [msg_data for _, msg_data in stream_messages]
                msg_ids = [msg_id for msg_id, _ in stream_messages]

                try:
                    await process_alarms(batch_data)
                    await redis_client.xack(stream_name, ALARM_CONSUMER_GROUP, *msg_ids)
                except Exception as e:
                    log.error("alarm_worker.process_failed", error=str(e), stream=stream_name)

        except asyncio.CancelledError:
            log.info("alarm_worker.cancelled", worker_id=worker_id)
            break
        except Exception as e:
            log.error("alarm_worker.loop_error", error=str(e))
            await asyncio.sleep(2)
