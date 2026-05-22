"""
Industrial Operations Cloud — Alarm Engine
DB-driven threshold evaluation with deadband, cooldown suppression, and threshold caching.
Tags without configured thresholds produce NO alarms (fail-safe).
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import asyncpg
import structlog

from app.config import settings
from app.models import AlarmSeverity, TelemetryPoint, TagQuality

from app.core.redis_keys import threshold_cache_key, alarm_cooldown_key

log = structlog.get_logger("historian.alarms")


# ── Threshold cache (in-memory, unused — Redis is the primary cache) ─────────
_threshold_cache: Dict[Tuple[str, str, str], dict] = {}
_cooldown_tracker: Dict[Tuple[str, str, str, str], float] = {}


async def _get_thresholds(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    tag_name: str,
) -> Optional[dict]:
    """Fetch alarm thresholds from DB (cached in Redis for ALARM_CACHE_TTL seconds).
    Returns None if tag has no thresholds configured — no alarm evaluation occurs."""
    import json
    from app.telemetry.stream_writer import redis_client

    key = threshold_cache_key(tenant_id, plant_id, tag_name)

    if redis_client:
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)

    row = await conn.fetchrow(
        """
        SELECT low_low_limit, low_limit, high_limit, high_high_limit,
               deadband, engineering_unit
        FROM tag_metadata
        WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 AND is_active=true
        """,
        tenant_id,
        plant_id,
        tag_name,
    )

    if row:
        data = dict(row)
        if redis_client:
            await redis_client.set(key, json.dumps(data), ex=settings.ALARM_CACHE_TTL)
        return data

    # No DB thresholds configured — log a debug-level warning, return None (fail-safe)
    log.debug("alarm.no_thresholds", tenant_id=tenant_id, plant_id=plant_id, tag_name=tag_name)
    return None


async def _check_cooldown(tenant_id: str, plant_id: str, tag_name: str, severity: str) -> bool:
    """Returns True if alarm can fire (cooldown expired). False = suppressed."""
    from app.telemetry.stream_writer import redis_client

    if not redis_client:
        return True

    cd_key = alarm_cooldown_key(tenant_id, plant_id, tag_name, severity)
    is_set = await redis_client.set(cd_key, "1", ex=settings.ALARM_COOLDOWN_SECONDS, nx=True)
    return bool(is_set)


async def evaluate_alarms_for_batch(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    points: List[TelemetryPoint],
) -> List[dict]:
    """
    Evaluate alarm thresholds against a batch of points.
    Returns list of alarm dicts ready for DB insert.
    Implements HiHi/Hi/Lo/LoLo with deadband and cooldown suppression.
    """
    alarms: List[dict] = []

    for pt in points:
        if pt.quality != TagQuality.GOOD:
            continue

        thresholds = await _get_thresholds(conn, tenant_id, plant_id, pt.tag_name)
        if not thresholds:
            continue

        deadband = thresholds.get("deadband", 0) or 0
        val = pt.value
        checks = []

        hh = thresholds.get("high_high_limit")
        if hh is not None and val >= (hh - deadband):
            checks.append((AlarmSeverity.CRITICAL, f"HiHi alarm: {pt.tag_name}={val:.2f} >= {hh}"))

        h = thresholds.get("high_limit")
        if h is not None and val >= (h - deadband) and not checks:
            checks.append((AlarmSeverity.ALARM, f"Hi alarm: {pt.tag_name}={val:.2f} >= {h}"))

        ll = thresholds.get("low_low_limit")
        if ll is not None and val <= (ll + deadband):
            checks.append((AlarmSeverity.CRITICAL, f"LoLo alarm: {pt.tag_name}={val:.2f} <= {ll}"))

        lo = thresholds.get("low_limit")
        if lo is not None and val <= (lo + deadband) and not checks:
            checks.append((AlarmSeverity.ALARM, f"Lo alarm: {pt.tag_name}={val:.2f} <= {lo}"))

        for severity, message in checks:
            if await _check_cooldown(tenant_id, plant_id, pt.tag_name, severity.value):
                occurred_at = pt.timestamp or datetime.now(timezone.utc)
                alarm_id_str = f"{tenant_id}:{plant_id}:{pt.tag_name}:{severity.value}:{occurred_at.isoformat()}"
                alarm_id = str(uuid.uuid5(uuid.NAMESPACE_OID, alarm_id_str))
                alarms.append(
                    {
                        "alarm_id": alarm_id,
                        "tenant_id": tenant_id,
                        "plant_id": plant_id,
                        "tag_name": pt.tag_name,
                        "severity": severity.value,
                        "message": message,
                        "trigger_value": round(val, 4),
                        "occurred_at": occurred_at,
                    }
                )

    return alarms


async def insert_alarms(conn: asyncpg.Connection, alarms: List[dict]) -> None:
    """Batch-insert alarms into the alarms table."""
    if not alarms:
        return
    await conn.executemany(
        """
        INSERT INTO alarms
            (alarm_id, tenant_id, plant_id, tag_name, severity,
             message, trigger_value, occurred_at, alarm_state)
        VALUES ($1::uuid,$2,$3,$4,$5,$6,$7,$8,'ACTIVE')
        ON CONFLICT (alarm_id, occurred_at) DO NOTHING
        """,
        [
            (
                a["alarm_id"],
                a["tenant_id"],
                a["plant_id"],
                a["tag_name"],
                a["severity"],
                a["message"],
                a["trigger_value"],
                a["occurred_at"],
            )
            for a in alarms
        ],
    )


async def evict_threshold_cache(tenant_id: str, plant_id: str, tag_name: str):
    """Remove a single tag's threshold from cache (called on metadata update)."""
    from app.telemetry.stream_writer import redis_client

    if redis_client:
        key = threshold_cache_key(tenant_id, plant_id, tag_name)
        await redis_client.delete(key)
