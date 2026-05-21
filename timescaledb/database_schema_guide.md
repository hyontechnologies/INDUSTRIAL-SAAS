# Piccadily Industrial Historian — Database Schema Guide v4.0

This document describes the TimescaleDB database schema and table structure for the Piccadily Industrial Historian v4.0. The architecture is optimized for high-throughput, multi-tenant industrial telemetry, boasting independent compression/retention rules, granular Row-Level Security (RLS), and real-time analytical rollups.

---

## 1. Entity-Relationship Diagram (ERD)

The following diagram illustrates the relational layout and the connection between the flat operational tables, metadata, and the time-series partition layers.

```mermaid
erDiagram
    tenants {
        TEXT tenant_id PK
        TEXT name
        TEXT plan
        BOOLEAN is_active
        JSONB metadata
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }
    plants {
        TEXT tenant_id PK, FK
        TEXT plant_id PK
        TEXT name
        TEXT location
        TEXT plant_type
        TEXT timezone
        BOOLEAN is_active
        JSONB config
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }
    tag_metadata {
        TEXT tenant_id PK, FK
        TEXT plant_id PK, FK
        TEXT tag_name PK
        TEXT description
        TEXT engineering_unit
        TEXT opc_node_id
        TEXT data_type
        TEXT tag_group
        DOUBLE PRECISION low_low_limit
        DOUBLE PRECISION low_limit
        DOUBLE PRECISION high_limit
        DOUBLE PRECISION high_high_limit
        DOUBLE PRECISION deadband
        BOOLEAN is_active
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }
    api_keys {
        UUID key_id PK
        TEXT label
        TEXT tenant_id FK
        TEXT key_hash
        BOOLEAN is_active
        TIMESTAMPTZ created_at
        TIMESTAMPTZ expires_at
        TIMESTAMPTZ last_used_at
    }
    tag_routing_rules {
        UUID id PK
        TEXT tenant_id FK
        TEXT pattern
        TEXT pattern_type
        TEXT target_table
        INTEGER priority
        TIMESTAMPTZ created_at
    }
    telemetry_latest {
        TEXT tenant_id PK, FK
        TEXT plant_id PK, FK
        TEXT tag_name PK, FK
        DOUBLE PRECISION value
        BOOLEAN bool_value
        TEXT quality
        TIMESTAMPTZ ts
        TEXT unit
    }
    alarms {
        UUID alarm_id PK
        TEXT tenant_id FK
        TEXT plant_id FK
        TEXT tag_name FK
        TEXT severity
        TEXT alarm_state
        TEXT message
        DOUBLE PRECISION trigger_value
        TIMESTAMPTZ occurred_at PK
        TEXT acked_by
        TIMESTAMPTZ acked_at
    }
    alarm_history {
        BIGINT id PK
        UUID alarm_id FK
        TEXT tenant_id FK
        TEXT action
        TEXT performed_by
        TEXT comment
        TIMESTAMPTZ created_at
    }
    audit_logs {
        BIGINT id PK
        TEXT tenant_id FK
        TEXT user_id
        TEXT user_email
        TEXT role
        TEXT action
        TEXT resource
        JSONB detail
        TIMESTAMPTZ created_at PK
    }

    tenants ||--o{ plants : "hosts"
    tenants ||--o{ api_keys : "owns"
    tenants ||--o{ tag_routing_rules : "defines"
    plants ||--o{ tag_metadata : "contains"
    tag_metadata ||--o{ telemetry_latest : "mirrors latest"
    alarms ||--o{ alarm_history : "logs transitions"
```

---

## 2. Core Operational Tables (Standard Relational)

These standard PostgreSQL tables handle system entities, metadata configuration, security credentials, and caching.

### 2.1 `tenants`
Stores system tenants subscribing to the historian service.
- **Primary Key:** `tenant_id`
- **Indices:**
  - `idx_tenants_active` on `is_active`

