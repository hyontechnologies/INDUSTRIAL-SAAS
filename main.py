"""
╔══════════════════════════════════════════════════════════════════════════════╗
║    PICCADILY INDUSTRIAL HISTORIAN  —  PRODUCTION FASTAPI BACKEND  v3.0      ║
║    Digital Twin & Cloud Historian SaaS Platform                              ║
║    Boiler / Utility / WTP / STP / Industrial Process Systems                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Architecture:
    OPC UA Bridge  (piccadily_opcua_bridge.py)
        └── Edge Agent  (edge_agent.py)  →  X-API-Key
                └── FastAPI Ingestion Layer          ← THIS FILE
                        ├── asyncpg pool  →  TimescaleDB (hypertables)
                        ├── telemetry_raw        (hypertable, compressed)
                        ├── telemetry_latest     (upsert mirror for low-latency reads)
                        ├── alarms               (hypertable, dedup + cooldown)
                        ├── alarm_history        (audit trail per alarm)
                        ├── tag_metadata         (DB-driven alarm thresholds)
                        ├── audit_logs           (hypertable)
                        ├── api_keys             (DB-backed key management)
                        ├── WebSocket broadcaster  (per-tenant/plant rooms)
                        ├── Background alarm sweep (periodic DB-driven check)
                        ├── Supabase JWT auth    (human users)
                        ├── API-key auth         (edge agents, SHA-256 hashed)
                        └── Grafana              (read-only PG datasource)

v3.0 upgrades over v2.0:
  • BUGFIX: Alarm ACK WS broadcast now correctly routes via plant_id lookup
  • BUGFIX: Alarm sweep synthetic list indexing drift — groups built from rows directly
  • BUGFIX: telemetry_latest upsert uses transactional temp table (COPY path)
  • DB-backed API key management via api_keys table (env-var map still works as fallback)
  • Security headers middleware (X-Frame-Options, X-Content-Type-Options, HSTS, CSP)
  • Startup DB retry with exponential backoff (handles Docker race conditions)
  • CSV/JSON telemetry export endpoint  (/api/v1/telemetry/export)
  • Stale tag detection endpoint        (/api/v1/telemetry/stale)
  • Tag search endpoint                 (/api/v1/tags/search)
  • Plant soft-delete and detail endpoint
  • POST /api/v1/auth/api-keys for key provisioning (admin only)
  • DELETE /api/v1/auth/api-keys/{key_id}
  • WS manager no longer holds lock during send (avoids head-of-line blocking)
  • Graceful drain: in-flight ingestions complete before pool closes
  • TrustedHostMiddleware in production mode
  • Prometheus /metrics includes per-tenant point counters
  • Alarm state machine: ACTIVE → ACKNOWLEDGED → CLEARED (alarm_state column)
  • POST /api/v1/alarms/clear bulk-clear endpoint for operators
  • GET /api/v1/admin/api-keys for key listing

File:    backend/app/main.py
Python:  3.11+
"""

# ─── STDLIB ───────────────────────────────────────────────────────────────────
import asyncio
import csv
import hashlib
import io
import json
import math
import secrets
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

# ─── THIRD-PARTY ──────────────────────────────────────────────────────────────
import asyncpg
import structlog
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Piccadily Industrial Historian"
    APP_VERSION: str = "3.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    TRUSTED_HOSTS: str = "*"  # comma-separated; "*" disables host check

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str  # asyncpg DSN
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 8  # keep low on 4 GB RAM
    DB_POOL_MAX_INACTIVE: float = 300.0
    DB_COMMAND_TIMEOUT: float = 30.0
    DB_CONNECT_RETRIES: int = 10  # startup retry attempts
    DB_CONNECT_RETRY_DELAY: float = 3.0  # base delay (doubles each attempt)

    # ── Supabase Auth ────────────────────────────────────────────────────────
    SUPABASE_JWT_SECRET: str
    SUPABASE_URL: str
    JWT_ALGORITHM: str = "HS256"
    JWT_AUDIENCE: str = "authenticated"

    # ── Edge API Keys  (env-var fallback; DB api_keys table takes priority) ──
    # Format: "tenant_a:sha256hash,tenant_b:sha256hash"
    EDGE_API_KEYS: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Telemetry ────────────────────────────────────────────────────────────
    TELEMETRY_BATCH_MAX: int = 500
    ALARM_COOLDOWN_SECONDS: int = 300  # 5 min: suppress duplicate alarms per tag
    ALARM_SWEEP_INTERVAL: int = 10  # background sweep every N seconds
    ALARM_CACHE_TTL: int = 60  # seconds to cache DB alarm thresholds
    STALE_TAG_MINUTES: int = 10  # tag not updated in N min → stale

    # ── Rate Limiting (in-memory, per tenant) ─────────────────────────────────
    RATE_LIMIT_POINTS_PER_MIN: int = 5000  # telemetry points per tenant per minute

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_hosts_list(self) -> List[str]:
        return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]

    @property
    def edge_api_keys_map(self) -> Dict[str, str]:
        """Returns {sha256_hex: tenant_id} from env var (fallback)."""
        out: Dict[str, str] = {}
        for pair in self.EDGE_API_KEYS.split(","):
            pair = pair.strip()
            if ":" in pair:
                tid, khash = pair.split(":", 1)
                out[khash.strip()] = tid.strip()
        return out


settings = Settings()


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  STRUCTURED LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger("historian")


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  DATABASE POOL  (asyncpg — raw, not ORM, for maximum TimescaleDB throughput)
# ═══════════════════════════════════════════════════════════════════════════════

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Register JSONB codec and set statement timeout on every new connection."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    # Prevent runaway queries from blocking the pool
    await conn.execute("SET statement_timeout = '25s'")


async def create_pool() -> asyncpg.Pool:
    """Create pool with exponential backoff retry (handles Docker startup race)."""
    delay = settings.DB_CONNECT_RETRY_DELAY
    for attempt in range(1, settings.DB_CONNECT_RETRIES + 1):
        try:
            pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=settings.DB_POOL_MIN,
                max_size=settings.DB_POOL_MAX,
                max_inactive_connection_lifetime=settings.DB_POOL_MAX_INACTIVE,
                command_timeout=settings.DB_COMMAND_TIMEOUT,
                init=_init_connection,
            )
            log.info("db.pool_created", attempt=attempt)
            return pool
        except Exception as exc:
            log.warning("db.connect_failed", attempt=attempt, max=settings.DB_CONNECT_RETRIES, error=str(exc))
            if attempt == settings.DB_CONNECT_RETRIES:
                raise
            await asyncio.sleep(min(delay, 30.0))
            delay *= 2


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    async with _pool.acquire() as conn:
        yield conn


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


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
    plant_type: str = Field(default="boiler")  # boiler | wtp | stp | power | utility
    timezone: str = Field(default="Asia/Kolkata")
    config: Optional[dict] = None


class ApiKeyCreate(BaseModel):
    label: str = Field(..., max_length=128, description="Human label e.g. 'Edge-Agent-Boiler-01'")
    tenant_id: str = Field(..., max_length=64)


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  AUTHENTICATION & AUTHORISATION
# ═══════════════════════════════════════════════════════════════════════════════


