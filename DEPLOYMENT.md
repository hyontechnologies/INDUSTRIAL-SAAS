# Piccadily Industrial Historian — Unified Deployment & Architecture Guide v3.0

> **Stack:** FastAPI · TimescaleDB · Grafana · Nginx · Supabase JWT · Docker Compose
> **Target:** Single Azure VM (Standard B2s — 2 vCPU / 4 GB RAM), Ubuntu 24 LTS

---

## 1. Folder Structure

```
industrial-platform/
├── backend-app/
│   ├── Dockerfile
│   ├── main.py                  ← upgraded v3.0
│   ├── requirements.txt
│   └── .env                     ← never commit; use Azure Key Vault secrets in CI/CD
│
├── edge-agent/
│   ├── Dockerfile
│   ├── edge-agent.py
│   └── requirements.txt
│
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── timescaledb.yml  ← auto-configure PG datasource
│       └── dashboards/
│           └── boiler.json      ← exported dashboard JSON
│
├── nginx/
│   ├── nginx.conf
│   └── ssl/                     ← Let's Encrypt certs (managed by certbot)
│
├── docker-compose.yml           ← v3.0
├── schema.sql                   ← v3.0 — run once on DB init
├── postgresql.conf              ← 4 GB RAM tuning
└── .env.example
```

---

## 2. Environment Variables (.env)

```dotenv
# Database
DB_PASSWORD=your_strong_password_here

# Supabase
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
SUPABASE_URL=https://your-project.supabase.co

# Edge agents (env-var fallback; DB api_keys table is primary)
# Format: tenant_id:sha256(raw_key),...
# Generate: python3 -c "import hashlib,secrets; k=secrets.token_urlsafe(32); print(k,'->',hashlib.sha256(k.encode()).hexdigest())"
EDGE_API_KEYS=piccadily:abc123sha256hash

# CORS (comma-separated)
CORS_ORIGINS=https://your-app.azurewebsites.net,http://localhost:3000

# Trusted hosts (comma-separated; set to * to disable)
TRUSTED_HOSTS=your-vm-domain.eastus.cloudapp.azure.com

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your_grafana_password
GRAFANA_ROOT_URL=https://your-vm-domain/grafana
```

---

## 3. postgresql.conf (4 GB RAM Tuning)

Create `postgresql.conf` in the project root — mounted read-only into TimescaleDB container:

```ini
# 4 GB RAM optimized TimescaleDB configuration
shared_buffers                 = 512MB
effective_cache_size           = 1536MB
maintenance_work_mem           = 128MB
work_mem                       = 16MB
max_connections                = 80
checkpoint_completion_target   = 0.9
wal_buffers                    = 16MB
default_statistics_target      = 100
random_page_cost               = 1.1   # SSD
effective_io_concurrency       = 200   # SSD
max_worker_processes           = 4
max_parallel_workers_per_gather= 1
max_parallel_workers           = 2
timescaledb.max_background_workers = 4
log_min_duration_statement     = 500   # log slow queries >500ms
```

---

## 4. Nginx Configuration

```nginx
# nginx/nginx.conf
worker_processes auto;
events { worker_connections 1024; }

http {
    gzip on;
    gzip_types text/plain application/json text/csv;

    # Rate limiting (protect ingest endpoint at network level)
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

    upstream backend  { server backend:8000; }
    upstream grafana  { server grafana:3000; }

    # HTTP → HTTPS redirect
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-vm-domain.eastus.cloudapp.azure.com;

        ssl_certificate     /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header X-Content-Type-Options nosniff always;

        # FastAPI backend
        location /api/ {
            limit_req zone=api burst=200 nodelay;
            proxy_pass         http://backend;
            proxy_http_version 1.1;
            proxy_set_header   Host              $host;
            proxy_set_header   X-Real-IP         $remote_addr;
            proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
            proxy_read_timeout 60s;
        }

        # WebSocket
        location /ws/ {
            proxy_pass         http://backend;
            proxy_http_version 1.1;
            proxy_set_header   Upgrade    $http_upgrade;
            proxy_set_header   Connection "upgrade";
            proxy_read_timeout 3600s;
        }

        # Grafana (embed support)
        location /grafana/ {
            rewrite ^/grafana/(.*) /$1 break;
            proxy_pass         http://grafana;
            proxy_set_header   Host $host;
        }

        # Health check (no auth)
        location /health {
            proxy_pass http://backend;
        }

        # Prometheus metrics (restrict to internal / monitoring IP)
        location /metrics {
            allow 10.0.0.0/8;
            deny  all;
            proxy_pass http://backend;
        }
    }
}
```

