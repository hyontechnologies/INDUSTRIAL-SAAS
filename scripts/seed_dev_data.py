#!/usr/bin/env python3
"""
Piccadily Industrial Historian — Dev Data Seeder
Backfills 24 hours of telemetry data for 'BOILER_PLC_01' into TimescaleDB.
Uses realistic sine wave simulation to produce meaningful Grafana trends out of the box.
"""

import asyncio
import math
import os
import random
from datetime import datetime, timedelta, timezone

import asyncpg
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_URL = os.getenv("DATABASE_URL", "postgresql://historian_user:historian_dev_password@localhost:5432/historian")

TENANT_ID = "piccadily"
PLANT_ID = "BOILER_PLC_01"
DAYS_TO_SEED = 1
POINTS_PER_MINUTE = 1  # 1 sample every minute

TAG_CONFIG = [
    ("temperature", "TT-201", "°C", 400.0, 10.0),
    ("temperature", "TE-101", "°C", 100.0, 5.0),
    ("temperature", "TE-201", "°C", 400.0, 10.0),
    ("temperature", "TE-301", "°C", 200.0, 15.0),
    ("temperature", "TE-304", "°C", 600.0, 50.0),
    ("temperature", "TE-305", "°C", 600.0, 50.0),
    ("pressure", "PT-201", "Kg/cm²", 30.0, 5.0),
    ("pressure", "PT-202", "Kg/cm²", 29.0, 5.0),
    ("pressure", "PT-203", "Kg/cm²", 0.8, 0.1),
    ("pressure", "PT-001", "Kg/cm²", 0.3, 0.05),
    ("level", "LT-201", "%", 50.0, 20.0),
    ("level", "LT-202", "%", 50.0, 20.0),
    ("level", "LT-001", "%", 50.0, 20.0),
    ("draught", "DT-401", "mmWc", -10.0, 3.0),
    ("flow", "FT-101", "TPH", 25.0, 5.0),
    ("motor_rpm", "ID_RPM", "RPM", 1000.0, 200.0),
    ("motor_rpm", "FD_RPM", "RPM", 1000.0, 200.0),
    ("motor_rpm", "SF1_RPM", "RPM", 500.0, 100.0),
    ("motor_rpm", "TG_RPM", "RPM", 5.0, 1.0),
    ("esp_electrical", "TRCC1_VOLT", "kV", 40.0, 10.0),
    ("esp_electrical", "TRCC2_VOLT", "kV", 40.0, 10.0),
]


async def seed_data():
    print(f"Connecting to {DB_URL}...")
    conn = await asyncpg.connect(DB_URL)

    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=DAYS_TO_SEED)

        print(f"Seeding from {start_time} to {end_time}...")

        # We will bulk insert into the specific hypertable
        records_by_group = {c[0]: [] for c in TAG_CONFIG}

        curr_time = start_time
        t_seq = 0.0

        total_points = 0

        while curr_time <= end_time:
            t_seq += 1.0
            for config in TAG_CONFIG:
                group, tag, unit, mean, amp = config

                # Daily cycle
                hour_val = curr_time.hour + (curr_time.minute / 60.0)
                daily_mod = math.sin(math.pi * (hour_val - 6) / 12)  # Peak at 12:00

                # High frequency oscillation
                osc = math.sin(t_seq * 0.1)

                # Noise
                noise = random.uniform(-1, 1)

                val = mean + (daily_mod * amp * 0.5) + (osc * amp * 0.4) + (noise * amp * 0.1)
                if val < 0 and group != "draught":
                    val = 0.0

                records_by_group[group].append((curr_time, TENANT_ID, PLANT_ID, tag, float(val), "GOOD", unit, "seed"))
                total_points += 1

            curr_time += timedelta(minutes=1)

        # Perform COPY for each group
        for group, records in records_by_group.items():
            if not records:
                continue

            table_name = f"telemetry_{group}"
            print(f"Inserting {len(records)} points into {table_name}...")

            await conn.copy_records_to_table(
                table_name,
                records=records,
                columns=["ts", "tenant_id", "plant_id", "tag_name", "value", "quality", "unit", "source_id"],
            )

        print(f"Successfully seeded {total_points} data points.")

        # Update latest
        print("Updating telemetry_latest...")
        for group, records in records_by_group.items():
            if not records:
                continue
            # Get last record for each tag in this group
            latest_recs = {}
            for r in records:
                latest_recs[r[3]] = r  # tag_name is index 3

            for r in latest_recs.values():
                await conn.execute(
                    """
                    INSERT INTO telemetry_latest (tenant_id, plant_id, tag_name, value, quality, ts, unit)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (tenant_id, plant_id, tag_name)
                    DO UPDATE SET value=EXCLUDED.value, quality=EXCLUDED.quality, ts=EXCLUDED.ts, unit=EXCLUDED.unit
                    """,
                    r[1],
                    r[2],
                    r[3],
                    r[4],
                    r[5],
                    r[0],
                    r[6],
                )

        # Refresh continuous aggregates
        print("Refreshing continuous aggregates...")
        aggs = ["telemetry_1min", "telemetry_5min", "telemetry_1hour", "telemetry_1day"]
        for agg in aggs:
            try:
                # The continuous aggregates in init.sql use refresh_continuous_aggregate
                await conn.execute(f"CALL refresh_continuous_aggregate('{agg}', NULL, NULL)")
                print(f"  Refreshed {agg}")
            except Exception as e:
                print(f"  Could not refresh {agg}: {e}")

        print("Done!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