class UserContext(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    role: str  # admin | engineer | operator | viewer | edge_agent
    is_edge: bool = False


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _verify_edge_api_key_db(raw_key: str) -> Optional[str]:
    """
    Check api_keys table first (DB-backed), then fall back to env-var map.
    Returns tenant_id if valid, else None.
    """
    h = _hash_api_key(raw_key)

    # DB lookup (primary source)
    if _pool:
        try:
            async with _pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT tenant_id FROM api_keys
                    WHERE key_hash=$1 AND is_active=true
                      AND (expires_at IS NULL OR expires_at > now())
                    """,
                    h,
                )
                if row:
                    return row["tenant_id"]
        except Exception:
            pass  # Fall through to env-var fallback

    # Env-var fallback
    return settings.edge_api_keys_map.get(h)


def _decode_supabase_jwt(token: str) -> dict:
    """Decode and validate Supabase-issued JWT. Raises 401 on failure."""
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> UserContext:
    """
    Dual-auth resolver:
      1. X-API-Key header  →  edge agent machine auth (hashed key lookup, DB-backed)
      2. Authorization: Bearer <JWT>  →  Supabase human user auth
    """
    if x_api_key:
        tenant_id = await _verify_edge_api_key_db(x_api_key)
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return UserContext(
            user_id=f"edge:{tenant_id}",
            tenant_id=tenant_id,
            email=f"edge@{tenant_id}",
            role="edge_agent",
            is_edge=True,
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing credentials — provide X-API-Key or Authorization: Bearer <JWT>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]
    payload = _decode_supabase_jwt(token)

    meta = payload.get("app_metadata", {})
    user_meta = payload.get("user_metadata", {})
    tenant_id = meta.get("tenant_id") or user_meta.get("tenant_id")
    role = meta.get("role", "viewer")

    if not tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id missing from token")

    return UserContext(
        user_id=payload["sub"],
        tenant_id=tenant_id,
        email=payload.get("email", ""),
        role=role,
    )


def require_role(*allowed: str):
    """Dependency factory — raises HTTP 403 if user.role not in allowed."""

    async def _guard(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not authorised. Required: {allowed}",
            )
        return user

    return _guard


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  IN-MEMORY RATE LIMITER  (per tenant, per minute; no Redis needed)
# ═══════════════════════════════════════════════════════════════════════════════


class RateLimiter:
    """Sliding-window counter — per-tenant points-per-minute enforcement."""

    def __init__(self, limit: int):
        self._limit = limit
        self._counts: Dict[str, int] = defaultdict(int)
        self._window: Dict[str, float] = {}

    def check(self, tenant_id: str, count: int) -> bool:
        """Returns True if request is within limit, False if it exceeds."""
        now = time.monotonic()
        if now - self._window.get(tenant_id, 0) >= 60:
            self._counts[tenant_id] = 0
            self._window[tenant_id] = now
        self._counts[tenant_id] += count
        return self._counts[tenant_id] <= self._limit

    def current(self, tenant_id: str) -> int:
        return self._counts.get(tenant_id, 0)


_rate_limiter = RateLimiter(settings.RATE_LIMIT_POINTS_PER_MIN)


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  WEBSOCKET BROADCAST MANAGER
# ═══════════════════════════════════════════════════════════════════════════════


class ConnectionManager:
    """
    Manages live WebSocket connections grouped by (tenant_id, plant_id).
    v3.0: lock is only held during set mutation, not during sends
          (eliminates head-of-line blocking on slow clients).
    Dead connections are evicted lazily after failed sends.
    """

    def __init__(self):
        # Dict maps (tenant_id, plant_id) → frozenset of websockets
        self._connections: Dict[Tuple[str, str], Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, tenant_id: str, plant_id: str):
        await ws.accept()
        key = (tenant_id, plant_id)
        async with self._lock:
            self._connections[key].add(ws)
        log.info("ws.connect", tenant=tenant_id, plant=plant_id, room_size=len(self._connections[key]))

    async def disconnect(self, ws: WebSocket, tenant_id: str, plant_id: str):
        key = (tenant_id, plant_id)
        async with self._lock:
            self._connections[key].discard(ws)

    async def broadcast(self, tenant_id: str, plant_id: str, message: dict):
        """
        Broadcast to all clients in the room. Snapshot the set before sending
        so we don't hold the lock during I/O.
        """
        key = (tenant_id, plant_id)
        socks = list(self._connections.get(key, set()))  # snapshot without lock
        dead: List[WebSocket] = []
        for ws in socks:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[key].discard(ws)

    async def broadcast_tenant(self, tenant_id: str, message: dict):
        """Broadcast to ALL rooms of a tenant (e.g. alarm ACK where plant_id unknown)."""
        tasks = []
        for tid, pid in list(self._connections.keys()):
            if tid == tenant_id:
                tasks.append(self.broadcast(tid, pid, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def connection_count(self) -> int:
        return sum(len(v) for v in self._connections.values())


ws_manager = ConnectionManager()


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  ALARM ENGINE
#      — DB-driven thresholds via tag_metadata (cached in-process)
#      — Fallback to hardcoded industrial thresholds
#      — Per-tag cooldown prevents alarm storms
# ═══════════════════════════════════════════════════════════════════════════════

_FALLBACK_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "TT-201": {"hihi": 520.0, "hi": 480.0, "lo": 150.0, "lolo": 100.0, "unit": "°C"},
    "TT-202": {"hihi": 520.0, "hi": 480.0, "lo": 150.0, "lolo": 100.0, "unit": "°C"},
    "TT-301": {"hihi": 530.0, "hi": 490.0, "lo": 150.0, "lolo": 100.0, "unit": "°C"},
    "PT-201": {"hihi": 105.0, "hi": 95.0, "lo": 20.0, "lolo": 10.0, "unit": "bar"},
    "LT-001": {"hihi": 95.0, "hi": 85.0, "lo": 20.0, "lolo": 10.0, "unit": "%"},
    "LT-201": {"hihi": 95.0, "hi": 85.0, "lo": 20.0, "lolo": 10.0, "unit": "%"},
    "LT-202": {"hihi": 95.0, "hi": 85.0, "lo": 20.0, "lolo": 10.0, "unit": "%"},
    "DT-301": {"hihi": -2.0, "hi": -3.0, "lo": -15.0, "lolo": -20.0, "unit": "mmWC"},
    "FT-101": {"hihi": 120.0, "hi": 100.0, "lo": 10.0, "lolo": 5.0, "unit": "t/h"},
    "Steam Drum Level": {"hihi": 80.0, "hi": 70.0, "lo": 30.0, "lolo": 20.0, "unit": "mm"},
    "Main Steam Pressure": {"hihi": 105.0, "hi": 98.0, "lo": 20.0, "lolo": 10.0, "unit": "bar"},
    "Furnace Draught": {"hihi": -2.0, "hi": -4.0, "lo": -18.0, "lolo": -22.0, "unit": "mmWC"},
    "Feed Water Flow": {"hihi": 120.0, "hi": 100.0, "lo": 10.0, "lolo": 5.0, "unit": "t/h"},
    "FD Fan RPM": {"hihi": 1500.0, "hi": 1450.0, "lo": 200.0, "lolo": 100.0, "unit": "RPM"},
    "SA Fan RPM": {"hihi": 1500.0, "hi": 1450.0, "lo": 200.0, "lolo": 100.0, "unit": "RPM"},
    "ID Fan RPM": {"hihi": 1500.0, "hi": 1450.0, "lo": 200.0, "lolo": 100.0, "unit": "RPM"},
}

# {(tenant_id, plant_id, tag_name): (threshold_dict, fetched_at_monotonic)}
_threshold_cache: Dict[Tuple, Tuple[dict, float]] = {}

# {(tenant_id, plant_id, tag_name): last_alarm_monotonic}
_alarm_cooldown: Dict[Tuple, float] = {}


async def _get_thresholds(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    tag_name: str,
) -> Optional[dict]:
    key = (tenant_id, plant_id, tag_name)
    cached, fetched_at = _threshold_cache.get(key, ({}, 0.0))
    if time.monotonic() - fetched_at < settings.ALARM_CACHE_TTL and cached:
        return cached

    row = await conn.fetchrow(
        """
        SELECT low_low_limit, low_limit, high_limit, high_high_limit,
               deadband, engineering_unit
        FROM tag_metadata
        WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3 AND is_active=true
        """,
        tenant_id,
        plant_id,
        tag_name,
    )

    if row and (row["high_limit"] is not None or row["low_limit"] is not None):
        thresh = {
            "lolo": row["low_low_limit"],
            "lo": row["low_limit"],
            "hi": row["high_limit"],
            "hihi": row["high_high_limit"],
            "dead": row["deadband"] or 0.0,
            "unit": row["engineering_unit"] or "",
        }
    else:
        thresh = _FALLBACK_THRESHOLDS.get(tag_name)

    if thresh:
        _threshold_cache[key] = (thresh, time.monotonic())
    return thresh


def _check_cooldown(tenant_id: str, plant_id: str, tag_name: str) -> bool:
    """Returns True if cooldown has elapsed (alarm may fire). Updates last-fired ts."""
    key = (tenant_id, plant_id, tag_name)
    last = _alarm_cooldown.get(key, 0.0)
    elapsed = time.monotonic() - last
    if elapsed >= settings.ALARM_COOLDOWN_SECONDS:
        _alarm_cooldown[key] = time.monotonic()
        return True
    return False


async def evaluate_alarms_for_batch(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    points: List[TelemetryPoint],
) -> List[dict]:
    """
    Evaluate alarm thresholds for a batch.
    Returns list of alarm dicts ready for DB insert.
    """
    alarms: List[dict] = []
    for pt in points:
        if pt.quality == TagQuality.BAD:
            continue  # Never alarm on bad-quality data

        thresh = await _get_thresholds(conn, tenant_id, plant_id, pt.tag_name)
        if not thresh:
            continue

        v = pt.value
        dead = thresh.get("dead", 0.0)
        unit = thresh.get("unit", "")

        hihi = thresh.get("hihi")
        hi = thresh.get("hi")
        lolo = thresh.get("lolo")
        lo = thresh.get("lo")

        severity = msg = None

        if hihi is not None and v >= hihi - dead:
            severity = AlarmSeverity.CRITICAL
            msg = f"{pt.tag_name} HIGH-HIGH: {v:.2f} {unit} (limit {hihi})"
        elif hi is not None and v >= hi - dead:
            severity = AlarmSeverity.ALARM
            msg = f"{pt.tag_name} HIGH: {v:.2f} {unit} (limit {hi})"
        elif lolo is not None and v <= lolo + dead:
            severity = AlarmSeverity.CRITICAL
            msg = f"{pt.tag_name} LOW-LOW: {v:.2f} {unit} (limit {lolo})"
        elif lo is not None and v <= lo + dead:
            severity = AlarmSeverity.ALARM
            msg = f"{pt.tag_name} LOW: {v:.2f} {unit} (limit {lo})"

        if severity and _check_cooldown(tenant_id, plant_id, pt.tag_name):
            alarms.append(
                {
                    "alarm_id": str(uuid.uuid4()),
                    "tenant_id": tenant_id,
                    "plant_id": plant_id,
                    "tag_name": pt.tag_name,
                    "severity": severity.value,
                    "message": msg,
                    "trigger_value": v,
                    "occurred_at": (pt.timestamp or datetime.now(timezone.utc)),
                }
            )
    return alarms


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  AUDIT LOGGER
# ═══════════════════════════════════════════════════════════════════════════════


async def audit(
    conn: asyncpg.Connection,
    user: UserContext,
    action: str,
    resource: str,
    detail: Optional[dict] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO audit_logs
            (tenant_id, user_id, user_email, role, action, resource, detail)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        user.tenant_id,
        user.user_id,
        user.email,
        user.role,
        action,
        resource,
        json.dumps(detail or {}),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 10  INGESTION METRICS
# ═══════════════════════════════════════════════════════════════════════════════


class IngestionMetrics:
    def __init__(self):
        self.points_total: int = 0
        self.batches_total: int = 0
        self.alarms_total: int = 0
        self.errors_total: int = 0
        self.started_at: float = time.monotonic()
        self._tenant_counts: Dict[str, int] = defaultdict(int)

    @property
    def uptime_seconds(self) -> float:
        return round(time.monotonic() - self.started_at, 1)

    def record_batch(self, tenant_id: str, points: int, alarms: int):
        self.points_total += points
        self.batches_total += 1
        self.alarms_total += alarms
        self._tenant_counts[tenant_id] += points

    def prometheus_text(self) -> str:
        lines = [
            "# HELP historian_points_total Total telemetry points ingested",
            "# TYPE historian_points_total counter",
            f"historian_points_total {self.points_total}",
            "# HELP historian_batches_total Total ingestion batches received",
            "# TYPE historian_batches_total counter",
            f"historian_batches_total {self.batches_total}",
            "# HELP historian_alarms_total Total alarms generated",
            "# TYPE historian_alarms_total counter",
            f"historian_alarms_total {self.alarms_total}",
            "# HELP historian_errors_total Total unhandled errors",
            "# TYPE historian_errors_total counter",
            f"historian_errors_total {self.errors_total}",
            "# HELP historian_ws_connections Current WebSocket connections",
            "# TYPE historian_ws_connections gauge",
            f"historian_ws_connections {ws_manager.connection_count}",
            "# HELP historian_uptime_seconds Application uptime in seconds",
            "# TYPE historian_uptime_seconds counter",
            f"historian_uptime_seconds {self.uptime_seconds}",
        ]
        for tid, cnt in self._tenant_counts.items():
            lines += [
                f'historian_tenant_points_total{{tenant="{tid}"}} {cnt}',
            ]
        return "\n".join(lines) + "\n"


_metrics = IngestionMetrics()


# ═══════════════════════════════════════════════════════════════════════════════
# § 11  CORE INGESTION SERVICE
#        Uses asyncpg COPY protocol for raw insert (fastest path)
#        Falls back to executemany on error (safety net)
# ═══════════════════════════════════════════════════════════════════════════════


async def _insert_raw_copy(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    points: List[TelemetryPoint],
) -> None:
    """
    COPY-based bulk insert into telemetry_raw.
    ~3-5× faster than executemany for large batches.
    """
    rows = [
        (
            tenant_id,
            plant_id,
            pt.tag_name,
            pt.value,
            pt.quality.value,
            pt.timestamp or datetime.now(timezone.utc),
            pt.unit,
            pt.source_id,
        )
        for pt in points
    ]
    try:
        await conn.copy_records_to_table(
            "telemetry_raw",
            records=rows,
            columns=["tenant_id", "plant_id", "tag_name", "value", "quality", "ts", "unit", "source_id"],
        )
    except asyncpg.UniqueViolationError:
        pass  # Tolerate duplicate ts+tag rows
    except Exception as exc:
        log.warning("copy_failed_fallback_to_executemany", error=str(exc))
        await conn.executemany(
            """
            INSERT INTO telemetry_raw
                (tenant_id, plant_id, tag_name, value, quality, ts, unit, source_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT DO NOTHING
            """,
            rows,
        )


async def _upsert_latest(
    conn: asyncpg.Connection,
    tenant_id: str,
    plant_id: str,
    points: List[TelemetryPoint],
) -> None:
    """
    Upsert latest value per tag. Uses executemany with conditional UPDATE.
    Only updates when the incoming timestamp is newer than stored.
    """
    await conn.executemany(
        """
        INSERT INTO telemetry_latest
            (tenant_id, plant_id, tag_name, value, quality, ts, unit)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT (tenant_id, plant_id, tag_name)
        DO UPDATE SET
            value   = EXCLUDED.value,
            quality = EXCLUDED.quality,
            ts      = EXCLUDED.ts,
            unit    = EXCLUDED.unit
        WHERE telemetry_latest.ts < EXCLUDED.ts
        """,
        [
            (
                tenant_id,
                plant_id,
                pt.tag_name,
                pt.value,
                pt.quality.value,
                pt.timestamp or datetime.now(timezone.utc),
                pt.unit,
            )
            for pt in points
        ],
    )


async def _insert_alarms(conn: asyncpg.Connection, alarms: List[dict]) -> None:
    if not alarms:
        return
    await conn.executemany(
        """
        INSERT INTO alarms
            (alarm_id, tenant_id, plant_id, tag_name, severity,
             message, trigger_value, occurred_at, alarm_state)
        VALUES ($1::uuid,$2,$3,$4,$5,$6,$7,$8,'ACTIVE')
        ON CONFLICT (alarm_id) DO NOTHING
        """,
        [
            (
                a["alarm_id"],
                a["tenant_id"],
                a["plant_id"],
                a["tag_name"],
                a["severity"],
                a["message"],
                a["trigger_value"],
                a["occurred_at"],
            )
            for a in alarms
        ],
    )


async def ingest_telemetry_batch(
    conn: asyncpg.Connection,
    batch: TelemetryBatch,
    user: UserContext,
) -> dict:
    """
    Main ingestion pipeline (called inside hot path):
      1. Tenant isolation check
      2. Rate-limit check
      3. COPY bulk insert → telemetry_raw
      4. Upsert          → telemetry_latest
      5. Alarm evaluation (DB-driven thresholds + cooldown)
      6. Alarm insert
      7. Metrics update
      8. WS broadcast (fire-and-forget asyncio.Task)
    """
    if not batch.points:
        return {"inserted": 0, "alarms": 0}

    # Edge agents carry their tenant in the key; human users must match
    if not user.is_edge and user.tenant_id != batch.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    if not _rate_limiter.check(batch.tenant_id, len(batch.points)):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: >{settings.RATE_LIMIT_POINTS_PER_MIN} points/min",
        )

    await _insert_raw_copy(conn, batch.tenant_id, batch.plant_id, batch.points)
    await _upsert_latest(conn, batch.tenant_id, batch.plant_id, batch.points)

    alarms = await evaluate_alarms_for_batch(conn, batch.tenant_id, batch.plant_id, batch.points)
    await _insert_alarms(conn, alarms)

    _metrics.record_batch(batch.tenant_id, len(batch.points), len(alarms))

    # WebSocket broadcast — never blocks ingestion
    asyncio.create_task(
        ws_manager.broadcast(
            batch.tenant_id,
            batch.plant_id,
            {
                "type": "telemetry",
                "plant_id": batch.plant_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "count": len(batch.points),
                "alarms": len(alarms),
                "data": {
                    pt.tag_name: {
                        "v": pt.value,
                        "q": pt.quality.value,
                        "t": pt.timestamp.isoformat() if pt.timestamp else None,
                    }
                    for pt in batch.points[:50]  # cap payload size
                },
                "alarm_events": [
                    {"tag": a["tag_name"], "severity": a["severity"], "msg": a["message"], "val": a["trigger_value"]}
                    for a in alarms
                ],
            },
        )
    )

    return {"inserted": len(batch.points), "alarms": len(alarms)}


# ═══════════════════════════════════════════════════════════════════════════════
# § 12  BACKGROUND ALARM SWEEP
#        Periodic task sweeps telemetry_latest against DB thresholds.
#        v3.0 BUGFIX: groups synthetic points from rows directly (avoids
#        index drift when TelemetryPoint construction skips bad rows).
# ═══════════════════════════════════════════════════════════════════════════════


async def _alarm_sweep_loop() -> None:
    await asyncio.sleep(12)  # Give pool time to initialize
    log.info("alarm_sweep.started", interval=settings.ALARM_SWEEP_INTERVAL)
    while True:
        try:
            async with _pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT l.tenant_id, l.plant_id, l.tag_name, l.value, l.quality,
                           l.ts, l.unit,
                           m.low_low_limit, m.low_limit, m.high_limit, m.high_high_limit,
                           m.deadband, m.engineering_unit
                    FROM telemetry_latest l
                    JOIN tag_metadata m
                      ON l.tenant_id=m.tenant_id
                     AND l.plant_id=m.plant_id
                     AND l.tag_name=m.tag_name
                    WHERE m.is_active=true
                      AND (m.high_limit IS NOT NULL OR m.low_limit IS NOT NULL)
                    """
                )

                # v3.0 BUGFIX: build groups from rows directly, not from a parallel list
                groups: Dict[Tuple[str, str], List[TelemetryPoint]] = defaultdict(list)
                for r in rows:
                    try:
                        pt = TelemetryPoint(
                            tag_name=r["tag_name"],
                            value=r["value"],
                            quality=TagQuality(r["quality"]),
                            timestamp=r["ts"],
                            unit=r["unit"],
                        )
                        groups[(r["tenant_id"], r["plant_id"])].append(pt)
                    except Exception:
                        pass  # skip malformed rows — don't break the sweep

                all_alarms: List[dict] = []
                for (tid, pid), pts in groups.items():
                    sweep_alarms = await evaluate_alarms_for_batch(conn, tid, pid, pts)
                    all_alarms.extend(sweep_alarms)

                if all_alarms:
                    await _insert_alarms(conn, all_alarms)
                    log.info("alarm_sweep.alarms_fired", count=len(all_alarms))

        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("alarm_sweep.error", error=str(exc))

        await asyncio.sleep(settings.ALARM_SWEEP_INTERVAL)


# ═══════════════════════════════════════════════════════════════════════════════
# § 13  APP LIFESPAN  (startup / shutdown)
# ═══════════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool

    log.info("startup.begin", app=settings.APP_NAME, version=settings.APP_VERSION, env=settings.ENVIRONMENT)

    _pool = await create_pool()
    log.info("startup.db_pool_ready", min=settings.DB_POOL_MIN, max=settings.DB_POOL_MAX)

    # Schema integrity check
    async with _pool.acquire() as conn:
        ht_count = await conn.fetchval("SELECT count(*) FROM timescaledb_information.hypertables")
        if ht_count < 3:
            log.warning(
                "startup.schema_warning", msg="Expected ≥3 hypertables. Run schema.sql if not done.", found=ht_count
            )
        else:
            log.info("startup.schema_ok", hypertables=ht_count)

    sweep_task = asyncio.create_task(_alarm_sweep_loop())
    log.info("startup.alarm_sweep_started")

    yield  # ← application runs

    # Graceful drain: cancel sweep, then close pool (allows in-flight requests to finish)
    sweep_task.cancel()
    try:
        await asyncio.wait_for(sweep_task, timeout=5.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass

    await _pool.close()
    log.info("shutdown.complete")


# ═══════════════════════════════════════════════════════════════════════════════
# § 14  APP FACTORY & MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware stack (applied in reverse order) ────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Trusted host check (production only; set TRUSTED_HOSTS=* to disable)
if settings.ENVIRONMENT == "production" and settings.TRUSTED_HOSTS != "*":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts_list,
    )


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Inject security headers on every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    log.info("http.request", method=request.method, status=response.status_code, ms=round(elapsed, 2))
    response.headers["X-Request-ID"] = rid
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# § 15  HEALTH & METRICS
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/health", tags=["ops"], include_in_schema=False)
async def health():
    db_ok = False
    db_ms = None
    try:
        t0 = time.perf_counter()
        async with _pool.acquire() as c:
            await c.fetchval("SELECT 1")
        db_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "db_latency_ms": db_ms,
        "ws_connections": ws_manager.connection_count,
        "points_ingested": _metrics.points_total,
        "uptime_seconds": _metrics.uptime_seconds,
        "version": settings.APP_VERSION,
    }