| Column | Type | Constraints | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `tenant_id` | `TEXT` | `PRIMARY KEY` | *None* | Unique tenant short code (e.g. `piccadily`). |
| `name` | `TEXT` | `NOT NULL` | *None* | Full business/corporation name. |
| `plan` | `TEXT` | `NOT NULL` | `'starter'` | Pricing tier (`starter`, `pro`, `enterprise`). |
| `is_active` | `BOOLEAN` | `NOT NULL` | `true` | Activation status indicator. |
| `metadata` | `JSONB` | `NOT NULL` | `'{}'` | Custom schema-less configuration values. |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL` | `now()` | Registration timestamp. |
| `updated_at` | `TIMESTAMPTZ`| `NOT NULL` | `now()` | Last modification timestamp. |

### 2.2 `plants`
Represents localized facilities or sites owned by a tenant.
- **Primary Key:** `(tenant_id, plant_id)`
- **Indices:**
  - `idx_plants_tenant` on `tenant_id`

| Column | Type | Constraints | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `tenant_id` | `TEXT` | `FOREIGN KEY` references `tenants(tenant_id) ON DELETE CASCADE` | *None* | Owner tenant. |
| `plant_id` | `TEXT` | `NOT NULL` | *None* | Tenant-scoped plant identifier (e.g. `BOILER_PLC_01`). |
| `name` | `TEXT` | `NOT NULL` | *None* | Friendly plant name. |
| `location` | `TEXT` | *None* | *None* | Geographic coordinates or address. |
| `plant_type` | `TEXT` | `NOT NULL` | `'boiler'` | Asset category (`boiler`, `utility`, `wtp`, `power`). |
| `timezone` | `TEXT` | `NOT NULL` | `'Asia/Kolkata'`| Local operating timezone for reporting offsets. |
| `is_active` | `BOOLEAN` | `NOT NULL` | `true` | Running/active state. |
| `config` | `JSONB` | `NOT NULL` | `'{}'` | Extensible operational config. |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL` | `now()` | Plant creation timestamp. |
| `updated_at` | `TIMESTAMPTZ`| `NOT NULL` | `now()` | Plant configuration update timestamp. |

### 2.3 `tag_metadata`
Stores system tag records, engineering units, OPC UA address bindings, and alarm thresholds.
- **Primary Key:** `(tenant_id, plant_id, tag_name)`
- **Indices:**
  - `idx_tag_metadata_active` on `(tenant_id, plant_id, is_active)`
  - `idx_tag_metadata_group` on `(tag_group)` where `tag_group IS NOT NULL`

| Column | Type | Constraints | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `tenant_id` | `TEXT` | `FOREIGN KEY` (compound) references `plants` | *None* | Part of compound reference key. |
| `plant_id` | `TEXT` | `FOREIGN KEY` (compound) references `plants` | *None* | Part of compound reference key. |
| `tag_name` | `TEXT` | `NOT NULL` | *None* | PLC tag identifier (e.g. `TT-201`, `PT-201`). |
| `description` | `TEXT` | *None* | *None* | Detailed text describing what the tag measures. |
| `engineering_unit` | `TEXT` | *None* | *None* | Measurement unit (e.g., `°C`, `Kg/cm²`, `RPM`, `t/h`). |
| `opc_node_id` | `TEXT` | *None* | *None* | OPC UA protocol address node string (e.g. `ns=2;s=...`). |
| `data_type` | `TEXT` | *None* | `'Float64'` | Tag primitive data type (`Float64`, `Int32`, `Boolean`). |
| `tag_group` | `TEXT` | *None* | *None* | Ingestion partition router category. |
| `low_low_limit` | `DOUBLE PRECISION`| *None* | *None* | Emergency low threshold (trigger CRITICAL alarm). |
| `low_limit` | `DOUBLE PRECISION`| *None* | *None* | Warning low threshold (trigger WARNING alarm). |
| `high_limit` | `DOUBLE PRECISION`| *None* | *None* | Warning high threshold (trigger WARNING alarm). |
| `high_high_limit` | `DOUBLE PRECISION`| *None* | *None* | Emergency high threshold (trigger CRITICAL alarm). |
| `deadband` | `DOUBLE PRECISION`| *None* | `0.0` | Ingestion compression delta threshold. |
| `is_active` | `BOOLEAN` | `NOT NULL` | `true` | Active scanning state. |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL` | `now()` | Registry creation timestamp. |
| `updated_at` | `TIMESTAMPTZ`| `NOT NULL` | `now()` | Tag threshold change timestamp. |

### 2.4 `api_keys`
API tokens for authorizing remote assets (such as local edge-agents pushing telemetry).
- **Primary Key:** `key_id` (UUID)
- **Indices:**
  - `idx_api_keys_tenant` on `tenant_id`
  - `idx_api_keys_hash` on `key_hash` where `is_active = true`

| Column | Type | Constraints | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `key_id` | `UUID` | `PRIMARY KEY` | `uuid_generate_v4()` | Globally unique key tracking ID. |
| `label` | `TEXT` | `NOT NULL` | *None* | Identification label (e.g. `Boiler Edge Agent 01`). |
| `tenant_id` | `TEXT` | `FOREIGN KEY` references `tenants` | *None* | Owner tenant namespace. |
| `key_hash` | `TEXT` | `UNIQUE` | *None* | Secure SHA-256 hash of the key credential. |
| `is_active` | `BOOLEAN` | `NOT NULL` | `true` | Key validity toggle. |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL` | `now()` | Generation timestamp. |
| `expires_at` | `TIMESTAMPTZ`| *None* | *None* | Expiration cutoff timestamp (NULL = permanent). |
| `last_used_at`| `TIMESTAMPTZ`| *None* | *None* | Last access tracking time. |

