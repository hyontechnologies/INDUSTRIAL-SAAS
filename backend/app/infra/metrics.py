"""
Piccadily Industrial Historian — Ingestion Metrics & Rate Limiter
In-memory counters for Prometheus exposition + per-tenant rate limiting.
"""

import time
from collections import defaultdict
from typing import Dict


class RateLimiter:
    """Sliding-window counter — per-tenant points-per-minute enforcement."""

    def __init__(self, limit: int):
        self._limit = limit

    async def check(self, tenant_id: str, count: int) -> bool:
        """Returns True if request is within limit, False if it exceeds."""
        from app.infra.redis import get_redis

        if not get_redis():
            return True  # Fallback if redis is not ready

        window_seconds = 60
        now_bucket = int(time.monotonic()) // window_seconds
        key = f"ratelimit:{tenant_id}:{now_bucket}"

        # We need to increment by `count`, not just 1, since the user uploads batches of points.
        current_count = await get_redis().incrby(key, count)
        if current_count == count:  # First time creating the key
            await get_redis().expire(key, window_seconds * 2)

        return current_count <= self._limit

    async def current(self, tenant_id: str) -> int:
        from app.infra.redis import get_redis

        if not get_redis():
            return 0
        window_seconds = 60
        now_bucket = int(time.monotonic()) // window_seconds
        key = f"ratelimit:{tenant_id}:{now_bucket}"
        val = await get_redis().get(key)
        return int(val) if val else 0


class IngestionMetrics:
    """Prometheus-compatible ingestion counters."""

    def __init__(self):
        self.points_total: int = 0
        self.batches_total: int = 0
        self.alarms_total: int = 0
        self.errors_total: int = 0
        self.redis_batches_processed: int = 0
        self.redis_messages_processed: int = 0
        self.started_at: float = time.monotonic()
        self._tenant_counts: Dict[str, int] = defaultdict(int)

    @property
    def uptime_seconds(self) -> float:
        return round(time.monotonic() - self.started_at, 1)

    def record_batch(self, tenant_id: str, points: int, alarms: int):
        self.points_total += points
        self.batches_total += 1
        self.alarms_total += alarms
        self._tenant_counts[tenant_id] += points

    def prometheus_text(self) -> str:
        from app.realtime.broadcaster import ws_manager

        lines = [
            "# HELP historian_points_total Total telemetry points ingested",
            "# TYPE historian_points_total counter",
            f"historian_points_total {self.points_total}",
            "# HELP historian_batches_total Total ingestion batches received",
            "# TYPE historian_batches_total counter",
            f"historian_batches_total {self.batches_total}",
            "# HELP historian_alarms_total Total alarms generated",
            "# TYPE historian_alarms_total counter",
            f"historian_alarms_total {self.alarms_total}",
            "# HELP historian_errors_total Total unhandled errors",
            "# TYPE historian_errors_total counter",
            f"historian_errors_total {self.errors_total}",
            "# HELP historian_ws_connections Current WebSocket connections",
            "# TYPE historian_ws_connections gauge",
            f"historian_ws_connections {ws_manager.connection_count}",
            "# HELP historian_redis_batches_processed Total Redis stream batches processed",
            "# TYPE historian_redis_batches_processed counter",
            f"historian_redis_batches_processed {self.redis_batches_processed}",
            "# HELP historian_redis_messages_processed Total Redis stream messages processed",
            "# TYPE historian_redis_messages_processed counter",
            f"historian_redis_messages_processed {self.redis_messages_processed}",
            "# HELP historian_uptime_seconds Application uptime in seconds",
            "# TYPE historian_uptime_seconds counter",
            f"historian_uptime_seconds {self.uptime_seconds}",
        ]
        for tid, cnt in self._tenant_counts.items():
            lines += [
                f'historian_tenant_points_total{{tenant="{tid}"}} {cnt}',
            ]
        return "\n".join(lines) + "\n"


# Singleton instances
from app.config import settings  # noqa: E402

metrics = IngestionMetrics()
rate_limiter = RateLimiter(settings.RATE_LIMIT_POINTS_PER_MIN)
