-- ╔══════════════════════════════════════════════════════════════════════════╗
-- ║  PICCADILY INDUSTRIAL HISTORIAN — TimescaleDB Schema v4.0               ║
-- ║  Per-group hypertables · RLS · Continuous Aggregates · Compression      ║
-- ║  Run once on a fresh TimescaleDB 2.x+ / PostgreSQL 15+ instance        ║
-- ║  Requirements: CREATE EXTENSION timescaledb (already enabled in image)  ║
-- ╚══════════════════════════════════════════════════════════════════════════╝
--
-- Execution order matters. Run as the superuser or the DB owner.
-- psql -U postgres -d historian -f init.sql

-- ─────────────────────────────────────────────────────────────────────────────
-- §0  Extensions
-- ─────────────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- ─────────────────────────────────────────────────────────────────────────────
-- §0.1 Roles and Users
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
-- §1  TENANTS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id   TEXT        PRIMARY KEY,
    name        TEXT        NOT NULL,
    plan        TEXT        NOT NULL DEFAULT 'starter',
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
    plant_type  TEXT        NOT NULL DEFAULT 'boiler',
    timezone    TEXT        NOT NULL DEFAULT 'Asia/Kolkata',
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    config      JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, plant_id)
);

CREATE INDEX IF NOT EXISTS idx_plants_tenant ON plants (tenant_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- §3  TAG METADATA  (DB-driven alarm thresholds + tag group assignment)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tag_metadata (
    tenant_id         TEXT    NOT NULL,
    plant_id          TEXT    NOT NULL,
    tag_name          TEXT    NOT NULL,
    description       TEXT,
    engineering_unit  TEXT,
    opc_node_id       TEXT,
    data_type         TEXT    DEFAULT 'Float64',
    tag_group         TEXT,                       -- v4.0: temperature, pressure, level, etc.
    low_low_limit     DOUBLE PRECISION,
    low_limit         DOUBLE PRECISION,
    high_limit        DOUBLE PRECISION,
    high_high_limit   DOUBLE PRECISION,
    deadband          DOUBLE PRECISION DEFAULT 0.0,
    is_active         BOOLEAN  NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, plant_id, tag_name),
    FOREIGN KEY (tenant_id, plant_id) REFERENCES plants (tenant_id, plant_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tag_metadata_active
    ON tag_metadata (tenant_id, plant_id, is_active);

CREATE INDEX IF NOT EXISTS idx_tag_metadata_group
    ON tag_metadata (tag_group) WHERE tag_group IS NOT NULL;


-- ─────────────────────────────────────────────────────────────────────────────
-- §4  API KEYS  (DB-backed edge agent key management)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
    key_id       UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    label        TEXT        NOT NULL,
    tenant_id    TEXT        NOT NULL REFERENCES tenants (tenant_id) ON DELETE CASCADE,
    key_hash     TEXT        NOT NULL UNIQUE,
    is_active    BOOLEAN     NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys (tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash   ON api_keys (key_hash) WHERE is_active = true;


-- ═════════════════════════════════════════════════════════════════════════════
-- §5  PER-GROUP HYPERTABLES — Core v4.0 Architecture
-- ═════════════════════════════════════════════════════════════════════════════
-- Each tag group gets its own hypertable for:
--   • Independent compression policies
--   • Independent retention policies
--   • Faster Grafana queries (no tag_name filter on massive table)
--   • Cleaner per-system alerting

CREATE TABLE IF NOT EXISTS tag_routing_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,
    pattern_type TEXT NOT NULL CHECK (pattern_type IN ('prefix', 'suffix', 'regex')),
    target_table TEXT NOT NULL CHECK (
        target_table IN (
            'telemetry_temperature', 'telemetry_pressure', 'telemetry_level',
            'telemetry_draught', 'telemetry_flow', 'telemetry_flow_totalizer',
            'telemetry_motor_rpm', 'telemetry_motor_current', 'telemetry_esp_electrical',
            'telemetry_control_valve', 'telemetry_digital_status', 'telemetry_performance',
            'telemetry_vibration', 'telemetry_power_metering', 'telemetry_raw'
        )
    ),
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tag_routing_rules ON tag_routing_rules(tenant_id, priority DESC);

-- ── §5.1 telemetry_temperature (TE-xxx, TT-xxx — 14 tags) ──────────────────
CREATE TABLE IF NOT EXISTS telemetry_temperature (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_temperature', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_temp_tag_ts
    ON telemetry_temperature (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_temperature SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_temperature',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_temperature',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.2 telemetry_pressure (PT-xxx — 8 tags) ─────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_pressure (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_pressure', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_pres_tag_ts
    ON telemetry_pressure (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_pressure SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_pressure',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_pressure',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.3 telemetry_level (LT-xxx — 6 tags) ────────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_level (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_level', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_level_tag_ts
    ON telemetry_level (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_level SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_level',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_level',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.4 telemetry_draught (DT-xxx) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_draught (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_draught', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_draught_tag_ts
    ON telemetry_draught (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_draught SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_draught',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_draught',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.5 telemetry_flow (FT-xxx) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_flow (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_flow', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_flow_tag_ts
    ON telemetry_flow (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_flow SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_flow',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_flow',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.6 telemetry_flow_totalizer (8hr running totals — long retention) ────
CREATE TABLE IF NOT EXISTS telemetry_flow_totalizer (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_flow_totalizer', 'ts',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_flow_tot_tag_ts
    ON telemetry_flow_totalizer (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_flow_totalizer SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_flow_totalizer',
    compress_after => INTERVAL '30 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_flow_totalizer',
    drop_after => INTERVAL '5 years', if_not_exists => TRUE);


-- ── §5.7 telemetry_motor_rpm (ID/FD/SF/TG/DE/FP RPM) ─────────────────────
CREATE TABLE IF NOT EXISTS telemetry_motor_rpm (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_motor_rpm', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_rpm_tag_ts
    ON telemetry_motor_rpm (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_motor_rpm SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_motor_rpm',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_motor_rpm',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.8 telemetry_motor_current (Ampere readings) ────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_motor_current (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_motor_current', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_current_tag_ts
    ON telemetry_motor_current (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_motor_current SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_motor_current',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_motor_current',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.9 telemetry_esp_electrical (TRCC kV/mA — longer retention) ─────────
CREATE TABLE IF NOT EXISTS telemetry_esp_electrical (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_esp_electrical', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_esp_tag_ts
    ON telemetry_esp_electrical (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_esp_electrical SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_esp_electrical',
    compress_after => INTERVAL '30 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_esp_electrical',
    drop_after => INTERVAL '2 years', if_not_exists => TRUE);


-- ── §5.10 telemetry_control_valve (FCV/TCV/LCV/PCV %) ────────────────────
CREATE TABLE IF NOT EXISTS telemetry_control_valve (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_control_valve', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_valve_tag_ts
    ON telemetry_control_valve (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_control_valve SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_control_valve',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_control_valve',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ── §5.11 telemetry_digital_status (Boolean run/trip — short chunks) ──────
CREATE TABLE IF NOT EXISTS telemetry_digital_status (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_digital_status', 'ts',
    chunk_time_interval => INTERVAL '4 hours',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_digital_tag_ts
    ON telemetry_digital_status (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_digital_status SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_digital_status',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_digital_status',
    drop_after => INTERVAL '90 days', if_not_exists => TRUE);


-- ── §5.12 telemetry_performance (Efficiency calcs — long retention) ───────
CREATE TABLE IF NOT EXISTS telemetry_performance (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_performance', 'ts',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_perf_tag_ts
    ON telemetry_performance (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_performance SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_performance',
    compress_after => INTERVAL '30 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_performance',
    drop_after => INTERVAL '5 years', if_not_exists => TRUE);


-- ── §5.13 telemetry_vibration (mm/s bearing vibs — 2yr retention) ─────────
CREATE TABLE IF NOT EXISTS telemetry_vibration (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_vibration', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_vib_tag_ts
    ON telemetry_vibration (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_vibration SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_vibration',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_vibration',
    drop_after => INTERVAL '2 years', if_not_exists => TRUE);


-- ── §5.14 telemetry_power_metering (kW/kWh/PF — long retention) ──────────
CREATE TABLE IF NOT EXISTS telemetry_power_metering (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_power_metering', 'ts',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_power_tag_ts
    ON telemetry_power_metering (tenant_id, plant_id, tag_name, ts DESC);

ALTER TABLE telemetry_power_metering SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_power_metering',
    compress_after => INTERVAL '30 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_power_metering',
    drop_after => INTERVAL '5 years', if_not_exists => TRUE);


-- ── §5.15 telemetry_raw (catch-all for unclassified tags) ─────────────────
CREATE TABLE IF NOT EXISTS telemetry_raw (
    ts          TIMESTAMPTZ      NOT NULL,
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
    quality     TEXT             NOT NULL DEFAULT 'GOOD',
    unit        TEXT,
    source_id   TEXT
);

SELECT create_hypertable('telemetry_raw', 'ts',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_raw_tag_ts
    ON telemetry_raw (tenant_id, plant_id, tag_name, ts DESC);

CREATE INDEX IF NOT EXISTS idx_raw_ts_brin
    ON telemetry_raw USING BRIN (ts);

ALTER TABLE telemetry_raw SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, plant_id, tag_name',
    timescaledb.compress_orderby   = 'ts DESC'
);

SELECT add_compression_policy('telemetry_raw',
    compress_after => INTERVAL '7 days', if_not_exists => TRUE);

SELECT add_retention_policy('telemetry_raw',
    drop_after => INTERVAL '1 year', if_not_exists => TRUE);


-- ─────────────────────────────────────────────────────────────────────────────
-- §6  TELEMETRY_LATEST  (flat upsert mirror — O(1) current-value reads)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS telemetry_latest (
    tenant_id   TEXT             NOT NULL,
    plant_id    TEXT             NOT NULL,
    tag_name    TEXT             NOT NULL,
    value       DOUBLE PRECISION,
    bool_value  BOOLEAN,
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
    severity      TEXT             NOT NULL,
    alarm_state   TEXT             NOT NULL DEFAULT 'ACTIVE',
    message       TEXT             NOT NULL,
    trigger_value DOUBLE PRECISION NOT NULL,
    occurred_at   TIMESTAMPTZ      NOT NULL DEFAULT now(),
    acked_by      TEXT,
    acked_at      TIMESTAMPTZ,
    PRIMARY KEY (alarm_id, occurred_at)
);

SELECT create_hypertable('alarms', 'occurred_at',
    chunk_time_interval => INTERVAL '1 month',
    migrate_data        => TRUE,
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_alarms_active
    ON alarms (tenant_id, plant_id, alarm_state, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_alarms_tag
    ON alarms (tenant_id, plant_id, tag_name, occurred_at DESC);

SELECT add_retention_policy('alarms',
    drop_after => INTERVAL '3 years', if_not_exists => TRUE);


-- ─────────────────────────────────────────────────────────────────────────────
-- §8  ALARM HISTORY  (immutable audit trail of alarm state transitions)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alarm_history (
    id           BIGSERIAL    PRIMARY KEY,
    alarm_id     UUID         NOT NULL,
    tenant_id    TEXT         NOT NULL,
    action       TEXT         NOT NULL,
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

SELECT create_hypertable('audit_logs', 'created_at',
    chunk_time_interval => INTERVAL '1 month',
    migrate_data        => TRUE,
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant_ts
    ON audit_logs (tenant_id, created_at DESC);

SELECT add_retention_policy('audit_logs',
    drop_after => INTERVAL '2 years', if_not_exists => TRUE);


-- ─────────────────────────────────────────────────────────────────────────────
-- §10  CONTINUOUS AGGREGATES  (on telemetry_raw catch-all)
-- ─────────────────────────────────────────────────────────────────────────────
-- Continuous aggregates are created on telemetry_raw for backward compatibility.
-- Per-group hypertables benefit from direct time_bucket queries which
-- TimescaleDB handles efficiently via chunk exclusion.

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

SELECT add_continuous_aggregate_policy('telemetry_1min',
    start_offset      => INTERVAL '2 hours',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists     => TRUE
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

SELECT add_continuous_aggregate_policy('telemetry_5min',
    start_offset      => INTERVAL '12 hours',
    end_offset        => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists     => TRUE
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

SELECT add_continuous_aggregate_policy('telemetry_1hour',
    start_offset      => INTERVAL '3 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists     => TRUE
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

SELECT add_continuous_aggregate_policy('telemetry_1day',
    start_offset      => INTERVAL '7 days',
    end_offset        => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists     => TRUE
);

-- ── Retain rollups longer than raw data ──────────────────────────────────────
SELECT add_retention_policy('telemetry_1min',  drop_after => INTERVAL '7 days',  if_not_exists => TRUE);
SELECT add_retention_policy('telemetry_5min',  drop_after => INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('telemetry_1hour', drop_after => INTERVAL '2 years', if_not_exists => TRUE);
SELECT add_retention_policy('telemetry_1day',  drop_after => INTERVAL '5 years', if_not_exists => TRUE);


-- ─────────────────────────────────────────────────────────────────────────────
-- §11  ROW LEVEL SECURITY  (tenant isolation at DB level)
-- ─────────────────────────────────────────────────────────────────────────────
-- Enable RLS on ALL tenant-scoped tables.
-- Policies use current_setting('app.current_tenant') set by the app on each connection.

-- Helper: enable RLS + create policy (idempotent)
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT unnest(ARRAY[
            'telemetry_temperature', 'telemetry_pressure', 'telemetry_level',
            'telemetry_draught', 'telemetry_flow', 'telemetry_flow_totalizer',
            'telemetry_motor_rpm', 'telemetry_motor_current', 'telemetry_esp_electrical',
            'telemetry_control_valve', 'telemetry_digital_status', 'telemetry_performance',
            'telemetry_vibration', 'telemetry_power_metering', 'telemetry_raw',
            'telemetry_latest', 'alarms', 'audit_logs', 'tag_metadata',
            'alarm_history', 'plants'
        ])
    LOOP
        -- Enable and Force RLS
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tbl);

        -- Create policy (skip if exists)
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE tablename = tbl AND policyname = tbl || '_tenant'
        ) THEN
            EXECUTE format(
                'CREATE POLICY %I ON %I FOR ALL TO historian_app USING (tenant_id = current_setting(''app.current_tenant'', true))',
                tbl || '_tenant', tbl
            );
        END IF;
    END LOOP;
END;
$$;


-- ─────────────────────────────────────────────────────────────────────────────
-- §12  GRANTS
-- ─────────────────────────────────────────────────────────────────────────────

-- App role: full CRUD on all tables
GRANT SELECT, INSERT, UPDATE, DELETE ON
    tenants, plants, tag_metadata, api_keys,
    telemetry_temperature, telemetry_pressure, telemetry_level,
    telemetry_draught, telemetry_flow, telemetry_flow_totalizer,
    telemetry_motor_rpm, telemetry_motor_current, telemetry_esp_electrical,
    telemetry_control_valve, telemetry_digital_status, telemetry_performance,
    telemetry_vibration, telemetry_power_metering, telemetry_raw,
    telemetry_latest,
    alarms, alarm_history, audit_logs
TO historian_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO historian_app;

-- Grafana role: read-only on telemetry + alarms
GRANT SELECT ON
    telemetry_temperature, telemetry_pressure, telemetry_level,
    telemetry_draught, telemetry_flow, telemetry_flow_totalizer,
    telemetry_motor_rpm, telemetry_motor_current, telemetry_esp_electrical,
    telemetry_control_valve, telemetry_digital_status, telemetry_performance,
    telemetry_vibration, telemetry_power_metering, telemetry_raw,
    telemetry_latest,
    telemetry_1min, telemetry_5min, telemetry_1hour, telemetry_1day,
    alarms, tag_metadata, plants
TO historian_grafana;


-- ─────────────────────────────────────────────────────────────────────────────
-- §13  SEED DATA — default tenant, plant, and tag metadata
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO tenants (tenant_id, name, plan)
VALUES ('piccadily', 'Piccadily Agro Industries', 'pro')
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO plants (tenant_id, plant_id, name, location, plant_type, timezone)
VALUES ('piccadily', 'BOILER_PLC_01', 'Piccadily Boiler Plant 01',
        'PICCADILY_PLANT_01', 'boiler', 'Asia/Kolkata')
ON CONFLICT (tenant_id, plant_id) DO NOTHING;

-- Tag metadata with alarm thresholds from SCADA report (28-08-2025)
INSERT INTO tag_metadata
    (tenant_id, plant_id, tag_name, description, engineering_unit, tag_group,
     low_low_limit, low_limit, high_limit, high_high_limit, deadband)
VALUES
    -- Temperature tags
    ('piccadily','BOILER_PLC_01','TT-201','Steam Temp at Main Steam Line','°C','temperature',
     100, 150, 480, 520, 2),
    ('piccadily','BOILER_PLC_01','TE-101','Feed Water Temp at Economiser Inlet','°C','temperature',
     50, 80, 120, 140, 1.5),
    ('piccadily','BOILER_PLC_01','TE-102','Flue Gas Temp at Economiser Outlet','°C','temperature',
     80, 120, 350, 400, 3),
    ('piccadily','BOILER_PLC_01','TE-201','Superheater Outlet Temp 1','°C','temperature',
     100, 150, 480, 520, 2),
    ('piccadily','BOILER_PLC_01','TE-202','Superheater Outlet Temp 2','°C','temperature',
     100, 150, 480, 520, 2),
    ('piccadily','BOILER_PLC_01','TE-301','Flue Gas Temp at APH Inlet','°C','temperature',
     50, 80, 350, 400, 5),
    ('piccadily','BOILER_PLC_01','TE-302','Flue Gas Temp at APH Outlet','°C','temperature',
     50, 80, 250, 300, 3),
    ('piccadily','BOILER_PLC_01','TE-303','Flue Gas Temp at Cyclone Outlet','°C','temperature',
     50, 80, 300, 350, 5),
    ('piccadily','BOILER_PLC_01','TE-304','Furnace Temperature','°C','temperature',
     100, 200, 950, 1050, 10),
    ('piccadily','BOILER_PLC_01','TE-305','Bed Thermocouple Compartment I','°C','temperature',
     100, 200, 950, 1050, 10),
    ('piccadily','BOILER_PLC_01','TE-306','Air Temp at APH Outlet I','°C','temperature',
     30, 50, 200, 250, 3),
    ('piccadily','BOILER_PLC_01','TE-307','Air Temp at APH Outlet II','°C','temperature',
     30, 50, 200, 250, 3),
    ('piccadily','BOILER_PLC_01','TE-308','Bearing Temperature','°C','temperature',
     20, 40, 85, 95, 2),
    -- Pressure tags
    ('piccadily','BOILER_PLC_01','PT-201','Pressure at Steam Drum','Kg/cm²','pressure',
     10, 20, 48, 52, 0.5),
    ('piccadily','BOILER_PLC_01','PT-202','Pressure at Main Steam Line','Kg/cm²','pressure',
     10, 20, 47, 50, 0.5),
    ('piccadily','BOILER_PLC_01','PT-203','Pressure at Soot Blower Line','Kg/cm²','pressure',
     0.1, 0.3, 1.0, 1.5, 0.05),
    ('piccadily','BOILER_PLC_01','PT-001','Pressure at Deaerator','Kg/cm²','pressure',
     0.1, 0.2, 0.5, 0.6, 0.02),
    -- Level tags
    ('piccadily','BOILER_PLC_01','LT-201','Steam Drum Level I','%','level',
     10, 20, 85, 95, 1),
    ('piccadily','BOILER_PLC_01','LT-202','Steam Drum Level II','%','level',
     10, 20, 85, 95, 1),
    ('piccadily','BOILER_PLC_01','LT-001','Deaerator Storage Tank Level','%','level',
     10, 20, 85, 95, 2),
    -- Draught tag
    ('piccadily','BOILER_PLC_01','DT-401','Furnace Draught Transmitter','mmWc','draught',
     -20, -15, -2, 0, 0.5),
    -- Flow tag
    ('piccadily','BOILER_PLC_01','FT-101','Feed Water Flow','TPH','flow',
     5, 10, 40, 45, 1),
    -- Motor RPM tags
    ('piccadily','BOILER_PLC_01','ID_RPM','ID Fan Motor Speed','RPM','motor_rpm',
     100, 200, 1450, 1500, 10),
    ('piccadily','BOILER_PLC_01','FD_RPM','FD Fan Motor Speed','RPM','motor_rpm',
     100, 200, 1450, 1500, 10),
    ('piccadily','BOILER_PLC_01','SF1_RPM','Screw Feeder 1 Speed','RPM','motor_rpm',
     50, 100, 1000, 1100, 5),
    ('piccadily','BOILER_PLC_01','SF2_RPM','Screw Feeder 2 Speed','RPM','motor_rpm',
     50, 100, 1000, 1100, 5),
    ('piccadily','BOILER_PLC_01','TG_RPM','Travelling Grate Speed','RPM','motor_rpm',
     1, 2, 10, 12, 0.5),
    ('piccadily','BOILER_PLC_01','DE1_RPM','Drum Feeder 1 Speed','RPM','motor_rpm',
     50, 100, 800, 900, 5),
    -- ESP Electrical tags
    ('piccadily','BOILER_PLC_01','TRCC1_VOLT','ESP Field 1 Voltage','kV','esp_electrical',
     10, 20, 60, 65, 1.5),
    ('piccadily','BOILER_PLC_01','TRCC2_VOLT','ESP Field 2 Voltage','kV','esp_electrical',
     10, 20, 60, 65, 1.5),
    ('piccadily','BOILER_PLC_01','TRCC3_VOLT','ESP Field 3 Voltage','kV','esp_electrical',
     10, 20, 60, 65, 1.5),
    -- Flow Totalizer tags
    ('piccadily','BOILER_PLC_01','TOTALIZER_FEED_WATER_CURRENT_8_HRS','Feed Water 8hr Total','TPH','flow_totalizer',
     NULL, NULL, NULL, NULL, 0),
    ('piccadily','BOILER_PLC_01','TOTALIZER_MAIN_STEAM_CURRENT_8_HRS','Main Steam 8hr Total','TPH','flow_totalizer',
     NULL, NULL, NULL, NULL, 0)
ON CONFLICT (tenant_id, plant_id, tag_name) DO NOTHING;

-- Seed Piccadily tag routing rules (migrated from hardcoded Python list)
INSERT INTO tag_routing_rules (tenant_id, pattern, pattern_type, target_table, priority)
VALUES
    ('piccadily', 'TE-', 'prefix', 'telemetry_temperature', 10),
    ('piccadily', 'TT-', 'prefix', 'telemetry_temperature', 10),
    ('piccadily', 'TE_', 'prefix', 'telemetry_temperature', 10),
    ('piccadily', 'PT-', 'prefix', 'telemetry_pressure', 10),
    ('piccadily', 'PT_', 'prefix', 'telemetry_pressure', 10),
    ('piccadily', 'LT-', 'prefix', 'telemetry_level', 10),
    ('piccadily', 'LT_', 'prefix', 'telemetry_level', 10),
    ('piccadily', 'LVL_', 'prefix', 'telemetry_level', 10),
    ('piccadily', 'STEAM_DRUM_LEVEL', 'prefix', 'telemetry_level', 100),
    ('piccadily', 'DT-', 'prefix', 'telemetry_draught', 10),
    ('piccadily', 'DT_', 'prefix', 'telemetry_draught', 10),
    ('piccadily', 'TOTALIZER', 'prefix', 'telemetry_flow_totalizer', 50),
    ('piccadily', 'FT-', 'prefix', 'telemetry_flow', 10),
    ('piccadily', 'FT_', 'prefix', 'telemetry_flow', 10),
    ('piccadily', 'ID_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'FD_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'SF1_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'SF2_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'SF3_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'DE1_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'DE2_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'DE3_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'FP1_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'FP2_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'TG_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'DRM_FDR_RPM', 'prefix', 'telemetry_motor_rpm', 20),
    ('piccadily', 'GM_', 'prefix', 'telemetry_motor_rpm', 10),
    ('piccadily', '_RPM', 'suffix', 'telemetry_motor_rpm', 5),
    ('piccadily', '_AMP', 'suffix', 'telemetry_motor_current', 5),
    ('piccadily', 'AMP_', 'prefix', 'telemetry_motor_current', 5),
    ('piccadily', '_CURRENT', 'suffix', 'telemetry_motor_current', 5),
    ('piccadily', 'TRCC', 'prefix', 'telemetry_esp_electrical', 10),
    ('piccadily', 'ESP_', 'prefix', 'telemetry_esp_electrical', 10),
    ('piccadily', 'FCV_', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', 'FCV-', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', 'TCV_', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', 'TCV-', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', 'LCV_', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', 'LCV-', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', 'PCV_', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', 'PCV-', 'prefix', 'telemetry_control_valve', 10),
    ('piccadily', '_RUN', 'suffix', 'telemetry_digital_status', 5),
    ('piccadily', '_TRIP', 'suffix', 'telemetry_digital_status', 5),
    ('piccadily', 'INTLK', 'prefix', 'telemetry_digital_status', 5),
    ('piccadily', '_STATUS', 'suffix', 'telemetry_digital_status', 5),
    ('piccadily', 'BOILER_EFF', 'prefix', 'telemetry_performance', 100),
    ('piccadily', 'STEAM_QUALITY', 'prefix', 'telemetry_performance', 100),
    ('piccadily', 'HEAT_RATE', 'prefix', 'telemetry_performance', 100),
    ('piccadily', 'EFF_', 'prefix', 'telemetry_performance', 10),
    ('piccadily', 'VIB_', 'prefix', 'telemetry_vibration', 10),
    ('piccadily', 'VIB-', 'prefix', 'telemetry_vibration', 10),
    ('piccadily', 'PWR_', 'prefix', 'telemetry_power_metering', 10),
    ('piccadily', 'KWH', 'prefix', 'telemetry_power_metering', 10),
    ('piccadily', 'KW_', 'prefix', 'telemetry_power_metering', 10),
    ('piccadily', 'PF_', 'prefix', 'telemetry_power_metering', 10);

-- ─────────────────────────────────────────────────────────────────────────────
-- §14  CONVENIENCE VIEW — telemetry_all (UNION ALL across group tables)
-- ─────────────────────────────────────────────────────────────────────────────
-- Useful for ad-hoc queries. Not used by the API (which queries specific tables).
CREATE OR REPLACE VIEW telemetry_all AS
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'temperature' AS tag_group FROM telemetry_temperature
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'pressure' FROM telemetry_pressure
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'level' FROM telemetry_level
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'draught' FROM telemetry_draught
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'flow' FROM telemetry_flow
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'flow_totalizer' FROM telemetry_flow_totalizer
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'motor_rpm' FROM telemetry_motor_rpm
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'motor_current' FROM telemetry_motor_current
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'esp_electrical' FROM telemetry_esp_electrical
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'control_valve' FROM telemetry_control_valve
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'digital_status' FROM telemetry_digital_status
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'performance' FROM telemetry_performance
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'vibration' FROM telemetry_vibration
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'power_metering' FROM telemetry_power_metering
    UNION ALL
    SELECT ts, tenant_id, plant_id, tag_name, value, bool_value, quality, unit, source_id, 'raw' FROM telemetry_raw;

GRANT SELECT ON telemetry_all TO historian_app;
GRANT SELECT ON telemetry_all TO historian_grafana;

-- ═════════════════════════════════════════════════════════════════════════════
-- Schema v4.0 complete.
-- Expected: 15 hypertables + 4 continuous aggregates + 1 convenience view
-- Verify: SELECT count(*) FROM timescaledb_information.hypertables;  -- should be ≥ 17
-- ═════════════════════════════════════════════════════════════════════════════
