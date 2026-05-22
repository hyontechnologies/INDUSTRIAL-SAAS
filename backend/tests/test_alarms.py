"""
Piccadily Industrial Historian — Alarm Engine Tests
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.alarms.engine import evaluate_alarms_for_batch
from app.models import TelemetryPoint, TagQuality, AlarmSeverity


@pytest.mark.asyncio
async def test_evaluate_alarms_high_high(mock_db_conn):
    # High limit is 480, high_high is 520 in our seeds.
    # We pass TT-201 with value 530 (exceeds high-high limit).
    points = [
        TelemetryPoint(
            tag_name="TT-201", value=530.0, quality=TagQuality.GOOD, timestamp=datetime.now(timezone.utc), unit="°C"
        )
    ]

    mock_db_conn.fetchrow = AsyncMock(
        return_value={
            "low_low_limit": 100.0,
            "low_limit": 150.0,
            "high_limit": 480.0,
            "high_high_limit": 520.0,
            "deadband": 2.0,
            "engineering_unit": "°C",
        }
    )

    with patch("app.alarms.engine._check_cooldown", return_value=True):
        alarms = await evaluate_alarms_for_batch(mock_db_conn, "piccadily", "BOILER_PLC_01", points)
        assert len(alarms) == 1
        assert alarms[0]["severity"] == AlarmSeverity.CRITICAL.value
        assert "HiHi" in alarms[0]["message"]
