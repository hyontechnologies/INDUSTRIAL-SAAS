"""
Piccadily Industrial Historian — Database Pool Factory
asyncpg pool with JSONB codec, statement timeout, and exponential backoff retry.
"""

import asyncio
import json
from typing import AsyncGenerator, Optional

import asyncpg
import structlog

from app.config import settings

log = structlog.get_logger("historian.database")

_read_pool: Optional[asyncpg.Pool] = None
_write_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register JSONB codec and set statement timeout on every new connection."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.execute("SET statement_timeout = '25s'")


async def create_pools() -> None:
    """Create separate read and write pools with exponential backoff retry."""
    global _read_pool, _write_pool
    delay = settings.DB_CONNECT_RETRY_DELAY
    for attempt in range(1, settings.DB_CONNECT_RETRIES + 1):
        try:
            _read_pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=settings.DB_POOL_MIN,
                max_size=settings.DB_POOL_MAX,
                max_inactive_connection_lifetime=settings.DB_POOL_MAX_INACTIVE,
                command_timeout=settings.DB_COMMAND_TIMEOUT,
                init=_init_connection,
            )
            # Write pool gets dedicated connections for ingestion workers
            _write_pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=2,
                max_size=10,
                max_inactive_connection_lifetime=settings.DB_POOL_MAX_INACTIVE,
                command_timeout=settings.DB_COMMAND_TIMEOUT,
                init=_init_connection,
            )
            log.info("db.pools_created", attempt=attempt)
            return
        except Exception as exc:
            log.warning("db.connect_failed", attempt=attempt, max=settings.DB_CONNECT_RETRIES, error=str(exc))
            if attempt == settings.DB_CONNECT_RETRIES:
                raise
            await asyncio.sleep(min(delay, 30.0))
            delay *= 2


def get_read_pool() -> asyncpg.Pool:
    if _read_pool is None:
        raise RuntimeError("Database pools not initialized. Call create_pools() first.")
    return _read_pool


def get_write_pool() -> asyncpg.Pool:
    if _write_pool is None:
        raise RuntimeError("Database pools not initialized. Call create_pools() first.")
    return _write_pool


from app.identity.auth import get_current_user
from app.models import UserContext
from fastapi import Depends


async def get_db(user: UserContext = Depends(get_current_user)) -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency — yields a connection from the pool with RLS tenant set."""
    async with get_read_pool().acquire() as conn:
        await conn.execute("SELECT set_config('app.current_tenant', $1, false)", user.tenant_id)
        try:
            yield conn
        finally:
            await conn.execute("RESET app.current_tenant")


async def close_pools() -> None:
    """Gracefully close the pools."""
    global _read_pool, _write_pool
    if _read_pool:
        await _read_pool.close()
        _read_pool = None
    if _write_pool:
        await _write_pool.close()
        _write_pool = None
    log.info("db.pools_closed")
