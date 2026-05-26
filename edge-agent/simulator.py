#!/usr/bin/env python3
"""
=============================================================================
PICCADILY INDUSTRIAL HISTORIAN — OPC UA PLC Simulator v1.0
Simulates a Boiler PLC with realistic fluctuating values for development.
=============================================================================
"""

import asyncio
import logging
import math
import random

from asyncua import Server, ua

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Simulator")

# Simulation config
OPC_PORT = 4840
OPC_NS_URI = "urn:piccadily:boilerbridge"

# Simulates the initial seed data from timescaledb/init.sql
TAG_CONFIG = [
    ("temperature", "TT-201", "°C", 400.0, 10.0),  # Mean, amplitude
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


async def update_tags(nodes):
    t = 0.0
    while True:
        t += 1.0
        for node, config in nodes:
            group, tag, unit, mean, amp = config

            # Simple sine wave + noise
            val = mean + (math.sin(t * 0.1) * amp) + (random.uniform(-1, 1) * amp * 0.1)

            # Keep values reasonable
            if val < 0 and group != "draught":
                val = 0.0

            await node.write_value(float(val))

        await asyncio.sleep(1.0)


async def main():
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{OPC_PORT}/piccadily/")
    server.set_server_name("Piccadily Simulator")

    # Setup namespace
    ns_idx = await server.register_namespace(OPC_NS_URI)

    # Create object hierarchy
    objects = server.nodes.objects
    plant_node = await objects.add_folder(ns_idx, "BOILER_PLC_01")
    device_node = await plant_node.add_folder(ns_idx, "BOILER_PLC_01")

    nodes = []
    groups = {}

    for config in TAG_CONFIG:
        group, tag, unit, mean, amp = config

        if group not in groups:
            groups[group] = await device_node.add_folder(ns_idx, group)

        node = await groups[group].add_variable(ns_idx, tag, mean)
        await node.set_writable()

        # Add unit as description like edge_agent.py expects: "[Unit]"
        await node.write_attribute(ua.AttributeIds.Description, ua.DataValue(ua.LocalizedText(f"[{unit}]")))

        nodes.append((node, config))

    log.info(f"Created {len(nodes)} simulated tags.")

    async with server:
        log.info(f"OPC UA Simulator running on opc.tcp://0.0.0.0:{OPC_PORT}/piccadily/")
        await update_tags(nodes)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Simulator stopped.")
