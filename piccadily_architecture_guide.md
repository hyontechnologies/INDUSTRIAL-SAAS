# Piccadily Agro Industries — Python OPC UA Bridge
## Final Architecture Guide
### Industrial Digital Twin SaaS — KEPServerEX-Free Stack

---

## 1. Full Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PLANT FLOOR                                                            │
│                                                                         │
│  ┌─────────────────────────────────────────────┐                        │
│  │  piccadily_boiler_simulator.py               │                        │
│  │  PyModbus TCP Slave  0.0.0.0:5022  Unit=1   │                        │
│  │  • ~236–422 tags (UInt16 raw registers)      │                        │
│  │  • FC1  Coils        00001–00200            │                        │
│  │  • FC3  Holding Regs 40400–40518            │                        │
│  │  • FC4  Input  Regs  30001–30476            │                        │
│  │  • Physics engine: 35 TPH boiler            │                        │
│  └─────────────────┬───────────────────────────┘                        │
│                    │ Modbus TCP :5022                                    │
│  ┌─────────────────▼───────────────────────────┐                        │
│  │  piccadily_opcua_bridge.py   ← THIS SCRIPT  │                        │
│  │                                             │                        │
│  │  Modbus Poller (AsyncModbusTcpClient)       │                        │
│  │  ├── Batch builder (contiguous addr groups) │                        │
│  │  ├── FC1/FC3/FC4 async batch reads          │                        │
│  │  ├── UInt16 → Engineering unit scaling      │                        │
│  │  ├── Bi-directional span (draught tags)     │                        │
│  │  └── Reconnect with exponential back-off    │                        │
│  │                                             │                        │
│  │  OPC UA Server (asyncua)                   │                        │
│  │  ├── Endpoint: opc.tcp://0.0.0.0:4840/     │                        │
│  │  ├── Namespace: urn:piccadily:boilerbridge  │                        │
│  │  ├── 14 group folders × 236 tag nodes      │                        │
│  │  ├── Float nodes (scaled EU) + Bool nodes   │                        │
│  │  ├── OPC UA Good/Bad quality per tag        │                        │
│  │  ├── Heartbeat node (increment every 1s)   │                        │
│  │  └── _Bridge diagnostics folder            │                        │
│  └─────────────────┬───────────────────────────┘                        │
└────────────────────┼────────────────────────────────────────────────────┘
                     │ OPC UA TCP :4840  (open standard, no licence)
┌────────────────────▼────────────────────────────────────────────────────┐
│  EDGE / CLOUD (Azure Ubuntu VM)                                         │
│                                                                         │
│  ┌──────────────────────────────────────────┐                           │
│  │  piccadily_opc_edge_agent.py             │                           │
│  │                                          │                           │
│  │  asyncua Client Subscriber              │                           │
│  │  ├── Monitored Items subscription       │                           │
│  │  ├── OPC UA Good-quality filter         │                           │
│  │  ├── Dedup window (0.5s)               │                           │
│  │  ├── Async queue (10,000 items)         │                           │
│  │  ├── HTTP batch uploader (aiohttp)      │                           │
│  │  ├── SQLite cursor (VM-restart resume)  │                           │
│  │  └── Exponential back-off reconnect     │                           │
│  └──────────────────┬───────────────────────┘                           │
│                     │ HTTPS POST /telemetry/ingest                      │
│  ┌──────────────────▼───────────────────────┐                           │
│  │  FastAPI  (uvicorn, port 8000)           │                           │
│  │  POST /telemetry/ingest                  │                           │
│  │  GET  /telemetry/latest/{tag}            │                           │
│  │  GET  /alarms/active                     │                           │
│  │  WS   /ws/live/{plant_id}               │                           │
│  └──────────────────┬───────────────────────┘                           │
│                     │ asyncpg                                           │
│  ┌──────────────────▼───────────────────────┐                           │
│  │  TimescaleDB (PostgreSQL + hypertable)   │                           │
│  │  telemetry(ts, plant_id, tag, value, q) │                           │
│  │  alarms(ts, plant_id, tag, state, ack)  │                           │
│  └──────────────────┬───────────────────────┘                           │
│                     │                                                   │
│  ┌──────────────────▼───────────────────────┐                           │
│  │  Grafana (port 3000)                     │                           │
│  │  TimescaleDB datasource                  │                           │
│  │  Dashboards: Overview, Trends, Alarms    │                           │
│  └──────────────────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Roles

