

| INDUSTRIAL DIGITAL TWIN & CLOUD HISTORIAN Agent Product Requirements Document Piccadily Industrial SaaS Platform Version 1.0  â€¢  Full-Stack \+ DevOps  â€¢  Coding Agent Ready |
| :---: |

| Document Type  Agent PRD Platform  Piccadily Industrial Historian v2.0 Target Agent  Claude Code / Cursor / Aider Date  2025 | Status  Active Development Architecture  Monorepo, Docker Compose Deployment  Local-first \-\> Azure VM Team Size  5 engineers (startup MVP) |
| :---- | :---- |

| 01 | Executive Summary & Project Vision What we are building and why |
| :---: | :---- |

This document is a complete Agent PRD for implementing the Piccadily Industrial Digital Twin and Cloud Historian SaaS Platform. It provides precise, unambiguous implementation instructions for a coding agent (Claude Code, Cursor, or Aider) to build the full production system without requiring additional clarification.

## System Philosophy

The platform is a lightweight industrial historian SaaS inspired by the architecture philosophy of Ignition SCADA, Canary Historian, AVEVA Historian, and OSIsoft PI â€” but designed specifically for:

* Startup-scale infrastructure (single Azure VM, 4 GB RAM)

* 5-engineer development team

* Docker Compose-based deployment (no Kubernetes)

* Local-first development workflow (test everything locally before cloud deployment)

* OPC UA as the primary industrial data source

* Multi-tenant SaaS with industrial RBAC and Row-Level Security

## Platform Capabilities

| Capability | Description |
| :---- | :---- |
| **Industrial Historian** | Time-series storage for 422+ OPC UA tags via TimescaleDB hypertables with 4-tier aggregation |
| **Real-time Streaming** | WebSocket telemetry broadcast to React dashboards with \<500ms latency |
| **Alarm Engine** | DB-driven threshold evaluation with cooldown, deduplication, and audit trail |
| **Digital Twin** | P\&ID SVG overlays with live telemetry bindings per plant asset |
| **Multi-tenant SaaS** | Full tenant isolation via RBAC roles and PostgreSQL Row-Level Security |
| **Edge Connectivity** | OPC UA subscription agent with Tailscale VPN, batch upload, and reconnect logic |
| **Grafana Integration** | Native PostgreSQL datasource with 4-tier continuous aggregate views |
| **AI-Ready Telemetry** | Structured schema for future anomaly detection and predictive maintenance |

| 02 | Final Project Folder Structure Monorepo layout the coding agent must create |
| :---: | :---- |

| AGENT INSTRUCTION Create this exact folder structure. Do not deviate. Every file listed must be created with the content specified in subsequent sections. |
| :---- |

| industrial-platform/                    \<- monorepo root \+-  backend/ |   \+-  app/ |   |   \+-  main.py                     \<- FastAPI app factory \+ lifespan |   |   \+-  config.py                   \<- pydantic-settings Settings class |   |   \+-  database.py                 \<- asyncpg pool factory \+ get\_db |   |   \+-  auth.py                     \<- Supabase JWT \+ API key auth |   |   \+-  models.py                   \<- Pydantic request/response schemas |   |   \+-  ingestion.py                \<- COPY-based bulk insert pipeline |   |   \+-  alarms.py                   \<- Alarm engine \+ background sweep |   |   \+-  broadcaster.py              \<- WebSocket ConnectionManager |   |   \+-  metrics.py                  \<- Prometheus-compatible counters |   |   \+-  routers/ |   |       \+-  telemetry.py            \<- /api/v1/telemetry/\* |   |       \+-  alarms.py               \<- /api/v1/alarms/\* |   |       \+-  tags.py                 \<- /api/v1/tags/\* |   |       \+-  plants.py               \<- /api/v1/plants/\* |   |       \+-  admin.py                \<- /api/v1/admin/\* |   |       \+-  websocket.py            \<- /ws/{tenant}/{plant} |   |       \+-  grafana.py              \<- /grafana/\* SimpleJSON compat |   \+-  tests/ |   |   \+-  test\_ingestion.py |   |   \+-  test\_alarms.py |   |   \+-  test\_auth.py |   \+-  Dockerfile |   \+-  requirements.txt | \+-  edge-agent/ |   \+-  edge\_agent.py                   \<- OPC UA subscriber \+ batch uploader |   \+-  Dockerfile |   \+-  requirements.txt |   \+-  .env.example | \+-  frontend/ |   \+-  src/ |   |   \+-  main.tsx |   |   \+-  router.tsx                  \<- TanStack Router routes |   |   \+-  api/                        \<- React Query hooks |   |   |   \+-  telemetry.ts |   |   |   \+-  alarms.ts |   |   |   \+-  plants.ts |   |   \+-  hooks/ |   |   |   \+-  useHistorianSocket.ts   \<- WebSocket hook with reconnect |   |   \+-  pages/ |   |   |   \+-  Overview.tsx |   |   |   \+-  Dashboard.tsx |   |   |   \+-  Historian.tsx |   |   |   \+-  AlarmCenter.tsx |   |   |   \+-  DigitalTwin.tsx |   |   \+-  components/ |   |   |   \+-  LiveTagCard.tsx |   |   |   \+-  TrendChart.tsx |   |   |   \+-  AlarmRow.tsx |   |   |   \+-  PIDView.tsx |   |   \+-  lib/ |   |       \+-  supabase.ts             \<- Supabase auth client |   \+-  package.json |   \+-  vite.config.ts |   \+-  tsconfig.json |   \+-  Dockerfile | \+-  timescaledb/ |   \+-  init.sql                        \<- All tables, hypertables, aggregates, RLS | \+-  grafana/ |   \+-  provisioning/ |   |   \+-  datasources/timescaledb.yml |   |   \+-  dashboards/dashboard.yml |   \+-  dashboards/ |       \+-  boiler\_plant.json | \+-  nginx/ |   \+-  nginx.conf | \+-  .github/ |   \+-  workflows/ |       \+-  ci.yml                      \<- Test on PR |       \+-  deploy.yml                  \<- Deploy to Azure VM on main | \+-  docker-compose.yml                  \<- Local development (all services) \+-  docker-compose.prod.yml             \<- Production overrides \+-  .env.example \+-  .gitignore \+-  README.md |
| :---- |

