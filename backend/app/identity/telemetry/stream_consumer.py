"""
Piccadily Industrial Historian v4.0 — Redis Stream Consumer (TimescaleDB Writer)
Reads telemetry from Redis Streams and bulk-inserts into per-group hypertables.
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Tuple

import asyncpg
import structlog

from app.config import settings
from app.infra.database import get_write_pool
from app.infra.redis import get_redis
from app.telemetry.tag_router import route_tag

log = structlog.get_logger("historian.stream_consumer")

CONSUMER_GROUP = "historian-writers"


async def setup_consumer_group(stream_key: str):
    """Ensure the consumer group exists for a stream."""
    try:
        await get_redis().xgroup_create(
            name=stream_key,
            groupname=CONSUMER_GROUP,
            id="$",  # Start from newest messages
            mkstream=True,
        )
        log.info("redis.consumer_group_created", stream=stream_key, group=CONSUMER_GROUP)
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass  # Group already exists
        else:
            log.error("redis.consumer_group_error", error=str(e), stream=stream_key)


async def get_active_streams() -> List[str]:
    """Scan Redis for all telemetry streams (e.g. tele:*)."""
    # In production with thousands of streams, use SCAN.
    # For a single plant with one tenant, KEYS is fine, but we'll use scan_iter.
    streams = []
    pattern = f"{settings.REDIS_STREAM_PREFIX}*"
    async for key in get_redis().scan_iter(match=pattern):
        streams.append(key)
    return streams


async def write_to_timescaledb(pool: asyncpg.Pool, batches: List[Dict[str, Any]]):
    """
    Route and bulk insert a mixed batch of telemetry points.
    1. Groups by target hypertable.
    2. Uses COPY for fast bulk inserts.
    3. Upserts telemetry_latest.
    """
    if not batches:
        return

    # Group by tenant_id first for RLS boundaries
    tenant_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in batches:
        tenant_groups[row["tenant_id"]].append(row)

    for tenant_id, tenant_batches in tenant_groups.items():
        table_groups: Dict[str, List[Tuple]] = defaultdict(list)
        latest_updates: Dict[Tuple[str, str, str], Tuple] = {}

        for row in tenant_batches:
            plant_id = row["plant_id"]
            tag_name = row["tag_name"]
            target_table = await route_tag(pool, tenant_id, tag_name)

            try:
                val = float(row["value"])
                ts = datetime.fromisoformat(row["ts"]) if row.get("ts") else datetime.utcnow()
            except (ValueError, TypeError):
                continue

            bool_val = row.get("bool_value")
            if bool_val is not None:
                bool_val = bool_val.lower() in ("true", "1", "yes")

            quality = row.get("quality", "GOOD")
            unit = row.get("unit")
            source_id = row.get("source_id")

            db_row = (ts, tenant_id, plant_id, tag_name, val, bool_val, quality, unit, source_id)
            table_groups[target_table].append(db_row)

            key = (tenant_id, plant_id, tag_name)
            existing = latest_updates.get(key)
            if not existing or existing[0] < ts:
                latest_updates[key] = (ts, tenant_id, plant_id, tag_name, val, bool_val, quality, unit)

        async with pool.acquire() as conn:
            await conn.execute("SELECT set_config('app.current_tenant', $1, false)", tenant_id)
            try:
                async with conn.transaction():
                    for table_name, rows in table_groups.items():
                        try:
                            await conn.copy_records_to_table(
                                table_name,
                                records=rows,
                                columns=[
                                    "ts",
                                    "tenant_id",
                                    "plant_id",
                                    "tag_name",
                                    "value",
                                    "bool_value",
                                    "quality",
                                    "unit",
                                    "source_id",
                                ],
                            )
                        except Exception as e:
                            log.error("db.copy_error", table=table_name, error=str(e), count=len(rows))
                            raise

                    if latest_updates:
                        latest_rows = list(latest_updates.values())
                        insert_vals = [(r[1], r[2], r[3], r[4], r[5], r[6], r[0], r[7]) for r in latest_rows]
                        await conn.executemany(
                            """
                            INSERT INTO telemetry_latest
                                (tenant_id, plant_id, tag_name, value, bool_value, quality, ts, unit)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (tenant_id, plant_id, tag_name)
                            DO UPDATE SET
                                value = EXCLUDED.value,
                                bool_value = EXCLUDED.bool_value,
                                quality = EXCLUDED.quality,
                                ts = EXCLUDED.ts,
                                unit = EXCLUDED.unit
                            """,
                            insert_vals,
                        )
            finally:
                await conn.execute("RESET app.current_tenant")

    log.debug("db.batch_written", total_points=len(batches))


async def stream_consumer_worker(worker_id: int):
    """
    Background worker that reads from Redis Streams and writes to TimescaleDB.
    """
    log.info("worker.started", worker_id=worker_id, group=CONSUMER_GROUP)
    consumer_name = f"writer-{worker_id}"

    # Wait for pool to initialize
    await asyncio.sleep(2)
    pool = get_write_pool()

    # --- PEL Recovery on Startup ---
    try:
        streams = await get_active_streams()
        for s in streams:
            await setup_consumer_group(s)

        if streams:
            log.info("worker.pel_recovery_start", worker_id=worker_id)
            streams_dict_0 = {s: "0" for s in streams}
            while True:
                messages = await get_redis().xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams=streams_dict_0,
                    count=settings.REDIS_CONSUMER_BATCH_SIZE,
                    block=None,
                )
                if not messages:
                    break

                has_pending = False
                for stream_name, stream_messages in messages:
                    if not stream_messages:
                        continue
                    has_pending = True
                    batch_data = [msg_data for _, msg_data in stream_messages]
                    msg_ids = [msg_id for msg_id, _ in stream_messages]
                    try:
                        await write_to_timescaledb(pool, batch_data)
                        await get_redis().xack(stream_name, CONSUMER_GROUP, *msg_ids)
                        log.info("worker.pel_recovered", stream=stream_name, count=len(msg_ids))
                    except Exception as e:
                        log.error("worker.pel_write_failed", error=str(e), stream=stream_name)

                if not has_pending:
                    break
            log.info("worker.pel_recovery_complete", worker_id=worker_id)
    except Exception as e:
        log.error("worker.pel_recovery_error", error=str(e))
    # -------------------------------

    while True:
        try:
            streams = await get_active_streams()
            if not streams:
                await asyncio.sleep(5)
                continue

            # Ensure groups exist
            for s in streams:
                await setup_consumer_group(s)

            # Read from all streams
            # Format: { stream_name: ">" } (">" means read un-ACKed new messages for this consumer)
            streams_dict = {s: ">" for s in streams}

            # XREADGROUP GROUP group consumer STREAMS stream1 stream2 > >
            messages = await get_redis().xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=consumer_name,
                streams=streams_dict,
                count=settings.REDIS_CONSUMER_BATCH_SIZE,
                block=settings.REDIS_BLOCK_MS,
            )

            if not messages:
                continue

            # Process messages
            for stream_name, stream_messages in messages:
                if not stream_messages:
                    continue

                # stream_messages is a list of tuples: (message_id, data_dict)
                batch_data = [msg_data for _, msg_data in stream_messages]
                msg_ids = [msg_id for msg_id, _ in stream_messages]

                try:
                    await write_to_timescaledb(pool, batch_data)
                    # ACK successful inserts
                    await get_redis().xack(stream_name, CONSUMER_GROUP, *msg_ids)
                except Exception as e:
                    log.error("worker.write_failed", error=str(e), stream=stream_name, count=len(msg_ids))
                    # Messages remain pending (un-ACKed) and can be claimed by other workers

        except asyncio.CancelledError:
            log.info("worker.cancelled", worker_id=worker_id)
            break
        except Exception as e:
            log.error("worker.loop_error", error=str(e))
            await asyncio.sleep(2)
