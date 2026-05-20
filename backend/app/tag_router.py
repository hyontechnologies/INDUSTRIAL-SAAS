"""
Piccadily Industrial Historian v4.0 — Tag Router
Maps tag_name prefixes/patterns → target hypertable name.

Each OPC UA tag is routed to the appropriate per-group hypertable based on
its naming convention from the MECGALE SCADA system.

Architecture Decision:
  - Per-group hypertables allow independent compression/retention policies
  - Each group has 5-40 tags — not per-tag tables
  - Unrecognized tags fall through to 'telemetry_raw' catch-all
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# ── Tag Routing Rules ───────────────────────────────────────────────────────────
# Order matters: more specific prefixes must appear before shorter ones.
# Example: "ID_RPM" must match before a hypothetical "ID" prefix.

TAG_ROUTING: List[Tuple[str, str]] = [
    # ── Temperature tags (TE-xxx, TT-xxx) ──────────────────────────────────
    ("TE-", "telemetry_temperature"),
    ("TT-", "telemetry_temperature"),
    ("TE_", "telemetry_temperature"),
    # ── Pressure tags (PT-xxx) ─────────────────────────────────────────────
    ("PT-", "telemetry_pressure"),
    ("PT_", "telemetry_pressure"),
    # ── Level tags (LT-xxx) ───────────────────────────────────────────────
    ("LT-", "telemetry_level"),
    ("LT_", "telemetry_level"),
    ("LVL_", "telemetry_level"),
    ("STEAM_DRUM_LEVEL", "telemetry_level"),
    # ── Draught tags (DT-xxx) ─────────────────────────────────────────────
    ("DT-", "telemetry_draught"),
    ("DT_", "telemetry_draught"),
    # ── Flow totalizer tags (running 8hr totals) ──────────────────────────
    # Must appear before flow tags to avoid "FT" prefix collision
    ("TOTALIZER", "telemetry_flow_totalizer"),
    # ── Flow tags (FT-xxx) ────────────────────────────────────────────────
    ("FT-", "telemetry_flow"),
    ("FT_", "telemetry_flow"),
    # ── Motor RPM tags ────────────────────────────────────────────────────
    ("ID_RPM", "telemetry_motor_rpm"),
    ("FD_RPM", "telemetry_motor_rpm"),
    ("SF1_RPM", "telemetry_motor_rpm"),
    ("SF2_RPM", "telemetry_motor_rpm"),
    ("SF3_RPM", "telemetry_motor_rpm"),
    ("DE1_RPM", "telemetry_motor_rpm"),
    ("DE2_RPM", "telemetry_motor_rpm"),
    ("DE3_RPM", "telemetry_motor_rpm"),
    ("FP1_RPM", "telemetry_motor_rpm"),
    ("FP2_RPM", "telemetry_motor_rpm"),
    ("TG_RPM", "telemetry_motor_rpm"),
    ("DRM_FDR_RPM", "telemetry_motor_rpm"),
    ("GM_", "telemetry_motor_rpm"),
    ("_RPM", "telemetry_motor_rpm"),  # catch-all for any RPM tag
    # ── Motor current tags ────────────────────────────────────────────────
    ("_AMP", "telemetry_motor_current"),
    ("AMP_", "telemetry_motor_current"),
    ("_CURRENT", "telemetry_motor_current"),
    # ── ESP / TRCC electrical tags ────────────────────────────────────────
    ("TRCC", "telemetry_esp_electrical"),
    ("ESP_", "telemetry_esp_electrical"),
    # ── Control valve tags ────────────────────────────────────────────────
    ("FCV_", "telemetry_control_valve"),
    ("FCV-", "telemetry_control_valve"),
    ("TCV_", "telemetry_control_valve"),
    ("TCV-", "telemetry_control_valve"),
    ("LCV_", "telemetry_control_valve"),
    ("LCV-", "telemetry_control_valve"),
    ("PCV_", "telemetry_control_valve"),
    ("PCV-", "telemetry_control_valve"),
    # ── Digital status tags (boolean run/trip/interlock) ──────────────────
    ("_RUN", "telemetry_digital_status"),
    ("_TRIP", "telemetry_digital_status"),
    ("INTLK", "telemetry_digital_status"),
    ("_STATUS", "telemetry_digital_status"),
    # ── Performance / efficiency calculated tags ─────────────────────────
    ("BOILER_EFF", "telemetry_performance"),
    ("STEAM_QUALITY", "telemetry_performance"),
    ("HEAT_RATE", "telemetry_performance"),
    ("EFF_", "telemetry_performance"),
    # ── Vibration tags ───────────────────────────────────────────────────
    ("VIB_", "telemetry_vibration"),
    ("VIB-", "telemetry_vibration"),
    # ── Power metering tags ──────────────────────────────────────────────
    ("PWR_", "telemetry_power_metering"),
    ("KWH", "telemetry_power_metering"),
    ("KW_", "telemetry_power_metering"),
    ("PF_", "telemetry_power_metering"),
]

# Pre-build a dict for exact-match lookups (fastest path)
_EXACT_MATCH: Dict[str, str] = {}

# Known exact tag names that don't follow prefix patterns
_EXACT_OVERRIDES: Dict[str, str] = {
    "STEAM_DRUM_LEVEL_AVERAGE": "telemetry_level",
    "TOTALIZER_FEED_WATER_CURRENT_8_HRS": "telemetry_flow_totalizer",
    "TOTALIZER_MAIN_STEAM_CURRENT_8_HRS": "telemetry_flow_totalizer",
}

# All valid hypertable names (for validation)
VALID_HYPERTABLES = frozenset(
    {
        "telemetry_temperature",
        "telemetry_pressure",
        "telemetry_level",
        "telemetry_draught",
        "telemetry_flow",
        "telemetry_flow_totalizer",
        "telemetry_motor_rpm",
        "telemetry_motor_current",
        "telemetry_esp_electrical",
        "telemetry_control_valve",
        "telemetry_digital_status",
        "telemetry_performance",
        "telemetry_vibration",
        "telemetry_power_metering",
        "telemetry_raw",
    }
)

CATCH_ALL_TABLE = "telemetry_raw"


def route_tag(tag_name: str) -> str:
    """
    Return the target hypertable name for a given tag.

    Routing priority:
      1. Exact override match (e.g. STEAM_DRUM_LEVEL_AVERAGE)
      2. Cached result from previous lookup
      3. Prefix/substring match from TAG_ROUTING rules
      4. Fallback to 'telemetry_raw' catch-all

    Returns:
        str: hypertable name (e.g. 'telemetry_temperature')
    """
    # 1. Exact override
    if tag_name in _EXACT_OVERRIDES:
        return _EXACT_OVERRIDES[tag_name]

    # 2. Cached
    cached = _EXACT_MATCH.get(tag_name)
    if cached is not None:
        return cached

    # 3. Prefix/substring match
    upper = tag_name.upper()
    for pattern, table in TAG_ROUTING:
        if upper.startswith(pattern) or pattern in upper:
            _EXACT_MATCH[tag_name] = table
            return table

    # 4. Catch-all
    _EXACT_MATCH[tag_name] = CATCH_ALL_TABLE
    return CATCH_ALL_TABLE


def route_batch(tag_names: list[str]) -> Dict[str, list[str]]:
    """
    Route a batch of tag names and group them by target hypertable.

    Returns:
        Dict mapping hypertable name → list of tag names routed there.
    """
    result: Dict[str, list[str]] = {}
    for tag in tag_names:
        table = route_tag(tag)
        if table not in result:
            result[table] = []
        result[table].append(tag)
    return result


def get_table_for_group(group_name: str) -> str:
    """
    Convert a tag_group name (from tag_metadata) to the hypertable name.

    Args:
        group_name: e.g. 'temperature', 'pressure', 'motor_rpm'

    Returns:
        Hypertable name e.g. 'telemetry_temperature'
    """
    if group_name in VALID_HYPERTABLES:
        return group_name
    table = f"telemetry_{group_name}"
    if table in VALID_HYPERTABLES:
        return table
    return CATCH_ALL_TABLE


def clear_cache() -> None:
    """Clear the routing cache. Used in tests and after tag metadata updates."""
    _EXACT_MATCH.clear()


class TagRouter:
    """
    Class wrapper for tag routing, matching the interface expected by backend routers.
    """

    def route_tag(self, tag_name: str, group: str | None = None) -> str:
        if group:
            table = get_table_for_group(group)
            if table != CATCH_ALL_TABLE:
                return table
        return route_tag(tag_name)