| 03 | Development Strategy: Local-First Build and validate locally before any cloud deployment |
| :---: | :---- |

| CRITICAL RULE The entire platform MUST be built and validated locally using Docker Compose before any Azure VM deployment. Cloud deployment happens only after every local validation gate passes. |
| :---- |

## Phase Gates

| Gate | Local Validation Required | Proceed To |
| :---- | :---- | :---- |
| **Gate 1** | Edge agent \-\> FastAPI ingestion working, TimescaleDB storing data | Gate 2 |
| **Gate 2** | Grafana connected, dashboards showing live data | Gate 3 |
| **Gate 3** | WebSocket streaming to React frontend working | Gate 4 |
| **Gate 4** | Alarm engine firing, RBAC enforced, audit log writing | Gate 5 |
| **Gate 5** | All Docker Compose services stable for 1hr under load | Azure VM Deploy |

## Local Docker Compose Services

| Service | Image / Build | Port | Purpose |
| :---- | :---- | :---- | :---- |
| **timescaledb** | timescale/timescaledb:latest-pg15 | 5432 | Historian database |
| **fastapi** | ./backend (build) | 8000 | API \+ ingestion \+ WS |
| **edge-agent** | ./edge-agent (build) | â€” | OPC UA \-\> FastAPI |
| **frontend** | ./frontend (build) | 5173 | React dev server (Vite) |
| **grafana** | grafana/grafana-oss:latest | 3001 | Dashboard visualization |
| **redis** | redis:7-alpine | 6379 | Cache \+ rate limiting |
| **nginx** | nginx:1.25-alpine | 80 | Reverse proxy (prod only) |
| **simulator** | ./simulator (build) | â€” | PyModbus boiler sim (dev) |

| 04 | FastAPI Backend Architecture Modular async Python backend â€” exact implementation spec |
| :---: | :---- |

## Module Responsibility Map

| Module | Responsibility |
| :---- | :---- |
| **main.py** | App factory, middleware registration, lifespan (pool \+ alarm sweep task) |
| **config.py** | pydantic-settings Settings: DATABASE\_URL, SUPABASE\_JWT\_SECRET, EDGE\_API\_KEYS, CORS\_ORIGINS, rate limits |
| **database.py** | asyncpg pool (min=2, max=8), JSONB codec, get\_db() dependency |
| **auth.py** | \_decode\_supabase\_jwt(), \_verify\_edge\_api\_key() SHA-256, get\_current\_user(), require\_role() factory |
| **models.py** | TelemetryPoint, TelemetryBatch (with dedup validator), AlarmAckRequest, TagMetadataUpdate, PlantCreate |
| **ingestion.py** | copy\_records\_to\_table() hot path, executemany fallback, \_upsert\_latest(), ingest\_telemetry\_batch() |
| **alarms.py** | \_get\_thresholds() with 60s cache, \_check\_cooldown() 5-min suppression, evaluate\_alarms\_for\_batch(), \_alarm\_sweep\_loop() |
| **broadcaster.py** | ConnectionManager: connect/disconnect/broadcast per (tenant,plant) tuple, dead socket cleanup |
| **metrics.py** | IngestionMetrics counters, prometheus\_text() output, error tracking |

## API Endpoint Inventory

