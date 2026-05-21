# Piccadily Industrial Historian (v4.0.0)

[![CI Pipeline](https://github.com/hyontechnologies/industrial-telemetry-platform-init/actions/workflows/ci.yml/badge.svg)](https://github.com/hyontechnologies/industrial-telemetry-platform-init/actions/workflows/ci.yml)
[![Docker Registry](https://img.shields.io/badge/Container%20Registry-GHCR-blue)](https://ghcr.io)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Platform Version](https://img.shields.io/badge/Version-v4.0.0--unified-orange)](CHANGELOG.md)

Piccadily Industrial Historian is a high-performance, local-first, multi-tenant Industrial IoT SaaS platform designed to capture, archive, analyze, and visualize high-frequency time-series data. Specifically optimized to operate efficiently on single-host systems (e.g., a single 4GB RAM cloud VM), the platform merges high-speed industrial protocols with modern web interfaces.

Version 4.0 merges the React/Vite client and FastAPI backend into a **single, unified, multi-stage Docker container**, eliminating multi-port orchestration issues, improving network latency, and enabling seamless, relative routing for high-throughput time-series streaming.

### ✨ What's New in the Latest Update
* **Enhanced Security & Auth**: Implemented WebSocket Ticket Pattern for secure WebSocket connections without exposing JWTs in URLs. Added Redis-backed session tracking for JWT revocation and enforced strict Database existence checks on endpoints.
* **Database & Ingestion Optimization**: Split `asyncpg` into dedicated read and write connection pools to prevent read-heavy queries from blocking real-time telemetry ingestion. Fixed alarm deduplication using deterministic UUIDs.
* **Resilience & Safety**: Implemented Redis Stream PEL (Pending Entries List) recovery on startup to claim messages from potentially dead consumers. Added explicit allowlist validation for telemetry endpoint intervals.
* **DevOps Clean-Up**: Removed legacy monolithic files, renamed schema initializers, and updated CI/CD pipelines to ensure Docker deployments depend strictly on CI success.

---

## 🏗️ System Architecture

```
                                 ┌────────────────────────────────────────────────────────┐
                                 │                 Industrial Edge (PLC)                  │
                                 │                                                        │
  ┌──────────────┐  Modbus TCP   │ ┌──────────────┐    OPC UA      ┌──────────────┐       │
  │  Piccadily   │──────────────>│ │    OPC UA    │───────────────>│  Edge Agent  │       │
  │ Boiler Sim   │               │ │    Bridge    │                │ (SQLite WAL) │       │
  └──────────────┘               │ └──────────────┘                └──────────────┘       │
                                 └────────────────────────────────────────┬───────────────┘
                                                                          │ HTTP Ingest (Nginx Proxy)
                                                                          ▼ (Port 80/443)
                                 ┌────────────────────────────────────────────────────────┐
                                 │              Unified Web App Container                 │
                                 │                                                        │
                                 │                     Nginx Gateway                      │
                                 │                 (Rate Limit & SSL)                     │
                                 │                           │                            │
                                 │                           ▼                            │
                                 │               FastAPI (Uvicorn Workers)                │
                                 │              ├─ Serve API routes                       │
                                 │              ├─ Stream WebSockets                      │
                                 │              └─ Serve React Static Assets (SPA)        │
                                 │                           │                            │
                                 │        ┌──────────────────┴──────────────────┐         │
                                 │        ▼ (XADD to Stream)                    ▼         │
                                 │   Redis 7 Ingest Buffer                 TimescaleDB    │
                                 │   (Stream Consumer Groups)              (15 Hypertables)
                                 └────────────────────────────────────────────────────────┘
```

---

## 🛠️ Framework-by-Framework Implementation Details

Every component of the Piccadily Historian has been engineered from the ground up to support high-frequency telemetry, low-latency client visualization, and absolute security:

### 1. Frontend Client: React (v19) + Vite (v8) + TS (v6)
* **Glassmorphism UI**: Built with a sleek, premium dark theme tailored for operations rooms. Styling is managed via Tailwind CSS v3.4 and PostCSS, incorporating responsive grids, layout backdrops, and active status animations.
* **Vibrant Visualizations**:
  * **Apache ECharts**: Renders dynamic radial gauges with threshold alerts for steam drum levels, feed water temperatures, and furnace drafts.
  * **Recharts**: Renders real-time, scrolling double-area charts representing complex variables like superheater outlets and speeds.
* **Zero-Config Relative Networking**: Configured with a relative path architecture (`fetch("/api/v1/...")` and `new WebSocket("ws://" + window.location.host + "/api/v1/ws/...")`). This automatically inherits the protocol, domain, and port of the host window.
* **SPA Routing Stability**: Integrates client-side React Router navigation. When pages (such as `/alarms` or `/dashboard`) are reloaded, the host FastAPI server gracefully falls back to `index.html` to prevent browser 404 errors.

### 2. Application Server: FastAPI (v0.111) + Uvicorn (v0.30)
* **Asynchronous Lifespan**: Starts database connections, Redis streams, pub/sub listeners, and runs separate concurrent background tasks on startup, draining them gracefully during container teardown.
* **Uvicorn Optimization**: Configured to run with `uvloop` (high-performance event loop written in Cython) and `httptools` (fast HTTP parser), operating behind multiple workers.
* **Token Bucket Rate-Limiter**: Features custom sliding-window rate-limiting at the HTTP layer, preventing denial-of-service from misconfigured edge devices.
* **Dual Authentication Core**: Authenticates REST requests using standard `Authorization: Bearer <JWT>` headers for dashboard users, and `X-API-Key` headers for machine-to-machine agents. WebSocket connections authenticate instantly via query parameters.
* **Permissions-Based RBAC**: Enforces modular access control utilizing a `Permission` enum mapped to viewer, operator, engineer, and administrator roles.

### 3. Queue Buffer: Redis (v7-Alpine)
* **Ingest Buffer (Redis Streams)**: Ingest routes execute high-speed `XADD` operations to push telemetry batches to Redis, returning an immediate HTTP `202 Accepted` response.
* **Stream Consumer Group Workers**: Two background worker threads read from the stream via `XREADGROUP`, chunking messages, executing DB writes, and sending acknowledgments (`XACK`).
* **Pub/Sub Fanout**: A pub/sub broker handles client-specific channels, fanning out live telemetry instantly to all active WebSocket connections across different Uvicorn processes.
* **Metrics Ingestion Tracker**: Exposes Redis stream lengths and pending counts under `/health` and Prometheus formats.

### 4. Database Layer: TimescaleDB (PostgreSQL 15)
* **Per-Group Hypertables (15 Tables)**: Replaced a single monolithic table with 15 specialized hypertables organized by tag group (e.g., `telemetry_temperature`, `telemetry_pressure`, `telemetry_flow_totalizer`).
* **Storage Compression & Retention**:
  * High-frequency tables are compressed after 7 days and deleted after 1 year.
  * Long-term totalizers (`telemetry_flow_totalizer`) are compressed after 30 days and retained for 5 years.
* **Binary Ingestion (asyncpg COPY)**: Background consumers bypass standard SQL `INSERT` structures, utilizing the high-speed PostgreSQL binary `COPY` protocol via `asyncpg` to load massive data chunks in microseconds.
* **Row-Level Security (RLS)**: Enforced across all tenant tables. Every query queries the DB using active session variables (`SET app.current_tenant`), isolating tenant data at the storage layer.

### 5. Resilient Collector: Edge Agent (Python + SQLite)
* **OPC UA Core**: Connects securely to on-site OPC UA servers and subscribes to tag changes.
* **SQLite Store-and-Forward**: Injects data into a local `buffer.db` SQLite database using Write-Ahead Logging (WAL) first.
* **Loss-of-Link Resiliency**: If connection to the cloud backend is lost, data continues spooling to disk. Once connection is restored, a background spooler replays data sequentially with exponential backoff retry.

---

## ⚠️ Architectural Gaps & Production Recommendations

While version 4.0.0 represents a production-grade historian, the following items represent current architecture gaps to address before enterprise scaling:

1. **Active-Active Redis High Availability**: Currently runs a single Redis node. In production, this should be transitioned to a Redis Sentinel or Redis Cluster setup to ensure continuous queue buffering.
2. **Cold-Path Object Storage Archiving (Data Lake)**: Ingested data remains in TimescaleDB indefinitely based on retention. Integrating a cold-path archiver that dumps old data into compressed Parquet files on AWS S3 or Azure Blob Storage would cut database storage costs.
3. **OPC UA Certificate Management**: The Edge Agent currently uses basic username/password auth. Enforcing strict PKI certificate-based validation for all edge-to-bridge integrations is recommended.
4. **SSO Identity Provider (OIDC)**: While Supabase JWT auth is fully implemented, enterprise deployments should wire FastAPI auth routes directly to corporate identity systems like Okta, Keycloak, or Active Directory.
5. **Continuous Aggregate Aggregation for Per-Group Tables**: Continuous aggregates are provisioned on `telemetry_raw`. Creating specialized materializations for core groups (e.g., flow, rpm, voltage) would optimize large-scale analytical reports.

---

## 📁 Repository Structure

```
.
├── .github/workflows/         # GitHub Actions workflows (CI checks & Deploy Builder)
├── backend/                   # Combined Web Application folder
│   ├── app/                   # FastAPI Codebase (Lifespan, Auth, Routers)
│   ├── tests/                 # Integration and unit pytest suite
│   └── Dockerfile             # Multi-stage Unified Web App Dockerfile
├── frontend/                  # React TS + Vite source code (bundled inside Docker)
├── edge-agent/                # Edge OPC UA collector & PLC Boiler Simulator
├── timescaledb/               # TimescaleDB initialization schemas & seed data
├── nginx/                     # Gateway Nginx reverse proxy configuration
├── api_integration_guide.md   # Specialized guide for frontend and custom clients
├── run_externals.py           # Local simulator runner
└── docker-compose.yml         # Dev Docker orchestration file
```

---

## 🔌 Frontend Engineer Quickstart & Docker Guide

If you are a front-end or integrations engineer looking to run the entire backend stack locally and connect your custom front-end interface, follow these steps.

### 1. Downloading the Dockerfile from a Release
To let your team download the production `Dockerfile` or compose files without pulling the whole repository, they can fetch them directly from the **GitHub Releases** page or query them using standard HTTP requests:

* **Download via Raw URL**:
  ```bash
  curl -sSL https://raw.githubusercontent.com/hyontechnologies/industrial-telemetry-platform-init/main/backend/Dockerfile -o Dockerfile
  ```
* **Download via GitHub CLI**:
  ```bash
  gh release download v4.0.0-unified -p "Dockerfile"
  ```

### 2. Pulling and Running the Pre-Built Unified Container (GHCR)
Our CI/CD pipeline pushes the compiled web container containing **both the APIs and React frontend** directly to the GitHub Container Registry. You can run it instantly without compiling code:

1. **Pull the latest image**:
   ```bash
   docker pull ghcr.io/hyontechnologies/industrial-telemetry-platform-init-unified:latest
   ```
2. **Run the entire stack in one command**:
   ```bash
   docker run -d -p 8000:8000 \
     -e ENVIRONMENT=production \
     -e DB_PASSWORD=your_secure_password \
     -e SUPABASE_JWT_SECRET=your_jwt_secret \
     ghcr.io/hyontechnologies/industrial-telemetry-platform-init-unified:latest
   ```
3. Open your browser to [http://localhost:8000](http://localhost:8000). The React App will render, communicating seamlessly with the APIs and WebSockets running on that same port.

---

## ⚡ Development & Local Orchestration

If you want to run the full historian stack, including TimescaleDB, Redis, and Nginx locally:

### 1. copy configuration files
Copy the environment template and configure your local parameters:
```bash
cp .env.example .env
```

### 2. Launch Local Containers
Start the infrastructure (Postgres, Redis, API + Static Files, Nginx, Grafana):
```bash
docker compose up -d --build
```

### 3. Launch Local Edge Simulator
To run the OPC UA bridge, boiler simulator, and the SQLite resilient Edge Agent:
```bash
python run_externals.py
```
Data will automatically begin flowing from the local simulator, buffering inside `buffer.db`, and uploading into the local container stack!