| Component | Role | Port | Technology |
|-----------|------|------|------------|
| Simulator | Modbus slave, physics engine | 5022 | pymodbus 3.x |
| **Bridge** | **Modbus→OPC UA translator** | **4840** | **asyncua + pymodbus** |
| Edge Agent | OPC UA subscriber → cloud uploader | — | asyncua client + aiohttp |
| FastAPI | REST + WebSocket API gateway | 8000 | FastAPI + uvicorn |
| TimescaleDB | Time-series historian | 5432 | PostgreSQL + TimescaleDB ext |
| Grafana | Dashboards | 3000 | Grafana OSS |

---

## 3. Installation (Azure Ubuntu 22.04 VM)

```bash
# System packages
sudo apt update && sudo apt install -y python3.11 python3-pip python3.11-venv

# Create isolated environment
python3.11 -m venv /opt/piccadily/venv
source /opt/piccadily/venv/bin/activate

# Bridge dependencies
pip install asyncua==1.1.0 pymodbus==3.7.0

# Edge agent dependencies
pip install asyncua==1.1.0 aiohttp==3.9.5

# Verify
python3 -c "from asyncua import Server; from pymodbus.client import AsyncModbusTcpClient; print('OK')"
```

---

## 4. Running the Stack (Correct Start Order)

```bash
# Terminal 1 — Simulator (must start FIRST)
python3 piccadily_boiler_simulator.py --host 0.0.0.0 --port 5022

# Terminal 2 — OPC UA Bridge
python3 piccadily_opcua_bridge.py \
  --modbus-host 127.0.0.1 \
  --modbus-port 5022 \
  --opc-port 4840 \
  --poll-ms 1000 \
  --batch-size 100 \
  --plant-id PICCADILY_PLANT_01 \
  --device-id BOILER_PLC_01

# Terminal 3 — Edge Agent
OPC_URL="opc.tcp://127.0.0.1:4840/piccadily/" \
API_URL="http://localhost:8000/telemetry/ingest" \
PLANT_ID="PICCADILY_PLANT_01" \
python3 piccadily_opc_edge_agent.py

# Terminal 4 — FastAPI (after TimescaleDB is running)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

---

## 5. Systemd Services (Production)

### Bridge service `/etc/systemd/system/piccadily-bridge.service`

```ini
[Unit]
Description=Piccadily OPC UA Bridge
After=network.target piccadily-simulator.service
Requires=piccadily-simulator.service

[Service]
Type=simple
User=piccadily
WorkingDirectory=/opt/piccadily
Environment=LOG_LEVEL=INFO
Environment=MODBUS_HOST=127.0.0.1
Environment=MODBUS_PORT=5022
Environment=OPC_PORT=4840
Environment=POLL_MS=1000
ExecStart=/opt/piccadily/venv/bin/python3 piccadily_opcua_bridge.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable piccadily-bridge piccadily-simulator piccadily-edge-agent
sudo systemctl start piccadily-bridge
sudo journalctl -u piccadily-bridge -f
```

---

## 6. Modbus Register Map Summary

### Function Code Mapping

| KEP Address | pymodbus FC | pymodbus index | Example |
|-------------|-------------|----------------|---------|
| 30001 | FC4 read_input_registers | addr − 30001 = 0 | TE_ECON_INLET |
| 30009 | FC4 | 8 | TE_FURN |
| 40400 | FC3 read_holding_registers | addr − 40001 = 399 | FCV_FW_CTRL |
| 40500 | FC3 | addr − 40001 = 499 | SP_DRUM_LVL |
| 00001 | FC1 read_coils | addr − 1 = 0 | BFP1_RUN |
| 00100 | FC1 | addr − 1 = 99 | INTLK_MASTER |

### Scaling Formula

```
# Standard unipolar  (0..span_hi)
eng_value = raw_uint16 / (4095 / span_hi)
         = raw_uint16 * span_hi / 4095

# Example: PT_DRUM  span_hi=60 kg/cm2
#   raw=2047  →  eng = 2047 * 60 / 4095 = 29.99 kg/cm2