---

## 5. Backend Dockerfile

```dockerfile
# backend-app/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps for asyncpg binary wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user for security
RUN useradd -m -u 1001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app",
     "--host", "0.0.0.0",
     "--port", "8000",
     "--workers", "2",
     "--loop", "uvloop",
     "--http", "httptools",
     "--log-level", "warning",
     "--no-access-log"]
```

---

## 6. requirements.txt

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
uvloop==0.21.0
httptools==0.6.4
asyncpg==0.30.0
pydantic==2.10.3
pydantic-settings==2.6.1
structlog==24.4.0
python-jose[cryptography]==3.3.0
```

---

## 7. Azure VM Deployment Steps

### 7a. Provision VM

```bash
# Azure CLI
az vm create \
  --resource-group piccadily-rg \
  --name piccadily-historian \
  --image Ubuntu2404 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard

# Open ports
az vm open-port --resource-group piccadily-rg --name piccadily-historian --port 80 --priority 100
az vm open-port --resource-group piccadily-rg --name piccadily-historian --port 443 --priority 110
```

### 7b. Install Docker on VM

```bash
ssh azureuser@<VM_IP>

# Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker

# Docker Compose plugin
sudo apt-get install -y docker-compose-plugin

# Verify
docker compose version
```

### 7c. Clone & Configure

```bash
git clone https://github.com/your-org/industrial-platform.git
cd industrial-platform
cp .env.example .env
nano .env   # Fill all secrets
```

### 7d. TLS Certificate (Let's Encrypt)

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone -d your-vm-domain.eastus.cloudapp.azure.com

# Certs land at /etc/letsencrypt/live/your-domain/
# Copy to project
sudo cp /etc/letsencrypt/live/your-domain/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain/privkey.pem   nginx/ssl/
sudo chown $(whoami):$(whoami) nginx/ssl/*

# Auto-renew cron
echo "0 3 * * * certbot renew --quiet && docker compose restart nginx" | sudo crontab -
```

### 7e. First Launch

```bash
# Pull images and build
docker compose build

# Start database first, let it initialize schema
docker compose up -d timescaledb
sleep 30

# Verify schema was applied
docker compose exec timescaledb psql -U historian_user -d historian \
  -c "SELECT hypertable_name FROM timescaledb_information.hypertables;"

# Start full stack
docker compose up -d

# Check all services healthy
docker compose ps
```

---

## 8. GitHub Actions CI/CD

```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure VM

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host:     ${{ secrets.VM_HOST }}
          username: ${{ secrets.VM_USER }}
          key:      ${{ secrets.VM_SSH_KEY }}
          script: |
            cd ~/industrial-platform
            git pull origin main
            docker compose build backend
            docker compose up -d --no-deps backend
            sleep 10
            curl -sf http://localhost:8000/health || exit 1
            echo "Deploy OK"
```

**GitHub Secrets to configure:**
- `VM_HOST` — VM public IP or domain
- `VM_USER` — `azureuser`
- `VM_SSH_KEY` — private SSH key

---

## 9. Grafana Setup

### Datasource Provisioning (`grafana/provisioning/datasources/timescaledb.yml`)

```yaml
apiVersion: 1
datasources:
  - name: TimescaleDB
    type: postgres
    url: timescaledb:5432
    database: historian
    user: grafana_reader
    secureJsonData:
      password: "${DB_PASSWORD}"
    jsonData:
      sslmode: disable
      maxOpenConns: 5
      maxIdleConns: 2
      connMaxLifetime: 14400
      postgresVersion: 1600
      timescaledb: true
```

