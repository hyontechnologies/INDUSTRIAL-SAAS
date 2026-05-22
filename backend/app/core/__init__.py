"""
Industrial Operations Cloud — Core Package

Cross-cutting concerns: exceptions, pagination, Redis key registry, observability.
"""

from .exceptions import DomainException
from .pagination import PaginatedResponse, PaginationParams, build_paginated_response
from .redis_keys import (
    CONSUMER_GROUP_ALARMS,
    CONSUMER_GROUP_WRITERS,
    active_streams_cache_key,
    alarm_cooldown_key,
    rate_limit_key,
    session_revoke_key,
    stream_key,
    threshold_cache_key,
    ws_broadcast_channel,
    ws_ticket_key,
)

__all__ = [
    "DomainException",
    "PaginatedResponse",
    "PaginationParams",
    "build_paginated_response",
    "CONSUMER_GROUP_ALARMS",
    "CONSUMER_GROUP_WRITERS",
    "active_streams_cache_key",
    "alarm_cooldown_key",
    "rate_limit_key",
    "session_revoke_key",
    "stream_key",
    "threshold_cache_key",
    "ws_broadcast_channel",
    "ws_ticket_key",
]
