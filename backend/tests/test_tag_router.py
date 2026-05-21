"""
Piccadily Industrial Historian v4.0 — Tag Router Unit Tests
Verifies dynamic tag routing rules.
"""

import pytest
from app.tag_router import TagRouter, CATCH_ALL_TABLE, clear_cache


class MockConn:
    async def fetch(self, query, tenant_id):
        return [
            {"pattern": "TT-", "pattern_type": "prefix", "target_table": "telemetry_temperature"},
            {"pattern": "^PT_.*", "pattern_type": "regex", "target_table": "telemetry_pressure"},
            {"pattern": "_RPM", "pattern_type": "suffix", "target_table": "telemetry_motor_rpm"},
        ]


@pytest.fixture(autouse=True)
def _clear_routing_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.mark.asyncio
async def test_dynamic_routing():
    router = TagRouter()
    conn = MockConn()

    # Test Prefix
    assert await router.route_tag(conn, "tenant1", "TT-123") == "telemetry_temperature"

    # Test Regex
    assert await router.route_tag(conn, "tenant1", "PT_456_A") == "telemetry_pressure"

    # Test Suffix
    assert await router.route_tag(conn, "tenant1", "PUMP_RPM") == "telemetry_motor_rpm"

    # Test Catch-all
    assert await router.route_tag(conn, "tenant1", "UNKNOWN_TAG") == CATCH_ALL_TABLE

    # Test Group Override
    assert await router.route_tag(conn, "tenant1", "UNKNOWN_TAG", group="pressure") == "telemetry_pressure"
