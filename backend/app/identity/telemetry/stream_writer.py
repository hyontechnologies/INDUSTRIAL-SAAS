"""
Piccadily Industrial Historian v4.0 — Redis Stream Publisher
Writes incoming telemetry batches to a Redis Stream for asynchronous processing.
"""

from typing import List

import structlog

from app.config import settings
from app.models import TelemetryPoint

log = structlog.get_logger("historian.stream_writer")

from app.infra.redis import get_redis


def get_stream_key(tenant_id: str, plant_id: str) -> str:
    """Get the Redis stream key for a given tenant and plant."""
    if not tenant_id or not plant_id:
        raise ValueError("tenant_id and plant_id cannot be empty")
    return f"telemetry:{tenant_id}:{plant_id}"


async def publish_batch_to_stream(
    tenant_id: str,
    plant_id: str,
    points: List[TelemetryPoint],
) -> None:
    """
    Publish a batch of telemetry points to the Redis Stream.
    Uses pipelining for maximum throughput.
    """
    if not get_redis():
        log.error("redis.not_initialized")
        raise RuntimeError("Redis client not initialized")

    stream_key = f"{settings.REDIS_STREAM_PREFIX}{tenant_id}:{plant_id}"

    # Use a pipeline to batch XADD commands
    pipe = get_redis().pipeline(transaction=False)

    for point in points:
        # Serialize the point payload (flattened for stream hash)
        payload = {
            "tenant_id": tenant_id,
            "plant_id": plant_id,
            "tag_name": point.tag_name,
            "value": str(point.value),
            "quality": point.quality.value,
            "ts": point.timestamp.isoformat() if point.timestamp else "",
        }

        # Add optional fields only if present
        if point.bool_value is not None:
            payload["bool_value"] = str(point.bool_value)
        if point.unit:
            payload["unit"] = point.unit
        if point.source_id:
            payload["source_id"] = point.source_id

        # XADD key * field value [field value ...] MAXLEN ~ N
        pipe.xadd(name=stream_key, fields=payload, maxlen=settings.REDIS_STREAM_MAXLEN, approximate=True)

    # Execute all XADDs in one network round trip
    results = await pipe.execute()
    log.debug("redis.stream_published", count=len(points), stream=stream_key)
