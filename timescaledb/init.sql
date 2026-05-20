-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  PICCADILY INDUSTRIAL HISTORIAN — TimescaleDB Schema v3.0               ║
-- ║  Run once on a fresh TimescaleDB 2.x+ / PostgreSQL 15+ instance         ║
-- ║  Requirements: CREATE EXTENSION timescaledb (already enabled in image)  ║
-- ╚══════════════════════════════════════════════════════════════════════════╝
--
-- Execution order matters. Run this file as the superuser or the DB owner.
-- psql -U postgres -d historian -f schema.sql

-- ─────────────────────────────────────────────────────────────────────────────
-- §0  Extensions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;   -- query performance insight

-- ─────────────────────────────────────────────────────────────────────────────
-- §0.1 Roles and Users (Created early to satisfy policy references)
-- ─────────────────────────────────────────────────────────────────────────────
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'historian_app') THEN
        CREATE ROLE historian_app NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'historian_grafana') THEN
        CREATE ROLE historian_grafana NOLOGIN;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'historian_user') THEN
        CREATE USER historian_user WITH PASSWORD 'CHANGE_IN_PRODUCTION';
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana_reader') THEN
        CREATE USER grafana_reader WITH PASSWORD 'CHANGE_IN_PRODUCTION';
    END IF;
END $$;

GRANT historian_app     TO historian_user;
GRANT historian_grafana TO grafana_reader;


-- ─────────────────────────────────────────────────────────────────────────────
-- §1  TENANTS  (multi-tenant root table)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id   TEXT        PRIMARY KEY,
    name        TEXT        NOT NULL,
    plan        TEXT        NOT NULL DEFAULT 'starter',   -- starter | pro | enterprise
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenants_active ON tenants (is_active);

-- ─────────────────────────────────────────────────────────────────────────────
-- §2  PLANTS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS plants (
    tenant_id   TEXT        NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    plant_id    TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    location    TEXT,
    plant_type  TEXT        NOT NULL DEFAULT 'boiler',   -- boiler | wtp | stp | power | utility
    timezone    TEXT        NOT NULL DEFAULT 'Asia/Kolkata',
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    config      JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, plant_id)
);