# Bi-directional  (span_lo..span_hi)  e.g. draught -30..+30 mmWc
total_span = span_hi - span_lo            # = 60
divisor    = 4095 / total_span            # = 68.25
eng_value  = raw_uint16 / divisor + span_lo
# raw=2047  →  eng = 2047/68.25 + (-30) = 29.99 - 30 = -0.01 mmWc  (≈ 0)

# Coils (boolean)
eng_value = bool(raw_bit)  # 0 or 1
```

---

## 7. OPC UA Node Hierarchy

```
Objects/
  PICCADILY_PLANT_01/
    BOILER_PLC_01/
      Temperature/          ← 35 tags  (TE_ECON_INLET … TE_BLOWDN_HEX)
      Pressure/             ← 15 tags  (PT_DEAER … PT_LP_STEAM)
      Level/                ← 19 tags  (LT_DEAER … LT_BLOWDOWN)
      Flow/                 ← 11 tags  (FT_MS_FLOW … FM_AIR_SA)
      Draught/              ←  8 tags  (DT_FURN_DFT … DT_STACK)
      MotorRPM/             ← 21 tags  (GM_SF1_RPM … GM_HP_DOS2_RPM)
      MotorCurrent/         ← 17 tags  (GM_SF1_AMP … GM_LP_DOS2_AMP)
      EspElectrical/        ← 10 tags  (TRCC1_VOLT … ESP_DUST_OUT)
      Energy/               ←  7 tags  (KWH_BFP1 … HEAT_RATE)
      ControlValves/        ← 11 tags  (FCV_FW_CTRL … VFD_FD_SPEED)
      Setpoints/            ←  9 tags  (SP_DRUM_LVL … SP_BOILER_LOAD)
      PidTuning/            ←  9 tags  (PID_DRUM_KP … PID_DRAFT_KI)
      DigitalStatus/        ← 43 tags  (BFP1_RUN … BLOWDN_AUTO)
      Interlocks/           ← 27 tags  (INTLK_MASTER … ALARM_VFD_FAULT)
      _Bridge/
        Heartbeat           ← increments every 1s
        ModbusConnected     ← True/False
        LastPollTs          ← ISO-8601 timestamp string
        TotalTagsOK         ← good reads per cycle
        TotalTagsBad        ← bad reads per cycle
```

---

## 8. Edge Agent OPC UA Subscription Configuration

The existing `piccadily_opc_edge_agent.py` connects to the bridge endpoint.
Update these constants:

```python
# In piccadily_opc_edge_agent.py — update these lines:
OPC_URL       = "opc.tcp://127.0.0.1:4840/piccadily/"
OPC_NAMESPACE = "PICCADILY_PLANT_01"
OPC_DEVICE    = "BOILER_PLC_01"

# OPC namespace URI must match bridge --opc-ns-uri
# default: "urn:piccadily:boilerbridge"
```

Tag path resolution in the edge agent:

```python
# Bridge exposes nodes as String NodeIds:
# Format: {group}/{tag}  under  PICCADILY_PLANT_01/BOILER_PLC_01/
# Example OPC path:
#   Objects/PICCADILY_PLANT_01/BOILER_PLC_01/Temperature/TE_ECON_INLET

# When browsing with asyncua:
device_node = await client.nodes.root.get_child([
    "0:Objects",
    f"2:{PLANT_ID}",
    f"2:{DEVICE_ID}",
])
```

---

## 9. TimescaleDB Schema

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Telemetry hypertable
CREATE TABLE telemetry (
    ts          TIMESTAMPTZ     NOT NULL,
    plant_id    TEXT            NOT NULL,
    group_name  TEXT            NOT NULL,
    tag         TEXT            NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT            DEFAULT 'Good',
    unit        TEXT
);

SELECT create_hypertable('telemetry', 'ts',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX ON telemetry (plant_id, tag, ts DESC);

-- Compression policy (after 7 days)
ALTER TABLE telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'plant_id, tag'
);
SELECT add_compression_policy('telemetry', INTERVAL '7 days');

-- Retention policy (keep 1 year)
SELECT add_retention_policy('telemetry', INTERVAL '365 days');

-- Alarms table
CREATE TABLE alarms (
    ts          TIMESTAMPTZ     NOT NULL,
    plant_id    TEXT            NOT NULL,
    tag         TEXT            NOT NULL,
    state       TEXT            NOT NULL,  -- 'ACTIVE' | 'CLEARED'
    acked       BOOLEAN         DEFAULT false,
    acked_by    TEXT,
    acked_at    TIMESTAMPTZ,
    message     TEXT
);

SELECT create_hypertable('alarms', 'ts',
    chunk_time_interval => INTERVAL '7 days');

-- Continuous aggregate: 1-minute averages
CREATE MATERIALIZED VIEW telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', ts) AS bucket,
    plant_id,
    tag,
    AVG(value)   AS avg_value,
    MIN(value)   AS min_value,
    MAX(value)   AS max_value,
    COUNT(*)     AS sample_count
FROM telemetry
WHERE quality = 'Good'
GROUP BY bucket, plant_id, tag;

SELECT add_continuous_aggregate_policy('telemetry_1min',
    start_offset => INTERVAL '5 minutes',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

---

## 10. FastAPI Ingest Endpoint

```python
# main.py (minimal working ingest endpoint)
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Any, Optional
import asyncpg, os
from datetime import datetime