| Method | Endpoint | Auth | Description |
| :---- | :---- | :---- | :---- |
| **GET** | /health | Public | DB ping, WS count, uptime, version |
| **GET** | /metrics | Internal | Prometheus text exposition |
| **POST** | /api/v1/telemetry/ingest | API Key / JWT | COPY bulk insert, 500 pt max, 202 Accepted |
| **GET** | /api/v1/telemetry/latest | JWT | Latest values from telemetry\_latest |
| **GET** | /api/v1/telemetry/history | JWT | Time-bucket history, auto agg selection |
| **GET** | /api/v1/telemetry/multi-history | JWT | Multi-tag pivot for React correlation charts |
| **GET** | /api/v1/telemetry/stats | JWT | Min/max/avg/stddev for N hours |
| **GET** | /api/v1/alarms/active | JWT | Unacknowledged alarms with filters |
| **POST** | /api/v1/alarms/ack | JWT (operator+) | Ack alarm \+ write alarm\_history \+ audit |
| **GET** | /api/v1/alarms/history | JWT | Paginated alarm history with filters |
| **GET** | /api/v1/alarms/summary | JWT | Alarm KPI counts by severity |
| **GET** | /api/v1/tags | JWT | List tag\_metadata for plant |
| **PUT** | /api/v1/tags/{name} | JWT (engineer+) | Upsert tag thresholds \+ evict cache |
| **GET** | /api/v1/plants | JWT | List plants for tenant |
| **POST** | /api/v1/plants | JWT (admin) | Create / upsert plant |
| **GET** | /api/v1/plants/{id}/summary | JWT | Live KPI tile data for plant |
| **GET** | /api/v1/admin/tenants | JWT (admin) | List tenants |
| **GET** | /api/v1/admin/audit-log | JWT (admin) | Audit log with limit |
| **GET** | /api/v1/admin/ingestion-stats | JWT (admin) | Live ingestion counters |
| **WS** | /ws/{tenant}/{plant} | JWT or API Key | Telemetry stream \+ snapshot on connect |
| **GET** | /grafana/ | None | SimpleJSON health check |
| **POST** | /grafana/search | None | Tag name search for Grafana |
| **POST** | /grafana/query | None | Time-series query using agg views |

| 05 | TimescaleDB Schema & Data Architecture All tables, hypertables, aggregates, RLS â€” exact SQL spec |
| :---: | :---- |

| AGENT INSTRUCTION Execute timescaledb/init.sql on first container start. The file is mounted as /docker-entrypoint-initdb.d/init.sql in the timescaledb container. |
| :---- |

## Database Tables

| Table | Type | Purpose |
| :---- | :---- | :---- |
| **tenants** | Regular | SaaS tenant registry, plan, config JSONB |
| **plants** | Regular | Plant config per tenant (boiler/wtp/stp/power) |
| **tag\_metadata** | Regular | 422+ tag definitions, alarm thresholds, OPC UA NodeId |
| **users** | Regular | Local mirror of Supabase user metadata \+ role |
| **telemetry\_raw** | HYPERTABLE (1d chunks) | Raw ingestion: ts, tenant, plant, tag, value, quality |
| **telemetry\_latest** | Regular | Latest value per tag (O(1) lookup for WS snapshot) |
| **telemetry\_1min** | Continuous Aggregate | 1-minute buckets: avg/min/max/first/last |
| **telemetry\_5min** | Continuous Aggregate | 5-minute buckets: avg/min/max/last |
| **telemetry\_1hour** | Continuous Aggregate | 1-hour buckets: avg/min/max/stddev |
| **telemetry\_1day** | Continuous Aggregate | 1-day buckets: avg/min/max â€” 10yr retention |
| **alarms** | HYPERTABLE (7d chunks) | Alarm events with severity, threshold value, ack state |
| **alarm\_history** | Regular | Per-alarm lifecycle audit trail (ACK/CLEAR/ESCALATE) |
| **audit\_logs** | HYPERTABLE (30d chunks) | All user/system actions with user context \+ detail JSON |

## Retention & Compression Policy Summary

| Table | Compress After | Retain For | Segment By |
| :---- | :---- | :---- | :---- |
| **telemetry\_raw** | 7 days | 90 days | tenant, plant, tag |
| **telemetry\_1min** | â€” | 1 year | â€” |
| **telemetry\_5min** | â€” | 2 years | â€” |
| **telemetry\_1hour** | â€” | 5 years | â€” |
| **telemetry\_1day** | â€” | 10 years | â€” |
| **alarms** | 30 days | 2 years | tenant, plant |
| **audit\_logs** | â€” | 1 year | â€” |

## 4-tier Aggregate Auto-Selection Logic

The history endpoint automatically selects the correct aggregate based on the query time span:

| Time Span Requested    \-\>  Source Table â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ \<= 6 hours             \-\>  telemetry\_1min  (raw resolution) \<= 48 hours            \-\>  telemetry\_5min  (shift analysis) \<= 30 days (720 hrs)   \-\>  telemetry\_1hour (daily trends) \> 30 days              \-\>  telemetry\_1day  (long-term historian) |
| :---- |

## PostgreSQL Low-Memory Settings (4 GB VM)

| max\_connections           \= 50 shared\_buffers            \= 256MB      \# 25% of DB alloc effective\_cache\_size      \= 768MB work\_mem                  \= 4MB        \# 50 conn x 4MB \= 200MB peak maintenance\_work\_mem      \= 64MB wal\_buffers               \= 16MB max\_worker\_processes      \= 4 max\_parallel\_workers      \= 2 timescaledb.max\_background\_workers \= 2 checkpoint\_completion\_target \= 0.9 random\_page\_cost          \= 1.1 effective\_io\_concurrency  \= 100 autovacuum\_max\_workers    \= 2 |
| :---- |

