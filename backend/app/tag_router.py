"""
Piccadily Industrial Historian v4.0 — Tag Router
Maps tag_name prefixes/patterns → target hypertable name dynamically using tag_routing_rules.
"""

import re
from typing import Dict, List, Tuple, Any

# Cache for loaded rules: tenant_id -> list of (compiled_regex_or_str, pattern_type, target_table)
_TENANT_RULES: Dict[str, List[Tuple[Any, str, str]]] = {}

# Fast lookup cache: (tenant_id, tag_name) -> target_table
_EXACT_MATCH: Dict[Tuple[str, str], str] = {}

CATCH_ALL_TABLE = "telemetry_raw"

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


async def _load_rules(conn_or_pool, tenant_id: str):
    rows = await conn_or_pool.fetch(
        "SELECT pattern, pattern_type, target_table FROM tag_routing_rules WHERE tenant_id=$1 ORDER BY priority DESC",
        tenant_id,
    )
    parsed_rules = []
    for r in rows:
        pattern = r["pattern"]
        ptype = r["pattern_type"]
        table = r["target_table"]
        if ptype == "regex":
            try:
                compiled = re.compile(pattern)
                parsed_rules.append((compiled, ptype, table))
            except re.error:
                continue
        else:
            # prefix or suffix
            parsed_rules.append((pattern, ptype, table))
    _TENANT_RULES[tenant_id] = parsed_rules


async def route_tag(conn_or_pool, tenant_id: str, tag_name: str) -> str:
    cache_key = (tenant_id, tag_name)
    cached = _EXACT_MATCH.get(cache_key)
    if cached is not None:
        return cached

    if tenant_id not in _TENANT_RULES:
        await _load_rules(conn_or_pool, tenant_id)

    rules = _TENANT_RULES.get(tenant_id, [])

    for matcher, ptype, table in rules:
        if ptype == "prefix" and tag_name.startswith(matcher):
            _EXACT_MATCH[cache_key] = table
            return table
        elif ptype == "suffix" and tag_name.endswith(matcher):
            _EXACT_MATCH[cache_key] = table
            return table
        elif ptype == "regex" and matcher.search(tag_name):
            _EXACT_MATCH[cache_key] = table
            return table

    _EXACT_MATCH[cache_key] = CATCH_ALL_TABLE
    return CATCH_ALL_TABLE


def get_table_for_group(group_name: str) -> str:
    if group_name in VALID_HYPERTABLES:
        return group_name
    table = f"telemetry_{group_name}"
    if table in VALID_HYPERTABLES:
        return table
    return CATCH_ALL_TABLE


def clear_cache() -> None:
    _EXACT_MATCH.clear()
    _TENANT_RULES.clear()


class TagRouter:
    async def route_tag(self, conn_or_pool, tenant_id: str, tag_name: str, group: str | None = None) -> str:
        if group:
            table = get_table_for_group(group)
            if table != CATCH_ALL_TABLE:
                return table
        return await route_tag(conn_or_pool, tenant_id, tag_name)