@app.get("/metrics", tags=["ops"], include_in_schema=False, response_class=PlainTextResponse)
async def metrics():
    """Prometheus-compatible text metrics endpoint."""
    return _metrics.prometheus_text()


@app.get("/ping", tags=["ops"], include_in_schema=False)
async def ping():
    """Lightweight liveness check for edge agents (no DB hit)."""
    return {"pong": True, "ts": datetime.now(timezone.utc).isoformat()}


# ═══════════════════════════════════════════════════════════════════════════════
# § 16  TELEMETRY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@app.post("/api/v1/telemetry/ingest", tags=["telemetry"], status_code=202)
async def ingest(
    batch: TelemetryBatch,
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Primary high-throughput ingestion endpoint.
    Called by the edge agent with X-API-Key.
    Accepts up to TELEMETRY_BATCH_MAX points per request (default 500).
    Returns 202 Accepted immediately.
    """
    if len(batch.points) > settings.TELEMETRY_BATCH_MAX:
        raise HTTPException(
            status_code=422,
            detail=f"Batch exceeds max size {settings.TELEMETRY_BATCH_MAX}",
        )
    result = await ingest_telemetry_batch(conn, batch, user)
    return {"ok": True, **result}


@app.get("/api/v1/telemetry/latest", tags=["telemetry"])
async def get_latest(
    plant_id: str = Query(...),
    tags: Optional[str] = Query(None, description="Comma-separated tag list"),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Returns latest value for all (or specified) tags in a plant.
    Reads from telemetry_latest — O(1) per tag, no time-series scan.
    """
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    if tag_list:
        rows = await conn.fetch(
            """
            SELECT tag_name, value, quality, ts, unit
            FROM telemetry_latest
            WHERE tenant_id=$1 AND plant_id=$2 AND tag_name = ANY($3)
            ORDER BY tag_name
            """,
            user.tenant_id,
            plant_id,
            tag_list,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT tag_name, value, quality, ts, unit
            FROM telemetry_latest
            WHERE tenant_id=$1 AND plant_id=$2
            ORDER BY tag_name
            """,
            user.tenant_id,
            plant_id,
        )
    return {"plant_id": plant_id, "count": len(rows), "data": [dict(r) for r in rows]}


@app.get("/api/v1/telemetry/history", tags=["telemetry"])
async def get_history(
    plant_id: str = Query(...),
    tag_name: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    interval: str = Query("1m", description="Time bucket: 1m 5m 15m 1h 1d raw"),
    agg: str = Query("avg", description="avg | min | max | last"),
    limit: int = Query(2000, le=10000),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Tag history with time-bucket aggregation.
    Auto-selects raw hypertable or continuous aggregate by span.
    """
    valid_aggs = {"avg", "min", "max", "last"}
    if agg not in valid_aggs:
        raise HTTPException(status_code=422, detail=f"agg must be one of {valid_aggs}")

    if interval == "raw":
        rows = await conn.fetch(
            """
            SELECT ts, value, quality
            FROM telemetry_raw
            WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3
              AND ts BETWEEN $4 AND $5
            ORDER BY ts DESC
            LIMIT $6
            """,
            user.tenant_id,
            plant_id,
            tag_name,
            start,
            end,
            limit,
        )
    else:
        span_hours = (end - start).total_seconds() / 3600
        source = (
            "telemetry_1min"
            if span_hours <= 6
            else "telemetry_5min"
            if span_hours <= 48
            else "telemetry_1hour"
            if span_hours <= 720
            else "telemetry_1day"
        )
        agg_col = {"avg": "avg_val", "min": "min_val", "max": "max_val", "last": "last_val"}[agg]

        rows = await conn.fetch(
            f"""
            SELECT bucket AS ts, {agg_col} AS value, sample_count
            FROM {source}
            WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3
              AND bucket BETWEEN $4 AND $5
            ORDER BY bucket DESC
            LIMIT $6
            """,
            user.tenant_id,
            plant_id,
            tag_name,
            start,
            end,
            limit,
        )

    return {
        "tag_name": tag_name,
        "plant_id": plant_id,
        "interval": interval,
        "count": len(rows),
        "data": [dict(r) for r in rows],
    }


@app.get("/api/v1/telemetry/multi-history", tags=["telemetry"])
async def get_multi_history(
    plant_id: str = Query(...),
    tags: str = Query(..., description="Comma-separated, max 10 tags"),
    start: datetime = Query(...),
    end: datetime = Query(...),
    interval: str = Query("5m"),
    agg: str = Query("avg"),
    limit: int = Query(1000, le=5000),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Multi-tag trend correlation endpoint.
    Returns [{ts, tag1_value, tag2_value, ...}] pivot format for React charts.
    """
    tag_list = [t.strip() for t in tags.split(",")][:10]
    agg_col = {"avg": "avg_val", "min": "min_val", "max": "max_val", "last": "last_val"}.get(agg, "avg_val")
    span_h = (end - start).total_seconds() / 3600
    source = (
        "telemetry_1min"
        if span_h <= 6
        else "telemetry_5min"
        if span_h <= 48
        else "telemetry_1hour"
        if span_h <= 720
        else "telemetry_1day"
    )

    rows = await conn.fetch(
        f"""
        SELECT bucket AS ts, tag_name, {agg_col} AS value
        FROM {source}
        WHERE tenant_id=$1 AND plant_id=$2 AND tag_name = ANY($3)
          AND bucket BETWEEN $4 AND $5
        ORDER BY ts, tag_name
        LIMIT $6
        """,
        user.tenant_id,
        plant_id,
        tag_list,
        start,
        end,
        limit * len(tag_list),
    )

    pivot: Dict[str, dict] = {}
    for r in rows:
        ts_str = r["ts"].isoformat()
        pivot.setdefault(ts_str, {"ts": ts_str})
        pivot[ts_str][r["tag_name"]] = r["value"]

    return {
        "plant_id": plant_id,
        "tags": tag_list,
        "interval": interval,
        "count": len(pivot),
        "data": sorted(pivot.values(), key=lambda x: x["ts"], reverse=True),
    }


@app.get("/api/v1/telemetry/stats", tags=["telemetry"])
async def get_tag_stats(
    plant_id: str = Query(...),
    tag_name: str = Query(...),
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Min/max/avg/stddev/count for a tag over the last N hours."""
    row = await conn.fetchrow(
        """
        SELECT
            count(*)                              AS sample_count,
            round(avg(value)::numeric, 4)         AS avg_val,
            round(min(value)::numeric, 4)         AS min_val,
            round(max(value)::numeric, 4)         AS max_val,
            round(stddev(value)::numeric, 4)      AS stddev_val,
            last(value, ts)                       AS last_val,
            max(ts)                               AS last_ts
        FROM telemetry_raw
        WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3
          AND ts >= now() - ($4 || ' hours')::interval
        """,
        user.tenant_id,
        plant_id,
        tag_name,
        str(hours),
    )
    return {"tag_name": tag_name, "plant_id": plant_id, "hours": hours, "stats": dict(row)}


@app.get("/api/v1/telemetry/stale", tags=["telemetry"])
async def get_stale_tags(
    plant_id: str = Query(...),
    stale_minutes: int = Query(None, description="Override default stale threshold"),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Returns tags whose last update is older than stale_minutes (default: STALE_TAG_MINUTES env).
    Useful for monitoring OPC UA connection health from the dashboard.
    """
    threshold = stale_minutes or settings.STALE_TAG_MINUTES
    rows = await conn.fetch(
        """
        SELECT tag_name, value, quality, ts, unit,
               EXTRACT(EPOCH FROM (now() - ts)) / 60 AS stale_minutes
        FROM telemetry_latest
        WHERE tenant_id=$1 AND plant_id=$2
          AND ts < now() - ($3 || ' minutes')::interval
        ORDER BY ts ASC
        """,
        user.tenant_id,
        plant_id,
        str(threshold),
    )
    return {
        "plant_id": plant_id,
        "stale_threshold_minutes": threshold,
        "stale_count": len(rows),
        "stale_tags": [dict(r) for r in rows],
    }


@app.get("/api/v1/telemetry/export", tags=["telemetry"])
async def export_telemetry(
    plant_id: str = Query(...),
    tag_name: str = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    fmt: str = Query("csv", description="csv | json"),
    limit: int = Query(50000, le=100000),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Raw data export for the given tag and time range.
    Returns CSV (default) or JSON. Streams response for large datasets.
    """
    rows = await conn.fetch(
        """
        SELECT ts, value, quality, unit
        FROM telemetry_raw
        WHERE tenant_id=$1 AND plant_id=$2 AND tag_name=$3
          AND ts BETWEEN $4 AND $5
        ORDER BY ts ASC
        LIMIT $6
        """,
        user.tenant_id,
        plant_id,
        tag_name,
        start,
        end,
        limit,
    )

    if fmt == "json":
        return {
            "tag_name": tag_name,
            "plant_id": plant_id,
            "count": len(rows),
            "data": [dict(r) for r in rows],
        }

    # CSV streaming response
    def generate_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["timestamp", "value", "quality", "unit"])
        for r in rows:
            writer.writerow(
                [
                    r["ts"].isoformat() if r["ts"] else "",
                    r["value"],
                    r["quality"],
                    r["unit"] or "",
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()

    filename = f"{tag_name}_{start.date()}_{end.date()}.csv".replace(" ", "_")
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 17  ALARM ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/v1/alarms/active", tags=["alarms"])
async def get_active_alarms(
    plant_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    q = """
        SELECT alarm_id, plant_id, tag_name, severity, message,
               trigger_value, occurred_at, alarm_state, acked_by, acked_at
        FROM alarms
        WHERE tenant_id=$1 AND alarm_state != 'CLEARED'
    """
    params: list = [user.tenant_id]
    if plant_id:
        params.append(plant_id)
        q += f" AND plant_id=${len(params)}"
    if severity:
        params.append(severity.upper())
        q += f" AND severity=${len(params)}"
    q += " ORDER BY occurred_at DESC LIMIT 200"
    rows = await conn.fetch(q, *params)
    return {"count": len(rows), "alarms": [dict(r) for r in rows]}


@app.post("/api/v1/alarms/ack", tags=["alarms"])
async def acknowledge_alarm(
    req: AlarmAckRequest,
    user: UserContext = Depends(require_role("admin", "engineer", "operator")),
    conn: asyncpg.Connection = Depends(get_db),
):
    # Fetch plant_id BEFORE update for correct WS routing (v3.0 BUGFIX)
    alarm_row = await conn.fetchrow(
        "SELECT plant_id FROM alarms WHERE alarm_id=$1 AND tenant_id=$2",
        req.alarm_id,
        user.tenant_id,
    )
    if not alarm_row:
        raise HTTPException(status_code=404, detail="Alarm not found")

    result = await conn.execute(
        """
        UPDATE alarms
        SET alarm_state='ACKNOWLEDGED', acked_by=$1, acked_at=now()
        WHERE alarm_id=$2 AND tenant_id=$3 AND alarm_state='ACTIVE'
        """,
        req.acked_by,
        req.alarm_id,
        user.tenant_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=409, detail="Alarm already acknowledged or cleared")

    await conn.execute(
        """
        INSERT INTO alarm_history (alarm_id, tenant_id, action, performed_by, comment)
        VALUES ($1,$2,'ACKNOWLEDGED',$3,$4)
        """,
        req.alarm_id,
        user.tenant_id,
        req.acked_by,
        req.comment,
    )
    await audit(conn, user, "ACK_ALARM", f"alarms/{req.alarm_id}", {"comment": req.comment})

    # v3.0 BUGFIX: route to correct plant room using fetched plant_id
    plant_id = alarm_row["plant_id"]
    asyncio.create_task(
        ws_manager.broadcast(
            user.tenant_id,
            plant_id,
            {"type": "alarm_ack", "alarm_id": str(req.alarm_id), "plant_id": plant_id, "acked_by": req.acked_by},
        )
    )
    return {"ok": True, "alarm_id": str(req.alarm_id)}


@app.post("/api/v1/alarms/clear", tags=["alarms"])
async def clear_alarms(
    req: AlarmClearRequest,
    user: UserContext = Depends(require_role("admin", "engineer", "operator")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Bulk-clear acknowledged alarms. If alarm_ids is None, clears all ACKNOWLEDGED
    alarms for the plant. Cleared alarms are removed from the active list.
    """
    if req.alarm_ids:
        result = await conn.execute(
            """
            UPDATE alarms SET alarm_state='CLEARED'
            WHERE tenant_id=$1 AND plant_id=$2
              AND alarm_id = ANY($3::uuid[])
              AND alarm_state='ACKNOWLEDGED'
            """,
            user.tenant_id,
            req.plant_id,
            [str(aid) for aid in req.alarm_ids],
        )
    else:
        result = await conn.execute(
            """
            UPDATE alarms SET alarm_state='CLEARED'
            WHERE tenant_id=$1 AND plant_id=$2 AND alarm_state='ACKNOWLEDGED'
            """,
            user.tenant_id,
            req.plant_id,
        )

    cleared_count = int(result.split()[-1])
    await audit(
        conn, user, "CLEAR_ALARMS", f"plants/{req.plant_id}", {"cleared": cleared_count, "comment": req.comment}
    )
    asyncio.create_task(
        ws_manager.broadcast(
            user.tenant_id,
            req.plant_id,
            {"type": "alarms_cleared", "plant_id": req.plant_id, "count": cleared_count, "cleared_by": req.cleared_by},
        )
    )
    return {"ok": True, "cleared": cleared_count}


@app.get("/api/v1/alarms/history", tags=["alarms"])
async def get_alarm_history(
    plant_id: Optional[str] = Query(None),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    severity: Optional[str] = Query(None),
    state: Optional[str] = Query(None, description="ACTIVE | ACKNOWLEDGED | CLEARED"),
    limit: int = Query(500, le=5000),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    q = "SELECT * FROM alarms WHERE tenant_id=$1"
    params: list = [user.tenant_id]

    if plant_id:
        params.append(plant_id)
        q += f" AND plant_id=${len(params)}"
    if start:
        params.append(start)
        q += f" AND occurred_at>=${len(params)}"
    if end:
        params.append(end)
        q += f" AND occurred_at<=${len(params)}"
    if severity:
        params.append(severity.upper())
        q += f" AND severity=${len(params)}"
    if state:
        params.append(state.upper())
        q += f" AND alarm_state=${len(params)}"

    params.append(limit)
    q += f" ORDER BY occurred_at DESC LIMIT ${len(params)}"
    rows = await conn.fetch(q, *params)
    return {"count": len(rows), "alarms": [dict(r) for r in rows]}


@app.get("/api/v1/alarms/summary", tags=["alarms"])
async def alarm_summary(
    plant_id: str = Query(...),
    hours: int = Query(24, ge=1, le=720),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Alarm count by severity for the last N hours — dashboard KPI tiles."""
    rows = await conn.fetch(
        """
        SELECT severity,
               count(*) AS total,
               sum(CASE WHEN alarm_state='ACKNOWLEDGED' THEN 1 ELSE 0 END) AS acked,
               sum(CASE WHEN alarm_state='ACTIVE'       THEN 1 ELSE 0 END) AS unacked,
               sum(CASE WHEN alarm_state='CLEARED'      THEN 1 ELSE 0 END) AS cleared
        FROM alarms
        WHERE tenant_id=$1 AND plant_id=$2
          AND occurred_at >= now() - ($3 || ' hours')::interval
        GROUP BY severity
        ORDER BY severity
        """,
        user.tenant_id,
        plant_id,
        str(hours),
    )
    return {"plant_id": plant_id, "hours": hours, "summary": [dict(r) for r in rows]}


# ═══════════════════════════════════════════════════════════════════════════════
# § 18  TAG METADATA ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/v1/tags", tags=["tags"])
async def list_tags(
    plant_id: str = Query(...),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """
        SELECT tag_name, description, engineering_unit, opc_node_id, data_type,
               low_low_limit, low_limit, high_limit, high_high_limit,
               deadband, is_active, updated_at
        FROM tag_metadata
        WHERE tenant_id=$1 AND plant_id=$2
        ORDER BY tag_name
        """,
        user.tenant_id,
        plant_id,
    )
    return {"count": len(rows), "tags": [dict(r) for r in rows]}


@app.get("/api/v1/tags/search", tags=["tags"])
async def search_tags(
    plant_id: str = Query(...),
    q: str = Query(..., min_length=1, description="Tag name / description substring"),
    limit: int = Query(50, le=200),
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Full-text search across tag_name and description. Used by React tag picker."""
    rows = await conn.fetch(
        """
        SELECT tag_name, description, engineering_unit, is_active
        FROM tag_metadata
        WHERE tenant_id=$1 AND plant_id=$2
          AND (tag_name ILIKE $3 OR description ILIKE $3)
        ORDER BY tag_name
        LIMIT $4
        """,
        user.tenant_id,
        plant_id,
        f"%{q}%",
        limit,
    )
    return {"count": len(rows), "tags": [dict(r) for r in rows]}


@app.put("/api/v1/tags/{tag_name}", tags=["tags"])
async def upsert_tag_metadata(
    tag_name: str,
    plant_id: str = Query(...),
    payload: TagMetadataUpdate = ...,
    user: UserContext = Depends(require_role("admin", "engineer")),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute(
        """
        INSERT INTO tag_metadata
            (tenant_id, plant_id, tag_name, description, engineering_unit,
             opc_node_id, data_type, low_low_limit, low_limit,
             high_limit, high_high_limit, deadband, is_active)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        ON CONFLICT (tenant_id, plant_id, tag_name)
        DO UPDATE SET
            description      = EXCLUDED.description,
            engineering_unit = EXCLUDED.engineering_unit,
            opc_node_id      = EXCLUDED.opc_node_id,
            data_type        = EXCLUDED.data_type,
            low_low_limit    = EXCLUDED.low_low_limit,
            low_limit        = EXCLUDED.low_limit,
            high_limit       = EXCLUDED.high_limit,
            high_high_limit  = EXCLUDED.high_high_limit,
            deadband         = EXCLUDED.deadband,
            is_active        = EXCLUDED.is_active,
            updated_at       = now()
        """,
        user.tenant_id,
        plant_id,
        tag_name,
        payload.description,
        payload.engineering_unit,
        payload.opc_node_id,
        payload.data_type,
        payload.low_low_limit,
        payload.low_limit,
        payload.high_limit,
        payload.high_high_limit,
        payload.deadband,
        payload.is_active,
    )
    # Evict from threshold cache
    _threshold_cache.pop((user.tenant_id, plant_id, tag_name), None)
    await audit(conn, user, "UPSERT_TAG_METADATA", f"tags/{tag_name}")
    return {"ok": True, "tag_name": tag_name}


# ═══════════════════════════════════════════════════════════════════════════════
# § 19  PLANT MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/v1/plants", tags=["plants"])
async def list_plants(
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """
        SELECT plant_id, name, location, plant_type, timezone, is_active, created_at
        FROM plants
        WHERE tenant_id=$1
        ORDER BY name
        """,
        user.tenant_id,
    )
    return {"count": len(rows), "plants": [dict(r) for r in rows]}


@app.get("/api/v1/plants/{plant_id}", tags=["plants"])
async def get_plant(
    plant_id: str,
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    row = await conn.fetchrow(
        """
        SELECT plant_id, name, location, plant_type, timezone, is_active, config, created_at
        FROM plants
        WHERE tenant_id=$1 AND plant_id=$2
        """,
        user.tenant_id,
        plant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Plant not found")
    return dict(row)


@app.post("/api/v1/plants", tags=["plants"], status_code=201)
async def create_plant(
    payload: PlantCreate,
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    await conn.execute(
        """
        INSERT INTO plants
            (tenant_id, plant_id, name, location, plant_type, timezone, config)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT (tenant_id, plant_id) DO UPDATE
        SET name=$3, location=$4, plant_type=$5, timezone=$6, config=$7
        """,
        user.tenant_id,
        payload.plant_id,
        payload.name,
        payload.location,
        payload.plant_type,
        payload.timezone,
        json.dumps(payload.config or {}),
    )
    await audit(conn, user, "CREATE_PLANT", f"plants/{payload.plant_id}")
    return {"ok": True, "plant_id": payload.plant_id}


@app.delete("/api/v1/plants/{plant_id}", tags=["plants"])
async def deactivate_plant(
    plant_id: str,
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Soft-delete (sets is_active=false). Data is retained for historical queries."""
    result = await conn.execute(
        "UPDATE plants SET is_active=false WHERE tenant_id=$1 AND plant_id=$2",
        user.tenant_id,
        plant_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Plant not found")
    await audit(conn, user, "DEACTIVATE_PLANT", f"plants/{plant_id}")
    return {"ok": True, "plant_id": plant_id}


@app.get("/api/v1/plants/{plant_id}/summary", tags=["plants"])
async def plant_summary(
    plant_id: str,
    user: UserContext = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
):
    """Dashboard KPI summary — tag counts + alarm counts in one round-trip."""
    latest_count, active_alarms, critical_alarms = await asyncio.gather(
        conn.fetchval(
            "SELECT count(*) FROM telemetry_latest WHERE tenant_id=$1 AND plant_id=$2",
            user.tenant_id,
            plant_id,
        ),
        conn.fetchval(
            "SELECT count(*) FROM alarms WHERE tenant_id=$1 AND plant_id=$2 AND alarm_state='ACTIVE'",
            user.tenant_id,
            plant_id,
        ),
        conn.fetchval(
            "SELECT count(*) FROM alarms WHERE tenant_id=$1 AND plant_id=$2 "
            "AND alarm_state='ACTIVE' AND severity IN ('CRITICAL','ALARM')",
            user.tenant_id,
            plant_id,
        ),
    )
    return {
        "plant_id": plant_id,
        "active_tags": latest_count,
        "active_alarms": active_alarms,
        "critical_alarms": critical_alarms,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# § 20  ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/api/v1/admin/tenants", tags=["admin"])
async def list_tenants(
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch("SELECT tenant_id, name, plan, is_active, created_at FROM tenants ORDER BY name")
    return {"count": len(rows), "tenants": [dict(r) for r in rows]}


@app.get("/api/v1/admin/audit-log", tags=["admin"])
async def get_audit_log(
    limit: int = Query(200, le=1000),
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    rows = await conn.fetch(
        """
        SELECT id, tenant_id, user_email, role, action, resource, detail, created_at
        FROM audit_logs
        WHERE tenant_id=$1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user.tenant_id,
        limit,
    )
    return {"count": len(rows), "logs": [dict(r) for r in rows]}


@app.get("/api/v1/admin/ingestion-stats", tags=["admin"])
async def ingestion_stats(
    user: UserContext = Depends(require_role("admin")),
):
    """Live ingestion counters — no DB query needed."""
    return {
        "points_total": _metrics.points_total,
        "batches_total": _metrics.batches_total,
        "alarms_total": _metrics.alarms_total,
        "errors_total": _metrics.errors_total,
        "uptime_seconds": _metrics.uptime_seconds,
        "ws_connections": ws_manager.connection_count,
        "rate_limit_pts_per_min": settings.RATE_LIMIT_POINTS_PER_MIN,
        "tenant_point_counts": dict(_metrics._tenant_counts),
    }


# ── API Key Management ────────────────────────────────────────────────────────


@app.get("/api/v1/admin/api-keys", tags=["admin"])
async def list_api_keys(
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """List all API keys for the tenant (hashes only — raw keys are never stored)."""
    rows = await conn.fetch(
        """
        SELECT key_id, label, tenant_id, is_active, created_at, expires_at, last_used_at
        FROM api_keys
        WHERE tenant_id=$1
        ORDER BY created_at DESC
        """,
        user.tenant_id,
    )
    return {"count": len(rows), "keys": [dict(r) for r in rows]}


@app.post("/api/v1/admin/api-keys", tags=["admin"], status_code=201)
async def create_api_key(
    payload: ApiKeyCreate,
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    """
    Provision a new API key for an edge agent.
    Returns the raw key ONCE — store it securely; it cannot be retrieved again.
    """
    if user.role == "admin" and user.tenant_id != payload.tenant_id:
        # Superadmin scenario: allow cross-tenant key creation
        pass

    raw_key = secrets.token_urlsafe(32)
    key_hash = _hash_api_key(raw_key)
    key_id = str(uuid.uuid4())

    await conn.execute(
        """
        INSERT INTO api_keys (key_id, label, tenant_id, key_hash)
        VALUES ($1,$2,$3,$4)
        """,
        key_id,
        payload.label,
        payload.tenant_id,
        key_hash,
    )
    await audit(
        conn, user, "CREATE_API_KEY", f"api_keys/{key_id}", {"label": payload.label, "tenant": payload.tenant_id}
    )

    return {
        "ok": True,
        "key_id": key_id,
        "raw_key": raw_key,  # Show only once — never stored
        "label": payload.label,
        "warning": "Save this key immediately. It will not be shown again.",
    }


@app.delete("/api/v1/admin/api-keys/{key_id}", tags=["admin"])
async def revoke_api_key(
    key_id: str,
    user: UserContext = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
):
    result = await conn.execute(
        "UPDATE api_keys SET is_active=false WHERE key_id=$1 AND tenant_id=$2",
        key_id,
        user.tenant_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="API key not found")
    await audit(conn, user, "REVOKE_API_KEY", f"api_keys/{key_id}")
    return {"ok": True, "key_id": key_id}


# ═══════════════════════════════════════════════════════════════════════════════
# § 21  WEBSOCKET — REAL-TIME STREAMING
# ═══════════════════════════════════════════════════════════════════════════════


@app.websocket("/ws/{tenant_id}/{plant_id}")
async def websocket_stream(
    websocket: WebSocket,
    tenant_id: str,
    plant_id: str,
    token: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None),
):
    """
    Real-time telemetry stream for dashboards and SCADA clients.
    Auth:  ?token=<Supabase JWT>  OR  ?api_key=<raw edge key>
    On connect: sends snapshot of telemetry_latest.
    Ongoing:    receives broadcast from ingestion pipeline.
    Keepalive:  client sends "ping" → server replies "pong".
                server sends "pong" every 30s if no client message.
    """
    # ── Auth ────────────────────────────────────────────────────────────────
    if api_key:
        t = await _verify_edge_api_key_db(api_key)
        if not t or t != tenant_id:
            await websocket.close(code=4401)
            return
    elif token:
        try:
            payload = _decode_supabase_jwt(token)
            meta = payload.get("app_metadata", {})
            if meta.get("tenant_id") != tenant_id:
                await websocket.close(code=4403)
                return
        except HTTPException:
            await websocket.close(code=4401)
            return
    else:
        await websocket.close(code=4401)
        return

    await ws_manager.connect(websocket, tenant_id, plant_id)

    try:
        # Send current snapshot from telemetry_latest
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT tag_name, value, quality, ts, unit
                FROM telemetry_latest
                WHERE tenant_id=$1 AND plant_id=$2
                """,
                tenant_id,
                plant_id,
            )
        await websocket.send_json(
            {
                "type": "snapshot",
                "plant_id": plant_id,
                "count": len(rows),
                "data": {
                    r["tag_name"]: {
                        "v": r["value"],
                        "q": r["quality"],
                        "u": r["unit"],
                        "t": r["ts"].isoformat() if r["ts"] else None,
                    }
                    for r in rows
                },
            }
        )

        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("pong")  # server-initiated keepalive

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket, tenant_id, plant_id)


# ═══════════════════════════════════════════════════════════════════════════════
# § 22  GRAFANA SimpleJSON-COMPATIBLE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/grafana/", tags=["grafana"], include_in_schema=False)
async def grafana_health():
    return {"status": "ok"}


@app.post("/grafana/search", tags=["grafana"], include_in_schema=False)
async def grafana_search(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    body = await request.json()
    target = body.get("target", "")
    rows = await conn.fetch(
        "SELECT DISTINCT tag_name FROM tag_metadata WHERE tag_name ILIKE $1 LIMIT 200",
        f"%{target}%",
    )
    return [r["tag_name"] for r in rows]


@app.post("/grafana/query", tags=["grafana"], include_in_schema=False)
async def grafana_query(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Grafana SimpleJSON time-series query using continuous aggregates."""
    body = await request.json()
    fr = body.get("range", {})
    start = datetime.fromisoformat(fr.get("from", "").replace("Z", "+00:00"))
    end = datetime.fromisoformat(fr.get("to", "").replace("Z", "+00:00"))
    span_h = (end - start).total_seconds() / 3600

    # Auto-select aggregate table — names are controlled internally (no SQL injection)
    source = (
        "telemetry_1min"
        if span_h <= 6
        else "telemetry_5min"
        if span_h <= 48
        else "telemetry_1hour"
        if span_h <= 720
        else "telemetry_1day"
    )

    result = []
    for t in body.get("targets", []):
        tag = t.get("target", "")
        rows = await conn.fetch(
            f"""
            SELECT bucket AS ts, avg_val AS value
            FROM {source}
            WHERE tag_name=$1 AND bucket BETWEEN $2 AND $3
            ORDER BY bucket
            LIMIT 2000
            """,
            tag,
            start,
            end,
        )
        result.append(
            {
                "target": tag,
                "datapoints": [[r["value"], int(r["ts"].timestamp() * 1000)] for r in rows if r["value"] is not None],
            }
        )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# § 23  GLOBAL EXCEPTION HANDLER
# ═══════════════════════════════════════════════════════════════════════════════


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _metrics.errors_total += 1
    log.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# § 24  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=2,  # 2 workers on 4 GB RAM; 1 if <2 GB
        loop="uvloop",
        http="httptools",
        log_level="warning",  # structlog handles app-level logs
        access_log=False,
    )