| 06 | Telemetry Ingestion Pipeline COPY-based bulk insert with alarm evaluation and WS broadcast |
| :---: | :---- |

## Ingestion Hot Path (6 Steps)

| Step | Operation | Detail |
| :---- | :---- | :---- |
| **1** | **Validation** | Pydantic parses batch; NaN/Inf guard; tag dedup (keep latest per tag per batch) |
| **2** | **Rate Limit** | In-memory RateLimiter: \>5000 points/tenant/min \-\> 429\. No Redis needed. |
| **3** | **Raw Insert** | copy\_records\_to\_table() \-\> telemetry\_raw. Falls back to executemany on UniqueViolationError. |
| **4** | **Latest Upsert** | executemany INSERT ... ON CONFLICT UPDATE WHERE ts \< EXCLUDED.ts \-\> telemetry\_latest |
| **5** | **Alarm Eval** | For each point: fetch threshold (DB cache 60s) \-\> check deadband \-\> check 5-min cooldown \-\> insert alarm |
| **6** | **WS Broadcast** | asyncio.create\_task(broadcast()) â€” fire-and-forget, never blocks ingestion return |

## Edge Agent \-\> FastAPI Protocol

| POST /api/v1/telemetry/ingest Header: X-API-Key: \<raw\_key\> Content-Type: application/json {   "tenant\_id": "piccadily",   "plant\_id":  "PICCADILY\_PLANT\_01",   "points": \[     { "tag\_name": "TT-201", "value": 485.3, "quality": "GOOD",       "timestamp": "2025-01-15T10:30:00.000Z", "unit": "degC",       "source\_id": "ns=2;s=BOILER\_PLC\_01.TT-201" },     ...   \] } Response: 202 Accepted { "ok": true, "inserted": 47, "alarms": 2 } |
| :---- |

## Alarm Thresholds â€” Industrial Tag Spec

| Tag | Description | LoLo | Lo | Hi | HiHi | Unit |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **TT-201** | SH Outlet Temp | 100 | 150 | 480 | 520 | degC |
| **TT-202** | SH Steam Temp | 100 | 150 | 480 | 520 | degC |
| **TT-301** | Furnace Exit | 100 | 150 | 490 | 530 | degC |
| **PT-201** | Main Steam Press | 10 | 20 | 95 | 105 | bar |
| **LT-001** | Steam Drum Level | 20 | 30 | 70 | 80 | mm |
| **LT-201** | Deaerator Level | 10 | 20 | 85 | 95 | % |
| **LT-202** | Hot Well Level | 10 | 20 | 85 | 95 | % |
| **DT-301** | Furnace Draught | \-20 | \-15 | \-3 | \-2 | mmWC |
| **FT-101** | Feed Water Flow | 5 | 10 | 100 | 120 | t/h |
| **FD Fan RPM** | FD Fan Speed | 100 | 200 | 1450 | 1500 | RPM |
| **SA Fan RPM** | SA Fan Speed | 100 | 200 | 1450 | 1500 | RPM |
| **ID Fan RPM** | ID Fan Speed | 100 | 200 | 1450 | 1500 | RPM |

| 07 | Security Architecture: Auth, RBAC & RLS Dual-auth, role hierarchy, and row-level isolation |
| :---: | :---- |

## Dual Authentication System

| Method | Used By | Implementation |
| :---- | :---- | :---- |
| **X-API-Key Header** | Edge agents / machine-to-machine | SHA-256 hash stored in EDGE\_API\_KEYS env var. Raw key only in edge .env. |
| **Authorization: Bearer** | Human users via Supabase Auth | Supabase JWT validated with HS256 \+ audience "authenticated". Claims: app\_metadata.tenant\_id, app\_metadata.role |

## RBAC Role Hierarchy

| Role | View Data | Ack Alarm | Edit Tags | Manage Plant | Admin | Notes |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **edge\_agent** | â€” | â€” | â€” | â€” | â€” | POST /ingest only |
| **viewer** | âœ“ | â€” | â€” | â€” | â€” | Read-only dashboards |
| **operator** | âœ“ | âœ“ | â€” | â€” | â€” | Alarm acknowledgement |
| **engineer** | âœ“ | âœ“ | âœ“ | â€” | â€” | Tag threshold changes |
| **plant\_manager** | âœ“ | âœ“ | âœ“ | âœ“ | â€” | Plant config |
| **admin** | âœ“ | âœ“ | âœ“ | âœ“ | âœ“ | Full tenant access |

## Supabase Auth Integration

| 1\. User logs in via Supabase Auth (email/password) 2\. Supabase returns access\_token (JWT, HS256) 3\. Frontend: Authorization: Bearer \<access\_token\> 4\. FastAPI \_decode\_supabase\_jwt():       jwt.decode(token, SUPABASE\_JWT\_SECRET,                  algorithms=\["HS256"\], audience="authenticated") 5\. Extract: payload\["app\_metadata"\]\["tenant\_id"\]             payload\["app\_metadata"\]\["role"\] Set claims in Supabase SQL editor:   UPDATE auth.users   SET raw\_app\_meta\_data \= raw\_app\_meta\_data ||   '{"tenant\_id": "piccadily", "role": "engineer"}'   WHERE email \= 'engineer@piccadily.com'; |
| :---- |

