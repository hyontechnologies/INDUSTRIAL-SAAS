-- Piccadily Industrial Historian v4.0 — Dev Seed Data (for testing only)
-- Inserts a few points into telemetry_latest and telemetry_temperature/pressure to test routing

INSERT INTO tenants (tenant_id, name, plan)
VALUES ('piccadily', 'Piccadily Agro Industries', 'pro')
ON CONFLICT DO NOTHING;

INSERT INTO plants (tenant_id, plant_id, name)
VALUES ('piccadily', 'BOILER_PLC_01', 'Boiler 1')
ON CONFLICT DO NOTHING;

-- This is just for local dev testing if the python seeder isn't used
INSERT INTO telemetry_temperature (ts, tenant_id, plant_id, tag_name, value)
VALUES
    (now() - interval '1 hour', 'piccadily', 'BOILER_PLC_01', 'TT-201', 450.5),
    (now() - interval '30 minutes', 'piccadily', 'BOILER_PLC_01', 'TT-201', 451.2),
    (now(), 'piccadily', 'BOILER_PLC_01', 'TT-201', 452.0);

INSERT INTO telemetry_latest (tenant_id, plant_id, tag_name, value, ts)
VALUES
    ('piccadily', 'BOILER_PLC_01', 'TT-201', 452.0, now())
ON CONFLICT (tenant_id, plant_id, tag_name)
DO UPDATE SET value = EXCLUDED.value, ts = EXCLUDED.ts;
