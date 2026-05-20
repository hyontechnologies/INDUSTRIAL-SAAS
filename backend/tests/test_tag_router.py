"""
Piccadily Industrial Historian v4.0 — Tag Router Unit Tests
Verifies all tag routing rules across 14 groups + catch-all.
"""

import pytest

from app.tag_router import (
    CATCH_ALL_TABLE,
    VALID_HYPERTABLES,
    clear_cache,
    get_table_for_group,
    route_batch,
    route_tag,
)


@pytest.fixture(autouse=True)
def _clear_routing_cache():
    """Ensure clean cache between tests."""
    clear_cache()
    yield
    clear_cache()


# ── Temperature routing ─────────────────────────────────────────────────────────


class TestTemperatureRouting:
    def test_tt_prefix(self):
        assert route_tag("TT-201") == "telemetry_temperature"
        assert route_tag("TT-202") == "telemetry_temperature"

    def test_te_dash_prefix(self):
        assert route_tag("TE-101") == "telemetry_temperature"
        assert route_tag("TE-308") == "telemetry_temperature"

    def test_te_underscore_prefix(self):
        assert route_tag("TE_FURN") == "telemetry_temperature"
        assert route_tag("TE_MS_OUTLET") == "telemetry_temperature"


# ── Pressure routing ────────────────────────────────────────────────────────────


class TestPressureRouting:
    def test_pt_prefix(self):
        assert route_tag("PT-201") == "telemetry_pressure"
        assert route_tag("PT-202") == "telemetry_pressure"
        assert route_tag("PT-203") == "telemetry_pressure"
        assert route_tag("PT-001") == "telemetry_pressure"

    def test_pt_underscore(self):
        assert route_tag("PT_DEAERATOR") == "telemetry_pressure"


# ── Level routing ───────────────────────────────────────────────────────────────


class TestLevelRouting:
    def test_lt_prefix(self):
        assert route_tag("LT-201") == "telemetry_level"
        assert route_tag("LT-202") == "telemetry_level"
        assert route_tag("LT-001") == "telemetry_level"

    def test_lt_underscore(self):
        assert route_tag("LT_DEAERATOR") == "telemetry_level"

    def test_lvl_prefix(self):
        assert route_tag("LVL_AVG") == "telemetry_level"

    def test_steam_drum_level_exact(self):
        assert route_tag("STEAM_DRUM_LEVEL_AVERAGE") == "telemetry_level"


# ── Draught routing ─────────────────────────────────────────────────────────────


class TestDraughtRouting:
    def test_dt_prefix(self):
        assert route_tag("DT-401") == "telemetry_draught"
        assert route_tag("DT-301") == "telemetry_draught"

    def test_dt_underscore(self):
        assert route_tag("DT_FURNACE") == "telemetry_draught"


# ── Flow routing ────────────────────────────────────────────────────────────────


class TestFlowRouting:
    def test_totalizer_before_flow(self):
        """Totalizer tags must route to flow_totalizer, not flow."""
        assert route_tag("TOTALIZER_FEED_WATER_CURRENT_8_HRS") == "telemetry_flow_totalizer"
        assert route_tag("TOTALIZER_MAIN_STEAM_CURRENT_8_HRS") == "telemetry_flow_totalizer"

    def test_ft_prefix(self):
        assert route_tag("FT-101") == "telemetry_flow"
        assert route_tag("FT_MAIN_STEAM") == "telemetry_flow"


# ── Motor RPM routing ──────────────────────────────────────────────────────────


class TestMotorRpmRouting:
    def test_specific_rpm_tags(self):
        assert route_tag("ID_RPM") == "telemetry_motor_rpm"
        assert route_tag("FD_RPM") == "telemetry_motor_rpm"
        assert route_tag("SF1_RPM") == "telemetry_motor_rpm"
        assert route_tag("SF2_RPM") == "telemetry_motor_rpm"
        assert route_tag("TG_RPM") == "telemetry_motor_rpm"
        assert route_tag("DE1_RPM") == "telemetry_motor_rpm"
        assert route_tag("FP1_RPM") == "telemetry_motor_rpm"

    def test_drm_fdr_rpm(self):
        assert route_tag("DRM_FDR_RPM") == "telemetry_motor_rpm"


# ── Motor Current routing ──────────────────────────────────────────────────────


class TestMotorCurrentRouting:
    def test_amp_suffix(self):
        assert route_tag("SF1_AMP") == "telemetry_motor_current"
        assert route_tag("ID_AMP") == "telemetry_motor_current"

    def test_current_suffix(self):
        assert route_tag("FD_CURRENT") == "telemetry_motor_current"