| 08 | WebSocket Real-Time Streaming Architecture Per-tenant/plant rooms, compact broadcast format, React hook |
| :---: | :---- |

## WebSocket Message Protocol

| Message Type | Payload Format |
| :---- | :---- |
| **snapshot** | On connect: {type:"snapshot", plant\_id, count, data:{tag:{v,q,u,t},...}} |
| **telemetry** | On ingest: {type:"telemetry", plant\_id, ts, count, alarms, data:{tag:{v,q,t},...}\[\<=50\]} |
| **alarm\_ack** | On ack: {type:"alarm\_ack", alarm\_id, acked\_by} |
| **pong** | Keepalive: server sends "pong" every 30s; client sends "ping" |

## React WebSocket Hook â€” Key Behaviors

| useHistorianSocket(tenantId, plantId):   \+-- URL: wss://HOST/ws/{tenant}/{plant}?token={JWT}   \+-- On open:   setConnected(true), clear retry timer   \+-- On message: setLastUpdate(parsedMsg)   \+-- On close:  setConnected(false), retry after 3000ms   \+-- Cleanup:   ws.close() \+ clearTimeout on unmount   \+-- Keepalive: setInterval(ping, 25000\) IMPORTANT: Do NOT use useState for individual tag values. Use a single Record\<string, TagValue\> ref updated via useRef to avoid React re-render thrashing on high-frequency telemetry. |
| :---- |

| 09 | React 18 Frontend Architecture TanStack Query \+ Router, WebSocket, Grafana embedding |
| :---: | :---- |

## Page Hierarchy

| Route | Page Content & Behavior |
| :---- | :---- |
| **/login** | Supabase Auth UI, redirects to /overview on success |
| **/overview** | Multi-plant KPI tiles, active alarm count badges, plant selector |
| **/plants/:id/dashboard** | Live tag cards via telemetry\_latest poll \+ WS updates |
| **/plants/:id/historian** | Multi-tag trend charts, date picker, interval selector, CSV export |
| **/plants/:id/alarms** | Active alarm table (TanStack Table), ACK modal, alarm history tab |
| **/plants/:id/twin** | SVG P\&ID with live tag overlays, alarm heatmap, asset click popups |
| **/plants/:id/grafana** | Embedded Grafana iframe (grafana/d/{dashId}) with JWT pass-through |
| **/admin/users** | RBAC user management, invite flow, role assignment |
| **/admin/tags** | Tag metadata editor, threshold config per plant |

## React Query Hook Patterns

| // Latest values â€” poll every 5s fallback to WS useTelemetryLatest(plantId)  \-\> queryKey: \['telemetry','latest',plantId\]                                refetchInterval: 5000                                staleTime: 2000 // Tag history â€” long cache, refetch on range change useTagHistory(plantId, tag, h) \-\> queryKey: \['telemetry','history',plantId,tag,h\]                                   staleTime: 60000 // Multi-tag pivot for correlation chart useMultiHistory(plantId, tags\[\]) \-\> queryKey: \['telemetry','multi',plantId,tags\] // Active alarms â€” poll every 10s useActiveAlarms(plantId)     \-\> queryKey: \['alarms','active',plantId\]                                refetchInterval: 10000 // Mutations useAckAlarm()  \-\> POST /api/v1/alarms/ack  \-\> invalidate \['alarms','active'\] useCreatePlant() \-\> POST /api/v1/plants     \-\> invalidate \['plants'\] |
| :---- |

| 10 | Grafana Configuration Native TimescaleDB datasource, dashboard provisioning, key queries |
| :---: | :---- |

## Datasource Configuration

| \# grafana/provisioning/datasources/timescaledb.yml apiVersion: 1 datasources:   \- name: TimescaleDB     type: postgres     url:  timescaledb:5432     user: grafana\_reader     secureJsonData:       password: "GRAFANA\_READER\_PW"     jsonData:       database: historian       sslmode:  disable       timescaledb: true       postgresVersion: 1500       maxOpenConns: 5       maxIdleConns: 3     editable: false |
| :---- |

## Required Dashboard Panels

| Panel | Type | Source Query |
| :---- | :---- | :---- |
| **Main Steam Pressure** | Gauge (0-120 bar) | telemetry\_1min WHERE tag\_name='PT-201' |
| **Steam Drum Level** | Gauge (0-100 mm) | telemetry\_1min WHERE tag\_name='LT-001' |
| **Furnace Temperature** | Time Series | telemetry\_5min WHERE tag\_name='TT-301' |
| **FD/SA/ID Fan RPM** | Multi-line Series | telemetry\_5min WHERE tag\_name IN (fan tags) |
| **Feed Water Flow** | Stat with sparkline | telemetry\_1min WHERE tag\_name='FT-101' |
| **Furnace Draught** | Time Series (negative) | telemetry\_1min WHERE tag\_name='DT-301' |
| **Active Alarms** | Stat (red if \>0) | SELECT count(\*) FROM alarms WHERE acked=false |
| **Alarm Frequency** | Bar Chart | alarms GROUP BY hour, severity |