### Key Grafana Queries

**Live Tag Value (for stat panel):**
```sql
SELECT value, ts
FROM telemetry_latest
WHERE tenant_id = 'piccadily'
  AND plant_id = 'BOILER_PLC_01'
  AND tag_name = 'TT-201'
```

**Trend Chart (1-hour aggregates):**
```sql
SELECT bucket AS time, avg_val, min_val, max_val
FROM telemetry_1hour
WHERE tenant_id = 'piccadily'
  AND plant_id = 'BOILER_PLC_01'
  AND tag_name = 'TT-201'
  AND bucket BETWEEN $__timeFrom() AND $__timeTo()
ORDER BY bucket
```

**Active Alarms Table:**
```sql
SELECT occurred_at AS time, tag_name, severity, message, trigger_value, alarm_state
FROM alarms
WHERE tenant_id = 'piccadily'
  AND alarm_state != 'CLEARED'
ORDER BY occurred_at DESC
LIMIT 50
```

**Alarm Count by Severity (pie chart):**
```sql
SELECT severity, count(*) AS count
FROM alarms
WHERE tenant_id = 'piccadily'
  AND plant_id = 'BOILER_PLC_01'
  AND alarm_state != 'CLEARED'
  AND occurred_at > now() - interval '24 hours'
GROUP BY severity
```

### Grafana Embedding in React

```tsx
// Embed a Grafana dashboard panel in React
const GrafanaPanel = ({ dashboardUid, panelId }) => (
  <iframe
    src={`${GRAFANA_URL}/d-solo/${dashboardUid}?panelId=${panelId}&orgId=1&refresh=5s&theme=dark`}
    width="100%"
    height="300"
    frameBorder="0"
  />
);
// Requires GF_SECURITY_ALLOW_EMBEDDING=true and GF_AUTH_ANONYMOUS_ENABLED=true
// OR use Grafana service account tokens for authenticated embedding
```

---

## 10. Supabase JWT Flow

```
React App
  │
  ├── POST https://your-project.supabase.co/auth/v1/token
  │      (email/password or OAuth)
  │   ← { access_token: "eyJ..." }
  │
  ├── Supabase Dashboard → Settings → Auth → app_metadata
  │      Add: { "tenant_id": "piccadily", "role": "engineer" }
  │      (set via Supabase Edge Function or admin API on user creation)
  │
  └── API calls: Authorization: Bearer <access_token>
         FastAPI decodes JWT, extracts tenant_id + role from app_metadata
```

### Setting app_metadata (Supabase Edge Function)

```typescript
// supabase/functions/on-user-created/index.ts
import { createClient } from '@supabase/supabase-js'

Deno.serve(async (req) => {
  const { user } = await req.json()
  const supabase = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SERVICE_ROLE_KEY')!)

  await supabase.auth.admin.updateUserById(user.id, {
    app_metadata: {
      tenant_id: 'piccadily',   // assign from your provisioning logic
      role: 'viewer'
    }
  })
  return new Response('ok')
})
```

---

## 11. RLS + RBAC Strategy

### RBAC Role Matrix

| Role        | Ingest | View Data | View Alarms | Ack Alarms | Clear Alarms | Tag Config | Admin |
|-------------|--------|-----------|-------------|------------|--------------|------------|-------|
| edge_agent  | ✓      | ✓         | ✗           | ✗          | ✗            | ✗          | ✗     |
| viewer      | ✗      | ✓         | ✓           | ✗          | ✗            | ✗          | ✗     |
| operator    | ✗      | ✓         | ✓           | ✓          | ✓            | ✗          | ✗     |
| engineer    | ✗      | ✓         | ✓           | ✓          | ✓            | ✓          | ✗     |
| admin       | ✗      | ✓         | ✓           | ✓          | ✓            | ✓          | ✓     |

### Two-Layer Isolation

