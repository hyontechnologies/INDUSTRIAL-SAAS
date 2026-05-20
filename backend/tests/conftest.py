"""
Piccadily Industrial Historian — Test Fixtures
"""

import pytest
import asyncio
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import UserContext


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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


@pytest.fixture
def client():
    return TestClient(app)