CREATE INDEX IF NOT EXISTS idx_plants_tenant ON plants (tenant_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- §3  TAG METADATA  (DB-driven alarm thresholds)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tag_metadata (
    tenant_id         TEXT    NOT NULL,
    plant_id          TEXT    NOT NULL,
    tag_name          TEXT    NOT NULL,
    description       TEXT,
    engineering_unit  TEXT,
    opc_node_id       TEXT,                 -- OPC UA NodeId string (ns=2;s=...)
    data_type         TEXT    DEFAULT 'Float64',
    -- Alarm limits (NULL = no limit configured)
    low_low_limit     DOUBLE PRECISION,     -- CRITICAL low
    low_limit         DOUBLE PRECISION,     -- ALARM low
    high_limit        DOUBLE PRECISION,     -- ALARM high
    high_high_limit   DOUBLE PRECISION,     -- CRITICAL high
    deadband          DOUBLE PRECISION DEFAULT 0.0,
    is_active         BOOLEAN  NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, plant_id, tag_name),
    FOREIGN KEY (tenant_id, plant_id) REFERENCES plants (tenant_id, plant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tag_metadata_active
    ON tag_metadata (tenant_id, plant_id, is_active);

-- ─────────────────────────────────────────────────────────────────────────────
-- §4  API KEYS  (DB-backed edge agent key management)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    key_id       UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    label        TEXT        NOT NULL,
    tenant_id    TEXT        NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    key_hash     TEXT        NOT NULL UNIQUE,   -- SHA-256 of raw key
    is_active    BOOLEAN     NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ,                   -- NULL = never expires
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant    ON api_keys (tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash      ON api_keys (key_hash) WHERE is_active = true;

-- ─────────────────────────────────────────────────────────────────────────────
-- §5  TELEMETRY_RAW  (TimescaleDB hypertable — the historian fact table)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_raw (
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',  -- GOOD | BAD | UNCERTAIN | STALE
    ts          TIMESTAMPTZ      NOT NULL,
    unit        TEXT,
    source_id   TEXT            -- OPC UA NodeId (for provenance)
);

-- Convert to hypertable (chunk by 1 day — optimal for 4 GB RAM)
SELECT create_hypertable(
    'telemetry_raw', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_raw_tag_ts
    ON telemetry_raw (tenant_id, plant_id, tag_name, ts DESC);

CREATE INDEX IF NOT EXISTS idx_raw_ts_brin
    ON telemetry_raw USING BRIN (ts);    -- fast range scans on ts

-- ── Compression (reduces storage 10-40×) ─────────────────────────────────────
ALTER TABLE telemetry_raw SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

-- Compress chunks older than 7 days
SELECT add_compression_policy(
    'telemetry_raw',
    compress_after => INTERVAL '7 days',
    if_not_exists  => TRUE
);

-- ── Retention: delete raw data older than 1 year ──────────────────────────────
SELECT add_retention_policy(
    'telemetry_raw',
    drop_after    => INTERVAL '1 year',
    if_not_exists => TRUE
);

-- ─────────────────────────────────────────────────────────────────────────────
-- §6  TELEMETRY_LATEST  (flat upsert mirror — O(1) current-value reads)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_latest (
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    ts          TIMESTAMPTZ      NOT NULL,
    unit        TEXT,
    PRIMARY KEY (tenant_id, plant_id, tag_name)
);

CREATE INDEX IF NOT EXISTS idx_latest_plant
    ON telemetry_latest (tenant_id, plant_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- §7  ALARMS  (hypertable with state machine)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id      UUID             NOT NULL DEFAULT uuid_generate_v4(),
    tenant_id     TEXT             NOT NULL,
    plant_id      TEXT             NOT NULL,
    tag_name      TEXT             NOT NULL,
    severity      TEXT             NOT NULL,   -- INFO | WARNING | ALARM | CRITICAL
    alarm_state   TEXT             NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | ACKNOWLEDGED | CLEARED
    message       TEXT             NOT NULL,
    trigger_value DOUBLE PRECISION NOT NULL,
    occurred_at   TIMESTAMPTZ      NOT NULL DEFAULT now(),
    acked_by      TEXT,
    acked_at      TIMESTAMPTZ,
    PRIMARY KEY (alarm_id, occurred_at)
);

-- Convert alarms to hypertable (partitioned by day)
SELECT create_hypertable(
    'alarms', 'occurred_at',
    chunk_time_interval => INTERVAL '1 month',
    migrate_data        => TRUE,
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_alarms_active
    ON alarms (tenant_id, plant_id, alarm_state, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_alarms_tag
    ON alarms (tenant_id, plant_id, tag_name, occurred_at DESC);

-- Enable Row Level Security before compression is turned on
ALTER TABLE alarms ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'alarms' AND policyname = 'alarms_tenant') THEN
        CREATE POLICY alarms_tenant ON alarms
            FOR ALL TO historian_app
            USING (tenant_id = current_setting('app.current_tenant', true));
    END IF;
END $$;

-- Retain alarm history for 3 years
SELECT add_retention_policy(
    'alarms',
    drop_after    => INTERVAL '3 years',
    if_not_exists => TRUE
);

-- ─────────────────────────────────────────────────────────────────────────────
-- §8  ALARM HISTORY  (immutable audit trail of alarm state transitions)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alarm_history (
    id           BIGSERIAL    PRIMARY KEY,
    alarm_id     UUID         NOT NULL,
    tenant_id    TEXT         NOT NULL,
    action       TEXT         NOT NULL,    -- ACKNOWLEDGED | CLEARED | REOPENED
    performed_by TEXT         NOT NULL,
    comment      TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alarm_history_alarm
    ON alarm_history (alarm_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_alarm_history_tenant
    ON alarm_history (tenant_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- §9  AUDIT_LOGS  (hypertable — all user actions)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGSERIAL,
    tenant_id   TEXT         NOT NULL,
    user_id     TEXT         NOT NULL,
    user_email  TEXT         NOT NULL,
    role        TEXT         NOT NULL,
    action      TEXT         NOT NULL,
    resource    TEXT         NOT NULL,
    detail      JSONB        NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
);

SELECT create_hypertable(
    'audit_logs', 'created_at',
    chunk_time_interval => INTERVAL '1 month',
    migrate_data        => TRUE,
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant_ts
    ON audit_logs (tenant_id, created_at DESC);

-- Enable Row Level Security before compression is turned on
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'audit_logs' AND policyname = 'audit_logs_tenant') THEN
        CREATE POLICY audit_logs_tenant ON audit_logs
            FOR ALL TO historian_app
            USING (tenant_id = current_setting('app.current_tenant', true));
    END IF;
END $$;



SELECT add_retention_policy(
    'audit_logs',
    drop_after    => INTERVAL '2 years',
    if_not_exists => TRUE
);

-- ─────────────────────────────────────────────────────────────────────────────
-- §10  CONTINUOUS AGGREGATES  (pre-materialized rollups for Grafana + API)
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1-minute rollup ──────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1min
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
    SELECT
        time_bucket('1 minute', ts) AS bucket,
        tenant_id,
        plant_id,
        tag_name,
        avg(value)              AS avg_val,
        min(value)              AS min_val,
        max(value)              AS max_val,
        last(value, ts)         AS last_val,
        count(*)                AS sample_count
    FROM telemetry_raw
    GROUP BY bucket, tenant_id, plant_id, tag_name
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'telemetry_1min',
    start_offset  => INTERVAL '2 hours',
    end_offset    => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);

-- ── 5-minute rollup ──────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_5min
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
    SELECT
        time_bucket('5 minutes', ts) AS bucket,
        tenant_id,
        plant_id,
        tag_name,
        avg(value)              AS avg_val,
        min(value)              AS min_val,
        max(value)              AS max_val,
        last(value, ts)         AS last_val,
        count(*)                AS sample_count
    FROM telemetry_raw
    GROUP BY bucket, tenant_id, plant_id, tag_name
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'telemetry_5min',
    start_offset  => INTERVAL '12 hours',
    end_offset    => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- ── 1-hour rollup ────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1hour
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
    SELECT
        time_bucket('1 hour', ts) AS bucket,
        tenant_id,
        plant_id,
        tag_name,
        avg(value)              AS avg_val,
        min(value)              AS min_val,
        max(value)              AS max_val,
        last(value, ts)         AS last_val,
        count(*)                AS sample_count
    FROM telemetry_raw
    GROUP BY bucket, tenant_id, plant_id, tag_name
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'telemetry_1hour',
    start_offset  => INTERVAL '3 days',
    end_offset    => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ── 1-day rollup ─────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1day
WITH (timescaledb.continuous, timescaledb.materialized_only = false)
AS
    SELECT
        time_bucket('1 day', ts) AS bucket,
        tenant_id,
        plant_id,
        tag_name,
        avg(value)              AS avg_val,
        min(value)              AS min_val,
        max(value)              AS max_val,
        last(value, ts)         AS last_val,
        count(*)                AS sample_count
    FROM telemetry_raw
    GROUP BY bucket, tenant_id, plant_id, tag_name
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'telemetry_1day',
    start_offset  => INTERVAL '7 days',
    end_offset    => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ── Retain rollups longer than raw data ──────────────────────────────────────
SELECT add_retention_policy('telemetry_1min',  drop_after => INTERVAL '7 days',  if_not_exists => TRUE);
SELECT add_retention_policy('telemetry_5min',  drop_after => INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('telemetry_1hour', drop_after => INTERVAL '2 years', if_not_exists => TRUE);
SELECT add_retention_policy('telemetry_1day',  drop_after => INTERVAL '5 years', if_not_exists => TRUE);

-- ─────────────────────────────────────────────────────────────────────────────
-- §11  ROW LEVEL SECURITY  (tenant isolation at DB level)
-- ─────────────────────────────────────────────────────────────────────────────


GRANT SELECT, INSERT, UPDATE, DELETE ON
    tenants, plants, tag_metadata, api_keys,
    telemetry_raw, telemetry_latest,
    alarms, alarm_history, audit_logs
TO historian_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO historian_app;

GRANT SELECT ON
    telemetry_raw, telemetry_latest, telemetry_1min, telemetry_5min,
    telemetry_1hour, telemetry_1day, alarms, tag_metadata, plants
TO historian_grafana;

ALTER TABLE telemetry_latest  ENABLE ROW LEVEL SECURITY;
ALTER TABLE tag_metadata      ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'telemetry_latest' AND policyname = 'telemetry_latest_tenant') THEN
        CREATE POLICY telemetry_latest_tenant ON telemetry_latest
            FOR ALL TO historian_app
            USING (tenant_id = current_setting('app.current_tenant', true));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'tag_metadata' AND policyname = 'tag_metadata_tenant') THEN
        CREATE POLICY tag_metadata_tenant ON tag_metadata
            FOR ALL TO historian_app
            USING (tenant_id = current_setting('app.current_tenant', true));
    END IF;
END $$;

ALTER TABLE telemetry_latest FORCE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────────────────────
-- §13  SEED DATA — default tenant and plant
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO tenants (tenant_id, name, plan)
VALUES ('piccadily', 'Piccadily Agro Industries', 'pro')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO plants (tenant_id, plant_id, name, location, plant_type, timezone)
VALUES ('piccadily', 'BOILER_PLC_01', 'Piccadily Boiler Plant 01',
        'PICCADILY_PLANT_01', 'boiler', 'Asia/Kolkata')
ON CONFLICT (tenant_id, plant_id) DO NOTHING;

-- ── Seed tag metadata for key boiler tags ────────────────────────────────────
INSERT INTO tag_metadata
    (tenant_id, plant_id, tag_name, description, engineering_unit,
     low_low_limit, low_limit, high_limit, high_high_limit, deadband)
VALUES
    ('piccadily','BOILER_PLC_01','TT-201','Superheater Outlet Temp 1','°C',      100, 150, 480, 520, 2),
    ('piccadily','BOILER_PLC_01','TT-202','Superheater Outlet Temp 2','°C',      100, 150, 480, 520, 2),
    ('piccadily','BOILER_PLC_01','TT-301','Main Steam Temp','°C',                100, 150, 490, 530, 2),
    ('piccadily','BOILER_PLC_01','PT-201','Main Steam Pressure','bar',           10,  20,  95,  105, 0.5),
    ('piccadily','BOILER_PLC_01','LT-001','Feed Water Tank Level','%',           10,  20,  85,  95,  1),
    ('piccadily','BOILER_PLC_01','LT-201','Steam Drum Level 1','%',              10,  20,  85,  95,  1),
    ('piccadily','BOILER_PLC_01','LT-202','Steam Drum Level 2','%',              10,  20,  85,  95,  1),
    ('piccadily','BOILER_PLC_01','DT-301','Furnace Draught','mmWC',             -20, -15,  -3,  -2,  0.5),
    ('piccadily','BOILER_PLC_01','FT-101','Feed Water Flow','t/h',               5,   10, 100, 120, 1),
    ('piccadily','BOILER_PLC_01','Steam Drum Level','Steam Drum Level','mm',    20,   30,  70,  80,  2),
    ('piccadily','BOILER_PLC_01','Main Steam Pressure','Main Steam Pressure','bar', 10, 20, 98, 105, 0.5),
    ('piccadily','BOILER_PLC_01','Furnace Draught','Furnace Draught','mmWC',   -22, -18,  -4,  -2,  0.5),
    ('piccadily','BOILER_PLC_01','Feed Water Flow','Feed Water Flow','t/h',      5,   10, 100, 120, 1),
    ('piccadily','BOILER_PLC_01','FD Fan RPM','FD Fan RPM','RPM',               100, 200,1450, 1500, 10),
    ('piccadily','BOILER_PLC_01','SA Fan RPM','SA Fan RPM','RPM',               100, 200,1450, 1500, 10),
    ('piccadily','BOILER_PLC_01','ID Fan RPM','ID Fan RPM','RPM',               100, 200,1450, 1500, 10)
ON CONFLICT (tenant_id, plant_id, tag_name) DO NOTHING;
