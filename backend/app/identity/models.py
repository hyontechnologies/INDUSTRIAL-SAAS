"""
Piccadily Industrial Historian — Pydantic Request/Response Schemas
All data models for telemetry, alarms, tags, plants, and API keys.
"""

import math
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class TagQuality(str, Enum):
    GOOD = "GOOD"
    BAD = "BAD"
    UNCERTAIN = "UNCERTAIN"
    STALE = "STALE"


class AlarmSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ALARM = "ALARM"
    CRITICAL = "CRITICAL"


class AlarmState(str, Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED = "CLEARED"


class TelemetryPoint(BaseModel):
    tag_name: str = Field(..., max_length=128)
    value: float
    bool_value: Optional[bool] = None
    quality: TagQuality = TagQuality.GOOD
    timestamp: Optional[datetime] = None  # UTC; None → server now
    unit: Optional[str] = None
    source_id: Optional[str] = None  # OPC UA NodeId string

    @field_validator("value", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            raise ValueError("value must be finite numeric")
        return f

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_ts(cls, v):
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    @field_validator("tag_name")
    @classmethod
    def clean_tag(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tag_name cannot be empty")
        return v


class TelemetryBatch(BaseModel):
    tenant_id: str = Field(..., max_length=64)
    plant_id: str = Field(..., max_length=64)
    points: List[TelemetryPoint] = Field(..., max_length=500)

    @field_validator("points")
    @classmethod
    def deduplicate_points(cls, pts: List[TelemetryPoint]):
        """Keep only the latest point per tag when duplicates exist in one batch."""
        seen: Dict[str, TelemetryPoint] = {}
        for pt in pts:
            existing = seen.get(pt.tag_name)
            if existing is None or (pt.timestamp or datetime.min) > (existing.timestamp or datetime.min):
                seen[pt.tag_name] = pt
        return list(seen.values())


class AlarmAckRequest(BaseModel):
    alarm_id: uuid.UUID
    acked_by: str
    comment: Optional[str] = None


class AlarmClearRequest(BaseModel):
    plant_id: str
    alarm_ids: Optional[List[uuid.UUID]] = None  # None = clear all acked alarms
    cleared_by: str
    comment: Optional[str] = None


class TagMetadataUpdate(BaseModel):
    description: Optional[str] = None
    engineering_unit: Optional[str] = None
    low_low_limit: Optional[float] = None
    low_limit: Optional[float] = None
    high_limit: Optional[float] = None
    high_high_limit: Optional[float] = None
    deadband: Optional[float] = None
    is_active: bool = True
    opc_node_id: Optional[str] = None
    data_type: Optional[str] = None


class PlantCreate(BaseModel):
    plant_id: str = Field(..., max_length=64)
    name: str = Field(..., max_length=128)
    location: Optional[str] = None
    plant_type: str = "generic"
    timezone: str = "UTC"
    config: Optional[dict] = None


class ApiKeyCreate(BaseModel):
    label: str = Field(..., max_length=128, description="Human label e.g. 'Edge-Agent-Boiler-01'")
    tenant_id: str = Field(..., max_length=64)


class UserContext(BaseModel):
    """Authenticated user context — populated by auth middleware."""

    user_id: str
    tenant_id: str
    email: str
    role: str  # admin | engineer | operator | viewer | edge_agent
    is_edge: bool = False
    plant_ids: List[str] = Field(default_factory=list)  # Allowed plant IDs for this user (empty = all for tenant)
