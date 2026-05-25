# Industrial Operations Cloud
## Production Maintenance & Governance Handbook
### Piccadily Industrial Historian v4.0

**Classification:** Internal Engineering — Enterprise Grade
**Platform:** FastAPI · TimescaleDB · Redis Streams · WebSocket · React 18 · Zustand
**Generated:** 2026-05-24

---

## EXECUTIVE SUMMARY

This handbook is the single authoritative reference for maintaining, debugging, extending, and operationalizing the Piccadily Industrial Historian platform. Following a comprehensive codebase intelligence audit, **11 critical architectural defects** were identified that partially explain the frontend rendering failures. This document maps every system layer, prescribes production-grade fixes, and establishes governance standards for sustainable engineering.

**Current state assessment:** The platform is in a dangerous hybrid state — partially production-grade, partially prototype. The backend pipeline is sound; the frontend rendering, authentication flow, and observability stack require immediate remediation.

---

# PART I — COMPLETE PROJECT ARCHITECTURE MAP

## 1.1 System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  PLANT FLOOR                                                         │
│  OPC UA Server (Modbus → asyncua bridge, port 4840)                 │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ OPC UA subscription (500ms)
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  EDGE AGENT  (plant_simulator/piccadily_opc_edge_agent.py)           │
│  • Dynamic tag discovery via OPC UA namespace browse                 │
│  • SQLite WAL cursor for store-and-forward persistence               │
│  • Batched HTTP POST to cloud backend                                │
│  • Exponential backoff reconnect                                     │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ HTTPS POST /api/v1/telemetry/ingest
                            │ X-API-Key: <sha256-keyed>
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND  (backend/app/main.py)                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  identity/   │  │  telemetry/  │  │  realtime/               │  │
│  │  Dual auth   │  │  ingestion   │  │  broadcaster.py          │  │
│  │  JWT + APIKey│  │  router.py   │  │  WebSocket fanout        │  │
│  └──────────────┘  └──────┬───────┘  └───────────┬──────────────┘  │
│                           │ XADD                  │ SUBSCRIBE       │
│                    ┌──────▼───────┐    ┌──────────▼──────────┐     │
│                    │    REDIS     │    │    REDIS PUB/SUB     │     │
│                    │  STREAMS     │    │  ws|broadcast|*      │     │
│                    │ historian:   │    └──────────────────────┘     │
│                    │ telemetry:   │                                  │
│                    │ {tid}:{pid}  │                                  │
│                    └──────┬───────┘                                  │
│                           │ XREADGROUP                               │
│          ┌────────────────┼────────────────────┐                    │
│          ▼                ▼                    ▼                     │
│  ┌───────────────┐ ┌──────────────┐  ┌──────────────┐              │
│  │stream_consumer│ │alarm_consumer│  │  TimescaleDB │              │
│  │ writer        │ │ engine       │  │  15 per-group│              │
│  │ 2 workers     │ │ 1 worker     │  │  hypertables │              │
│  └───────────────┘ └──────────────┘  └──────────────┘              │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ WebSocket + REST API
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  REACT FRONTEND  (frontend/src/)                                     │
│                                                                      │
│  useWebSocket hook → Zustand useAppStore → DashboardPage            │
│  (layout.tsx)         (latestValues)       (tagList render)         │
│                                                                      │
│  Auth: LoginPage (mock JWT) → AuthGuard → Layout (WS connect)      │
└──────────────────────────────────────────────────────────────────────┘
```

## 1.2 Complete Folder Structure

```
industrial-telemetry-platform-init/
├── backend/
│   ├── app/
│   │   ├── main.py                    ← App factory, lifespan, middleware, SPA serving
│   │   ├── config.py                  ← pydantic-settings (Settings class)
│   │   ├── models.py                  ← All Pydantic schemas
│   │   ├── admin/
│   │   │   ├── grafana.py             ← Grafana SimpleJSON compatible endpoints
│   │   │   └── router.py             ← Tenant/audit/key management CRUD
│   │   ├── alarms/
│   │   │   ├── consumer.py           ← Redis Stream alarm consumer (background task)
│   │   │   ├── engine.py             ← Threshold evaluation, cooldown, cache
│   │   │   └── router.py             ← Active/history/ack/clear/summary endpoints
│   │   ├── core/
│   │   │   ├── exceptions.py         ← Domain exception hierarchy
│   │   │   ├── observability.py      ← FastAPI exception handler registration
│   │   │   ├── pagination.py         ← Cursor-based pagination
│   │   │   └── redis_keys.py         ← ⚠️ CENTRALIZED key registry (partially unused)
│   │   ├── identity/
│   │   │   ├── auth.py               ← ⚠️ DUPLICATES Permission, ROLE_PERMISSIONS, audit()
│   │   │   ├── rbac.py               ← ⚠️ DUPLICATES Permission, ROLE_PERMISSIONS
│   │   │   ├── router.py             ← EMPTY FILE (placeholder only)
│   │   │   └── session.py            ← ⚠️ DUPLICATES audit() function
│   │   ├── infra/
│   │   │   ├── database.py           ← asyncpg dual pool (read + write)
│   │   │   ├── metrics.py            ← Prometheus text, RateLimiter, IngestionMetrics
│   │   │   └── redis.py              ← Redis client pool
│   │   ├── plant/
│   │   │   └── router.py             ← Plant CRUD + summary
│   │   ├── realtime/
│   │   │   ├── broadcaster.py        ← ConnectionManager, Redis Pub/Sub listener
│   │   │   └── router.py             ← WS endpoint + ticket generation
│   │   └── telemetry/
│   │       ├── ingestion.py          ← Main ingest pipeline (rate limit → stream → broadcast)
│   │       ├── router.py             ← History/latest/export/stale/stats endpoints
│   │       ├── stream_consumer.py    ← Redis → TimescaleDB writer workers
│   │       ├── stream_writer.py      ← XADD to Redis stream
│   │       ├── tag_router.py         ← LRU-cached tag → hypertable routing
│   │       └── tags_router.py        ← Tag metadata CRUD
│   ├── refactor.py                   ← ⚠️ DEAD FILE (migration script, already ran)
│   ├── fix_redis.py                  ← ⚠️ DEAD FILE (one-time fix script)
│   ├── requirements.txt
│   ├── Dockerfile                    ← Multi-stage: Node (frontend) + Python (backend)
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── App.tsx               ← QueryClient + RouterProvider
│       │   ├── layout.tsx            ← Sidebar + Header + WS connection + AlarmBadge
│       │   └── router.tsx            ← React Router v7 route config
│       ├── features/
│       │   ├── admin/AdminPage.tsx
│       │   ├── alarms/AlarmsPage.tsx
│       │   ├── auth/
│       │   │   ├── AuthGuard.tsx
│       │   │   └── LoginPage.tsx     ← ⚠️ MOCK AUTH - hardcoded 'mock_jwt_token'
│       │   ├── dashboard/DashboardPage.tsx
│       │   ├── historian/HistorianPage.tsx  ← ⚠️ PLACEHOLDER only
│       │   ├── plants/PlantsPage.tsx        ← ⚠️ PLACEHOLDER only
│       │   └── telemetry/TelemetryPage.tsx
│       └── shared/
│           ├── api/client.ts         ← fetchApi wrapper with VITE_API_URL base
│           ├── hooks/useWebSocket.ts ← WebSocket hook with reconnect + heartbeat
│           ├── stores/useAppStore.ts ← Zustand store (auth, telemetry, alarms, UI)
│           ├── types/index.ts        ← All TypeScript interfaces
│           └── utils/cn.ts
├── plant_simulator/                  ← Local dev: Modbus sim + OPC UA bridge + edge agent
├── grafana/provisioning/
├── nginx/nginx.conf
├── timescaledb/V1__init.sql
├── docker-compose.yml
├── docker-compose.prod.yml
└── scripts/                         ← CI lint, seed, export scripts
```

---

# PART II — CRITICAL DEFECT REGISTRY

## DEFECT-001 — DUPLICATE PERMISSION/RBAC DEFINITIONS (SEVERITY: HIGH)

**Location:** `backend/app/identity/auth.py` AND `backend/app/identity/rbac.py`

Both files define identical `Permission` enum and `ROLE_PERMISSIONS` dict. The `identity/__init__.py` imports `Permission` and `require_permission` from `rbac.py`, but `admin/router.py` imports directly from `identity.auth`. This creates a split-brain situation where type comparisons can fail silently.

**Root Cause:** Incomplete DDD refactor — auth.py was not cleaned up after rbac.py was extracted.

**Fix:**
```python
# DELETE backend/app/identity/rbac.py entirely
# In backend/app/identity/__init__.py:
from app.identity.auth import (
    get_current_user, _hash_api_key,
    Permission, require_permission, require_plant_access,
    ROLE_PERMISSIONS, audit,
)
__all__ = [
    "get_current_user", "_hash_api_key",
    "Permission", "require_permission", "require_plant_access",
    "ROLE_PERMISSIONS", "audit",
]
```

## DEFECT-002 — DUPLICATE audit() FUNCTION (SEVERITY: HIGH)

**Location:** `backend/app/identity/auth.py` (lines ~220+) AND `backend/app/identity/session.py`

Two implementations of `audit()` with identical signatures. Only `auth.py`'s version is actually called. `session.py` is dead code.

**Fix:** Delete `backend/app/identity/session.py`. Ensure all imports point to `app.identity.auth.audit`.

## DEFECT-003 — STREAM KEY INCONSISTENCY (SEVERITY: HIGH)

**Location:** Three conflicting patterns:

| File | Key Pattern |
|------|------------|
| `core/redis_keys.py` `stream_key()` | `"{prefix}:{tenant_id}:{plant_id}"` |
| `telemetry/stream_writer.py` | `f"{settings.REDIS_STREAM_PREFIX}{tenant_id}:{plant_id}"` → `historian:telemetry:{tid}:{pid}` |
| `config.py REDIS_STREAM_PREFIX` | `"historian:telemetry:"` |
| `alarms/consumer.py` scan pattern | `f"{settings.REDIS_STREAM_PREFIX}*"` → `historian:telemetry:*` |
| `telemetry/stream_consumer.py` | `f"{settings.REDIS_STREAM_PREFIX}*"` → matches ✓ |

The `core/redis_keys.py` `stream_key()` function is **never used** by the actual pipeline. The stream_writer and both consumers all use the `settings.REDIS_STREAM_PREFIX` path, which is internally consistent. The dead function in redis_keys.py is misleading but not breaking.

**Fix:** Remove `stream_key()` from `core/redis_keys.py` and its `__all__` export, or rewrite it to match:
```python
def stream_key(tenant_id: str, plant_id: str) -> str:
    from app.config import settings
    return f"{settings.REDIS_STREAM_PREFIX}{tenant_id}:{plant_id}"