1. **FastAPI layer** (primary): Every query includes `WHERE tenant_id = user.tenant_id`. This is the fast path and covers 100% of API traffic.

2. **PostgreSQL RLS** (defence-in-depth): Enabled on all tenant-scoped tables. Activated for Grafana's native datasource and any direct psql access. Set `app.current_tenant` per connection if enforcing at DB level:
   ```python
   # In _init_connection or before queries:
   await conn.execute(f"SET app.current_tenant = '{tenant_id}'")
   ```

---

## 12. React 18 + TanStack Integration

### WebSocket Live Updates

```typescript
// hooks/useTelemetryStream.ts
import { useEffect, useRef, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'

export function useTelemetryStream(tenantId: string, plantId: string, token: string) {
  const qc = useQueryClient()
  const ws = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    const url = `wss://your-api/ws/${tenantId}/${plantId}?token=${token}`
    ws.current = new WebSocket(url)

    ws.current.onmessage = (e) => {
      const msg = JSON.parse(e.data)

      if (msg.type === 'snapshot' || msg.type === 'telemetry') {
        // Merge into TanStack Query cache — triggers re-renders automatically
        qc.setQueryData(['telemetry', 'latest', plantId], (old: any) => ({
          ...old,
          data: { ...old?.data, ...msg.data }
        }))
      }
      if (msg.type === 'telemetry' && msg.alarms?.length > 0) {
        qc.invalidateQueries({ queryKey: ['alarms', 'active'] })
      }
      if (msg.type === 'alarm_ack') {
        qc.invalidateQueries({ queryKey: ['alarms'] })
      }
    }

    ws.current.onclose = () => setTimeout(connect, 3000)  // auto-reconnect

    const keepalive = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) ws.current.send('ping')
    }, 25000)

    return () => clearInterval(keepalive)
  }, [tenantId, plantId, token, qc])

  useEffect(() => {
    const cleanup = connect()
    return () => { cleanup?.(); ws.current?.close() }
  }, [connect])
}
```

### TanStack Query API Hooks

```typescript
// hooks/useAlarms.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

export const useActiveAlarms = (plantId: string) =>
  useQuery({
    queryKey: ['alarms', 'active', plantId],
    queryFn:  () => api.get(`/api/v1/alarms/active?plant_id=${plantId}`).then(r => r.data),
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

export const useAckAlarm = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: { alarm_id: string; acked_by: string; comment?: string }) =>
      api.post('/api/v1/alarms/ack', req).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alarms'] }),
  })
}

export const useTagHistory = (plantId: string, tagName: string, start: Date, end: Date) =>
  useQuery({
    queryKey: ['telemetry', 'history', plantId, tagName, start, end],
    queryFn: () => api.get('/api/v1/telemetry/history', {
      params: { plant_id: plantId, tag_name: tagName,
                start: start.toISOString(), end: end.toISOString(), interval: '5m' }
    }).then(r => r.data),
    staleTime: 60_000,
  })
```

---

## 13. Performance Optimizations for 4 GB RAM

| Layer | Setting | Value | Reason |
|-------|---------|-------|--------|
| PostgreSQL | `shared_buffers` | 512 MB | Standard 1/8 RAM rule |
| PostgreSQL | `work_mem` | 16 MB | 80 connections × 16 MB = 1.28 GB max |
| PostgreSQL | `max_connections` | 80 | asyncpg pool max 8 × workers 2 = 16 actual |
| TimescaleDB | `chunk_time_interval` | 1 day | ~50-200 MB per chunk — fits in cache |
| TimescaleDB | Compression | After 7 days | 10-40× compression ratio |
| FastAPI | `workers` | 2 | Each takes ~100-150 MB |
| asyncpg | `DB_POOL_MAX` | 8 | 8 × 2 workers = 16 DB connections |
| Grafana | memory limit | 256 MB | Lightweight with cached queries |
| Nginx | memory limit | 64 MB | Static proxy |

### Memory Budget (4 GB)
```
OS + system:    ~512 MB
TimescaleDB:    1536 MB  (configured limit)
FastAPI × 2:    ~300 MB
Grafana:        ~200 MB
Nginx:          ~64 MB
Buffer/cache:   ~400 MB
────────────────────────
Total:          ~3012 MB  ✓ fits within 4 GB
```

---

## 14. Operations Runbook

### Daily Health Check

```bash
# Check all containers
docker compose ps