### 2.5 `telemetry_latest`
Standard table acts as a fast cache mirror for the absolute latest values. Offers `O(1)` query efficiency for current status cards.
- **Primary Key:** `(tenant_id, plant_id, tag_name)`
- **Indices:**
  - `idx_latest_plant` on `(tenant_id, plant_id)`

| Column | Type | Constraints | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `tenant_id` | `TEXT` | `NOT NULL` | *None* | Compound key part. |
| `plant_id` | `TEXT` | `NOT NULL` | *None* | Compound key part. |
| `tag_name` | `TEXT` | `NOT NULL` | *None* | Compound key part. |
| `value` | `DOUBLE PRECISION`| *None* | *None* | Mirror of latest numeric metric. |
| `bool_value` | `BOOLEAN` | *None* | *None* | Mirror of latest boolean metric. |
| `quality` | `TEXT` | `NOT NULL` | `'GOOD'` | Sensor quality flag (`GOOD`, `BAD`, `UNCERTAIN`). |
| `ts` | `TIMESTAMPTZ`| `NOT NULL` | *None* | Timestamp of last recorded change. |
| `unit` | `TEXT` | *None* | *None* | Metric unit representation. |

### 2.6 `tag_routing_rules`
Dynamic rules for routing incoming tags to specific hypertable groups based on prefixes, suffixes, or regex.
- **Primary Key:** `id`
- **Indices:**
  - `idx_tag_routing_rules` on `(tenant_id, priority DESC)`

| Column | Type | Constraints | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | `uuid_generate_v4()` | Unique rule ID. |
| `tenant_id` | `TEXT` | `FOREIGN KEY` references `tenants(tenant_id) ON DELETE CASCADE` | *None* | Owner tenant namespace. |
| `pattern` | `TEXT` | `NOT NULL` | *None* | String pattern to match against tag names. |
| `pattern_type`| `TEXT` | `NOT NULL` | *None* | Type of match (`prefix`, `suffix`, `regex`). |
| `target_table`| `TEXT` | `NOT NULL` | *None* | Target hypertable (e.g., `telemetry_temperature`). |
| `priority` | `INTEGER` | `NOT NULL` | `0` | Routing rule evaluation priority (higher evaluated first). |
| `created_at` | `TIMESTAMPTZ`| *None* | `now()` | Rule creation timestamp. |

---

## 3. TimescaleDB Specialized Hypertables

Hypertables are split into chunks over time partitions automatically. Under v4.0, telemetry is partitioned into **15 specialized hypertables** depending on their functional group. This enables independent storage optimization, compression intervals, and long-term retention.

### 3.1 Common Telemetry Column Layout
All 15 telemetry hypertables (`telemetry_{group}`) share this exact column blueprint:

| Column | Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `ts` | `TIMESTAMPTZ`| `NOT NULL` | Primary time-partition key. |
| `tenant_id` | `TEXT` | `NOT NULL` | Multi-tenant namespace. |
| `plant_id` | `TEXT` | `NOT NULL` | Operating plant. |
| `tag_name` | `TEXT` | `NOT NULL` | OPC UA tag key. |
| `value` | `DOUBLE PRECISION`| *None* | Numeric sensor measurement. |
| `bool_value` | `BOOLEAN` | *None* | Binary state indicator. |
| `quality` | `TEXT` | `'GOOD'` | Value health indicator. |
| `unit` | `TEXT` | *None* | Physical engineering unit. |
| `source_id` | `TEXT` | *None* | Ingestion source identifier. |

### 3.2 Hypertable Storage & Optimization Comparison Matrix

Every telemetry table is segmented and compressed based on the composite key `(tenant_id, plant_id, tag_name)` and ordered by `ts DESC` inside the compressed chunks. The table below outlines the chunk sizing and policies for each:

| Hypertable | Chunk Interval | Primary Index | Compression Trigger | Raw Data Retention | Primary Use Case / Examples |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **`telemetry_temperature`** | 1 day | `idx_temp_tag_ts` | After 7 days | 1 year | Thermocouples (`TT-201`, `TE-301`). |
| **`telemetry_pressure`** | 1 day | `idx_pres_tag_ts` | After 7 days | 1 year | Pressure sensors (`PT-201`, `PT-001`). |
| **`telemetry_level`** | 1 day | `idx_level_tag_ts` | After 7 days | 1 year | Drum/storage levels (`LT-201`, `LT-001`). |
| **`telemetry_draught`** | 1 day | `idx_draught_tag_ts` | After 7 days | 1 year | Furnace draft values (`DT-401`). |
| **`telemetry_flow`** | 1 day | `idx_flow_tag_ts` | After 7 days | 1 year | Inflow/Outflow rates (`FT-101`). |
| **`telemetry_flow_totalizer`**| 1 hour | `idx_flow_tot_tag_ts`| After 30 days| 5 years | Running flow totals (8hr metrics). |
| **`telemetry_motor_rpm`** | 1 day | `idx_rpm_tag_ts` | After 7 days | 1 year | Fan/Feeder speeds (`ID_RPM`, `SF1_RPM`). |
| **`telemetry_motor_current`**| 1 day | `idx_current_tag_ts` | After 7 days | 1 year | Electric load currents (Amperes). |
| **`telemetry_esp_electrical`**| 1 day | `idx_esp_tag_ts` | After 30 days| 2 years | Electrostatic precipitator metrics (`TRCC1_VOLT`).|
| **`telemetry_control_valve`**| 1 day | `idx_valve_tag_ts` | After 7 days | 1 year | Valve opening positions (`FCV-101` %). |
| **`telemetry_digital_status`**| 4 hours | `idx_digital_tag_ts` | After 7 days | 90 days | Binary trips/states. Short chunk, fast drops. |
| **`telemetry_performance`** | 1 hour | `idx_perf_tag_ts` | After 30 days| 5 years | System efficiency indexes & computed metrics.|
| **`telemetry_vibration`** | 1 day | `idx_vib_tag_ts` | After 7 days | 2 years | Bearing vibration analysis (mm/s). |
| **`telemetry_power_metering`**| 1 hour | `idx_power_tag_ts` | After 30 days| 5 years | Power parameters (`kW`, `kWh`, Power Factor).|
| **`telemetry_raw`** | 1 day | `idx_raw_tag_ts` | After 7 days | 1 year | Catch-all for untyped or legacy tags. |

> [!TIP]
> `telemetry_raw` possesses an additional `idx_raw_ts_brin` index using the BRIN (Block Range Index) engine to enable swift timezone-wide range scans on historical catch-alls.

---

## 4. Alarms, Audits & Histograms

These tables log structural system histories, state machines, and immutable logs.