| 11 | Docker Networking & Environment Strategy Network topology, service discovery, env var architecture |
| :---: | :---- |

## Docker Network Topology

| Networks defined in docker-compose.yml: industrial\_net (bridge, internal):   timescaledb:5432    \<- never exposed to host publicly   fastapi:8000        \<- proxied by nginx   redis:6379          \<- internal only   grafana:3001        \<- proxied by nginx   frontend:5173       \<- served by nginx in prod edge\_net (host mode in prod / bridge in dev):   edge-agent          \<- needs Tailscale route to OPC UA server Port exposure (host):   Dev:   5432, 8000, 3001, 5173 (direct, no nginx)   Prod:  80, 443 via nginx only (all others internal) |
| :---- |

## Environment Variable Architecture

| Variable | Purpose \+ Example |
| :---- | :---- |
| **DATABASE\_URL** | postgresql://historian\_app:PW@timescaledb:5432/historian |
| **SUPABASE\_JWT\_SECRET** | JWT signing secret from Supabase project \-\> Settings \-\> API |
| **SUPABASE\_URL** | https://xxxx.supabase.co |
| **EDGE\_API\_KEYS** | piccadily:\<sha256\_hex\_of\_raw\_key\> (comma-separated for multi-tenant) |
| **CORS\_ORIGINS** | http://localhost:3000,https://yourdomain.com |
| **DB\_PASSWORD** | Strong random password used by historian\_app role |
| **GRAFANA\_READER\_PW** | Password for grafana\_reader Postgres role |
| **GRAFANA\_ADMIN\_PASSWORD** | Grafana admin UI password |
| **EDGE\_API\_KEY\_RAW** | Raw API key â€” only in edge-agent .env, never in backend |
| **OPCUA\_ENDPOINT** | opc.tcp://100.x.x.x:4840/piccadily/boiler (Tailscale IP) |
| **VITE\_API\_URL** | https://yourdomain.com or http://localhost:8000 in dev |
| **VITE\_WS\_URL** | wss://yourdomain.com or ws://localhost:8000 in dev |
| **VITE\_SUPABASE\_URL** | Supabase project URL for frontend auth client |
| **VITE\_SUPABASE\_ANON\_KEY** | Supabase anon key for frontend auth client |

| 12 | GitHub Actions CI/CD Pipeline Test \-\> Build \-\> Deploy to Azure VM via SSH |
| :---: | :---- |

## Pipeline Stages

| Stage | Trigger | Actions |
| :---- | :---- | :---- |
| **ci.yml** | Pull Request to main | Ruff lint, pytest (with asyncpg mock), frontend tsc \--noEmit, Vite build check |
| **deploy.yml: test** | Push to main | Full test suite must pass before deploy |
| **deploy.yml: build** | After test | docker build backend \+ frontend, push to GHCR with :latest and :sha tags |
| **deploy.yml: deploy** | After build | SSH into Azure VM, git pull, docker compose pull, zero-downtime fastapi restart, health check |
| **deploy.yml: verify** | After deploy | curl /health \-\> must return db:true within 30s or rollback |

## GitHub Secrets Required

| Secret Name | Value |
| :---- | :---- |
| **AZURE\_VM\_HOST** | VM public IP or DNS name |
| **AZURE\_VM\_USER** | ubuntu (or your SSH user) |
| **AZURE\_SSH\_PRIVATE\_KEY** | Full private key PEM (public key in VM authorized\_keys) |
| **GHCR\_TOKEN** | GitHub Personal Access Token with packages:write scope |

## deploy.yml â€” Deploy Step Script

| ssh script on Azure VM:   cd /opt/industrial-platform   git pull origin main   docker compose \-f docker-compose.yml \-f docker-compose.prod.yml pull fastapi   docker compose \-f docker-compose.yml \-f docker-compose.prod.yml \\     up \-d \--no-deps \--build fastapi   sleep 15   curl \-sf http://localhost:8000/health | python3 \-c \\     "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d\['db'\] else 1)"   docker image prune \-f |
| :---- |

| 13 | Azure VM Production Deployment Step-by-step VM setup, SSL, swap, disk, Tailscale |
| :---: | :---- |

## VM Specifications

| Parameter | Value |
| :---- | :---- |
| **VM Size** | Standard\_B2s (2 vCPU, 4 GB RAM) â€” minimum |
| **OS** | Ubuntu 22.04 LTS |
| **Disk** | OS: 30 GB Standard SSD \+ Data: 128 GB Premium SSD P10 (500 IOPS) |
| **Swap** | 2 GB swapfile (critical on 4 GB RAM) |
| **Network** | Static public IP, NSG: ports 22/80/443 only |
| **VPN** | Tailscale mesh for OPC UA edge agent connectivity |

## Deployment Checklist

