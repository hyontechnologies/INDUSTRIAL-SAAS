# Piccadily Industrial Historian + Digital Twin SaaS Platform

Piccadily Industrial Historian is a production-grade, local-first, multi-tenant Industrial IoT SaaS platform. Optimized to run on a single Azure VM (4GB RAM) under Docker Compose, the system achieves sub-second OPC UA telemetry ingestion, TimescaleDB hypertable persistence, background alarm checking, and real-time frontend monitoring.

---

## 🏗️ System Architecture & Components

```
                               ┌────────────────────────────────────────────────────────┐
                               │                    Industrial Edge                     │
                               │                                                        │
┌──────────────┐  Modbus TCP   │ ┌──────────────┐    OPC UA      ┌──────────────┐       │
│  Piccadily   │──────────────>│ │    OPC UA    │───────────────>│  Edge Agent  │       │
│ Boiler Sim   │               │ │    Bridge    │                │ (SQLite Buf) │       │
└──────────────┘               │ └──────────────┘                └──────────────┘       │
                               └────────────────────────────────────────┬───────────────┘
                                                                        │ HTTP Ingest (Nginx)
                                                                        ▼
                               ┌────────────────────────────────────────────────────────┐
                               │                 Cloud VM (Single Host)                 │
                               │                                                        │
                               │                        Nginx                           │
                               │                     (Port 80/443)                      │
                               │                           │                            │
                               │       ┌───────────────────┴───────────────────┐        │
                               │       ▼                                       ▼        │
                               │  FastAPI Backend ◄─── Pub/Sub ───►  Redis rate-limit   │
                               │  (Async Ingest)                     & WS Broadcaster   │
                               │       │                                       │        │
                               │       ▼ (asyncpg COPY)                        ▼        │
                               │  TimescaleDB (Hypertables) ◄────────── WebSocket       │
                               │  (Telemetry & Alarms)               (React Frontend)   │
                               └────────────────────────────────────────────────────────┘
```

### 1. The Telemetry Source Pipeline
- **Piccadily Boiler Simulator**: An industrial simulator replicating Modbus registers for a complete steam generation plant (boiler drum, furnace, economizer, air preheater, and turbine).
- **OPC UA Bridge**: Maps Modbus holding and input registers into an organized OPC UA Address Space containing **422 tags** grouped by process system (e.g., Feedwater, Fuel, Combustibles).
- **Edge Agent**: A resilient Python-based service subscribing to the OPC UA Bridge. It uses a local **SQLite buffer (`CursorDB`)** to store telemetry during network outages and uploads data in batches of 200 points with exponential backoff retry.

### 2. High-Performance FastAPI Backend
- Decomposed into a modular, clean structure using Pydantic Settings, asyncpg connection pooling, and structured logging.
- **Fast Ingest Hot-path**: Utilizes PostgreSQL's binary `COPY` protocol via `asyncpg` to bypass ORM overhead, processing thousands of points/sec.
- **Alarm Sweep Engine**: A continuous background task running every 10 seconds. It evaluates latest values against configured limits (`high_high`, `high`, `low`, `low_low`) and records events into the `alarms` hypertable.
- **WebSocket Broadcaster**: Distributes real-time tag updates to client subscription rooms utilizing Redis Pub/Sub.
- **Multi-Tenant Security**: Validates Supabase JWTs and enforces Row-Level Security (RLS) on PostgreSQL tables to isolate client and plant configurations.

### 3. TimescaleDB Time-Series Storage
- Employs TimescaleDB hypertables for `telemetry_raw`, `alarms`, and `audit_logs` to optimize writes and queries on time-series data.
- Built-in continuous aggregation schemas pre-calculate 1-minute, 5-minute, and hourly metrics for analytics.

### 4. Premium React TS Frontend Dashboard
- Responsive dark-theme dashboard styled with a modern **Glassmorphism UI** (Tailwind CSS v3 + PostCSS).
- **Advanced Charts**:
  - **Apache ECharts Gauges**: Radial pointer widgets with threshold warnings.
  - **Recharts Area Charts**: Real-time trend visualizers for key boiler variables.
- **Operational Controls**: Real-time tag browser, alarm history viewer, and hooks to **Acknowledge** or **Clear** triggered alerts.

---

## 📁 Repository Layout

```
.
├── .github/workflows/         # CI/CD Workflows (PR verification & Azure VM CD)
├── .pre-commit-config.yaml    # Pre-commit git hooks
├── backend/                   # FastAPI backend server
│   ├── app/                   # App source code (config, db, auth, alarms, etc.)
│   │   ├── routers/           # Router endpoints (telemetry, ws, grafana, alarms)
│   │   └── main.py            # FastAPI entry point
│   ├── tests/                 # Backend pytest suite
│   └── Dockerfile             # Production container definition
├── edge-agent/                # Standalone Edge collector
├── timescaledb/               # Database SQL schemas & seeds
├── nginx/                     # Reverse proxy configuration
├── grafana/                   # Grafana pre-provisioned dashboards
├── frontend/                  # React TS + Vite frontend
├── ruff.toml                  # Ruff linter config
├── run_externals.py           # Unified runner for local edge simulation
└── docker-compose.yml         # Dev docker orchestration definition
```

---

## ⚡ Development & Launch Guide

### 1. Prerequisites
- **Python 3.11** (with virtual environment recommended)
- **Node.js 18+**
- **Docker Desktop** (running on host machine)

### 2. Quickstart Script (Simulator, Bridge, & Agent)
To start the Modbus Simulator, OPC UA Bridge, and Edge Agent simultaneously with a single command:
```bash
python run_externals.py
```

### 3. Docker Infrastructure & Backend
Start all containerized services (TimescaleDB, Redis, FastAPI, Nginx, Grafana):
1. Copy `.env.example` to `.env` and configure credentials.
2. Run:
   ```bash
   docker compose up -d --build
   ```

### 4. React Frontend Development
Install dependencies and run the Vite local development server:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🛡️ Pre-commit Hooks, Linting, & Code Quality

The project enforces strict code quality checks using **Ruff** and **pre-commit** hooks.

### 1. Running the Linter
To scan python codebase for violations:
```bash
python -m ruff check .
```

### 2. Auto-fixing violations
To run the linter and format your python code automatically:
```bash
python -m ruff check --fix .
python -m ruff format .
```

### 3. Pre-commit Hook Integration
Pre-commit checks are active. Whenever you commit code, it will automatically run:
- Trailing Whitespace cleanup
- End-of-file formatting
- YAML Syntax checking
- Ruff check & format

To manually trigger pre-commit checks on all files:
```bash
python -m pre_commit run --all-files
```

---

## 🧪 Verification & CI/CD Pipelines

### 1. Automated Tests
You can run the pytest suite inside the backend workspace:
```bash
cd backend
pytest
```

### 2. GitHub Actions Integration Check
- **CI Pipeline (`.github/workflows/ci.yml`)**: Triggered on every pull request and push to the `main` branch. It compiles code and runs backend unit tests to prevent regression.
- **CD Pipeline (`.github/workflows/deploy.yml`)**: Automatically deploys the latest codebase to the target Azure VM instance via SSH key secrets and triggers a Docker Compose build.
