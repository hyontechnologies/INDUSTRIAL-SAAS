"""
Piccadily Industrial Historian — Ingestion Pipeline Tests
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.telemetry.ingestion import ingest_telemetry_batch
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
        patch("app.telemetry.ingestion.rate_limiter.check", return_value=True),
        patch("app.telemetry.ingestion.publish_batch_to_stream") as mock_publish,
    ):
        res = await ingest_telemetry_batch(mock_db_conn, batch, mock_user)
        assert res["inserted"] == 1
        assert res["status"] == "buffered_to_stream"

        # Verify publish was called
        mock_publish.assert_called_once_with("piccadily", "BOILER_PLC_01", batch.points)


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