```

## DEFECT-004 — HARDCODED API KEY IN FRONTEND (SEVERITY: CRITICAL)

**Location:** `frontend/src/app/layout.tsx` line ~110

```typescript
useWebSocket({
    ...
    apiKey: 'changeme',   // ← HARDCODED PLAINTEXT KEY IN FRONTEND BUNDLE
    ...
});
```

This exposes the API key in the compiled JavaScript bundle. Any user can view it via browser DevTools.

**Fix:** Implement the ticket-based WebSocket auth flow that is already implemented on the backend:
```typescript
// layout.tsx
const [wsTicket, setWsTicket] = useState<string | null>(null);

useEffect(() => {
    if (!user) return;
    fetch('/api/v1/ws/ticket', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('industrial_auth_token')}` }
    })
    .then(r => r.json())
    .then(d => setWsTicket(d.ticket));
}, [user]);

useWebSocket({
    ticket: wsTicket ?? undefined,
    apiKey: undefined,
    enabled: !!wsTicket,
    ...
});
```

## DEFECT-005 — MOCK AUTHENTICATION IN PRODUCTION CODE PATH (SEVERITY: CRITICAL)

**Location:** `frontend/src/features/auth/LoginPage.tsx`

```typescript
localStorage.setItem('industrial_auth_token', 'mock_jwt_token');
```

The mock JWT is stored and the `client.ts` API wrapper sends it in requests. The backend validates JWT via Supabase — this mock token will be rejected by the backend, causing all authenticated API calls to fail with 401.

**Fix:** Integrate real Supabase auth client or implement a dev-mode bypass in the backend that accepts a configured dev token.

## DEFECT-006 — FRONTEND API CLIENT BASE URL MISCONFIGURATION (SEVERITY: HIGH)

**Location:** `frontend/src/shared/api/client.ts`

```typescript
let base = import.meta.env.VITE_API_URL || '/api/v1';
if (base && !base.endsWith('/api/v1') && base !== '/api/v1') {
    base = `${base.replace(/\/$/, '')}/api/v1`;
}
```

When `VITE_API_URL` is not set, `base = '/api/v1'` (correct for unified container). When set to `http://localhost:8000`, it becomes `http://localhost:8000/api/v1` (also correct). The Vite proxy in `vite.config.ts` forwards `/api` → `http://localhost:8000`, which means the full path `/api/v1/telemetry/latest` is proxied correctly. **This is working**, but the URL-building logic is fragile and confusing.

**Fix:** Simplify:
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api/v1`
    : '/api/v1';
```

## DEFECT-007 — require_plant_access DEPENDENCY INJECTION FAILURE (SEVERITY: HIGH)

**Location:** `backend/app/telemetry/router.py`, `backend/app/plant/router.py`, etc.

```python
async def get_history(
    plant_id: str = Query(...),
    ...
    _=Depends(require_plant_access),  # ← BUG: require_plant_access(plant_id, user)
    ...
):
```

`require_plant_access` signature is:
```python
async def require_plant_access(plant_id: str, user: UserContext = Depends(get_current_user)) -> UserContext:
```

FastAPI will attempt to inject `plant_id` from the path/query for the dependency function — but the plant_id is a separate query param on the endpoint, not automatically threaded into the dependency. This causes FastAPI to treat `plant_id` inside `require_plant_access` as a **separate** required query parameter, meaning `plant_id` appears twice in the OpenAPI schema and may cause unexpected behavior.

**Fix:** Use a factory pattern:
```python
def check_plant_access(plant_id_param: str = "plant_id"):
    async def _check(
        request: Request,
        user: UserContext = Depends(get_current_user)
    ) -> None:
        plant_id = request.query_params.get(plant_id_param) or request.path_params.get(plant_id_param)
        if plant_id:
            await _verify_plant(plant_id, user)
    return _check
```

Or more simply, inline the check in each route handler.

## DEFECT-008 — DEAD FILES IN BACKEND ROOT (SEVERITY: MEDIUM)

**Files:**
- `backend/refactor.py` — one-time migration script, now dead
- `backend/fix_redis.py` — one-time fix script, now dead

**Fix:** Delete both files. They are confusing to new engineers and reference old module paths that no longer exist.

## DEFECT-009 — PLACEHOLDER PAGES WITH NO TELEMETRY (SEVERITY: MEDIUM)

**Files:**
- `frontend/src/features/historian/HistorianPage.tsx` — "Coming in Phase 3" stub
- `frontend/src/features/plants/PlantsPage.tsx` — "Coming in Phase 3" stub

These pages are registered in the router but serve no data. The TagsPage route maps to `TelemetryPage` which is acceptable as a browser.

## DEFECT-010 — WEBSOCKET PAYLOAD TRUNCATION (SEVERITY: MEDIUM)

**Location:** `backend/app/telemetry/ingestion.py`

```python
"data": {
    pt.tag_name: {"v": pt.value, "q": pt.quality.value, "t": ...}
    for pt in batch.points[:50]  # ← caps at 50 tags per broadcast
},
```

For plants with 422 tags, only 50 are broadcast per batch. The remaining tags are written to TimescaleDB via Redis Streams but never appear in the live WebSocket update — requiring the client to poll `telemetry/latest` to see them. This is the **primary cause of missing KPI values on the dashboard**.

**Fix Options:**
- Remove the `[:50]` cap and instead paginate or compress the payload
- Or restructure so the broadcaster sends only changed-tag diffs, not full snapshots
- Or increase cap to 500 (matches TELEMETRY_BATCH_MAX) and gzip the WebSocket frames

## DEFECT-011 — ZUSTAND SNAPSHOT DOES NOT MERGE WITH EXISTING STATE (SEVERITY: HIGH)

**Location:** `frontend/src/shared/stores/useAppStore.ts`

```typescript
case 'snapshot': {
    const newValues: Record<string, TelemetryLatest> = {};
    for (const [tagName, val] of Object.entries(snap.data)) {
        newValues[tagName] = { ... };
    }
    set({ latestValues: newValues });  // ← REPLACES entire state, not merges
    break;
}
```

If the snapshot comes with 30 tags and there are already 422 tags loaded from a prior poll, the snapshot wipes the existing values. The `telemetry` update case does merge correctly:

```typescript
case 'telemetry': {
    set((state) => {
        const merged = { ...state.latestValues };  // ← spreads existing state
        ...
        return { latestValues: merged };
    });
}
```

**Fix:** Apply the same merge pattern to the snapshot handler:
```typescript
case 'snapshot': {
    const snap = msg as WsSnapshot;
    set((state) => {
        const merged = { ...state.latestValues };
        for (const [tagName, val] of Object.entries(snap.data)) {
            merged[tagName] = {
                tag_name: tagName,
                value: val.v,
                quality: val.q,
                ts: val.t,
                unit: val.u,
            };
        }
        return { latestValues: merged };
    });
    break;
}
```

---

# PART III — COMPLETE DATA FLOW DIAGRAMS

## 3.1 Telemetry Ingestion Flow

```
Edge Agent
  │  POST /api/v1/telemetry/ingest
  │  { tenant_id, plant_id, points: [{tag_name, value, quality, timestamp}] }
  ▼
FastAPI Ingestion (backend/app/telemetry/ingestion.py)
  ├─ 1. Tenant match check (edge agent: tenant from API key)
  ├─ 2. Rate limiter check (Redis sliding window, 500k pts/min)
  ├─ 3. publish_batch_to_stream() → XADD to Redis
  │      Key: historian:telemetry:{tenant_id}:{plant_id}
  │      MAXLEN: 100,000
  ├─ 4. metrics.record_batch()
  └─ 5. asyncio.create_task(ws_manager.broadcast(...))
         └─ ws_manager.broadcast() → Redis PUBLISH ws|broadcast|{tid}|{pid}
         └─ Payload: {type:"telemetry", data:{tag:{v,q,t}...}[:50]}

Redis Streams
  ├─ Consumer Group "historian-writers" (2 workers)
  │    stream_consumer.py → write_to_timescaledb()
  │    ├─ Groups by tenant_id
  │    ├─ route_tag() → target hypertable (LRU cached)
  │    ├─ copy_records_to_table() → per-group hypertable
  │    ├─ executemany() → telemetry_latest UPSERT
  │    └─ XACK
  │
  └─ Consumer Group "historian-alarms" (1 worker)
       alarm_consumer.py → process_alarms()
       ├─ TelemetryPoint conversion
       ├─ evaluate_alarms_for_batch() → threshold check + cooldown
       ├─ insert_alarms() → alarms hypertable
       └─ XACK

TimescaleDB
  ├─ telemetry_{group} hypertable (15 tables)
  ├─ telemetry_latest (upsert mirror)
  └─ alarms (alarm events)
```

## 3.2 WebSocket Real-Time Flow

```
React Frontend (layout.tsx)
  │  useWebSocket({tenantId, plantId, apiKey: 'changeme'})
  │  → ws://{host}/api/v1/ws/{tenant}/{plant}?api_key=changeme
  ▼
FastAPI WebSocket Router (realtime/router.py)
  ├─ Auth: validate api_key OR ticket
  ├─ ws_manager.connect(ws, tenant, plant)
  ├─ Snapshot: SELECT FROM telemetry_latest → send {type:"snapshot", data:{...}}
  └─ Heartbeat loop: receive "ping" → send "pong" (or auto-pong every 30s)

Redis Pub/Sub Listener (broadcaster.py _listen_to_redis)
  │  PSUBSCRIBE ws|broadcast|*
  │  ← Redis PUBLISH ws|broadcast|{tid}|{pid}
  │    (from ingestion.py → ws_manager.broadcast())
  ▼
ConnectionManager._local_fanout()
  └─ Parallel asyncio.gather(ws.send_json(message) for all sockets in room)
     └─ React frontend receives {type:"telemetry", data:{...}}
        └─ useAppStore.handleWsMessage() → latestValues merged → React re-render
```

## 3.3 Complete Auth Flow

```
Human User:
  1. POST https://project.supabase.co/auth/v1/token → JWT
  2. JWT contains app_metadata: {tenant_id, role, plant_ids}
  3. Frontend: Authorization: Bearer <JWT>
  4. FastAPI get_current_user():
     ├─ Extract from header
     ├─ jose.jwt.decode(SUPABASE_JWT_SECRET, audience="authenticated")
     ├─ Check session_id not revoked (Redis revoked:session:{sid})
     └─ Return UserContext(user_id, tenant_id, role, plant_ids)

Edge Agent:
  1. X-API-Key: <raw_key> header
  2. FastAPI _verify_edge_api_key_db():
     ├─ SHA-256 hash of raw_key
     ├─ SELECT tenant_id FROM api_keys WHERE key_hash=$1 AND is_active=true
     └─ Return tenant_id
  3. UserContext(user_id=f"edge:{tenant_id}", role="edge_agent", is_edge=True)

Permission Check:
  └─ require_permission(Permission.TELEMETRY_READ)
     └─ ROLE_PERMISSIONS[user.role] → set of Permission enums
        └─ perm in user_perms → proceed or raise 403
```

## 3.4 Alarm Evaluation Flow

```
Redis alarm consumer reads batch from historian:telemetry:{tid}:{pid}
  ↓
process_alarms() groups by (tenant_id, plant_id)
  ↓
For each TelemetryPoint with quality == GOOD:
  ↓
_get_thresholds(conn, tid, pid, tag_name):
  ├─ Check Redis cache: threshold:cache:{tid}:{pid}:{tag}
  └─ If miss: SELECT FROM tag_metadata → cache for ALARM_CACHE_TTL=60s

  ↓ thresholds loaded (low_low, low, high, high_high, deadband)
  ↓
Check: val >= high_high - deadband → CRITICAL "HiHi"
Check: val >= high - deadband      → ALARM "Hi"
Check: val <= low_low + deadband   → CRITICAL "LoLo"
Check: val <= low + deadband       → ALARM "Lo"
  ↓
_check_cooldown(tid, pid, tag, severity):
  └─ Redis SET NX alarm:cooldown:{tid}:{pid}:{tag}:{sev} EX 300
     └─ If key already exists → suppressed (cooldown active)
  ↓
insert_alarms() → INSERT INTO alarms ... ON CONFLICT DO NOTHING
```

---

# PART IV — FRONTEND RENDERING DEBUG GUIDE

## 4.1 Full Rendering Pipeline Trace

```
Edge Agent POST /ingest
  → ingestion.py XADD to Redis
  → ws_manager.broadcast() → Redis PUBLISH
  → broadcaster._listen_to_redis() receives
  → _local_fanout() → ws.send_json({type:"telemetry", data:{...}[:50]})
  → useWebSocket.ts ws.onmessage → JSON.parse → onMessage callback
  → useAppStore.handleWsMessage({type:"telemetry", ...})
  → Zustand set() → latestValues merged
  → React re-render: DashboardPage useMemo recalculates tagList
  → TagRow components render with new values
```

## 4.2 Debugging Checklist — Frontend Not Showing Values

**Step 1: Verify WebSocket Connects**
```javascript
// Browser DevTools → Network tab → WS filter
// Look for: ws://localhost:3000/api/v1/ws/piccadily/BOILER_PLC_01?api_key=changeme
// Status should show 101 Switching Protocols
```

**Step 2: Verify Snapshot is Received**
```javascript
// Add temp logging to useAppStore.ts handleWsMessage:
handleWsMessage: (msg) => {
    console.log('[WS]', msg.type, Object.keys(msg.data || {}).length, 'tags');
    ...
}
```

**Step 3: Verify Zustand State**
```javascript
// Browser Console:
window.__zustand_store = useAppStore.getState();
Object.keys(window.__zustand_store.latestValues).length; // should be > 0
```

**Step 4: Verify API Authentication**
```bash
# Test with curl — if this 401s, mock JWT is rejected
curl -H "Authorization: Bearer mock_jwt_token" \
  http://localhost:8000/api/v1/telemetry/latest?plant_id=BOILER_PLC_01
```

**Step 5: Verify Backend is Receiving Data**
```bash
curl http://localhost:8000/health
# Should show: points_ingested > 0 if edge agent is running

curl http://localhost:8000/metrics | grep historian_points_total
```

**Step 6: Verify Redis Has Data**
```bash
docker exec piccadily-redis redis-cli XLEN "historian:telemetry:piccadily:BOILER_PLC_01"
docker exec piccadily-redis redis-cli XREVRANGE "historian:telemetry:piccadily:BOILER_PLC_01" + - COUNT 1
```

**Step 7: Verify TimescaleDB Has Data**
```bash
docker exec piccadily-tsdb psql -U historian_user -d historian -c \
  "SELECT tag_name, value, ts FROM telemetry_latest WHERE tenant_id='piccadily' LIMIT 5;"
```

## 4.3 Root Cause Summary — "Frontend Shows No Values"

The three most likely causes in order of probability:

1. **Authentication failure** (DEFECT-005): `mock_jwt_token` is rejected by the backend. All API calls return 401. The WS connection with `apiKey: 'changeme'` may succeed if that key is configured, but the snapshot SELECT query still needs auth. **Fix:** Configure a valid Supabase JWT or add a dev bypass.

2. **Snapshot wipes telemetry state** (DEFECT-011): Snapshot replaces rather than merges `latestValues`. If the WS connects and snapshot arrives with only recently-updated tags, prior values are erased. **Fix:** Apply the merge pattern shown above.

3. **50-tag broadcast cap** (DEFECT-010): Only 50 tags are broadcast per ingestion batch. The other 372 tags from the OPC bridge require polling `telemetry/latest`. **Fix:** Remove cap or increase it.

---

# PART V — REALTIME SYSTEM DEBUG GUIDE

## 5.1 WebSocket Connection Debugging

```bash
# Test WS connection directly
wscat -c "ws://localhost:8000/api/v1/ws/piccadily/BOILER_PLC_01?api_key=changeme"
# Expect: {"type":"snapshot","plant_id":"BOILER_PLC_01","count":422,"data":{...}}

# Monitor WS broadcasts via Redis
docker exec piccadily-redis redis-cli SUBSCRIBE "ws|broadcast|piccadily|BOILER_PLC_01"
```

## 5.2 Redis Stream Health Check

```bash
# Check stream depth (should be < MAXLEN 100,000)
docker exec piccadily-redis redis-cli XLEN "historian:telemetry:piccadily:BOILER_PLC_01"

# Check consumer group lag
docker exec piccadily-redis redis-cli XPENDING \
  "historian:telemetry:piccadily:BOILER_PLC_01" "historian-writers" - + 10

# Check if consumers are alive
docker exec piccadily-redis redis-cli XINFO GROUPS \
  "historian:telemetry:piccadily:BOILER_PLC_01"
```

## 5.3 TimescaleDB Ingestion Health

```sql
-- Check recent ingestion rate
SELECT count(*), date_trunc('minute', ts) AS minute
FROM telemetry_raw
WHERE tenant_id = 'piccadily' AND ts > now() - interval '5 minutes'
GROUP BY minute ORDER BY minute DESC;

-- Check hypertable sizes
SELECT hypertable_name,
       pg_size_pretty(total_bytes) AS total_size,
       num_chunks
FROM timescaledb_information.hypertables
ORDER BY total_bytes DESC;

-- Check for stale consumers
SELECT consumer_name, pending_count, idle_time
FROM (
    SELECT unnest(consumers) AS c FROM
    (SELECT xinfo_groups_consumers FROM ... -- use redis-cli instead)
) -- use redis XINFO CONSUMERS
```

---

# PART VI — DOCKER & NGINX OPERATIONS

## 6.1 Service Architecture

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| `timescaledb` | `piccadily-tsdb` | 5432 | Primary time-series database |
| `fastapi` | `piccadily-backend` | 8000 | API + WS + static SPA serving |
| `redis` | `piccadily-redis` | 6379 | Streams + Pub/Sub + rate limiting |
| `grafana` | `piccadily-grafana` | 3001 | Dashboards |
| `nginx` | `piccadily-nginx` | 80 | Reverse proxy |

## 6.2 Service Start Order (Critical)

```bash
# Always start in this order:
docker compose up -d timescaledb redis
sleep 30  # Wait for TimescaleDB to initialize schema

docker compose up -d fastapi
sleep 15  # Wait for app startup + pool creation

docker compose up -d grafana nginx
```

## 6.3 Common Docker Runbook

```bash
# View all service health
docker compose ps

# Backend logs (structured JSON)
docker compose logs fastapi --since 1h --follow | python3 -m json.tool

# Backend structured log query
docker compose logs fastapi --since 1h | grep '"level":"error"'

# Hot reload during development (NOT production)
docker compose exec fastapi bash
# Inside: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Restart single service without downtime
docker compose up -d --no-deps fastapi

# Check memory usage
docker stats --no-stream

# Scale workers (production only)
docker compose up -d --scale fastapi=2  # requires load balancer config
```

## 6.4 Nginx Routing Reference

| Path Pattern | Upstream | Notes |
|-------------|----------|-------|
| `/api/` | `fastapi:8000` | Rate limited: 100r/s burst 50 |
| `/ws/` | `fastapi:8000` | WebSocket upgrade, 3600s timeout |
| `/grafana/` | `grafana:3000` | Proxy pass with URL rewrite |
| `/health` | `fastapi:8000` | No auth, for health checks |
| `/metrics` | `fastapi:8000` | Restricted to 10.0.0.0/8 |
| `/` (everything else) | `fastapi:8000` | SPA fallback |

---

# PART VII — REDIS OPERATIONS GUIDE

## 7.1 Key Namespace Reference

| Key Pattern | Purpose | TTL |
|------------|---------|-----|
| `historian:telemetry:{tid}:{pid}` | Telemetry input stream | MAXLEN 100k |
| `threshold:cache:{tid}:{pid}:{tag}` | Alarm threshold cache | 60s |
| `alarm:cooldown:{tid}:{pid}:{tag}:{sev}` | Alarm suppression | 300s |
| `ratelimit:{tid}:{bucket}` | Sliding window rate limit | 120s |
| `revoked:session:{sid}` | Revoked JWT sessions | 7 days |
| `ws:ticket:{ticket}` | Short-lived WS auth ticket | 30s |
| `ws\|broadcast\|{tid}\|{pid}` | Pub/Sub broadcast channel | N/A |

## 7.2 RedisInsight Integration

RedisInsight provides a GUI for inspecting all of the above. Access via:
```bash
# Add to docker-compose.yml:
redisinsight:
    image: redis/redisinsight:latest
    ports:
      - "5540:5540"
    networks:
      - industrial_net
```

Navigate to `http://localhost:5540`, connect to `redis:6379` (internal Docker network).

## 7.3 Redis Health Commands

```bash
# Check memory usage
docker exec piccadily-redis redis-cli INFO memory | grep used_memory_human

# Check connected clients
docker exec piccadily-redis redis-cli CLIENT LIST

# Monitor live commands (caution: verbose)
docker exec piccadily-redis redis-cli MONITOR

# Flush threshold cache (force re-read from DB after tag config change)
docker exec piccadily-redis redis-cli KEYS "threshold:cache:piccadily:*" | xargs redis-cli DEL
```

---

# PART VIII — TIMESCALEDB OPERATIONS GUIDE

## 8.1 Hypertable Health Queries

```sql
-- All hypertables with size and chunk count
SELECT
    hypertable_name,
    pg_size_pretty(total_bytes) AS total_size,
    pg_size_pretty(compressed_heap_size) AS compressed,
    num_chunks
FROM timescaledb_information.hypertables
ORDER BY total_bytes DESC;

-- Compression status
SELECT hypertable_name,
       before_compression_total_bytes,
       after_compression_total_bytes,
       round(after_compression_total_bytes::numeric /
             before_compression_total_bytes * 100, 1) AS pct
FROM timescaledb_information.hypertable_compression_stats
WHERE hypertable_name LIKE 'telemetry_%';

-- Check continuous aggregate refresh status
SELECT view_name, last_run_started_at, last_run_status
FROM timescaledb_information.jobs j
JOIN timescaledb_information.job_stats js USING (job_id)
WHERE application_name LIKE 'Continuous Aggregate%';

-- Tag count per group
SELECT 'latest' AS source, count(*) AS tags
FROM telemetry_latest WHERE tenant_id = 'piccadily';

-- Recent ingestion rate
SELECT date_trunc('minute', ts) AS minute, count(*) AS points
FROM telemetry_raw
WHERE ts > now() - interval '10 minutes'
GROUP BY minute ORDER BY minute DESC;
```

## 8.2 Slow Query Identification

```sql
-- From pg_stat_statements (must be enabled)
SELECT query, calls, mean_exec_time::int AS avg_ms, total_exec_time::int AS total_ms
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC
LIMIT 20;

-- Active queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND query_start < now() - interval '5 seconds'
ORDER BY duration DESC;
```

## 8.3 pgAdmin Integration

```bash
# Add to docker-compose.yml:
pgadmin:
    image: dpage/pgadmin4:latest
    environment:
        PGADMIN_DEFAULT_EMAIL: admin@piccadily.com
        PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    networks:
      - industrial_net
```

Navigate to `http://localhost:5050`, connect to `timescaledb:5432`.

---

# PART IX — GRAFANA OPERATIONS GUIDE

## 9.1 Datasource Configuration

The provisioned datasource in `grafana/provisioning/datasources/timescaledb.yml` connects via the `grafana_reader` role with read-only access. The password must match `GRAFANA_READER_PW` in `.env`.

## 9.2 Key Dashboard Queries

```sql
-- Live tag value (stat panel)
SELECT ts AS time, value
FROM telemetry_latest
WHERE tenant_id = 'piccadily'
  AND plant_id = 'BOILER_PLC_01'
  AND tag_name = 'TT-201'

-- Temperature trend (1-minute aggregates)
SELECT bucket AS time, avg_val, min_val, max_val
FROM telemetry_1min
WHERE tenant_id = 'piccadily'
  AND plant_id = 'BOILER_PLC_01'
  AND tag_name = 'TT-201'
  AND bucket BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY bucket

-- Active alarm count (stat, turns red when > 0)
SELECT count(*) FROM alarms
WHERE tenant_id = 'piccadily'
  AND alarm_state = 'ACTIVE'

-- Ingestion rate (from Prometheus metrics endpoint)
-- Configure Prometheus datasource pointing to http://fastapi:8000/metrics
-- historian_points_total counter → rate([5m])
```

## 9.3 Grafana Alert Configuration

```yaml
# grafana/provisioning/alerting/rules.yml (create this file)
apiVersion: 1
groups:
  - orgId: 1
    name: IngestionHealth
    folder: Industrial Alerts
    interval: 1m
    rules:
      - uid: ingestion-rate
        title: Telemetry Ingestion Stopped
        condition: B
        data:
          - refId: A
            queryType: ''
            relativeTimeRange: { from: 300, to: 0 }
            datasourceUid: piccadily_tsdb
            model:
              rawSql: |
                SELECT EXTRACT(EPOCH FROM now()) * 1000 AS time,
                       count(*) AS value
                FROM telemetry_raw
                WHERE ts > now() - interval '5 minutes'
                  AND tenant_id = 'piccadily'
```

---

# PART X — OBSERVABILITY IMPLEMENTATION PLAN

## 10.1 Current Observability Gaps

| Layer | Current State | Required |
|-------|--------------|----------|
| Metrics | `/metrics` Prometheus text endpoint (basic) | Full Prometheus scraping + Grafana panels |
| Tracing | None | OpenTelemetry spans for ingest pipeline |
| Logging | structlog JSON stdout | Loki log aggregation |
| Alerting | None | Grafana alerting on key metrics |
| Frontend perf | None | Web Vitals, WS latency tracking |

## 10.2 Prometheus Integration

Add to `docker-compose.yml`:
```yaml
prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    networks:
      - industrial_net
```

Create `prometheus/prometheus.yml`:
```yaml
global:
    scrape_interval: 15s

scrape_configs:
  - job_name: 'historian-backend'
    static_configs:
      - targets: ['fastapi:8000']
    metrics_path: /metrics
    scheme: http
```

## 10.3 Available Prometheus Metrics

The backend already exposes these at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `historian_points_total` | counter | Total telemetry points ingested |
| `historian_batches_total` | counter | Total ingestion batches |
| `historian_alarms_total` | counter | Total alarms generated |
| `historian_errors_total` | counter | Total unhandled errors |
| `historian_ws_connections` | gauge | Active WebSocket connections |
| `historian_redis_batches_processed` | counter | Redis stream batches consumed |
| `historian_redis_messages_processed` | counter | Redis stream messages consumed |
| `historian_uptime_seconds` | counter | Application uptime |
| `historian_tenant_points_total{tenant}` | counter | Per-tenant point count |

## 10.4 OpenTelemetry Integration (Phase 2)

```python
# backend/app/core/telemetry_otel.py (to be created)
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

def setup_telemetry(app):
    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint="http://tempo:4317"))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    AsyncPGInstrumentor().instrument()
    RedisInstrumentor().instrument()
```

## 10.5 Loki Log Aggregation

```yaml
# Add to docker-compose.yml
loki:
    image: grafana/loki:latest
    command: -config.file=/etc/loki/config.yml
    volumes:
      - ./loki/config.yml:/etc/loki/config.yml:ro
    ports:
      - "3100:3100"
    networks:
      - industrial_net

promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail/config.yml:/etc/promtail/config.yml:ro
    networks:
      - industrial_net
```

Promtail will scrape Docker container logs. Add Loki datasource in Grafana provisioning.

---

# PART XI — INCIDENT RESPONSE GUIDE

## 11.1 Incident Severity Levels

| Level | Description | Response Time |
|-------|------------|---------------|
| P0 | No telemetry flowing, all dashboards empty | 15 minutes |
| P1 | Partial data loss, >10% tags missing | 1 hour |
| P2 | Grafana down, alarms delayed | 4 hours |
| P3 | UI issues, non-critical performance | Next business day |

## 11.2 P0 Runbook — No Telemetry Flowing

```bash
# 1. Check all services are running
docker compose ps

# 2. Check backend health
curl http://localhost:8000/health

# 3. Check edge agent logs
docker compose logs edge-agent --since 5m  # if running in Docker
# OR check the process running piccadily_opc_edge_agent.py

# 4. Check Redis stream has data
docker exec piccadily-redis redis-cli XLEN "historian:telemetry:piccadily:BOILER_PLC_01"
# If 0: edge agent is not sending

# 5. Check consumer group is processing
docker exec piccadily-redis redis-cli XINFO GROUPS "historian:telemetry:piccadily:BOILER_PLC_01"
# Look at: "pending" count — if high, consumers are stuck

# 6. Check DB connection
docker compose logs fastapi | grep "db.connect_failed\|db.pools"

# 7. Restart backend (consumers will PEL-recover)
docker compose restart fastapi

# 8. Verify recovery
sleep 30
curl http://localhost:8000/metrics | grep historian_points_total
```

## 11.3 P1 Runbook — Missing Tags

```bash
# 1. Check telemetry_latest row count
docker exec piccadily-tsdb psql -U historian_user -d historian -c \
  "SELECT count(*) FROM telemetry_latest WHERE tenant_id='piccadily';"

# 2. If count is low, check tag routing rules
docker exec piccadily-tsdb psql -U historian_user -d historian -c \
  "SELECT pattern, target_table FROM tag_routing_rules WHERE tenant_id='piccadily' ORDER BY priority DESC;"

# 3. Check if tags are hitting telemetry_raw (unrouted)
docker exec piccadily-tsdb psql -U historian_user -d historian -c \
  "SELECT count(DISTINCT tag_name) FROM telemetry_raw WHERE ts > now() - interval '5 minutes';"

# 4. Clear tag router LRU cache (requires backend restart)
docker compose restart fastapi
```

## 11.4 Alarm Storm Prevention

The alarm cooldown (300s per tag+severity) prevents storms. If alarms are firing excessively:

```bash
# Check cooldown keys
docker exec piccadily-redis redis-cli KEYS "alarm:cooldown:piccadily:*" | wc -l

# Check active alarm count
docker exec piccadily-tsdb psql -U historian_user -d historian -c \
  "SELECT severity, count(*) FROM alarms WHERE alarm_state='ACTIVE'
   AND tenant_id='piccadily' GROUP BY severity;"

# Emergency: clear all cooldowns to reset suppression
docker exec piccadily-redis redis-cli KEYS "alarm:cooldown:piccadily:*" | \
  xargs docker exec piccadily-redis redis-cli DEL
```

---

# PART XII — MAINTENANCE GOVERNANCE STANDARDS

## 12.1 Architecture Governance Rules

### RULE-01: Single Source of Truth for Redis Keys
All Redis key patterns MUST be defined in `backend/app/core/redis_keys.py`. No magic strings elsewhere.

### RULE-02: No Duplicate Module Definitions
Each domain concept (Permission, auth, pagination) exists in exactly ONE module. Imports from that canonical location everywhere.

### RULE-03: Tenant Isolation at Every Query
Every DB query involving telemetry, alarm, or plant data MUST include `WHERE tenant_id = $1` using the value from `user.tenant_id`. The CI linter (`scripts/check_tenant_isolation.py`) enforces this.

### RULE-04: Stream Writer is the Only Ingest Path
All telemetry ingestion goes through `publish_batch_to_stream()`. Direct DB inserts at the API layer are forbidden (except seeding scripts).

### RULE-05: Background Tasks Never Block Responses
All database-heavy operations in the realtime path use `asyncio.create_task()`. Ingestion returns 202 immediately.

### RULE-06: No Plaintext Secrets in Frontend Bundle
API keys, JWT secrets, and connection strings must never appear in frontend source code.

## 12.2 Naming Conventions

### Backend
- Routes: `/api/v1/{domain}/{action}` — kebab-case for multi-word actions
- Functions: `snake_case`, async functions prefixed with no special marker
- Models: `PascalCase` Pydantic models
- DB columns: `snake_case`
- Redis keys: `{namespace}:{entity}:{id}` with pipe separator for Pub/Sub (`ws|broadcast|...`)

### Frontend
- Components: `PascalCase.tsx`
- Hooks: `use{Purpose}.ts`
- Stores: `use{Domain}Store.ts`
- Types: `PascalCase` interfaces in `shared/types/index.ts`
- API clients: `{domain}Api.ts` in `shared/api/`

## 12.3 WebSocket Protocol Standards

All WebSocket messages MUST conform to the discriminated union type in `frontend/src/shared/types/index.ts`:
```typescript
type WsMessage = WsTelemetryUpdate | WsSnapshot | WsAlarmEvent | WsAlarmAck | WsAlarmsClear;
```

The `type` field is the discriminator. No new message types without:
1. Adding to the Python backend broadcaster
2. Adding to the TypeScript union
3. Adding a handler in `useAppStore.handleWsMessage()`

## 12.4 Migration Standards

All DB schema changes use the Flyway-compatible migration naming: `V{n}__{description}.sql` in `timescaledb/`. Never modify `V1__init.sql` after deployment — create `V2__...sql`.

## 12.5 Docker Standards

- All services have `deploy.resources.limits.memory` set
- All services have `healthcheck` configured
- Production uses `docker-compose.prod.yml` overlays only (no code mounts)
- Never expose DB or Redis ports in production (`ports: []` override)

---

# PART XIII — ONBOARDING STANDARDS

## 13.1 New Developer Setup

```bash
# 1. Clone and configure
git clone https://github.com/hyontechnologies/industrial-telemetry-platform-init.git
cd industrial-telemetry-platform-init
cp .env.example .env
# Edit .env: fill DB_PASSWORD, SUPABASE_JWT_SECRET, SUPABASE_URL

# 2. Install pre-commit hooks
pip install pre-commit
pre-commit install

# 3. Start infrastructure
docker compose up -d timescaledb redis
sleep 30

# 4. Start backend
docker compose up -d fastapi

# 5. Verify backend
curl http://localhost:8000/health
# Expect: {"status":"ok","db":true,"redis":true}

# 6. Start edge simulator (local dev only)
python plant_simulator/run_externals.py
# This starts: Modbus simulator + OPC UA bridge + Edge agent

# 7. Start frontend dev server
cd frontend && npm ci && npm run dev
# Access: http://localhost:3000

# 8. Seed historical data (optional)
docker compose run --rm seeder
```

## 13.2 Local Dev Architecture Differences

| Aspect | Local Dev | Production |
|--------|----------|------------|
| Frontend | Vite dev server (port 3000) | Built into FastAPI static |
| API proxy | Vite proxy `/api` → localhost:8000 | Nginx proxy |
| Auth | Mock JWT (DEFECT-005) | Supabase JWT |
| Edge | plant_simulator/run_externals.py | Physical OPC UA + edge agent |
| SSL | None | Let's Encrypt via Nginx |

---

# PART XIV — SPECIALIZED AGENT PROMPTS

## Frontend Debugging Agent

```
You are debugging the Piccadily Industrial Historian React frontend.

Context:
- React 18 + Zustand + react-router-dom v7
- WebSocket managed by useWebSocket hook (frontend/src/shared/hooks/useWebSocket.ts)
- Global state in useAppStore (frontend/src/shared/stores/useAppStore.ts)
- Auth: LoginPage stores 'mock_jwt_token' which is rejected by backend (known defect)

Your task: [DESCRIBE SPECIFIC ISSUE]

Key files to examine:
1. frontend/src/shared/stores/useAppStore.ts - handleWsMessage() and latestValues
2. frontend/src/shared/hooks/useWebSocket.ts - connection and reconnect logic
3. frontend/src/app/layout.tsx - where WebSocket is initialized
4. frontend/src/features/dashboard/DashboardPage.tsx - where values are rendered

Check these specific bugs first:
1. Is the snapshot handler merging (spread existing state) or replacing state?
2. Is apiKey: 'changeme' in layout.tsx matching a real configured API key?
3. Is the backend actually receiving ingested data? (curl http://localhost:8000/health)
4. Is the 50-tag broadcast cap causing missing values?
```

## Backend WebSocket Debugging Agent

```
You are debugging the Piccadily Industrial Historian WebSocket system.

Architecture:
- WebSocket endpoint: /api/v1/ws/{tenant_id}/{plant_id}?api_key=X OR ?ticket=Y
- Broadcaster: backend/app/realtime/broadcaster.py (ConnectionManager)
- Uses Redis Pub/Sub pattern "ws|broadcast|{tid}|{pid}"
- Redis psubscribe("ws|broadcast|*") in _listen_to_redis background task

Pipeline:
1. POST /ingest → ingestion.py → ws_manager.broadcast() → Redis PUBLISH
2. broadcaster._listen_to_redis() receives → _local_fanout() → ws.send_json()

Common failure modes:
1. Redis Pub/Sub listener task crashed (check ws.pubsub_started log)
2. No WebSocket clients in the room (ws_manager.connection_count = 0)
3. Broadcaster sends to wrong channel (tenant/plant mismatch)
4. asyncio.create_task() swallowing exceptions silently

Debug commands:
redis-cli SUBSCRIBE "ws|broadcast|piccadily|BOILER_PLC_01"
redis-cli PUBLISH "ws|broadcast|piccadily|BOILER_PLC_01" '{"type":"telemetry","data":{}}'
```

## TimescaleDB Optimization Agent

```
You are optimizing TimescaleDB queries for the Piccadily historian.

Schema: 15 per-group hypertables + telemetry_latest + 4 continuous aggregates
Key tables: telemetry_temperature, telemetry_pressure, telemetry_latest, telemetry_1min

Optimization rules:
1. Always include tenant_id AND plant_id in WHERE clause (RLS + index)
2. Use continuous aggregates (telemetry_1min/5min/1hour/1day) for historical queries
3. Use telemetry_latest for current-value lookups (O(1) per tag)
4. Avoid UNION ALL across telemetry_all view in hot paths
5. Use time_bucket() with explicit chunk exclusion via ts range filters
6. Compression is active after 7 days — decompression needed for DELETE/UPDATE

Tag routing rules stored in tag_routing_rules table (tenant-scoped).
LRU cache (10k entries, 5-minute TTL) in backend/app/telemetry/tag_router.py.
Clear cache by restarting FastAPI.
```

## Redis Debugging Agent

```
You are debugging Redis usage in the Piccadily industrial historian.

Redis serves three purposes:
1. STREAMS (telemetry ingestion buffer): historian:telemetry:{tenant}:{plant}
   - Consumer groups: historian-writers (2 workers), historian-alarms (1 worker)
   - XREADGROUP with block=2000ms, count=2000
   - PEL recovery on startup (reads from "0" before switching to ">")

2. PUB/SUB (WebSocket fanout): ws|broadcast|{tenant}|{plant}
   - Pattern subscription: ws|broadcast|*
   - Published by ws_manager.broadcast() in ingestion.py and alarm acks

3. KEY-VALUE (caching): threshold:cache:*, alarm:cooldown:*, ratelimit:*, ws:ticket:*

Common failure modes:
1. Stream lag: XPENDING count high → consumers crashed, restart fastapi
2. Pub/Sub not working: pubsub_task cancelled → restart fastapi
3. Rate limit too aggressive: ratelimit:{tid}:{bucket} → check RATE_LIMIT_POINTS_PER_MIN in config
4. Threshold cache stale: clear with DEL threshold:cache:piccadily:BOILER_PLC_01:*

All key patterns defined in backend/app/core/redis_keys.py (canonical reference).
```

## Alarm Engine Development Agent

```
You are developing alarm features for the Piccadily historian.

Alarm engine location: backend/app/alarms/engine.py
Alarm consumer location: backend/app/alarms/consumer.py

Architecture:
- Runs independently from the DB writer (separate Redis consumer group)
- Evaluates thresholds from tag_metadata table (cached 60s in Redis)
- Cooldown suppression: 300s per (tenant, plant, tag, severity) via Redis SET NX
- Alarm IDs are deterministic UUID5 to prevent duplicates across restarts
- Alarm state machine: ACTIVE → ACKNOWLEDGED → CLEARED

Alarm broadcast: triggered by alarm ack in alarms/router.py → ws_manager.broadcast()
Frontend handles: {type:"alarm"} for new alarms, {type:"alarm_ack"} for acks

To add new alarm type:
1. Add to evaluate_alarms_for_batch() in engine.py
2. Add tag threshold fields to tag_metadata schema if needed
3. Add WS message type to frontend/src/shared/types/index.ts
4. Handle in useAppStore.handleWsMessage()
5. Render in AlarmsPage.tsx

Thresholds set via PUT /api/v1/tags/{tag_name}?plant_id=X (engineer+ role)
After update: evict_threshold_cache() is called automatically.
```

## Zustand State Management Agent

```
You are optimizing the Zustand state in the Piccadily historian frontend.

Store location: frontend/src/shared/stores/useAppStore.ts
Uses subscribeWithSelector middleware for fine-grained subscriptions.

State slices:
- AuthSlice: user, isAuthenticated
- PlantSlice: plants, selectedPlantId
- TelemetrySlice: latestValues (Record<tagName, TelemetryLatest>), connectionStatus
- AlarmSlice: activeAlarms, alarmCount, criticalCount
- UiSlice: sidebarCollapsed

Performance rules:
1. Never select the entire store in a component — always use a selector function
   GOOD: useAppStore((s) => s.latestValues)
   BAD:  useAppStore() and then .latestValues

2. Memoize derived values with useMemo in components
3. The latestValues object is dense (422+ keys) — avoid iterating in render without memoization
4. Use subscribeWithSelector for subscribing to specific slice changes in non-React code

Known defect: snapshot handler replaces latestValues instead of merging.
Fix: use (state) => ({latestValues: {...state.latestValues, ...newValues}}) pattern.

WebSocket messages flow: useWebSocket.onMessage → useAppStore.handleWsMessage → set() → React re-render
```

---

# PART XV — IMMEDIATE ACTION ITEMS (PRIORITIZED)

## P0 — Fix Before Any Production Load

| # | Defect | File | Impact |
|---|--------|------|--------|
| 1 | DEFECT-005: Mock auth | LoginPage.tsx | All API calls fail |
| 2 | DEFECT-004: Hardcoded API key | layout.tsx | Security breach |
| 3 | DEFECT-011: Snapshot replaces state | useAppStore.ts | Missing tag values |
| 4 | DEFECT-010: 50-tag broadcast cap | ingestion.py | Missing tag values |

## P1 — Fix Before Scaling

| # | Defect | File | Impact |
|---|--------|------|--------|
| 5 | DEFECT-001: Duplicate Permission | rbac.py | Silent type mismatch |
| 6 | DEFECT-002: Duplicate audit() | session.py | Dead code confusion |
| 7 | DEFECT-003: Dead stream_key() | redis_keys.py | Developer confusion |
| 8 | DEFECT-008: Dead scripts | refactor.py, fix_redis.py | Confusion |

## P2 — Operational Improvements

| # | Item | Priority |
|---|------|---------|
| 9 | Add Prometheus scraping | Required for SLA monitoring |
| 10 | Add Loki log aggregation | Required for incident analysis |
| 11 | Add Grafana alerting rules | Required for 24/7 ops |
| 12 | Implement pgAdmin/CloudBeaver | Required for DB ops without SSH |
| 13 | Add Portainer | Required for container ops GUI |
| 14 | DEFECT-007: require_plant_access | Potential FastAPI routing confusion |

---

# APPENDIX A — ENVIRONMENT VARIABLE REFERENCE

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | postgresql://... | asyncpg connection string |
| `REDIS_URL` | redis://redis:6379/0 | Redis connection |
| `SUPABASE_JWT_SECRET` | (required) | JWT validation |
| `SUPABASE_URL` | (required) | Supabase project URL |
| `EDGE_API_KEYS` | "" | Fallback API keys (hash:tenant format) |
| `CORS_ORIGINS` | localhost list | Allowed CORS origins |
| `REDIS_STREAM_PREFIX` | historian:telemetry: | Stream key prefix |
| `REDIS_CONSUMER_BATCH_SIZE` | 2000 | Messages per XREADGROUP call |
| `REDIS_CONSUMER_WORKERS` | 2 | DB writer worker count |
| `ALARM_COOLDOWN_SECONDS` | 300 | Alarm suppression window |
| `ALARM_CACHE_TTL` | 60 | Threshold cache TTL |
| `RATE_LIMIT_POINTS_PER_MIN` | 500000 | Per-tenant rate limit |
| `TELEMETRY_BATCH_MAX` | 500 | Max points per ingest request |
| `STALE_TAG_MINUTES` | 10 | Stale tag threshold |
| `DEBUG` | false | Enables /docs, /redoc, console logging |
| `ENVIRONMENT` | production | Affects logging format and middleware |
| `GRAFANA_ADMIN_PASSWORD` | (required) | Grafana UI login |
| `GRAFANA_READER_PW` | (required) | TimescaleDB grafana_reader password |
| `VITE_API_URL` | (optional) | Frontend API base (default: relative) |

---

*End of Industrial Operations Cloud — Production Maintenance & Governance Handbook v1.0*
*Generated by codebase intelligence audit on 2026-05-24*
*For Piccadily Agro Industries — Piccadily Industrial Historian v4.0*
