"""
Redis connection pooling and utilities.
"""

import structlog
from redis.asyncio import Redis

from app.config import settings

log = structlog.get_logger("historian.redis")

# Global Redis client instance
redis_client: Redis = None  # type: ignore


def get_redis() -> Redis:
    return redis_client


async def init_redis_pool():
    """Initialize the global async Redis connection pool."""
    global redis_client
    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )
    await redis_client.ping()
    log.info("redis.pool_initialized", url=settings.REDIS_URL)


async def close_redis_pool():
    """Close the global Redis connection pool."""
    global redis_client
    if redis_client:
        await redis_client.close()
        log.info("redis.pool_closed")
