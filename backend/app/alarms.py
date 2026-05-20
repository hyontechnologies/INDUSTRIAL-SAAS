"""
Piccadily Industrial Historian — Alarm Engine
DB-driven threshold evaluation with deadband, cooldown suppression, and threshold caching.
Background alarm sweep for periodic checking against telemetry_latest.
"""

import asyncio
import uuid
from collections import defaultdict
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
    import time

    key = (tenant_id, plant_id, tag_name)
    cached = _threshold_cache.get(key)
    if cached and (time.time() - cached["_fetched_at"]) < settings.ALARM_CACHE_TTL:
        return cached

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
        data["_fetched_at"] = time.time()
        _threshold_cache[key] = data
        return data

    # Fallback from hardcoded map
    fb = _FALLBACK_THRESHOLDS.get(tag_name)
    if fb:
        result = {**fb, "_fetched_at": time.time()}
        _threshold_cache[key] = result
        return result
    return None


def _check_cooldown(tenant_id: str, plant_id: str, tag_name: str, severity: str) -> bool:
    """Returns True if alarm can fire (cooldown expired). False = suppressed."""
    import time

    key = (tenant_id, plant_id, tag_name, severity)
    last = _cooldown_tracker.get(key, 0)
    if time.time() - last < settings.ALARM_COOLDOWN_SECONDS:
        return False
    _cooldown_tracker[key] = time.time()
    return True


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
            if _check_cooldown(tenant_id, plant_id, pt.tag_name, severity.value):
                alarms.append(
                    {
                        "alarm_id": str(uuid.uuid4()),
                        "tenant_id": tenant_id,
                        "plant_id": plant_id,
                        "tag_name": pt.tag_name,
                        "severity": severity.value,
                        "message": message,
                        "trigger_value": round(val, 4),
                        "occurred_at": pt.timestamp or datetime.now(timezone.utc),
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


async def alarm_sweep_loop() -> None:
    """
    Background task: sweeps telemetry_latest against tag_metadata thresholds.
    v3.0 BUGFIX: groups synthetic points from rows directly.
    """
    from .database import get_pool

    await asyncio.sleep(12)  # Give pool time to initialize
    log.info("alarm_sweep.started", interval=settings.ALARM_SWEEP_INTERVAL)

    while True:
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT l.tenant_id, l.plant_id, l.tag_name, l.value, l.quality,
                           l.ts, l.unit
                    FROM telemetry_latest l
                    JOIN tag_metadata m
                      ON l.tenant_id=m.tenant_id
                     AND l.plant_id=m.plant_id
                     AND l.tag_name=m.tag_name
                    WHERE m.is_active=true
                      AND (m.high_limit IS NOT NULL OR m.low_limit IS NOT NULL)
                    """
                )

                groups: Dict[Tuple[str, str], List[TelemetryPoint]] = defaultdict(list)
                for r in rows:
                    try:
                        pt = TelemetryPoint(
                            tag_name=r["tag_name"],
                            value=r["value"],
                            quality=TagQuality(r["quality"]),
                            timestamp=r["ts"],
                            unit=r["unit"],
                        )
                        groups[(r["tenant_id"], r["plant_id"])].append(pt)
                    except Exception:
                        pass  # skip malformed rows

                all_alarms: List[dict] = []
                for (tid, pid), pts in groups.items():
                    sweep_alarms = await evaluate_alarms_for_batch(conn, tid, pid, pts)
                    all_alarms.extend(sweep_alarms)

                if all_alarms:
                    await insert_alarms(conn, all_alarms)
                    log.info("alarm_sweep.alarms_fired", count=len(all_alarms))

        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("alarm_sweep.error", error=str(exc))

        await asyncio.sleep(settings.ALARM_SWEEP_INTERVAL)


def evict_threshold_cache(tenant_id: str, plant_id: str, tag_name: str):
    """Remove a single tag's threshold from cache (called on metadata update)."""
    _threshold_cache.pop((tenant_id, plant_id, tag_name), None)