1. **VM Setup:** apt update, Docker install, Tailscale install, ufw rules
2. **Swap:** fallocate \-l 2G /swapfile && mkswap \+ swapon
3. **Data Disk:** format, mount /mnt/data, move Docker volumes
4. **SSL:** certbot certonly \--standalone \-d YOUR\_DOMAIN
5. **Repo:** git clone into /opt/industrial-platform
6. **Env:** cp .env.example .env && fill all values
7. **Start:** docker compose \-f docker-compose.yml \-f docker-compose.prod.yml up \-d
8. **Verify:** curl https://YOUR\_DOMAIN/health \-\> must return {status:ok, db:true}
9. **Grafana:** Open https://YOUR\_DOMAIN/grafana \-\> verify datasource \-\> test panel query
10. **Edge:** Deploy edge-agent on plant network, test POST /ingest flow

| 14 | Coding Agent Implementation Roadmap Exact sprint-by-sprint build order for Claude Code / Cursor |
| :---: | :---- |

| AGENT INSTRUCTION Follow this roadmap strictly in order. Complete and validate each sprint before starting the next. Each sprint has explicit success criteria that must be verified before proceeding. |
| :---- |

## Sprint 1 â€” Project Scaffold (Day 1\)

| Tasks:   1\. Create exact folder structure from Section 02   2\. Create docker-compose.yml with all 7 services   3\. Create timescaledb/init.sql (all tables from Section 05\)   4\. Create backend/requirements.txt with pinned versions   5\. Create .env.example with all variables from Section 11   6\. Create .gitignore Success Criteria:   \[OK\] docker compose up \--build succeeds (all services healthy)   \[OK\] TimescaleDB init.sql runs without errors   \[OK\] psql SELECT count(\*) FROM timescaledb\_information.hypertables \-\> 3   \[OK\] psql SELECT count(\*) FROM tag\_metadata \-\> 16 |
| :---- |

## Sprint 2 â€” FastAPI Modular Backend (Day 2-3)

| Tasks:   1\. Implement all modules: config, database, auth, models, ingestion,      alarms, broadcaster, metrics   2\. Implement all routers: telemetry, alarms, tags, plants, admin,      websocket, grafana   3\. Register routers in main.py with lifespan   4\. Write pytest tests for ingestion and auth Success Criteria:   \[OK\] GET /health \-\> {status:ok, db:true}   \[OK\] POST /api/v1/telemetry/ingest with X-API-Key \-\> 202   \[OK\] SELECT count(\*) FROM telemetry\_raw \> 0   \[OK\] SELECT count(\*) FROM telemetry\_latest \> 0   \[OK\] pytest passes all tests |
| :---- |

## Sprint 3 â€” Edge Agent \+ Live Ingestion (Day 3-4)

| Tasks:   1\. Update edge\_agent.py: Tailscale endpoint, batch config   2\. Verify OPC UA \-\> edge agent \-\> FastAPI \-\> TimescaleDB flow   3\. Verify alarm evaluation fires for out-of-range tags   4\. Verify WS broadcast received by test client Success Criteria:   \[OK\] 422 OPC UA tags visible in telemetry\_latest   \[OK\] GET /api/v1/telemetry/latest \-\> count: 422   \[OK\] Trigger alarm by pushing OPC UA value above HiHi   \[OK\] GET /api/v1/alarms/active \-\> count: 1   \[OK\] WS message received within 500ms of ingest |
| :---- |

## Sprint 4 â€” Grafana Dashboards (Day 4-5)

| Tasks:   1\. Verify grafana\_reader role has SELECT on all aggregate views   2\. Test datasource connection \-\> green tick   3\. Create all 8 required dashboard panels from Section 10   4\. Verify continuous aggregates populated (may need manual refresh) Success Criteria:   \[OK\] Grafana datasource test: success   \[OK\] Steam Pressure gauge shows live data   \[OK\] Alarm count stat turns red when active alarms exist   \[OK\] Fan RPM multi-line trend shows last 1 hour of data |
| :---- |

## Sprint 5 â€” React Frontend (Day 5-7)

| Tasks:   1\. Scaffold Vite \+ React 18 \+ TypeScript project   2\. Install: @tanstack/react-query, @tanstack/react-router,               @tanstack/react-table, recharts, @supabase/supabase-js   3\. Implement all API hooks from Section 09   4\. Implement useHistorianSocket with reconnect   5\. Implement pages: Overview, Dashboard, Historian, AlarmCenter   6\. Implement components: LiveTagCard, TrendChart, AlarmRow Success Criteria:   \[OK\] Login page \-\> Supabase auth \-\> redirect to /overview   \[OK\] Dashboard shows live tag values updating in real-time   \[OK\] Historian page shows 24h trend for TT-201   \[OK\] AlarmCenter shows active alarms; ACK button works   \[OK\] WS connected indicator shows green |
| :---- |

## Sprint 6 â€” Local Validation Gate (Day 7-8)