### 4.1 `alarms`
A TimescaleDB hypertable managing warning and alert states triggered by tag thresholds.
- **Time-Partition Chunk Size:** `1 month`
- **Retention Policy:** `3 years`
- **Primary Key:** `(alarm_id, occurred_at)`
- **Indices:**
  - `idx_alarms_active` on `(tenant_id, plant_id, alarm_state, occurred_at DESC)`
  - `idx_alarms_tag` on `(tenant_id, plant_id, tag_name, occurred_at DESC)`

| Column | Type | Constraints / Default | Description |
| :--- | :--- | :--- | :--- |
| `alarm_id` | `UUID` | `NOT NULL DEFAULT uuid_generate_v4()` | Unique alarm trace ID (deterministically generated using `uuid5` in backend layer for deduplication). |
| `tenant_id` | `TEXT` | `NOT NULL` | Tenant namespace. |
| `plant_id` | `TEXT` | `NOT NULL` | Associated facility ID. |
| `tag_name` | `TEXT` | `NOT NULL` | Triggering PLC metric tag. |
| `severity` | `TEXT` | `NOT NULL` | Alarm urgency (`INFO`, `WARNING`, `ALARM`, `CRITICAL`). |
| `alarm_state` | `TEXT` | `NOT NULL DEFAULT 'ACTIVE'` | Machine state (`ACTIVE`, `ACKNOWLEDGED`, `CLEARED`). |
| `message` | `TEXT` | `NOT NULL` | Autogenerated alarm text. |
| `trigger_value`| `DOUBLE PRECISION`| `NOT NULL` | Sensor value that crossed limits. |
| `occurred_at` | `TIMESTAMPTZ`| `PRIMARY KEY DEFAULT now()` | Ingestion timestamp when limits were crossed. |
| `acked_by` | `TEXT` | *None* | Operator ID who acknowledged. |
| `acked_at` | `TIMESTAMPTZ`| *None* | Acknowledgment timestamp. |

### 4.2 `alarm_history`
Standard relational table recording an immutable audit trail of alarm state updates.
- **Primary Key:** `id` (BIGSERIAL)
- **Indices:**
  - `idx_alarm_history_alarm` on `(alarm_id, created_at DESC)`
  - `idx_alarm_history_tenant` on `(tenant_id, created_at DESC)`

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `PRIMARY KEY DEFAULT nextval(...)`| Incremental transaction sequence ID. |
| `alarm_id` | `UUID` | `NOT NULL` | Target alarm key. |
| `tenant_id` | `TEXT` | `NOT NULL` | Scope owner. |
| `action` | `TEXT` | `NOT NULL` | Operation logged (`ACKNOWLEDGED`, `CLEARED`, `REOPENED`). |
| `performed_by`| `TEXT` | `NOT NULL` | User identifier or system worker. |
| `comment` | `TEXT` | *None* | Context comment left by operator. |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT now()` | Event log timestamp. |

### 4.3 `audit_logs`
A TimescaleDB hypertable tracking system changes and admin actions for security validation.
- **Time-Partition Chunk Size:** `1 month`
- **Retention Policy:** `2 years`
- **Primary Key:** `(id, created_at)`
- **Indices:**
  - `idx_audit_tenant_ts` on `(tenant_id, created_at DESC)`

| Column | Type | Constraints | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGINT` | `PRIMARY KEY` | `nextval(...)` | Sequential ID. |
| `tenant_id` | `TEXT` | `NOT NULL` | *None* | Associated tenant space. |
| `user_id` | `TEXT` | `NOT NULL` | *None* | Operator ID performing action. |
| `user_email` | `TEXT` | `NOT NULL` | *None* | Operator email address. |
| `role` | `TEXT` | `NOT NULL` | *None* | Active authorization role context. |
| `action` | `TEXT` | `NOT NULL` | *None* | Action taken (`EDIT_LIMITS`, `DELETE_PLANT`). |
| `resource` | `TEXT` | `NOT NULL` | *None* | Identifier of mutated asset. |
| `detail` | `JSONB` | `NOT NULL` | `'{}'` | JSON metadata holding diff states (pre/post values). |
| `created_at` | `TIMESTAMPTZ`| `PRIMARY KEY` | `now()` | Log commit timestamp. |

