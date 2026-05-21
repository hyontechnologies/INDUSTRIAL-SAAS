import pytest
from app.tag_router import TagRouter


class MockConn:
    async def fetch(self, query, tenant_id):
        return []


@pytest.mark.asyncio
async def test_tag_router_temperature():
    router = TagRouter()
    conn = MockConn()
    hypertable = await router.route_tag(conn, "test_tenant", "TT-201", "temperature")
    assert hypertable == "telemetry_temperature"


@pytest.mark.asyncio
async def test_tag_router_pressure():
    router = TagRouter()
    conn = MockConn()
    hypertable = await router.route_tag(conn, "test_tenant", "PT-201", "pressure")
    assert hypertable == "telemetry_pressure"


@pytest.mark.asyncio
async def test_tag_router_raw_fallback():
    router = TagRouter()
    conn = MockConn()
    hypertable = await router.route_tag(conn, "test_tenant", "UNKNOWN-100", None)
    assert hypertable == "telemetry_raw"


@pytest.mark.asyncio
async def test_tag_router_level():
    router = TagRouter()
    conn = MockConn()
    hypertable = await router.route_tag(conn, "test_tenant", "LT-201", "level")
    assert hypertable == "telemetry_level"