app = FastAPI(title="Piccadily Telemetry API")

DB_URL  = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/piccadily")
API_KEY = os.getenv("API_KEY", "changeme")

class TelemetryPoint(BaseModel):
    plant_id:  str
    group:     str
    tag:       str
    unit:      str
    value:     Any
    quality:   str
    ts_server: str

class IngestPayload(BaseModel):
    plant_id: str
    count:    int
    points:   List[TelemetryPoint]


@app.on_event("startup")
async def startup():
    app.state.pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)


@app.post("/telemetry/ingest", status_code=202)
async def ingest(payload: IngestPayload, x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    records = []
    for p in payload.points:
        is_bool = isinstance(p.value, bool)
        records.append((
            datetime.fromisoformat(p.ts_server),
            p.plant_id,
            p.group,
            p.tag,
            None if is_bool else float(p.value),
            p.value if is_bool else None,
            p.quality,
            p.unit,
        ))

    async with app.state.pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO telemetry
               (ts, plant_id, group_name, tag, value, bool_value, quality, unit)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
               ON CONFLICT DO NOTHING""",
            records,
        )

    return {"accepted": len(records)}
```

---

## 11. Batch Optimisation Strategy

The bridge's `_build_batches()` function automatically groups contiguous
register addresses into single Modbus requests, dramatically reducing
round-trips:

```
Without batching:  236 individual requests/cycle
With batching:     ~18 batch requests/cycle  (at batch_size=100)

Request breakdown:
  FC4 Input Regs:
    Batch 1:  30001–30035  (35 temperature regs)
    Batch 2:  30100–30114  (15 pressure regs)
    Batch 3:  30150–30168  (19 level regs)
    Batch 4:  30200–30210  (11 flow regs)
    Batch 5:  30250–30257  (8 draught regs)
    Batch 6:  30300–30320  (21 motor RPM regs)
    Batch 7:  30350–30366  (17 motor current regs)
    Batch 8:  30450–30459  (10 ESP regs)
    Batch 9:  30470–30476  (7 energy regs)
  FC3 Holding Regs:
    Batch 10: 40400–40410  (11 control valve regs)
    Batch 11: 40500–40518  (19 setpoint/PID regs)
  FC1 Coils:
    Batch 12: 00001–00042  (digital status coils)
    Batch 13: 00100–00128  (interlock/alarm coils)

Total: ~13 Modbus requests per poll cycle
At poll_ms=1000: 13 requests/second  (trivial for Modbus TCP)
```

---

## 12. Scaling to 422 Tags

To add the remaining tags (beyond the 236 in the current registry):

```python
# In piccadily_opcua_bridge.py, extend _build_registry():

# Add new group
G = "AshHandling"
tags += [
    TagDef(G,"ASH_CONV_SPEED", IR, 30490, _s(100), "RPM", "Ash Conveyor Speed"),
    TagDef(G,"ASH_HOPPER_TEMP",IR, 30491, _s(300), "degC","Ash Hopper Temperature"),
    # ... etc
]

# Add new coil block
G = "DigitalStatus"
tags += [
    TagDef(G,"ASH_CONV_RUN",   CO, 50, 1.0, "-", "Ash Conveyor Run Status"),
    # ... etc
]
```

No changes to the bridge engine are required. The batch builder and
namespace builder dynamically handle any number of tags.

**Memory estimate at 1000 tags:**
- OPC UA node objects: ~1000 × 2 KB = ~2 MB
- Poll cycle buffer:   ~1000 × 8 bytes = ~8 KB
- Total RSS: < 150 MB — suitable for a 2 GB VM

---

## 13. Multi-Plant SaaS Scaling

Run one bridge instance per plant. Each bridge is stateless and
independently configurable via environment variables:

```bash
# Plant 1 — Piccadily
docker run -d --name bridge-piccadily \
  -e MODBUS_HOST=192.168.1.100 \
  -e MODBUS_PORT=5022 \
  -e OPC_PORT=4840 \
  -e PLANT_ID=PICCADILY_PLANT_01 \
  -e DEVICE_ID=BOILER_PLC_01 \
  piccadily/opcua-bridge:latest

# Plant 2 — Second boiler
docker run -d --name bridge-plant2 \
  -e MODBUS_HOST=192.168.2.100 \
  -e MODBUS_PORT=5022 \
  -e OPC_PORT=4841 \
  -e PLANT_ID=PLANT_02 \
  -e DEVICE_ID=BOILER_PLC_01 \
  piccadily/opcua-bridge:latest
```

The TimescaleDB `plant_id` column provides multi-tenant isolation.
Each Grafana dashboard uses a `$plant_id` variable for tenant separation.

---

## 14. Docker Compose (Full Stack)

```yaml
version: "3.9"
services:

  simulator:
    image: python:3.11-slim
    command: python piccadily_boiler_simulator.py --host 0.0.0.0 --port 5022
    volumes: [".:/app"]
    working_dir: /app
    ports: ["5022:5022"]

  bridge:
    image: python:3.11-slim
    command: >
      sh -c "pip install asyncua pymodbus -q &&
             python piccadily_opcua_bridge.py
             --modbus-host simulator --modbus-port 5022
             --opc-port 4840 --poll-ms 1000"
    volumes: [".:/app"]
    working_dir: /app
    ports: ["4840:4840"]
    depends_on: [simulator]
    environment:
      PLANT_ID: PICCADILY_PLANT_01
      DEVICE_ID: BOILER_PLC_01

  edge-agent:
    image: python:3.11-slim
    command: >
      sh -c "pip install asyncua aiohttp -q &&
             python piccadily_opc_edge_agent.py"
    volumes: [".:/app"]
    working_dir: /app
    depends_on: [bridge, api]
    environment:
      OPC_URL: opc.tcp://bridge:4840/piccadily/
      API_URL: http://api:8000/telemetry/ingest
      API_KEY: changeme
      PLANT_ID: PICCADILY_PLANT_01

  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_PASSWORD: piccadily
      POSTGRES_DB: piccadily
    volumes: ["tsdb_data:/var/lib/postgresql/data"]
    ports: ["5432:5432"]

  api:
    build: ./api
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://postgres:piccadily@timescaledb/piccadily
      API_KEY: changeme
    depends_on: [timescaledb]

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    volumes: ["grafana_data:/var/lib/grafana"]
    depends_on: [timescaledb]

volumes:
  tsdb_data:
  grafana_data:
```

---

## 15. Bridge Diagnostics Checklist

| Check | OPC UA Node | Expected Value |
|-------|-------------|----------------|
| Bridge alive | `_Bridge/Heartbeat` | Incrementing every 1s |
| Modbus OK | `_Bridge/ModbusConnected` | `True` |
| Last poll | `_Bridge/LastPollTs` | Within last 2s |
| Good tags | `_Bridge/TotalTagsOK` | = Total tags (236) |
| Bad tags | `_Bridge/TotalTagsBad` | = 0 (normal operation) |

**If `ModbusConnected = False`:**
1. Verify simulator is running: `nc -zv 127.0.0.1 5022`
2. Check `--modbus-host` and `--modbus-port` match simulator
3. Check `journalctl -u piccadily-simulator` for errors

**If `TotalTagsBad > 0`:**
1. Check for address gaps in the simulator register map
2. Verify `--modbus-unit` matches simulator `--unit` (default: 1)
3. Enable debug logging: `--log-level DEBUG`

**If OPC UA clients cannot connect:**
1. Verify port 4840 is open: `sudo ufw allow 4840/tcp`
2. Test locally: `python3 -c "from asyncua import Client; import asyncio; asyncio.run(Client('opc.tcp://127.0.0.1:4840/piccadily/').connect())"`
