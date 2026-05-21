"""
Piccadily Industrial Historian — Alarm Engine
DB-driven threshold evaluation with deadband, cooldown suppression, and threshold caching.
Background alarm sweep for periodic checking against telemetry_latest.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import asyncpg
import structlog

from .config import settings
from .models import AlarmSeverity, TelemetryPoint, TagQuality

log = structlog.get_logger("historian.alarms")


# ── Threshold cache ─────────────────────────────────────────────────────────────
# {(tenant_id, plant_id, tag_name): {"high_limit": ..., "ts": ...}}
_threshold_cache: Dict[Tuple[str, str, str], dict] = {}

# ── Cooldown tracker (in-memory) ────────────────────────────────────────────────
# {(tenant_id, plant_id, tag_name, severity): last_alarm_epoch}
_cooldown_tracker: Dict[Tuple[str, str, str, str], float] = {}

# ── Fallback thresholds (when DB has no metadata for a tag) ─────────────────────
_FALLBACK_THRESHOLDS: Dict[str, dict] = {
    # Temperature tags
    "TE_FURN": {"low_limit": 450, "high_limit": 950, "high_high_limit": 1050, "deadband": 10.0},
    "TE_MS_OUTLET": {"low_limit": 300, "high_limit": 520, "high_high_limit": 560, "deadband": 5.0},
    "TE_SH_OUTLET": {"low_limit": 300, "high_limit": 520, "high_high_limit": 560, "deadband": 5.0},
    # Pressure tags
    "PT_DRUM": {"low_limit": 20, "high_limit": 52, "high_high_limit": 58, "deadband": 1.0},
    "PT_MS_HDR": {"low_limit": 15, "high_limit": 48, "high_high_limit": 55, "deadband": 1.0},
    "PT_FW": {"low_limit": 25, "high_limit": 55, "high_high_limit": 60, "deadband": 1.0},
    # Level tags
    "LT_DRUM": {"low_limit": -80, "low_low_limit": -120, "high_limit": 80, "high_high_limit": 120, "deadband": 5.0},
    "LT_DEAER": {"low_limit": 30, "high_limit": 90, "high_high_limit": 95, "deadband": 3.0},
    # Flow tags
    "FT_MS_FLOW": {"high_limit": 38, "high_high_limit": 42, "deadband": 1.0},
    "FT_FW_FLOW": {"high_limit": 40, "high_high_limit": 45, "deadband": 1.0},
}


async def _get_thresholds(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    tag_name: str,
) -> Optional[dict]:
    """Fetch alarm thresholds from DB (cached for ALARM_CACHE_TTL seconds)."""
    import json
    from .stream_writer import redis_client

    key = f"threshold:cache:{tenant_id}:{plant_id}:{tag_name}"

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

    # Fallback from hardcoded map
    fb = _FALLBACK_THRESHOLDS.get(tag_name)
    if fb:
        if redis_client:
            await redis_client.set(key, json.dumps(fb), ex=settings.ALARM_CACHE_TTL)
        return fb
    return None


async def _check_cooldown(tenant_id: str, plant_id: str, tag_name: str, severity: str) -> bool:
    """Returns True if alarm can fire (cooldown expired). False = suppressed."""
    from .stream_writer import redis_client

    if not redis_client:
        return True

    cooldown_key = f"alarm:cooldown:{tenant_id}:{plant_id}:{tag_name}:{severity}"
    is_set = await redis_client.set(cooldown_key, "1", ex=settings.ALARM_COOLDOWN_SECONDS, nx=True)
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
    from .stream_writer import redis_client

    if redis_client:
        key = f"threshold:cache:{tenant_id}:{plant_id}:{tag_name}"
        await redis_client.delete(key)
