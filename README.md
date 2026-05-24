# Piccadily Industrial Historian (v4.0.0)

[![CI Pipeline](https://github.com/hyontechnologies/industrial-telemetry-platform-init/actions/workflows/ci.yml/badge.svg)](https://github.com/hyontechnologies/industrial-telemetry-platform-init/actions/workflows/ci.yml)
[![Docker Registry](https://img.shields.io/badge/Container%20Registry-GHCR-blue)](https://ghcr.io)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Platform Version](https://img.shields.io/badge/Version-v4.0.0--unified-orange)](CHANGELOG.md)

Welcome to the **Piccadily Industrial Historian** repository. This is a high-performance, local-first, multi-tenant Industrial IoT SaaS platform designed to capture, archive, analyze, and visualize high-frequency time-series data.

This README provides a structured, step-by-step overview of the entire codebase so you can understand how the system is built, how data flows, and how to operate it.

---

## Step 1: The Unified Architecture

The system uses a Unified Docker Architecture. The React/Vite client and FastAPI backend are built into a **single, unified, multi-stage Docker container**. This eliminates multi-port orchestration issues, improves network latency, and enables seamless relative routing.

### Key Components
- **Frontend**: React (v19), Vite (v8), Tailwind CSS, shadcn/ui.
- **Backend**: FastAPI (v0.111), Uvicorn, asyncpg.
- **Database**: TimescaleDB (PostgreSQL 15) with 15 specialized hypertables.
- **Queue**: Redis 7 for high-speed buffering (Redis Streams) and Pub/Sub.
- **Edge Collection**: Resilient Python Edge Agent with SQLite Store-and-Forward.

---

## Step 2: The Domain-Driven Backend (FastAPI)

The backend (`backend/app/`) is architected using Domain-Driven Design (DDD). It is modularized into distinct bounded contexts:

1. **`core/`**: Central utilities including exceptions, custom pagination classes, and OpenTelemetry observability.
2. **`identity/`**: Handles Dual-Authentication (Supabase JWT for UI users, SHA-256 API Keys for Edge Agents). Also manages RBAC (Role-Based Access Control).
3. **`plant/`**: Manages the multi-tenant physical hierarchy (Tenants -> Plants -> Assets).
4. **`telemetry/`**: The heart of the ingestion engine. It validates data, pushes to Redis Streams (`stream_writer.py`), and runs background tasks to bulk-insert into TimescaleDB (`stream_consumer.py`).
5. **`alarms/`**: A background Redis consumer (`engine.py`) that evaluates live telemetry against pre-configured thresholds and generates deterministic alarms.
6. **`realtime/`**: Manages high-performance WebSocket fanout (`broadcaster.py`) using Redis Pub/Sub to push data to active browser clients.
7. **`infra/`**: Houses the global connection pools for TimescaleDB and Redis (`database.py`, `redis.py`), and tracks internal Prometheus metrics.

---

## Step 3: The Feature-Based Frontend (React + Vite)

The frontend (`frontend/src/`) is an enterprise Single Page Application (SPA) utilizing a feature-driven architecture:

1. **`app/`**: Contains the global application layout, routing configuration (React Router v7), and centralized Context providers.
2. **`features/`**: Code is isolated by domain.
   - **`dashboard/`**: Overview metrics, recent alarms, and plant summaries.
   - **`telemetry/`**: Real-time rendering of tags using high-performance Apache ECharts and Recharts.
   - **`alarms/`**: Data tables for acknowledged and unacknowledged alarms.
   - **`identity/`**: Login components and session management.
3. **`shared/`**: Reusable components (buttons, dialogs, charts), API clients (`axios`), and global Zustand state stores.

The frontend uses zero-config relative networking (`fetch("/api/v1/...")`), meaning it works seamlessly behind the unified container's Nginx gateway.

---

## Step 4: The Data Ingestion Pipeline

Data flows from the factory floor to the cloud via a highly resilient pipeline:

1. **The Edge Agent (`edge-agent/`)**: Connects to on-premise OPC UA servers (or our local `plant_simulator`). It subscribes to tag changes and buffers them in a local SQLite Write-Ahead Log (WAL) database.
2. **Store and Forward**: If the internet goes down, the Edge Agent continues spooling to disk. When the connection returns, it uploads data in batches.
3. **Redis Buffering**: The backend accepts HTTP POST requests and immediately writes them to a Redis Stream (`XADD`) for durability, returning a `202 Accepted` to the Agent.
4. **TimescaleDB Bulk Insert**: Background Uvicorn workers pull from Redis Streams and use `asyncpg` binary `COPY` to insert thousands of points into TimescaleDB in microseconds, enforcing Row-Level Security (`SET set_config('app.current_tenant', ...)`).

---

## Step 5: How to Run the Platform

### Running the Unified Production Container
The easiest way to run the historian is to pull the pre-compiled unified image from the GitHub Container Registry:

```bash
docker pull ghcr.io/hyontechnologies/industrial-telemetry-platform-init-unified:latest

docker run -d -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DB_PASSWORD=your_secure_password \
  -e SUPABASE_JWT_SECRET=your_jwt_secret \
  ghcr.io/hyontechnologies/industrial-telemetry-platform-init-unified:latest
```
Visit `http://localhost:8000` to access the application.

### Running Local Development
To run the full stack locally (including TimescaleDB, Redis, Grafana, and hot-reloading components):

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
2. **Start Docker Compose:**
   ```bash
   docker compose up -d --build
   ```
3. **Start the Edge Simulator (optional):**
   ```bash
   python plant_simulator/run_externals.py
   ```
   This will start generating simulated boiler data and pushing it into your local backend.

---
*Built with ❤️ for Industrial Operations.*
