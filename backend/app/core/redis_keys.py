"""
Industrial Operations Cloud — Centralized Redis Key Registry

All Redis key patterns in one place. No more magic strings scattered across modules.
"""


def stream_key(tenant_id: str, plant_id: str) -> str:
    """Redis stream key for telemetry ingestion pipeline."""
    from app.config import settings

    return f"{settings.REDIS_STREAM_PREFIX}{tenant_id}:{plant_id}"


def threshold_cache_key(tenant_id: str, plant_id: str, tag_name: str) -> str:
    """Alarm threshold cache."""
    return f"threshold:cache:{tenant_id}:{plant_id}:{tag_name}"


def alarm_cooldown_key(tenant_id: str, plant_id: str, tag_name: str, severity: str) -> str:
    """Per-tag alarm cooldown to prevent alarm storms."""
    return f"alarm:cooldown:{tenant_id}:{plant_id}:{tag_name}:{severity}"


def rate_limit_key(tenant_id: str, bucket: int) -> str:
    """Sliding-window rate limiter bucket."""
    return f"ratelimit:{tenant_id}:{bucket}"


def session_revoke_key(session_id: str) -> str:
    """Revoked session marker."""
    return f"revoked:session:{session_id}"


def ws_ticket_key(ticket: str) -> str:
    """Short-lived WebSocket auth ticket."""
    return f"ws:ticket:{ticket}"


def ws_broadcast_channel(tenant_id: str, plant_id: str) -> str:
    """Redis Pub/Sub channel for cross-worker WS broadcast.
    Uses pipe separator to avoid conflicts with tenant/plant IDs containing colons.
    """
    return f"ws|broadcast|{tenant_id}|{plant_id}"


def active_streams_cache_key() -> str:
    """Cache key for the set of currently active Redis streams."""
    return "meta:active_streams"


# Consumer group names — single source of truth
CONSUMER_GROUP_WRITERS = "historian-writers"
CONSUMER_GROUP_ALARMS = "historian-alarms"