# ── ESP Electrical routing ──────────────────────────────────────────────────────


class TestEspRouting:
    def test_trcc_prefix(self):
        assert route_tag("TRCC1_VOLT") == "telemetry_esp_electrical"
        assert route_tag("TRCC2_VOLT") == "telemetry_esp_electrical"
        assert route_tag("TRCC3_VOLT") == "telemetry_esp_electrical"

    def test_esp_prefix(self):
        assert route_tag("ESP_FIELD_1") == "telemetry_esp_electrical"


# ── Control Valve routing ───────────────────────────────────────────────────────


class TestControlValveRouting:
    def test_valve_prefixes(self):
        assert route_tag("FCV_001") == "telemetry_control_valve"
        assert route_tag("TCV_001") == "telemetry_control_valve"
        assert route_tag("LCV_001") == "telemetry_control_valve"
        assert route_tag("PCV_001") == "telemetry_control_valve"

    def test_valve_dash(self):
        assert route_tag("FCV-001") == "telemetry_control_valve"


# ── Digital Status routing ──────────────────────────────────────────────────────


class TestDigitalStatusRouting:
    def test_run_suffix(self):
        assert route_tag("FD_FAN_RUN") == "telemetry_digital_status"

    def test_trip_suffix(self):
        assert route_tag("ID_FAN_TRIP") == "telemetry_digital_status"

    def test_interlock(self):
        assert route_tag("INTLK_FLAME") == "telemetry_digital_status"


# ── Performance routing ────────────────────────────────────────────────────────


class TestPerformanceRouting:
    def test_efficiency(self):
        assert route_tag("BOILER_EFF") == "telemetry_performance"

    def test_steam_quality(self):
        assert route_tag("STEAM_QUALITY") == "telemetry_performance"


# ── Vibration routing ──────────────────────────────────────────────────────────


class TestVibrationRouting:
    def test_vib_prefix(self):
        assert route_tag("VIB_BEARING_DE") == "telemetry_vibration"
        assert route_tag("VIB-001") == "telemetry_vibration"


# ── Power Metering routing ─────────────────────────────────────────────────────


class TestPowerMeteringRouting:
    def test_power_tags(self):
        assert route_tag("PWR_TOTAL") == "telemetry_power_metering"
        assert route_tag("KWH_TOTAL") == "telemetry_power_metering"
        assert route_tag("KW_DEMAND") == "telemetry_power_metering"


# ── Catch-all routing ──────────────────────────────────────────────────────────


class TestCatchAllRouting:
    def test_unknown_tag(self):
        assert route_tag("RANDOM_UNKNOWN_TAG") == CATCH_ALL_TABLE

    def test_empty_like_tag(self):
        assert route_tag("X") == CATCH_ALL_TABLE


# ── Batch routing ──────────────────────────────────────────────────────────────


class TestBatchRouting:
    def test_batch_groups_correctly(self):
        tags = ["TT-201", "PT-201", "LT-001", "ID_RPM", "RANDOM_TAG"]
        result = route_batch(tags)

        assert "TT-201" in result["telemetry_temperature"]
        assert "PT-201" in result["telemetry_pressure"]
        assert "LT-001" in result["telemetry_level"]
        assert "ID_RPM" in result["telemetry_motor_rpm"]
        assert "RANDOM_TAG" in result[CATCH_ALL_TABLE]

    def test_batch_preserves_all_tags(self):
        tags = ["TT-201", "TT-202", "PT-201"]
        result = route_batch(tags)
        total = sum(len(v) for v in result.values())
        assert total == len(tags)


# ── Helper functions ───────────────────────────────────────────────────────────


class TestHelpers:
    def test_get_table_for_valid_group(self):
        assert get_table_for_group("temperature") == "telemetry_temperature"
        assert get_table_for_group("pressure") == "telemetry_pressure"
        assert get_table_for_group("motor_rpm") == "telemetry_motor_rpm"

    def test_get_table_for_invalid_group(self):
        assert get_table_for_group("nonexistent") == CATCH_ALL_TABLE

    def test_valid_hypertables_count(self):
        """Must have exactly 15 valid hypertable names (14 groups + raw)."""
        assert len(VALID_HYPERTABLES) == 15

    def test_cache_clear(self):
        route_tag("TT-201")  # populate cache
        clear_cache()
        # Should still work after cache clear
        assert route_tag("TT-201") == "telemetry_temperature"
