import pytest
from app.stream_writer import get_stream_key


def test_stream_key_generation():
    key = get_stream_key("piccadily", "BOILER_PLC_01")
    assert key == "telemetry:piccadily:BOILER_PLC_01"


def test_stream_key_invalid():
    with pytest.raises(Exception):
        get_stream_key("", "")
