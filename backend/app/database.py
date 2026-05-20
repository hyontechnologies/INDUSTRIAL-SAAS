"""
Piccadily Industrial Historian — Database Pool Factory
asyncpg pool with JSONB codec, statement timeout, and exponential backoff retry.
"""

import asyncio
import json
from typing import AsyncGenerator, Optional

import asyncpg
import structlog

from .config import settings

log = structlog.get_logger("historian.database")

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register JSONB codec and set statement timeout on every new connection."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.execute("SET statement_timeout = '25s'")


async def create_pool() -> asyncpg.Pool:
    """Create pool with exponential backoff retry (handles Docker startup race)."""
    global _pool
    delay = settings.DB_CONNECT_RETRY_DELAY
    for attempt in range(1, settings.DB_CONNECT_RETRIES + 1):
        try:
            pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=settings.DB_POOL_MIN,
                max_size=settings.DB_POOL_MAX,
                max_inactive_connection_lifetime=settings.DB_POOL_MAX_INACTIVE,
                command_timeout=settings.DB_COMMAND_TIMEOUT,
                init=_init_connection,
            )
            log.info("db.pool_created", attempt=attempt)
            _pool = pool
            return pool
        except Exception as exc:
            log.warning("db.connect_failed", attempt=attempt, max=settings.DB_CONNECT_RETRIES, error=str(exc))
            if attempt == settings.DB_CONNECT_RETRIES:
                raise
            await asyncio.sleep(min(delay, 30.0))
            delay *= 2


def get_pool() -> asyncpg.Pool:
    """Return the current pool instance. Raises if pool not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call create_pool() first.")
    return _pool


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency — yields a connection from the pool."""
    async with get_pool().acquire() as conn:
        yield conn


async def close_pool() -> None:
    """Gracefully close the pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        log.info("db.pool_closed")
