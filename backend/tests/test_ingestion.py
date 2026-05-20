"""
Piccadily Industrial Historian — Ingestion Pipeline Tests
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.ingestion import ingest_telemetry_batch
from app.models import TelemetryBatch, TelemetryPoint, TagQuality


@pytest.mark.asyncio
async def test_ingest_telemetry_batch_success(mock_db_conn, mock_user):
    batch = TelemetryBatch(
        tenant_id="piccadily",
        plant_id="BOILER_PLC_01",
        points=[
            TelemetryPoint(
                tag_name="TT-201", value=450.5, quality=TagQuality.GOOD, timestamp=datetime.now(timezone.utc), unit="°C"
            )
        ],
    )

    with (
        patch("app.ingestion.rate_limiter.check", return_value=True),
        patch("app.ingestion.evaluate_alarms_for_batch", return_value=[]),
        patch("app.ingestion.insert_alarms", return_value=None),
    ):
        res = await ingest_telemetry_batch(mock_db_conn, batch, mock_user)
        assert res["inserted"] == 1
        assert res["alarms"] == 0

        # Verify copy was called
        mock_db_conn.copy_records_to_table.assert_called_once()
        # Verify latest was upserted
        mock_db_conn.executemany.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_telemetry_tenant_mismatch(mock_db_conn, mock_user):
    from fastapi import HTTPException

    batch = TelemetryBatch(
        tenant_id="other_tenant",
        plant_id="BOILER_PLC_01",
        points=[
            TelemetryPoint(
                tag_name="TT-201", value=450.5, quality=TagQuality.GOOD, timestamp=datetime.now(timezone.utc), unit="°C"
            )
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await ingest_telemetry_batch(mock_db_conn, batch, mock_user)
    assert exc.value.status_code == 403