| Full integration test before Azure VM deployment: Load test:   python stress\_test.py  (500 batches x 100 points \= 50k points)   Target: \>=5000 points/sec, P99 \<200ms, 0 dropped Reconnect test:   docker compose restart timescaledb   \-\> FastAPI recovers within 30s (pool reconnect) WS stress test:   Open 20 browser tabs \-\> all receive telemetry updates RBAC test:   viewer JWT \-\> POST /alarms/ack \-\> 403   operator JWT \-\> POST /alarms/ack \-\> 200 Memory test:   docker stats \-\> timescaledb \< 400MB, fastapi \< 200MB each worker |
| :---- |

## Sprint 7 â€” Azure VM Deployment (Day 8-10)

| Tasks:   1\. Provision Azure VM (B2s, Ubuntu 22.04)   2\. Execute VM setup checklist from Section 13   3\. Configure GitHub Secrets (Section 12\)   4\. Push to main \-\> GitHub Actions deploys automatically   5\. Verify health endpoint from public URL   6\. Deploy edge agent on plant network   7\. End-to-end test: OPC UA \-\> cloud historian Success Criteria:   \[OK\] GET https://YOUR\_DOMAIN/health \-\> {status:ok, db:true}   \[OK\] Grafana accessible at https://YOUR\_DOMAIN/grafana   \[OK\] React app loads at https://YOUR\_DOMAIN   \[OK\] 422 tags flowing from plant \-\> cloud historian   \[OK\] SSL certificate valid (A grade on SSL Labs) |
| :---- |

| 15 | Improved System Prompt for Coding Agents Copy-paste this prompt to initialize a coding agent session |
| :---: | :---- |

The following prompt is an improved, agent-ready version of the original system description. Use it to initialize a new Claude Code, Cursor, or Aider session.

| HOW TO USE Paste this entire prompt as the first message in your coding agent session. The agent will use it as the authoritative specification for the entire platform build. |
| :---- |

## Improved Agent Initialization Prompt

| SYSTEM ROLE You are a senior industrial IoT SaaS architect and full-stack engineer. You are implementing a production-grade Industrial Digital Twin and Cloud Historian SaaS platform. Follow this PRD exactly. Build in the order specified. Do not deviate from the folder structure, API contracts, or database schema defined here. PROJECT Piccadily Industrial Historian â€” a lightweight SaaS historian inspired by Ignition/AVEVA/OSIsoft PI. Single Azure VM deployment (4 GB RAM), Docker Compose, local-first development strategy. TECH STACK (do not substitute) Backend: FastAPI 0.111+, asyncpg 0.29+, pydantic-settings 2+, python-jose, structlog, uvloop, httptools Database: TimescaleDB (PostgreSQL 15\) â€” hypertables \+ continuous aggregates Frontend: React 18, TypeScript, Vite, TanStack Query v5, TanStack Router v1, TanStack Table v8, Recharts Auth: Supabase Auth (JWT only â€” no other Supabase features) Infra: Docker Compose, nginx, GitHub Actions, Azure VM, Tailscale VPN Monitoring: Grafana (local, native PostgreSQL datasource) ARCHITECTURE RULES (non-negotiable) DO NOT use Kubernetes, Kafka, Redis (except for caching if explicitly specified), microservices, or any cloud-managed databases DO NOT generate Kubernetes manifests, Helm charts, or Terraform DO NOT split services beyond what is defined in the folder structure DO follow the local-first development strategy: build locally, validate all 6 gates, then deploy to Azure DO use copy\_records\_to\_table() for telemetry\_raw bulk insert (not executemany) DO use in-memory rate limiting (no Redis required for MVP) DO implement alarm cooldown (5 minutes per tag) to prevent storm flooding DO implement the 4-tier aggregate auto-selection in history endpoints BUILD ORDER (must follow exactly) Sprint 1: Folder structure \+ Docker Compose \+ TimescaleDB init.sql Sprint 2: FastAPI modular backend (all modules \+ routers) Sprint 3: Edge agent integration \+ live OPC UA ingestion Sprint 4: Grafana dashboard provisioning Sprint 5: React frontend with TanStack \+ WebSocket Sprint 6: Local validation gate (load test \+ RBAC test \+ memory test) Sprint 7: Azure VM deployment \+ CI/CD pipeline KEY INDUSTRIAL CONTEXT OPC UA Hierarchy: Objects \-\> PICCADILY\_PLANT\_01 \-\> BOILER\_PLC\_01 Namespace URI: urn:piccadily:boilerbridge Critical tags: TT-201/202/301 (temp), PT-201 (pressure), LT-001/201/202 (levels), DT-301 (draught), FT-101 (flow), fan RPMs All thresholds are pre-defined in init.sql tag\_metadata table and in the fallback ALARM\_THRESHOLDS dict in alarms.py SUCCESS DEFINITION The platform is complete when: 422 OPC UA tags flow from the plant network through the edge agent to TimescaleDB, appear on Grafana dashboards and the React frontend in real-time, trigger alarms with audit trail, and the system runs stably on a 4 GB Azure VM for 24+ hours under production load. |
| :---- |

| DOCUMENT COMPLETE This PRD is the single source of truth for the Piccadily Industrial Historian platform. All implementation decisions must reference this document. Version 1.0. |
| :---: |
