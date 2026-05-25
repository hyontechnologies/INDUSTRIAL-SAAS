"""
Piccadily Industrial Historian — Test Fixtures
"""

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import UserContext


# Removed event_loop fixture to use pytest-asyncio default session loop


@pytest.fixture
def mock_db_conn():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.executemany = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def mock_user():
    return UserContext(
        user_id="test-user-uuid", tenant_id="piccadily", email="test@piccadily.com", role="admin", is_edge=False
    )


from app.infra.database import get_read_pool


@pytest.fixture
def mock_pool(mock_db_conn):
    pool = AsyncMock()

    # Mock async with pool.acquire() as conn:
    import contextlib

    @contextlib.asynccontextmanager
    async def mock_acquire():
        yield mock_db_conn

    pool.acquire = mock_acquire
    return pool


@pytest.fixture
def client(mock_pool):
    import contextlib

    @contextlib.asynccontextmanager
    async def mock_lifespan(app):
        yield

    app.router.lifespan_context = mock_lifespan

    app.dependency_overrides[get_read_pool] = lambda: mock_pool
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