---

## 5. Continuous Aggregates (Materialized Rollups)

Continuous aggregates optimize multi-day analytical queries in Grafana. Rather than scanning millions of raw rows, Grafana queries these pre-materialized summaries. They run on the `telemetry_raw` catch-all hypertable for backward compatibility.

### 5.1 Common Rollup Column Blueprint
All aggregate views share these columns:

| Column | Type | Description |
| :--- | :--- | :--- |
| `bucket` | `TIMESTAMPTZ`| Time-bucket floor (e.g. 5-min intervals). |
| `tenant_id` | `TEXT` | Owner tenant. |
| `plant_id` | `TEXT` | Facility code. |
| `tag_name` | `TEXT` | Targeted tag name. |
| `avg_val` | `DOUBLE PRECISION`| Average sensor value in bucket. |
| `min_val` | `DOUBLE PRECISION`| Minimum sensor value in bucket. |
| `max_val` | `DOUBLE PRECISION`| Maximum sensor value in bucket. |
| `last_val` | `DOUBLE PRECISION`| Latest actual reading in bucket. |
| `sample_count` | `BIGINT` | Total number of data samples within bucket. |

### 5.2 Rollup Configuration Matrix

| Aggregate View Name | Bucket Width | Policy Refresh Start Offset | Policy Refresh End Offset | Policy Refresh Interval | Rollup Data Retention |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`telemetry_1min`** | 1 minute | 2 hours | 1 minute | 1 minute | **7 days** |
| **`telemetry_5min`** | 5 minutes| 12 hours | 5 minutes | 5 minutes | **30 days** |
| **`telemetry_1hour`**| 1 hour | 3 days | 1 hour | 1 hour | **2 years** |
| **`telemetry_1day`** | 1 day | 7 days | 1 day | 1 day | **5 years** |

---

## 6. Security, Roles & Permissions

The database enforces security at the connection and query levels through standard role-grants and granular Row-Level Security.

### 6.1 Database Users & Roles
1. **`historian_app` (NOLOGIN Role):** Full CRUD capability on all standard and partition tables.
2. **`historian_grafana` (NOLOGIN Role):** Strict read-only (`SELECT`) access on telemetry, aggregates, alarm views, and metadata.
3. **`historian_user` (Login User):** Member of `historian_app`. Utilized by the FastAPI asyncpg connection pool.
4. **`grafana_reader` (Login User):** Member of `historian_grafana`. Used by the Grafana PostgreSQL dashboard datasource.

### 6.2 Row-Level Security (RLS)
RLS is enabled on all 22 tenant-scoped tables:
* `telemetry_latest`, `alarms`, `audit_logs`, `tag_metadata`, `alarm_history`, `api_keys`, `plants`
* All 15 `telemetry_{group}` hypertables.

#### The Dynamic Tenant Context Policy
Each table is assigned a policy that matches rows dynamically based on the session variable `app.current_tenant`:
```sql
CREATE POLICY {table_name}_tenant ON {table_name}
    FOR ALL TO historian_app
    USING (tenant_id = current_setting('app.current_tenant', true));
```
When FastAPI checkout connections from the pool, it executes a session setup query:
```sql
SET LOCAL app.current_tenant = 'piccadily';
```
This forces the engine to automatically isolate all returned and inserted rows to `'piccadily'` for the lifetime of that query transaction, preventing multi-tenant data leaks at the database level.
*Note: RLS is forced even on the table owner for `telemetry_latest` via `ALTER TABLE telemetry_latest FORCE ROW LEVEL SECURITY`.*

---

## 7. Convenience View

### `telemetry_all`
A `UNION ALL` logical view spanning all 15 functional telemetry hypertables. Offers analytical queries the comfort of a unified schema without sacrificing the hypertable segmenting performance at scale.
```sql
CREATE VIEW telemetry_all AS
    SELECT *, 'temperature' AS tag_group FROM telemetry_temperature UNION ALL
    SELECT *, 'pressure'                 FROM telemetry_pressure    UNION ALL
    ...
```
Both `historian_app` and `historian_grafana` possess `SELECT` authorization on `telemetry_all`.