# Check ingestion throughput
curl -s http://localhost:8000/metrics | grep historian_points_total

# Check latest DB size
docker compose exec timescaledb psql -U historian_user -d historian -c "
SELECT hypertable_name,
       pg_size_pretty(total_bytes) AS total,
       pg_size_pretty(compressed_heap_size) AS compressed
FROM timescaledb_information.hypertables h
JOIN timescaledb_information.compression_settings cs USING (hypertable_name);
"

# View stale tags (OPC UA connection health)
curl -H "Authorization: Bearer <TOKEN>" \
  "https://your-api/api/v1/telemetry/stale?plant_id=BOILER_PLC_01"
```

### Log Monitoring

```bash
# Backend structured logs (JSON)
docker compose logs backend --since 1h --follow | jq '.level,.event,.ms'

# Slow query log (from PostgreSQL)
docker compose exec timescaledb psql -U historian_user -d historian -c "
SELECT query, calls, mean_exec_time::int AS avg_ms
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
"
```

### Backup Strategy

```bash
# Daily automated backup script (add to crontab)
#!/bin/bash
DATE=$(date +%Y%m%d)
docker compose exec -T timescaledb pg_dump \
  -U historian_user -d historian \
  --exclude-table-data='telemetry_raw' \   # exclude raw data from schema backup
  -F c -f /tmp/historian_schema_$DATE.dump

# For full data backup (use pg_basebackup or TimescaleDB dump selectively)
docker compose exec -T timescaledb pg_dump \
  -U historian_user -d historian -F c \
  -f /tmp/historian_full_$DATE.dump

# Copy to Azure Blob Storage
az storage blob upload \
  --account-name piccadilybackups \
  --container-name db-backups \
  --name historian_full_$DATE.dump \
  --file /tmp/historian_full_$DATE.dump
```

### Provision a New Edge Agent Key

```bash
# Via API (admin JWT required)
curl -X POST https://your-api/api/v1/admin/api-keys \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"label": "Edge-Agent-Boiler-02", "tenant_id": "piccadily"}'

# Response contains raw_key — copy it to the edge agent's .env
# It will NOT be shown again (only hash is stored in DB)
```

---

## 15. Ingestion Architecture Summary

```
OPC UA Server (Boiler PLC)
    │  OPC UA subscription (100ms deadband)
    ▼
Edge Agent (edge-agent.py)
    │  Batches N points per 1-2s
    │  POST /api/v1/telemetry/ingest
    │  Header: X-API-Key: <raw_key>
    ▼
FastAPI (main.py)
    ├── _verify_edge_api_key_db()  ← SHA-256 lookup in api_keys table
    ├── _rate_limiter.check()      ← 5000 pts/min per tenant
    ├── _insert_raw_copy()         ← asyncpg COPY to telemetry_raw (fastest)
    ├── _upsert_latest()           ← ON CONFLICT upsert to telemetry_latest
    ├── evaluate_alarms_for_batch() ← DB-driven thresholds + 5-min cooldown
    ├── _insert_alarms()           ← insert new alarm rows
    └── ws_manager.broadcast()     ← fire-and-forget to WS subscribers
         │
         ▼
    React Dashboard (TanStack Query + WebSocket)
         │
         ▼
    Grafana (native PG datasource on TimescaleDB)
```

**Throughput capacity on 4 GB VM:**
- ~500 points/batch × 10 batches/sec = **5,000 points/sec** sustained
- TimescaleDB COPY insert: ~50,000 rows/sec peak
- Memory footprint per 1M rows raw: ~200 MB uncompressed → ~15 MB compressed
- 1-year retention at 100 tags × 1 Hz = ~3.15 billion rows → ~50 GB compressed
