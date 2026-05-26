"""
Industrial Operations Cloud — Tag Router v4.1
Maps tag_name prefixes/patterns → target hypertable name dynamically using tag_routing_rules.
Features: LRU-bounded exact match cache, TTL-based tenant rules cache.
"""

import re
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import structlog

log = structlog.get_logger("historian.tag_router")

# ── Configuration ────────────────────────────────────────────────────────────

MAX_EXACT_CACHE_SIZE = 10_000  # LRU eviction threshold
TENANT_RULES_TTL_SECONDS = 300  # 5 minutes

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

# ── LRU Cache for exact tag→table matches ────────────────────────────────────

_EXACT_MATCH: OrderedDict[Tuple[str, str], str] = OrderedDict()

# ── Tenant rules with TTL ────────────────────────────────────────────────────
# {tenant_id: (loaded_at_epoch, rules_list)}
_TENANT_RULES: Dict[str, Tuple[float, List[Tuple[Any, str, str]]]] = {}

# ── Cache metrics ────────────────────────────────────────────────────────────
_cache_hits = 0
_cache_misses = 0


def _lru_put(key: Tuple[str, str], value: str) -> None:
    """Insert into LRU cache with eviction."""
    global _EXACT_MATCH
    if key in _EXACT_MATCH:
        _EXACT_MATCH.move_to_end(key)
        _EXACT_MATCH[key] = value
    else:
        _EXACT_MATCH[key] = value
        if len(_EXACT_MATCH) > MAX_EXACT_CACHE_SIZE:
            _EXACT_MATCH.popitem(last=False)


def _lru_get(key: Tuple[str, str]) -> Optional[str]:
    """Get from LRU cache, promoting to end."""
    global _cache_hits, _cache_misses
    if key in _EXACT_MATCH:
        _EXACT_MATCH.move_to_end(key)
        _cache_hits += 1
        return _EXACT_MATCH[key]
    _cache_misses += 1
    return None


async def _load_rules(conn_or_pool, tenant_id: str) -> List[Tuple[Any, str, str]]:
    """Load routing rules from DB and cache with TTL."""
    rows = await conn_or_pool.fetch(
        "SELECT pattern, pattern_type, target_table FROM tag_routing_rules WHERE tenant_id=$1 ORDER BY priority DESC",
        tenant_id,
    )
    parsed_rules: List[Tuple[Any, str, str]] = []
    for r in rows:
        pattern = r["pattern"]
        ptype = r["pattern_type"]
        table = r["target_table"]
        if ptype == "regex":
            try:
                compiled = re.compile(pattern)
                parsed_rules.append((compiled, ptype, table))
            except re.error:
                log.warning("tag_router.invalid_regex", pattern=pattern, tenant_id=tenant_id)
                continue
        else:
            parsed_rules.append((pattern, ptype, table))

    _TENANT_RULES[tenant_id] = (time.monotonic(), parsed_rules)
    log.info("tag_router.rules_loaded", tenant_id=tenant_id, rule_count=len(parsed_rules))
    return parsed_rules


def _get_cached_rules(tenant_id: str) -> Optional[List[Tuple[Any, str, str]]]:
    """Get tenant rules if cached and not expired."""
    entry = _TENANT_RULES.get(tenant_id)
    if entry is None:
        return None
    loaded_at, rules = entry
    if (time.monotonic() - loaded_at) > TENANT_RULES_TTL_SECONDS:
        del _TENANT_RULES[tenant_id]
        return None
    return rules


async def route_tag(conn_or_pool, tenant_id: str, tag_name: str) -> str:
    """Route a tag to the appropriate hypertable.

    Uses a 2-tier cache:
    1. Exact match LRU cache (bounded, O(1) lookup)
    2. Tenant rules cache with TTL (reloaded from DB on expiry)
    """
    cache_key = (tenant_id, tag_name)
    cached = _lru_get(cache_key)
    if cached is not None:
        return cached

    rules = _get_cached_rules(tenant_id)
    if rules is None:
        rules = await _load_rules(conn_or_pool, tenant_id)

    for matcher, ptype, table in rules:
        if ptype == "prefix" and tag_name.startswith(matcher):
            _lru_put(cache_key, table)
            return table
        elif ptype == "suffix" and tag_name.endswith(matcher):
            _lru_put(cache_key, table)
            return table
        elif ptype == "regex" and matcher.search(tag_name):
            _lru_put(cache_key, table)
            return table

    _lru_put(cache_key, CATCH_ALL_TABLE)
    return CATCH_ALL_TABLE


def get_table_for_group(group_name: str) -> str:
    """Map a tag group name to a hypertable."""
    if group_name in VALID_HYPERTABLES:
        return group_name
    table = f"telemetry_{group_name}"
    if table in VALID_HYPERTABLES:
        return table
    return CATCH_ALL_TABLE


def clear_cache() -> None:
    """Clear all caches (used in tests and on rule updates)."""
    _EXACT_MATCH.clear()
    _TENANT_RULES.clear()


def get_cache_stats() -> dict:
    """Return cache statistics for observability."""
    return {
        "exact_cache_size": len(_EXACT_MATCH),
        "tenant_rules_cached": len(_TENANT_RULES),
        "cache_hits": _cache_hits,
        "cache_misses": _cache_misses,
    }


class TagRouter:
    """Object-oriented wrapper for tag routing (used by routers)."""

    async def route_tag(self, conn_or_pool, tenant_id: str, tag_name: str, group: str | None = None) -> str:
        if group:
            table = get_table_for_group(group)
            if table != CATCH_ALL_TABLE:
                return table
        return await route_tag(conn_or_pool, tenant_id, tag_name)
