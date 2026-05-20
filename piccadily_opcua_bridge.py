#!/usr/bin/env python3
"""
=============================================================================
PICCADILY AGRO INDUSTRIES — Python OPC UA Bridge  v2.0  (FINAL)
=============================================================================
Replaces KEPServerEX entirely.  Zero-licence, Python-native stack.

Architecture:
    PyModbus Simulator (port 5022)
        └─► THIS BRIDGE (Modbus TCP client + OPC UA server)
              └─► OPC UA endpoint  opc.tcp://0.0.0.0:4840/piccadily/
                    └─► Edge Agent (asyncua subscriber)
                          └─► FastAPI → TimescaleDB → Grafana

FULL 422+ TAG COVERAGE — VERIFIED AGAINST:
  • piccadily_boiler_simulator.py   (register writer address map)
  • extended_registers.py           (Tier-2/3 register writes)

REGISTER ADDRESS MAP (KEP-style 1-based):
  Input  Regs  30001–30629   pymodbus idx = address − 30001
  Holding Regs 40100–40518   pymodbus idx = address − 40001
  Coils        00001–00231   pymodbus idx = address − 1
  ──────────────────────────────────────────────────────────

SCALING FORMULA:
  Standard (0-based span):
      eng = raw * span_hi / 4095
      divisor = _s(span_hi)  →  eng = raw / divisor

  Bi-directional (signed span):
      eng = raw / divisor + span_lo
      divisor, offset = _s_bi(span_lo, span_hi)
      TagDef(…, scale=divisor, scale_offset=offset)

  Totalisers (65535 raw range):
      divisor = _s(span_hi, raw_hi=65535)

  Coils:
      eng = bool(raw)   scale=1.0, no offset

VALIDATION FIXES IN THIS VERSION:
  [FIX-01] MotorRPM tags 30310–30320 remapped to avoid collision with
           VFD-feedback block (30310–30319) which the simulator writes.
           VFD block moved to new group "VfdFeedback".
  [FIX-02] MotorCurrent tags 30356–30366 verified against extended_registers
           addr range 30356–30369. Added missing SF3_AMP→30356, TG_AMP→30359,
           SAC_AMP→30360, BFP1/2_AMP→30361/30362, dos pump amps 30363–30368,
           DRM_FDR_AMP→30369. Removed stale addr 30358,30362–30366 placeholders.
  [FIX-03] MotorRPM extended block 30370–30385 added as "MotorRPMExt".
  [FIX-04] ControlValveFB group added for 30400–30405 (valve feedback regs).
  [FIX-05] ESP block extended: 30453–30468 (currents, primary volts, DERM,
           CERM, insulator heaters, PAF flag).
  [FIX-06] Performance group: 30500–30511 mapped correctly.
  [FIX-07] SootBlower, SystemStatus, PID_PV groups: 30550–30573 added.
  [FIX-08] Dosing group: 30580–30583 added.
  [FIX-09] Utilities group: 30590–30593 added.
  [FIX-10] Vibration & Bearing group: 30600–30610 added.
  [FIX-11] PowerMetering group: 30620–30629 added.
  [FIX-12] VFD setpoints HR 40100–40109 added as "VfdSetpoints".
  [FIX-13] PID outputs HR 40200–40205 added as "PidOutputs".
  [FIX-14] Extended setpoints HR 40504–40515 merged into Setpoints group.
  [FIX-15] Extended coils 30–54 (motor run), 60–85 (faults), 107–121
           (extended interlocks), 200–231 (commands) added.
  [FIX-16] Discrete inputs (alarms 10001–10064) added via read_discrete_inputs
           as a new "Alarms" group using FC2.
  [FIX-17] Draught scaling verified: sim uses _ir(30252, dt_aph_dp, 0, 100)
           so bridge must use _s(100) unipolar for DT_APH_DP etc.
  [FIX-18] Temperature tags 30018–30028 re-aligned to exact sim spans.
  [FIX-19] Pressure tags 30104–30114 re-aligned to exact sim spans.
  [FIX-20] Simulator port default corrected to 5022 in BridgeConfig.

TOTAL TAGS: 431 process points + 5 diagnostic = 436 OPC UA variables.

Requirements:
    pip install asyncua==1.1.0 pymodbus==3.7.0

Usage:
    python3 piccadily_opcua_bridge.py
    python3 piccadily_opcua_bridge.py --modbus-host 192.168.1.10 --modbus-port 5022
    python3 piccadily_opcua_bridge.py --opc-port 4840 --poll-ms 500 --log-level DEBUG

Environment overrides (all optional):
    MODBUS_HOST  MODBUS_PORT  MODBUS_UNIT
    OPC_HOST     OPC_PORT     OPC_NS_URI
    POLL_MS      BATCH_SIZE   LOG_LEVEL
    PLANT_ID     DEVICE_ID
=============================================================================
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
import dotenv

dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

# ── third-party ───────────────────────────────────────────────────────────────
from asyncua import Server, ua  # pip install asyncua
from asyncua.common.node import Node
from pymodbus.client import AsyncModbusTcpClient  # pip install pymodbus>=3.0
from pymodbus.exceptions import ModbusException

# =============================================================================
# LOGGING
# =============================================================================
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("OpcBridge")
logging.getLogger("asyncua").setLevel(logging.WARNING)
logging.getLogger("pymodbus").setLevel(logging.WARNING)


# =============================================================================
# CONFIGURATION
# =============================================================================
@dataclass
class BridgeConfig:
    # ── Modbus source ──────────────────────────────────────────────────────
    modbus_host: str = os.getenv("MODBUS_HOST", "127.0.0.1")
    modbus_port: int = int(os.getenv("MODBUS_PORT", "5022"))  # simulator default
    modbus_unit: int = int(os.getenv("MODBUS_UNIT", "1"))

    # ── OPC UA server ──────────────────────────────────────────────────────
    opc_host: str = os.getenv("OPC_HOST", "0.0.0.0")
    opc_port: int = int(os.getenv("OPC_PORT", "4840"))
    opc_ns_uri: str = os.getenv("OPC_NS_URI", "urn:piccadily:boilerbridge")

    # ── Polling ────────────────────────────────────────────────────────────
    poll_ms: int = int(os.getenv("POLL_MS", "1000"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "100"))

    # ── Reliability ────────────────────────────────────────────────────────
    modbus_timeout: float = float(os.getenv("MODBUS_TIMEOUT", "3.0"))
    reconnect_base: float = float(os.getenv("RECONNECT_BASE", "2.0"))
    reconnect_max: float = float(os.getenv("RECONNECT_MAX", "60.0"))
    stale_threshold: float = float(os.getenv("STALE_THRESHOLD", "30.0"))

    # ── Plant identity ─────────────────────────────────────────────────────
    plant_id: str = os.getenv("PLANT_ID", "PICCADILY_PLANT_01")
    device_id: str = os.getenv("DEVICE_ID", "BOILER_PLC_01")


CFG = BridgeConfig()


# =============================================================================
# MODBUS REGISTER TYPES
# =============================================================================
class RegType(Enum):
    INPUT_REGISTER = auto()  # FC4  read_input_registers   (3xxxx)
    HOLDING_REGISTER = auto()  # FC3  read_holding_registers (4xxxx)
    COIL = auto()  # FC1  read_coils             (0xxxx)
    DISCRETE_INPUT = auto()  # FC2  read_discrete_inputs   (1xxxx)


# =============================================================================
# TAG DEFINITION
# =============================================================================
@dataclass(frozen=True)
class TagDef:
    group: str
    tag: str
    reg_type: RegType
    address: int  # 1-based KEP-style address
    scale: float  # eng = raw / scale  (for COIL: scale=1.0 → bool)
    unit: str
    description: str
    poll_ms: int = 0  # 0 = use global CFG.poll_ms
    scale_offset: float = 0.0  # added after division: eng = raw/scale + offset


# =============================================================================
# SCALING HELPERS
# =============================================================================
def _s(span_hi: float, raw_hi: float = 4095.0) -> float:
    """Divisor for unipolar span 0..span_hi.  eng = raw / _s(span_hi)"""
    return raw_hi / span_hi if span_hi != 0 else 1.0


def _s_bi(span_lo: float, span_hi: float, raw_hi: float = 4095.0) -> Tuple[float, float]:
    """
    Bi-directional divisor+offset for signed spans (e.g. draught -30..+30).
    Returns (divisor, offset) where:  eng = raw / divisor + offset
    """
    total_span = span_hi - span_lo
    divisor = raw_hi / total_span
    offset = span_lo
    return divisor, offset


# =============================================================================
# TAG REGISTRY  —  431 TAGS  (verified against simulator + extended_registers)
# =============================================================================
def _build_registry() -> List[TagDef]:
    IR = RegType.INPUT_REGISTER
    HR = RegType.HOLDING_REGISTER
    CO = RegType.COIL
    DI = RegType.DISCRETE_INPUT

    tags: List[TagDef] = []

    # =========================================================================
    # GROUP: Temperature   Input Registers 30001–30028
    # Simulator writes 30001–30017 in write_all(), 30018–30028 in write_extended()
    # =========================================================================
    G = "Temperature"
    tags += [
        # ── Core 17 tags (write_all) ──────────────────────────────────────
        TagDef(G, "TE_ECON_INLET", IR, 30001, _s(200), "degC", "FW Temp – Economiser Inlet"),
        TagDef(G, "TE_FG_APH_OUT", IR, 30002, _s(300), "degC", "Flue Gas – APH Outlet"),
        TagDef(G, "TE_SB_LINE", IR, 30003, _s(200), "degC", "Soot Blower Steam Line Temp"),
        TagDef(G, "TE_SSH_OUT", IR, 30004, _s(500), "degC", "Secondary SH Outlet Steam Temp", poll_ms=500),
        TagDef(G, "TE_PSH_OUT", IR, 30005, _s(500), "degC", "Primary SH Outlet Steam Temp", poll_ms=500),
        TagDef(G, "TE_SB_HDR", IR, 30006, _s(200), "degC", "Soot Blower Steam Header Temp"),
        TagDef(G, "TE_ECO_OUT", IR, 30007, _s(250), "degC", "Economiser Gas Outlet Temp"),
        TagDef(G, "TE_FG_APH_IN", IR, 30008, _s(200), "degC", "Flue Gas – APH Inlet"),
        TagDef(G, "TE_FURN", IR, 30009, _s(1100), "degC", "Furnace Temperature", poll_ms=500),
        TagDef(G, "TE_BED_1", IR, 30010, _s(400), "degC", "Bed Thermocouple – Compt-I", poll_ms=500),
        TagDef(G, "TE_BED_2", IR, 30011, _s(400), "degC", "Bed Thermocouple – Compt-II", poll_ms=500),
        TagDef(G, "TE_AIR_APH_IN", IR, 30012, _s(100), "degC", "Air Temp APH Inlet (Ambient)"),
        TagDef(G, "TE_AIR_APH_OUT", IR, 30013, _s(200), "degC", "Air Temp APH Outlet (Preheated)"),
        TagDef(G, "TE_FG_ESP_IN", IR, 30014, _s(200), "degC", "Flue Gas Temp – ESP Inlet"),
        TagDef(G, "TE_DEAER", IR, 30015, _s(150), "degC", "Deaerator Internal Temperature"),
        TagDef(G, "TT_DEAER", IR, 30016, _s(150), "degC", "Deaerator Storage Tank Temp"),
        TagDef(G, "TT_MS_TEMP", IR, 30017, _s(500), "degC", "Main Steam Temperature Transmitter", poll_ms=500),
        # ── Extended 11 tags (write_extended: 30018–30028) ────────────────
        # sim: _ir(30018, bed_temp_3, 0, 400)
        TagDef(G, "TE_BED_3", IR, 30018, _s(400), "degC", "Bed Thermocouple – Compt-III", poll_ms=500),
        # sim: _ir(30019, bed_temp_4, 0, 400)
        TagDef(G, "TE_BED_4", IR, 30019, _s(400), "degC", "Bed Thermocouple – Compt-IV", poll_ms=500),
        # sim: _ir(30020, drum_sat_temp, 0, 300)
        TagDef(G, "TE_DRUM_SAT", IR, 30020, _s(300), "degC", "Steam Drum Saturation Temperature"),
        # sim: _ir(30021, te_ssh_in, 0, 400)
        TagDef(G, "TE_SSH_IN", IR, 30021, _s(400), "degC", "Secondary SH Inlet Steam Temp"),
        # sim: _ir(30022, te_psh_in, 0, 400)
        TagDef(G, "TE_PSH_IN", IR, 30022, _s(400), "degC", "Primary SH Inlet Steam Temp"),
        # sim: _ir(30023, te_desup_out, 0, 500)
        TagDef(G, "TE_DESUP_OUT", IR, 30023, _s(500), "degC", "Desuperheater Outlet Steam Temp"),
        # sim: _ir(30024, fw_temp - 5, 0, 150)
        TagDef(G, "TE_FW_PUMP_IN", IR, 30024, _s(150), "degC", "FW Pump Inlet Temperature"),
        # sim: _ir(30025, te_ms_header, 0, 500)
        TagDef(G, "TE_MS_HEADER", IR, 30025, _s(500), "degC", "Main Steam Header Temperature"),
        # sim: _ir(30026, te_cyclone_out, 0, 250)
        TagDef(G, "TE_CYCLONE_OUT", IR, 30026, _s(250), "degC", "Cyclone Outlet Flue Gas Temp"),
        # sim: _ir(30027, te_ash_pit, 0, 200)
        TagDef(G, "TE_ASH_PIT", IR, 30027, _s(200), "degC", "Ash Pit Temperature"),
        # sim: _ir(30028, te_aerofoil_vt, 0, 200)
        TagDef(G, "TE_AEROFOIL_VT", IR, 30028, _s(200), "degC", "Aerofoil Vortex Tube Temperature"),
    ]

    # =========================================================================
    # GROUP: Pressure   Input Registers 30100–30114
    # Sim writes 30100–30103 in write_all(), 30104–30114 in write_extended()
    # =========================================================================
    G = "Pressure"
    tags += [
        # ── Core 4 (write_all) ────────────────────────────────────────────
        # sim: _ir(30100, deaer_pressure, 0, 2.0)
        TagDef(G, "PT_DEAER", IR, 30100, _s(2.0), "kg/cm2", "Deaerator Tank Pressure"),
        # sim: _ir(30101, drum_pressure, 0, 60.0)
        TagDef(G, "PT_DRUM", IR, 30101, _s(60.0), "kg/cm2", "Steam Drum Pressure", poll_ms=500),
        # sim: _ir(30102, ms_pressure, 0, 60.0)
        TagDef(G, "PT_MS", IR, 30102, _s(60.0), "kg/cm2", "Main Steam Line Pressure", poll_ms=500),
        # sim: _ir(30103, max(0, ms_pressure*0.012), 0, 2.0)
        TagDef(G, "PT_SB_LINE", IR, 30103, _s(2.0), "kg/cm2", "Soot Blower Steam Line Pressure"),
        # ── Extended 11 (write_extended: 30104–30114) ────────────────────
        # sim: _ir(30104, drum_pressure, 0, 60.0)   PT_201_RDN
        TagDef(G, "PT_DRUM_RDN", IR, 30104, _s(60.0), "kg/cm2", "Steam Drum Pressure Redundant (PT-201)"),
        # sim: _ir(30105, ms_pressure, 0, 60.0)    PT_202_RDN
        TagDef(G, "PT_MS_RDN", IR, 30105, _s(60.0), "kg/cm2", "Main Steam Pressure Redundant (PT-202)"),
        # sim: _ir(30106, max(0, ms_pressure*0.012), 0, 2.0)  PT_203_SB
        TagDef(G, "PT_SB_HDR", IR, 30106, _s(2.0), "kg/cm2", "Soot Blower Header Pressure (PT-203)"),
        # sim: _ir(30107, deaer_pressure, 0, 2.0)  PT_001_DEAER
        TagDef(G, "PT_DEAER_RDN", IR, 30107, _s(2.0), "kg/cm2", "Deaerator Pressure Redundant (PT-001)"),
        # sim: _ir(30108, pt_fw_pump_out, 0, 70.0)
        TagDef(G, "PT_FW_PUMP_OUT", IR, 30108, _s(70.0), "kg/cm2", "FW Pump Discharge Pressure"),
        # sim: _ir(30109, pt_fw_pump_in, 0, 5.0)
        TagDef(G, "PT_FW_PUMP_IN", IR, 30109, _s(5.0), "kg/cm2", "FW Pump Suction Pressure"),
        # sim: _ir(30110, pt_aerofoil_dp, 0, 1.0)
        TagDef(G, "DP_AEROFOIL", IR, 30110, _s(1.0), "kg/cm2", "Aerofoil DP Transmitter"),
        # sim: _ir(30111, pt_sa_windbox, 0, 500.0)
        TagDef(G, "PT_SA_WINDBOX", IR, 30111, _s(500.0), "mmWc", "Secondary Air Windbox Pressure"),
        # sim: _ir(30112, pt_pa_windbox, 0, 500.0)
        TagDef(G, "PT_PA_WINDBOX", IR, 30112, _s(500.0), "mmWc", "Primary Air Windbox Pressure"),
        # sim: _ir(30113, pt_spray_line, 0, 60.0)
        TagDef(G, "PT_SPRAY_LINE", IR, 30113, _s(60.0), "kg/cm2", "Desuperheater Spray Line Pressure"),
        # sim: _ir(30114, pt_lcv_upstrm, 0, 60.0)
        TagDef(G, "PT_LCV_UPSTRM", IR, 30114, _s(60.0), "kg/cm2", "LCV Upstream Drum Pressure"),
    ]

    # =========================================================================
    # GROUP: Level   Input Registers 30150–30162
    # Sim: 30150–30159 write_all(), 30160–30162 write_extended()
    # =========================================================================
    G = "Level"
    tags += [
        TagDef(G, "LT_DEAER", IR, 30150, _s(100), "%", "Deaerator Storage Tank Level"),
        TagDef(G, "LT_FWST", IR, 30151, _s(100), "%", "Feed Water Storage Tank Level"),
        TagDef(G, "LT_FUEL_BIN", IR, 30152, _s(100), "%", "Fuel Bin Level"),
        TagDef(G, "LT_DRUM_1", IR, 30153, _s(100), "%", "Steam Drum Level LT-201", poll_ms=500),
        TagDef(G, "LT_DRUM_2", IR, 30154, _s(100), "%", "Steam Drum Level LT-202", poll_ms=500),
        TagDef(G, "LT_DRUM_AVG", IR, 30155, _s(100), "%", "Steam Drum Level Average", poll_ms=500),
        TagDef(G, "LTM_DEAER_1", IR, 30156, _s(100), "%", "Deaerator Magnetic Level-1"),
        TagDef(G, "LTM_DEAER_2", IR, 30157, _s(100), "%", "Deaerator Magnetic Level-2"),
        TagDef(G, "LTM_FWST_1", IR, 30158, _s(100), "%", "FW Storage Tank Mag Level-1"),
        TagDef(G, "LTM_FWST_2", IR, 30159, _s(100), "%", "FW Storage Tank Mag Level-2"),
        # write_extended:
        # sim: _ir(30160, fwst_level + 1.5, 0, 100)
        TagDef(G, "LT_FWST_RDN", IR, 30160, _s(100), "%", "FW Storage Tank Redundant Level"),
        # sim: _ir(30161, lt_bfp_seal, 0, 100)
        TagDef(G, "LT_BFP_SEAL", IR, 30161, _s(100), "%", "BFP Mechanical Seal Pot Level"),
        # sim: _ir(30162, drum_level_avg, 0, 100)
        TagDef(G, "LT_DRUM_COMP", IR, 30162, _s(100), "%", "Steam Drum Level Computed Average"),
    ]

    # =========================================================================
    # GROUP: Flow   Input Registers 30200–30208
    # Sim: 30200–30203 write_all(), 30204–30208 write_extended()
    # =========================================================================
    G = "Flow"
    tags += [
        # sim: _ir(30200, ms_flow, 0, 50)
        TagDef(G, "FT_MS_FLOW", IR, 30200, _s(50), "TPH", "Main Steam Flow", poll_ms=500),
        # sim: _ir(30201, fw_flow, 0, 50)
        TagDef(G, "FT_FW_FLOW", IR, 30201, _s(50), "TPH", "Feed Water Flow", poll_ms=500),
        # sim: _ir(30202, fw_tot, 0, 999999.9, 0, 65535)  — 65535 raw range
        TagDef(G, "FT_FW_TOT", IR, 30202, _s(999999.9, 65535), "Tonnes", "Feed Water Totaliser", poll_ms=60000),
        # sim: _ir(30203, ms_tot, 0, 999999.9, 0, 65535)
        TagDef(G, "FT_MS_TOT", IR, 30203, _s(999999.9, 65535), "Tonnes", "Main Steam Totaliser", poll_ms=60000),
        # write_extended:
        # sim: _ir(30204, fw_flow + 0.1, 0, 50)
        TagDef(G, "FT_FW_AEROFOIL", IR, 30204, _s(50), "TPH", "FW Aerofoil Flow Transmitter"),
        # sim: _ir(30205, ft_sb_steam, 0, 5)
        TagDef(G, "FT_SB_STEAM", IR, 30205, _s(5), "TPH", "Soot Blower Steam Consumption"),
        # sim: _ir(30206, ft_spray_flow, 0, 5)
        TagDef(G, "FT_SPRAY_FLOW", IR, 30206, _s(5), "TPH", "Desuperheater Spray Flow"),
        # sim: _ir(30207, ft_fw_8hr, 0, 999999.9, 0, 65535)
        TagDef(G, "FT_FW_8HR", IR, 30207, _s(999999.9, 65535), "Tonnes", "FW 8-Hour Running Total", poll_ms=5000),
        # sim: _ir(30208, ft_ms_8hr, 0, 999999.9, 0, 65535)
        TagDef(G, "FT_MS_8HR", IR, 30208, _s(999999.9, 65535), "Tonnes", "MS 8-Hour Running Total", poll_ms=5000),
    ]

    # =========================================================================
    # GROUP: Draught   Input Registers 30250–30257
    # Sim: 30250 write_all(), 30251–30257 write_extended()
    # All bi-directional spans — verified against simulator _ir() calls
    # =========================================================================
    G = "Draught"
    _d30, _o30 = _s_bi(-30, 30)  # mmWc  furnace draught
    _d100, _o100 = _s_bi(0, 100)  # 0..100 mmWc  APH DP
    _d50, _o50 = _s_bi(0, 50)  # 0..50  mmWc  ESP DP
    _d80, _o80 = _s_bi(0, 80)  # 0..80  mmWc  ECO DP
    _d200, _o200 = _s_bi(-200, 0)  # -200..0 mmWc  IDFA inlet
    _d300, _o300 = _s_bi(0, 300)  # 0..300 mmWc  FDFA outlet
    _d30b, _o30b = _s_bi(-30, 30)  # boiler back-draught

    tags += [
        # sim: _ir(30250, furn_draught, -30, 30)
        TagDef(G, "DT_FURN_DFT", IR, 30250, _d30, "mmWc", "Furnace Draught", poll_ms=500, scale_offset=_o30),
        # sim: _ir(30251, furn_draught + 0.3, -30, 30)
        TagDef(G, "DT_FURN_DFT2", IR, 30251, _d30, "mmWc", "Furnace Draught Redundant", poll_ms=500, scale_offset=_o30),
        # sim: _ir(30252, dt_aph_dp, 0, 100)  — unipolar 0..100 mmWc
        TagDef(G, "DT_APH_DP", IR, 30252, _s(100), "mmWc", "APH Differential Pressure"),
        # sim: _ir(30253, dt_esp_dp, 0, 50)
        TagDef(G, "DT_ESP_DP", IR, 30253, _s(50), "mmWc", "ESP Differential Pressure"),
        # sim: _ir(30254, dt_eco_dp, 0, 80)
        TagDef(G, "DT_ECO_DP", IR, 30254, _s(80), "mmWc", "Economiser Differential Pressure"),
        # sim: _ir(30255, dt_idfa_inlet, -200, 0)
        TagDef(G, "DT_IDFA_INLET", IR, 30255, _d200, "mmWc", "ID Fan Inlet Draught", scale_offset=_o200),
        # sim: _ir(30256, dt_fdfa_out, 0, 300)
        TagDef(G, "DT_FDFA_OUT", IR, 30256, _s(300), "mmWc", "FD Fan Outlet Pressure"),
        # sim: _ir(30257, dt_boiler_back, -30, 30)
        TagDef(G, "DT_BOILER_BACK", IR, 30257, _d30b, "mmWc", "Boiler Back-Draught", scale_offset=_o30b),
    ]

    # =========================================================================
    # GROUP: MotorRPM   Input Registers 30300–30309
    # Sim write_all(): 30300–30309 only.
    # IMPORTANT: 30310–30319 are VFD feedback regs (write_extended).
    #            30370–30385 are extended motor RPM (write_extended).
    # =========================================================================
    G = "MotorRPM"
    tags += [
        TagDef(G, "GM_SF1_RPM", IR, 30300, _s(50), "RPM", "Screw Feeder-1 Speed"),
        TagDef(G, "GM_SF2_RPM", IR, 30301, _s(50), "RPM", "Screw Feeder-2 Speed"),
        TagDef(G, "GM_SF3_RPM", IR, 30302, _s(50), "RPM", "Screw Feeder-3 Speed"),
        TagDef(G, "GM_PF1_RPM", IR, 30303, _s(120), "RPM", "Pocket Feeder-1 Speed"),
        TagDef(G, "GM_PF2_RPM", IR, 30304, _s(300), "RPM", "Pocket Feeder-2 Speed"),
        TagDef(G, "GM_PF3_RPM", IR, 30305, _s(200), "RPM", "Pocket Feeder-3 Speed"),
        TagDef(G, "GM_TG_RPM", IR, 30306, _s(15), "RPM", "Travelling Grate Speed"),
        TagDef(G, "GM_IDFA_RPM", IR, 30307, _s(1500), "RPM", "ID Fan Speed", poll_ms=500),
        TagDef(G, "GM_SA_FAN_RPM", IR, 30308, _s(1500), "RPM", "Secondary Air Fan Speed"),
        TagDef(G, "GM_FDFA_RPM", IR, 30309, _s(1500), "RPM", "FD Fan Speed", poll_ms=500),
    ]

    # =========================================================================
    # GROUP: VfdFeedback   Input Registers 30310–30319
    # Sim write_extended(): VFD feedback from drives
    # =========================================================================
    G = "VfdFeedback"
    tags += [
        # sim: _ir(30310, id_fan_rpm/15.0*100, 0, 100)
        TagDef(G, "VFD_IDFA_SPD_FB", IR, 30310, _s(100), "%", "ID Fan VFD Speed Feedback", poll_ms=500),
        # sim: _ir(30311, fd_fan_rpm/15.0*100, 0, 100)
        TagDef(G, "VFD_FDFA_SPD_FB", IR, 30311, _s(100), "%", "FD Fan VFD Speed Feedback", poll_ms=500),
        # sim: _ir(30312, 0.0, 0, 100)
        TagDef(G, "VFD_SA_SPD_FB", IR, 30312, _s(100), "%", "SA Fan VFD Speed Feedback"),
        # sim: _ir(30313, tg_rpm/15.0*100, 0, 100)
        TagDef(G, "VFD_TG_SPD_FB", IR, 30313, _s(100), "%", "Travelling Grate VFD Speed Feedback"),
        # sim: _ir(30314, id_fan_rpm/1500.0*50, 0, 60)
        TagDef(G, "VFD_IDFA_HZ", IR, 30314, _s(60), "Hz", "ID Fan VFD Output Frequency"),
        # sim: _ir(30315, fd_fan_rpm/1500.0*50, 0, 60)
        TagDef(G, "VFD_FDFA_HZ", IR, 30315, _s(60), "Hz", "FD Fan VFD Output Frequency"),
        # sim: _ir(30316, 0.0, 0, 60)
        TagDef(G, "VFD_SA_HZ", IR, 30316, _s(60), "Hz", "SA Fan VFD Output Frequency"),
        # sim: _ir(30317, 0.0, 0, 999) — fault codes
        TagDef(G, "VFD_IDFA_FAULT", IR, 30317, _s(999), "-", "ID Fan VFD Fault Code", poll_ms=5000),
        # sim: _ir(30318, 0.0, 0, 999)
        TagDef(G, "VFD_FDFA_FAULT", IR, 30318, _s(999), "-", "FD Fan VFD Fault Code", poll_ms=5000),
        # sim: _ir(30319, tg_amp/3.0*100, 0, 200)
        TagDef(G, "VFD_TG_TORQUE", IR, 30319, _s(200), "%", "Travelling Grate VFD Torque Feedback"),
    ]

    # =========================================================================
    # GROUP: MotorCurrent   Input Registers 30350–30369
    # Sim write_all(): 30350–30355 (SF1,SF2,PF1,PF2,IDFA,FDFA amps)
    # Sim write_extended(): 30356–30369 (extended motor amps)
    # =========================================================================
    G = "MotorCurrent"
    tags += [
        # write_all:
        # sim: _ir(30350, sf1_amp, 0, 20)
        TagDef(G, "GM_SF1_AMP", IR, 30350, _s(20), "A", "Screw Feeder-1 Motor Current"),
        # sim: _ir(30351, sf2_amp, 0, 20)
        TagDef(G, "GM_SF2_AMP", IR, 30351, _s(20), "A", "Screw Feeder-2 Motor Current"),
        # sim: _ir(30352, pf1_amp, 0, 15)
        TagDef(G, "GM_PF1_AMP", IR, 30352, _s(15), "A", "Pocket Feeder-1 Motor Current"),
        # sim: _ir(30353, pf2_amp, 0, 15)
        TagDef(G, "GM_PF2_AMP", IR, 30353, _s(15), "A", "Pocket Feeder-2 Motor Current"),
        # sim: _ir(30354, id_fan_amp, 0, 35)   NOTE: sim uses 35A span
        TagDef(G, "GM_IDFA_AMP", IR, 30354, _s(35), "A", "ID Fan Motor Current", poll_ms=500),
        # sim: _ir(30355, fd_fan_amp, 0, 90)   NOTE: sim uses 90A span
        TagDef(G, "GM_FDFA_AMP", IR, 30355, _s(90), "A", "FD Fan Motor Current", poll_ms=500),
        # write_extended:
        # sim: _ir(30356, sf3_amp, 0, 20)
        TagDef(G, "GM_SF3_AMP", IR, 30356, _s(20), "A", "Screw Feeder-3 Motor Current"),
        # sim: _ir(30357, pf3_rpm * 0.01, 0, 15)
        TagDef(G, "GM_PF3_AMP", IR, 30357, _s(15), "A", "Pocket Feeder-3 Motor Current"),
        # sim: _ir(30358, sa_fan_amp_ext, 0, 50)
        TagDef(G, "GM_SA_AMP", IR, 30358, _s(50), "A", "Secondary Air Fan Motor Current"),
        # sim: _ir(30359, tg_amp, 0, 10)
        TagDef(G, "GM_TG_AMP", IR, 30359, _s(10), "A", "Travelling Grate Motor Current"),
        # sim: _ir(30360, sac_amp, 0, 20)
        TagDef(G, "GM_SAC_AMP", IR, 30360, _s(20), "A", "Submerged Ash Conveyor Current"),
        # sim: _ir(30361, bfp1_amp, 0, 90)
        TagDef(G, "GM_BFP1_AMP", IR, 30361, _s(90), "A", "Boiler Feed Pump-1 Motor Current", poll_ms=500),
        # sim: _ir(30362, bfp2_amp, 0, 90)
        TagDef(G, "GM_BFP2_AMP", IR, 30362, _s(90), "A", "Boiler Feed Pump-2 Motor Current", poll_ms=500),
        # sim: _ir(30363, lpdp1_amp, 0, 5)
        TagDef(G, "GM_LPDP1_AMP", IR, 30363, _s(5), "A", "LP Dosing Pump-1 Motor Current", poll_ms=5000),
        # sim: _ir(30364, lpdp2_amp, 0, 5)
        TagDef(G, "GM_LPDP2_AMP", IR, 30364, _s(5), "A", "LP Dosing Pump-2 Motor Current", poll_ms=5000),
        # sim: _ir(30365, hpdp1_amp, 0, 5)
        TagDef(G, "GM_HPDP1_AMP", IR, 30365, _s(5), "A", "HP Dosing Pump-1 Motor Current", poll_ms=5000),
        # sim: _ir(30366, hpdp2_amp, 0, 5)
        TagDef(G, "GM_HPDP2_AMP", IR, 30366, _s(5), "A", "HP Dosing Pump-2 Motor Current", poll_ms=5000),
        # sim: _ir(30367, lp_agi_amp, 0, 5)
        TagDef(G, "GM_LP_AGI_AMP", IR, 30367, _s(5), "A", "LP Dosing Agitator Motor Current", poll_ms=5000),
        # sim: _ir(30368, hp_agi_amp, 0, 5)
        TagDef(G, "GM_HP_AGI_AMP", IR, 30368, _s(5), "A", "HP Dosing Agitator Motor Current", poll_ms=5000),
        # sim: _ir(30369, drm_fdr_amp, 0, 30)
        TagDef(G, "GM_DRM_FDR_AMP", IR, 30369, _s(30), "A", "Drum Feeder Motor Current"),
    ]

    # =========================================================================
    # GROUP: MotorRPMExt   Input Registers 30370–30385
    # All from write_extended()
    # =========================================================================
    G = "MotorRPMExt"
    tags += [
        # sim: _ir(30370, drm_fdr_rpm, 0, 1500)
        TagDef(G, "GM_DRM_FDR_RPM", IR, 30370, _s(1500), "RPM", "Drum Feeder Motor Speed"),
        # sim: _ir(30371, sf1_rpm, 0, 50)
        TagDef(G, "GM_M301_RPM", IR, 30371, _s(50), "RPM", "M-301 Screw Feeder-1 Speed (Mirror)"),
        # sim: _ir(30372, sf2_rpm, 0, 50)
        TagDef(G, "GM_M302_RPM", IR, 30372, _s(50), "RPM", "M-302 Screw Feeder-2 Speed (Mirror)"),
        # sim: _ir(30373, sf3_rpm, 0, 50)
        TagDef(G, "GM_M303_RPM", IR, 30373, _s(50), "RPM", "M-303 Screw Feeder-3 Speed"),
        # sim: _ir(30374, tg_rpm, 0, 15)
        TagDef(G, "GM_M304_RPM", IR, 30374, _s(15), "RPM", "M-304 Travelling Grate (Mirror)"),
        # sim: _ir(30375, id_fan_rpm, 0, 1500)
        TagDef(G, "GM_M305_RPM", IR, 30375, _s(1500), "RPM", "M-305 ID Fan Speed (Mirror)"),
        # sim: _ir(30376, sa_fan_rpm, 0, 1500)
        TagDef(G, "GM_M306_RPM", IR, 30376, _s(1500), "RPM", "M-306 SA Fan Speed"),
        # sim: _ir(30377, fd_fan_rpm, 0, 1500)
        TagDef(G, "GM_M307_RPM", IR, 30377, _s(1500), "RPM", "M-307 FD Fan Speed (Mirror)"),
        # sim: _ir(30378, pf1_rpm * 5, 0, 1500)
        TagDef(G, "GM_M401_RPM", IR, 30378, _s(1500), "RPM", "M-401 Pocket Feeder-1 VFD Speed"),
        # sim: _ir(30379, pf1_rpm, 0, 1500)
        TagDef(G, "GM_M402_RPM", IR, 30379, _s(1500), "RPM", "M-402 Pocket Feeder Speed"),
        # sim: _ir(30380, pf2_rpm, 0, 1500)
        TagDef(G, "GM_M403_RPM", IR, 30380, _s(1500), "RPM", "M-403 Pocket Feeder-2 Speed"),
        # sim: _ir(30381, 0.0, 0, 1500)
        TagDef(G, "GM_M404_RPM", IR, 30381, _s(1500), "RPM", "M-404 Ash Conveyor Speed", poll_ms=5000),
        # sim: _ir(30382, gm405_rpm, 0, 1500)
        TagDef(G, "GM_M405_RPM", IR, 30382, _s(1500), "RPM", "M-405 PA Fan / Ash Handling Speed"),
        # sim: _ir(30383, 0.0, 0, 1500)
        TagDef(G, "GM_M406_RPM", IR, 30383, _s(1500), "RPM", "M-406 Speed", poll_ms=5000),
        # sim: _ir(30384, 0.0, 0, 1500)
        TagDef(G, "GM_M407_RPM", IR, 30384, _s(1500), "RPM", "M-407 Speed", poll_ms=5000),
        # sim: _ir(30385, 0.0, 0, 1500)
        TagDef(G, "GM_M408_RPM", IR, 30385, _s(1500), "RPM", "M-408 Speed", poll_ms=5000),
    ]

    # =========================================================================
    # GROUP: ControlValveFB   Input Registers 30400–30405
    # All from write_extended() — valve position feedbacks
    # =========================================================================
    G = "ControlValveFB"
    tags += [
        # sim: _ir(30400, fcv_fw, 0, 100)
        TagDef(G, "FCV_FW_FB", IR, 30400, _s(100), "%", "Feed Water Control Valve Feedback", poll_ms=500),
        # sim: _ir(30401, tcv_temp, 0, 100)
        TagDef(G, "TCV_TEMP_FB", IR, 30401, _s(100), "%", "Desuperheater Spray Valve Feedback", poll_ms=500),
        # sim: _ir(30402, lcv_drum, 0, 100)
        TagDef(G, "LCV_DRUM_FB", IR, 30402, _s(100), "%", "Drum Level Control Valve Feedback", poll_ms=500),
        # sim: _ir(30403, pcv_ms, 0, 100)
        TagDef(G, "PCV_MS_FB", IR, 30403, _s(100), "%", "Main Steam PCV Feedback", poll_ms=500),
        # sim: _ir(30404, 0.0, 0, 100)
        TagDef(G, "PRV_MS_FB", IR, 30404, _s(100), "%", "Main Steam PRV Position Feedback"),
        # sim: _ir(30405, 0.0, 0, 100)
        TagDef(G, "SUV_DRUM_FB", IR, 30405, _s(100), "%", "Drum Safety Unloading Valve Feedback"),
    ]

    # =========================================================================
    # GROUP: EspElectrical   Input Registers 30450–30468
    # Sim write_all(): 30450–30452 (voltages)
    # Sim write_extended(): 30453–30468 (currents, primary volts, DERM, CERM,
    #                        insulator heaters, PAF flag)
    # =========================================================================
    G = "EspElectrical"
    tags += [
        # write_all:
        # sim: _ir(30450, trcc1_volt, 0, 100)
        TagDef(G, "TRCC1_VOLT", IR, 30450, _s(100), "kV", "ESP Field-1 T/R Secondary Voltage"),
        # sim: _ir(30451, trcc2_volt, 0, 100)
        TagDef(G, "TRCC2_VOLT", IR, 30451, _s(100), "kV", "ESP Field-2 T/R Secondary Voltage"),
        # sim: _ir(30452, trcc3_volt, 0, 100)
        TagDef(G, "TRCC3_VOLT", IR, 30452, _s(100), "kV", "ESP Field-3 T/R Secondary Voltage"),
        # write_extended:
        # sim: _ir(30453, trcc1_curr, 0, 2000)  — mA
        TagDef(G, "TRCC1_CURR", IR, 30453, _s(2000), "mA", "ESP Field-1 T/R Secondary Current"),
        TagDef(G, "TRCC2_CURR", IR, 30454, _s(2000), "mA", "ESP Field-2 T/R Secondary Current"),
        TagDef(G, "TRCC3_CURR", IR, 30455, _s(2000), "mA", "ESP Field-3 T/R Secondary Current"),
        # sim: _ir(30456, trcc1_pri_volt, 0, 480)
        TagDef(G, "TRCC1_PRI_VOLT", IR, 30456, _s(480), "V", "ESP Field-1 Primary Voltage"),
        TagDef(G, "TRCC2_PRI_VOLT", IR, 30457, _s(480), "V", "ESP Field-2 Primary Voltage"),
        TagDef(G, "TRCC3_PRI_VOLT", IR, 30458, _s(480), "V", "ESP Field-3 Primary Voltage"),
        # sim: _ir(30459, esp_derm1, 0, 100)   — % dust emission rate
        TagDef(G, "ESP_DERM1", IR, 30459, _s(100), "%", "ESP Field-1 Dust Emission Rate Monitor", poll_ms=5000),
        TagDef(G, "ESP_DERM2", IR, 30460, _s(100), "%", "ESP Field-2 Dust Emission Rate Monitor", poll_ms=5000),
        TagDef(G, "ESP_DERM3", IR, 30461, _s(100), "%", "ESP Field-3 Dust Emission Rate Monitor", poll_ms=5000),
        # sim: _ir(30462, esp_cerm1, 0, 100)  — % corona energy rate
        TagDef(G, "ESP_CERM1", IR, 30462, _s(100), "%", "ESP Field-1 Corona Energy Rate Monitor", poll_ms=5000),
        TagDef(G, "ESP_CERM2", IR, 30463, _s(100), "%", "ESP Field-2 Corona Energy Rate Monitor", poll_ms=5000),
        TagDef(G, "ESP_CERM3", IR, 30464, _s(100), "%", "ESP Field-3 Corona Energy Rate Monitor", poll_ms=5000),
        # sim: _ir(30465, esp_inshtr1, 0, 200)  — insulator heater temp °C
        TagDef(G, "ESP_INSHTR1", IR, 30465, _s(200), "degC", "ESP Field-1 Insulator Heater Temp", poll_ms=5000),
        TagDef(G, "ESP_INSHTR2", IR, 30466, _s(200), "degC", "ESP Field-2 Insulator Heater Temp", poll_ms=5000),
        TagDef(G, "ESP_INSHTR3", IR, 30467, _s(200), "degC", "ESP Field-3 Insulator Heater Temp", poll_ms=5000),
        # sim: _ir(30468, 1.0, 0, 1)
        TagDef(G, "ESP_PAF_FLAG", IR, 30468, _s(1), "-", "ESP Pulse Activated Flag", poll_ms=5000),
    ]

    # =========================================================================
    # GROUP: Performance   Input Registers 30500–30511
    # All from write_extended()
    # =========================================================================
    G = "Performance"
    tags += [
        # sim: _ir(30500, boiler_eff, 0, 100)
        TagDef(G, "BOILER_EFF", IR, 30500, _s(100), "%", "Boiler Thermal Efficiency", poll_ms=5000),
        # sim: _ir(30501, steam_quality, 0, 100)
        TagDef(G, "STEAM_QUALITY", IR, 30501, _s(100), "%", "Steam Quality (Dryness Fraction)", poll_ms=5000),
        # sim: _ir(30502, heat_rate, 0, 5000)
        TagDef(G, "HEAT_RATE", IR, 30502, _s(5000), "kCal/kg", "Specific Heat Rate", poll_ms=5000),
        # sim: _ir(30503, spec_steam, 0, 10)
        TagDef(G, "SPEC_STEAM", IR, 30503, _s(10), "kg/kg", "Specific Steam Generation", poll_ms=5000),
        # sim: _ir(30504, evap_ratio, 0, 10)
        TagDef(G, "EVAP_RATIO", IR, 30504, _s(10), "-", "Evaporation Ratio", poll_ms=5000),
        # sim: _ir(30505, excess_air, 0, 100)
        TagDef(G, "EXCESS_AIR", IR, 30505, _s(100), "%", "Excess Air Percentage", poll_ms=5000),
        # sim: _ir(30506, co2_loss, 0, 20)
        TagDef(G, "CO2_LOSS", IR, 30506, _s(20), "%", "CO2 Heat Loss", poll_ms=5000),
        # sim: _ir(30507, unburn_loss, 0, 20)
        TagDef(G, "UNBURN_LOSS", IR, 30507, _s(20), "%", "Unburned Carbon Loss", poll_ms=5000),
        # sim: _ir(30508, rad_loss, 0, 5)
        TagDef(G, "RAD_LOSS", IR, 30508, _s(5), "%", "Radiation Heat Loss", poll_ms=5000),
        # sim: _ir(30509, sh_enthalpy, 0, 900)
        TagDef(G, "SH_ENTHALPY", IR, 30509, _s(900), "kCal/kg", "Superheated Steam Enthalpy", poll_ms=5000),
        # sim: _ir(30510, fuel_rate, 0, 10000)
        TagDef(G, "FUEL_RATE", IR, 30510, _s(10000), "kg/hr", "Fuel Feed Rate", poll_ms=5000),
        # sim: _ir(30511, steam_load_pct, 0, 100)
        TagDef(G, "STEAM_LOAD_PCT", IR, 30511, _s(100), "%", "Steam Load Percentage", poll_ms=5000),
    ]

    # =========================================================================
    # GROUP: SootBlower   Input Register 30550
    # =========================================================================
    G = "SootBlower"
    tags += [
        # sim: _ir(30550, sb_step, 0, 10)
        TagDef(G, "SB_SEQ_STEP", IR, 30550, _s(10), "-", "Soot Blower Sequence Step (0=Idle)"),
    ]

    # =========================================================================
    # GROUP: SystemStatus   Input Registers 30560–30573
    # =========================================================================
    G = "SystemStatus"
    _dsig, _osig = _s_bi(-50, 50)  # signed error -50..+50
    tags += [
        TagDef(G, "OPER_MODE", IR, 30560, _s(5), "-", "Operator Mode (1=Auto)", poll_ms=5000),
        TagDef(G, "STEAM_LOAD_PCT2", IR, 30561, _s(100), "%", "Steam Load % (Mirror)"),
        TagDef(G, "UPTIME_HR", IR, 30562, _s(9999), "hr", "Plant Uptime Hours", poll_ms=60000),
        TagDef(G, "TOTAL_RUN_HR", IR, 30563, _s(99999), "hr", "Total Run Hours", poll_ms=60000),
        TagDef(G, "START_CNT", IR, 30564, _s(9999), "-", "Total Start Count", poll_ms=60000),
        TagDef(G, "TRIP_CNT", IR, 30565, _s(999), "-", "Total Trip Count", poll_ms=60000),
        TagDef(G, "LAST_TRIP_CODE", IR, 30566, _s(30), "-", "Last Trip Code", poll_ms=60000),
        # PID process values:
        TagDef(G, "PID_FW_PV", IR, 30567, _s(50), "TPH", "PID FW Flow Process Value"),
        TagDef(G, "PID_DRM_PV", IR, 30568, _s(100), "%", "PID Drum Level Process Value"),
        TagDef(G, "PID_PRES_PV", IR, 30569, _s(60), "kg/cm2", "PID Steam Pressure PV"),
        TagDef(G, "PID_TEMP_PV", IR, 30570, _s(500), "degC", "PID Steam Temp PV"),
        # sim: _ir(30571, furn_draught, -30, 30)
        TagDef(G, "PID_DFT_PV", IR, 30571, _d30, "mmWc", "PID Furnace Draught PV", scale_offset=_o30),
        # sim: _ir(30572, fw_flow - sp_fw_flow, -50, 50)
        TagDef(G, "PID_FW_ERR", IR, 30572, _dsig, "TPH", "PID FW Flow Error", scale_offset=_osig),
        # sim: _ir(30573, drum_level_avg - sp_drum_level, -50, 50)
        TagDef(G, "PID_DRM_ERR", IR, 30573, _dsig, "%", "PID Drum Level Error", scale_offset=_osig),
    ]

    # =========================================================================
    # GROUP: Dosing   Input Registers 30580–30583
    # =========================================================================
    G = "Dosing"
    tags += [
        TagDef(G, "DOS_LP_RATE", IR, 30580, _s(100), "L/hr", "LP Dosing Pump-1 Dosing Rate", poll_ms=5000),
        TagDef(G, "DOS_HP_RATE", IR, 30581, _s(50), "L/hr", "HP Dosing Pump-1 Dosing Rate", poll_ms=5000),
        TagDef(G, "DOS_LP_TANK", IR, 30582, _s(100), "%", "LP Chemical Dosing Tank Level", poll_ms=60000),
        TagDef(G, "DOS_HP_TANK", IR, 30583, _s(100), "%", "HP Chemical Dosing Tank Level", poll_ms=60000),
    ]

    # =========================================================================
    # GROUP: Utilities   Input Registers 30590–30593
    # =========================================================================
    G = "Utilities"
    tags += [
        TagDef(G, "UTIL_INST_AIR", IR, 30590, _s(10), "kg/cm2", "Instrument Air Header Pressure"),
        TagDef(G, "UTIL_CW_PRESS", IR, 30591, _s(5), "kg/cm2", "Cooling Water Supply Pressure"),
        TagDef(G, "UTIL_CW_IN", IR, 30592, _s(60), "degC", "Cooling Water Inlet Temperature"),
        TagDef(G, "UTIL_CW_OUT", IR, 30593, _s(60), "degC", "Cooling Water Outlet Temperature"),
    ]

    # =========================================================================
    # GROUP: VibrationBearing   Input Registers 30600–30610
    # =========================================================================
    G = "VibrationBearing"
    tags += [
        TagDef(G, "VIB_IDFA_DE", IR, 30600, _s(25), "mm/s", "ID Fan Drive-End Vibration"),
        TagDef(G, "VIB_IDFA_NDE", IR, 30601, _s(25), "mm/s", "ID Fan Non-Drive-End Vibration"),
        TagDef(G, "VIB_FDFA_DE", IR, 30602, _s(25), "mm/s", "FD Fan Drive-End Vibration"),
        TagDef(G, "VIB_FDFA_NDE", IR, 30603, _s(25), "mm/s", "FD Fan Non-Drive-End Vibration"),
        TagDef(G, "VIB_BFP1_DE", IR, 30604, _s(25), "mm/s", "BFP-1 Drive-End Vibration"),
        TagDef(G, "VIB_BFP2_DE", IR, 30605, _s(25), "mm/s", "BFP-2 Drive-End Vibration"),
        TagDef(G, "TEMP_IDFA_BRG", IR, 30606, _s(120), "degC", "ID Fan Bearing Temperature"),
        TagDef(G, "TEMP_FDFA_BRG", IR, 30607, _s(120), "degC", "FD Fan Bearing Temperature"),
        TagDef(G, "TEMP_BFP1_BRG", IR, 30608, _s(100), "degC", "BFP-1 Bearing Temperature"),
        TagDef(G, "TEMP_BFP2_BRG", IR, 30609, _s(100), "degC", "BFP-2 Bearing Temperature"),
        TagDef(G, "TEMP_SA_BRG", IR, 30610, _s(100), "degC", "SA Fan Bearing Temperature"),
    ]

    # =========================================================================
    # GROUP: PowerMetering   Input Registers 30620–30629
    # =========================================================================
    G = "PowerMetering"
    _pf_bi, _pf_off = _s_bi(45, 55)  # 45..55 Hz frequency
    tags += [
        TagDef(G, "PWR_IDFA_KW", IR, 30620, _s(200), "kW", "ID Fan Active Power"),
        TagDef(G, "PWR_FDFA_KW", IR, 30621, _s(200), "kW", "FD Fan Active Power"),
        TagDef(G, "PWR_SA_KW", IR, 30622, _s(100), "kW", "SA Fan Active Power"),
        TagDef(G, "PWR_BFP1_KW", IR, 30623, _s(100), "kW", "BFP-1 Active Power"),
        TagDef(G, "PWR_BFP2_KW", IR, 30624, _s(100), "kW", "BFP-2 Active Power"),
        TagDef(G, "PWR_TOTAL_KW", IR, 30625, _s(1000), "kW", "Total Auxiliary Active Power"),
        # sim: _ir(30626, pwr_total_kwh, 0, 999999.9, 0, 65535)
        TagDef(G, "PWR_TOTAL_KWH", IR, 30626, _s(999999.9, 65535), "kWh", "Total Auxiliary Energy", poll_ms=60000),
        TagDef(G, "PWR_PF", IR, 30627, _s(1), "PF", "Bus Power Factor"),
        TagDef(G, "PWR_BUS_VOLT", IR, 30628, _s(480), "V", "MCC Bus Voltage"),
        # sim: _ir(30629, pwr_bus_freq, 45, 55)
        TagDef(G, "PWR_BUS_FREQ", IR, 30629, _pf_bi, "Hz", "MCC Bus Frequency", scale_offset=_pf_off),
    ]

    # =========================================================================
    # GROUP: ControlValves   Holding Registers 40400–40410
    # Sim write_all(): 40400–40403
    # =========================================================================
    G = "ControlValves"
    tags += [
        TagDef(G, "FCV_FW_CTRL", HR, 40400, _s(100), "%", "Feed Water Control Valve Setpoint", poll_ms=500),
        TagDef(G, "TCV_TEMP_CTRL", HR, 40401, _s(100), "%", "Desuperheater Spray Valve Setpoint", poll_ms=500),
        TagDef(G, "LCV_DRUM_CTRL", HR, 40402, _s(100), "%", "Drum Level Control Valve Setpoint", poll_ms=500),
        TagDef(G, "PCV_MS_CTRL", HR, 40403, _s(100), "%", "Main Steam PCV Setpoint", poll_ms=500),
    ]

    # =========================================================================
    # GROUP: VfdSetpoints   Holding Registers 40100–40109
    # Sim write_extended(): VFD speed setpoints (%)
    # =========================================================================
    G = "VfdSetpoints"
    tags += [
        TagDef(G, "VFD_IDFA_SP", HR, 40100, _s(100), "%", "ID Fan VFD Speed Setpoint", poll_ms=500),
        TagDef(G, "VFD_FDFA_SP", HR, 40101, _s(100), "%", "FD Fan VFD Speed Setpoint", poll_ms=500),
        TagDef(G, "VFD_SA_SP", HR, 40102, _s(100), "%", "SA Fan VFD Speed Setpoint"),
        TagDef(G, "VFD_TG_SP", HR, 40103, _s(100), "%", "Travelling Grate VFD Setpoint"),
        TagDef(G, "VFD_SF1_SP", HR, 40104, _s(100), "%", "Screw Feeder-1 VFD Setpoint"),
        TagDef(G, "VFD_SF2_SP", HR, 40105, _s(100), "%", "Screw Feeder-2 VFD Setpoint"),
        TagDef(G, "VFD_SF3_SP", HR, 40106, _s(100), "%", "Screw Feeder-3 VFD Setpoint"),
        TagDef(G, "VFD_PF1_SP", HR, 40107, _s(100), "%", "Pocket Feeder-1 VFD Setpoint"),
        TagDef(G, "VFD_PF2_SP", HR, 40108, _s(100), "%", "Pocket Feeder-2 VFD Setpoint"),
        TagDef(G, "VFD_PF3_SP", HR, 40109, _s(100), "%", "Pocket Feeder-3 VFD Setpoint"),
    ]

    # =========================================================================
    # GROUP: PidOutputs   Holding Registers 40200–40205
    # Sim write_extended(): PID controller outputs (%)
    # =========================================================================
    G = "PidOutputs"
    tags += [
        TagDef(G, "PID_FW_OUT", HR, 40200, _s(100), "%", "PID FW Flow Controller Output", poll_ms=500),
        TagDef(G, "PID_DRM_OUT", HR, 40201, _s(100), "%", "PID Drum Level Controller Output", poll_ms=500),
        TagDef(G, "PID_PRES_OUT", HR, 40202, _s(100), "%", "PID Steam Pressure Controller Output"),
        TagDef(G, "PID_TEMP_OUT", HR, 40203, _s(100), "%", "PID Steam Temp Controller Output"),
        TagDef(G, "PID_DFT_OUT", HR, 40204, _s(100), "%", "PID Draught Controller Output"),
        TagDef(G, "PID_FD_OUT", HR, 40205, _s(100), "%", "PID FD Fan Controller Output"),
    ]

    # =========================================================================
    # GROUP: Setpoints   Holding Registers 40500–40515
    # Sim write_all(): 40500–40503
    # Sim write_extended(): 40504–40515
    # =========================================================================
    G = "Setpoints"
    _sp_dft, _sp_dft_off = _s_bi(-30, 30)
    tags += [
        TagDef(G, "SP_DRUM_LVL", HR, 40500, _s(100), "%", "Setpoint – Drum Level", poll_ms=500),
        TagDef(G, "SP_MS_PRES", HR, 40501, _s(60), "kg/cm2", "Setpoint – Main Steam Pressure"),
        TagDef(G, "SP_MS_TEMP", HR, 40502, _s(500), "degC", "Setpoint – Main Steam Temperature"),
        TagDef(G, "SP_FURN_DFT", HR, 40503, _sp_dft, "mmWc", "Setpoint – Furnace Draught", scale_offset=_sp_dft_off),
        TagDef(G, "SP_IDFA_MAN", HR, 40504, _s(100), "%", "Manual Setpoint – ID Fan Speed"),
        TagDef(G, "SP_FDFA_MAN", HR, 40505, _s(100), "%", "Manual Setpoint – FD Fan Speed"),
        TagDef(G, "SP_SA_MAN", HR, 40506, _s(100), "%", "Manual Setpoint – SA Fan Speed"),
        TagDef(G, "SP_TG_MAN", HR, 40507, _s(100), "%", "Manual Setpoint – Travelling Grate"),
        TagDef(G, "SP_SF1_MAN", HR, 40508, _s(100), "%", "Manual Setpoint – Screw Feeder-1"),
        TagDef(G, "SP_SF2_MAN", HR, 40509, _s(100), "%", "Manual Setpoint – Screw Feeder-2"),
        TagDef(G, "SP_SF3_MAN", HR, 40510, _s(100), "%", "Manual Setpoint – Screw Feeder-3"),
        TagDef(G, "SP_PF1_MAN", HR, 40511, _s(100), "%", "Manual Setpoint – Pocket Feeder-1"),
        TagDef(G, "SP_PF2_MAN", HR, 40512, _s(100), "%", "Manual Setpoint – Pocket Feeder-2"),
        TagDef(G, "SP_PF3_MAN", HR, 40513, _s(100), "%", "Manual Setpoint – Pocket Feeder-3"),
        TagDef(G, "SP_DEAER_LVL", HR, 40514, _s(100), "%", "Setpoint – Deaerator Level"),
        TagDef(G, "SP_FW_FLOW", HR, 40515, _s(50), "TPH", "Setpoint – Feed Water Flow"),
    ]

    # =========================================================================
    # GROUP: DigitalStatus   Coils 00001–00054
    # Sim write_all(): 1–20 (BFP, motors, RALV, MRSB, SB_AUTO)
    # Sim write_extended(): 30–54 (motor run statuses)
    # =========================================================================
    G = "DigitalStatus"
    tags += [
        # write_all:
        TagDef(G, "BFP1_RUN", CO, 1, 1.0, "-", "Boiler Feed Pump-1 Run", poll_ms=500),
        TagDef(G, "BFP2_RUN", CO, 2, 1.0, "-", "Boiler Feed Pump-2 Run", poll_ms=500),
        TagDef(G, "M001_RUN", CO, 3, 1.0, "-", "LP Dosing Pump-1 Run"),
        TagDef(G, "M002_RUN", CO, 4, 1.0, "-", "LP Dosing Pump-2 Run"),
        TagDef(G, "M310_SAC_RUN", CO, 5, 1.0, "-", "Submerged Ash Conveyor Run"),
        TagDef(G, "RALV1_RUN", CO, 6, 1.0, "-", "Rotary Air Lock Valve-1 Run"),
        TagDef(G, "RALV2_RUN", CO, 7, 1.0, "-", "Rotary Air Lock Valve-2 Run"),
        TagDef(G, "RALV3_RUN", CO, 8, 1.0, "-", "Rotary Air Lock Valve-3 Run"),
        TagDef(G, "MRSB1_RUN", CO, 10, 1.0, "-", "Soot Blower MRSB-1 Run", poll_ms=500),
        TagDef(G, "MRSB2_RUN", CO, 11, 1.0, "-", "Soot Blower MRSB-2 Run", poll_ms=500),
        TagDef(G, "MRSB3_RUN", CO, 12, 1.0, "-", "Soot Blower MRSB-3 Run", poll_ms=500),
        TagDef(G, "MRSB4_RUN", CO, 13, 1.0, "-", "Soot Blower MRSB-4 Run", poll_ms=500),
        TagDef(G, "MRSB5_RUN", CO, 14, 1.0, "-", "Soot Blower MRSB-5 Run", poll_ms=500),
        TagDef(G, "MRSB6_RUN", CO, 15, 1.0, "-", "Soot Blower MRSB-6 Run", poll_ms=500),
        TagDef(G, "MRSB7_RUN", CO, 16, 1.0, "-", "Soot Blower MRSB-7 Run", poll_ms=500),
        TagDef(G, "SB_AUTO", CO, 20, 1.0, "-", "Soot Blower Auto Sequence"),
        # write_extended: motor run statuses 30–54
        TagDef(G, "M301_SF1_RUN", CO, 30, 1.0, "-", "M-301 Screw Feeder-1 Run"),
        TagDef(G, "M302_SF2_RUN", CO, 31, 1.0, "-", "M-302 Screw Feeder-2 Run"),
        TagDef(G, "M303_SF3_RUN", CO, 32, 1.0, "-", "M-303 Screw Feeder-3 Run"),
        TagDef(G, "M304_TG_RUN", CO, 33, 1.0, "-", "M-304 Travelling Grate Run"),
        TagDef(G, "M305_IDFA_RUN", CO, 34, 1.0, "-", "M-305 ID Fan Run", poll_ms=500),
        TagDef(G, "M306_SA_RUN", CO, 35, 1.0, "-", "M-306 SA Fan Run"),
        TagDef(G, "M307_FDFA_RUN", CO, 36, 1.0, "-", "M-307 FD Fan Run", poll_ms=500),
        TagDef(G, "M401_RUN", CO, 37, 1.0, "-", "M-401 Run"),
        TagDef(G, "M402_RUN", CO, 38, 1.0, "-", "M-402 Run"),
        TagDef(G, "M403_RUN", CO, 39, 1.0, "-", "M-403 Run"),
        TagDef(G, "M404_RUN", CO, 40, 1.0, "-", "M-404 Run"),
        TagDef(G, "M405_PA_RUN", CO, 41, 1.0, "-", "M-405 PA Fan Run"),
        TagDef(G, "M406_PA_RUN", CO, 42, 1.0, "-", "M-406 PA Fan Run"),
        TagDef(G, "M407_RUN", CO, 43, 1.0, "-", "M-407 Run"),
        TagDef(G, "M408_RUN", CO, 44, 1.0, "-", "M-408 Run"),
        TagDef(G, "M210_LPDP_RUN", CO, 45, 1.0, "-", "M-210 LP Dosing Pump Run"),
        TagDef(G, "M212_LPDP_RUN", CO, 46, 1.0, "-", "M-212 LP Dosing Pump-2 Run"),
        TagDef(G, "M501_HPDP_RUN", CO, 47, 1.0, "-", "M-501 HP Dosing Pump Run"),
        TagDef(G, "M502_HPDP_RUN", CO, 48, 1.0, "-", "M-502 HP Dosing Pump-2 Run"),
        TagDef(G, "M213_LP_AGI_RUN", CO, 49, 1.0, "-", "M-213 LP Dosing Agitator Run"),
        TagDef(G, "M214_HP_AGI_RUN", CO, 50, 1.0, "-", "M-214 HP Dosing Agitator Run"),
        TagDef(G, "M215_PF2_RUN", CO, 51, 1.0, "-", "M-215 Pocket Feeder-2 Run"),
        TagDef(G, "M216_RUN", CO, 52, 1.0, "-", "M-216 Run"),
        TagDef(G, "M218_RUN", CO, 53, 1.0, "-", "M-218 Run"),
        TagDef(G, "M219_RUN", CO, 54, 1.0, "-", "M-219 Run"),
    ]

    # =========================================================================
    # GROUP: Faults   Coils 00060–00085
    # Sim write_extended(): faults[0]–faults[25]
    # =========================================================================
    G = "Faults"
    FAULT_NAMES = [
        "FAULT_BFP1",
        "FAULT_BFP2",
        "FAULT_IDFA",
        "FAULT_FDFA",
        "FAULT_SF1",
        "FAULT_SF2",
        "FAULT_SF3",
        "FAULT_PF1",
        "FAULT_PF2",
        "FAULT_PF3",
        "FAULT_TG",
        "FAULT_SAC",
        "FAULT_M401",
        "FAULT_M402",
        "FAULT_M403",
        "FAULT_M404",
        "FAULT_M405",
        "FAULT_M406",
        "FAULT_M407",
        "FAULT_M408",
        "FAULT_LPDP1",
        "FAULT_LPDP2",
        "FAULT_HPDP1",
        "FAULT_HPDP2",
        "FAULT_ESP1",
        "FAULT_ESP2",
    ]
    FAULT_DESC = [
        "BFP-1 Motor Fault",
        "BFP-2 Motor Fault",
        "ID Fan Motor Fault",
        "FD Fan Motor Fault",
        "Screw Feeder-1 Fault",
        "Screw Feeder-2 Fault",
        "Screw Feeder-3 Fault",
        "Pocket Feeder-1 Fault",
        "Pocket Feeder-2 Fault",
        "Pocket Feeder-3 Fault",
        "Travelling Grate Fault",
        "Submerged Ash Conveyor Fault",
        "M-401 Fault",
        "M-402 Fault",
        "M-403 Fault",
        "M-404 Fault",
        "M-405 Fault",
        "M-406 Fault",
        "M-407 Fault",
        "M-408 Fault",
        "LP Dosing Pump-1 Fault",
        "LP Dosing Pump-2 Fault",
        "HP Dosing Pump-1 Fault",
        "HP Dosing Pump-2 Fault",
        "ESP Field-1 Fault",
        "ESP Field-2 Fault",
    ]
    for i in range(26):
        tags.append(TagDef(G, FAULT_NAMES[i], CO, 60 + i, 1.0, "-", FAULT_DESC[i], poll_ms=500))

    # =========================================================================
    # GROUP: Interlocks   Coils 00100–00121
    # Sim write_all(): 100–106
    # Sim write_extended(): 107–121
    # =========================================================================
    G = "Interlocks"
    tags += [
        # write_all:
        TagDef(G, "INTLK_MASTER", CO, 100, 1.0, "-", "Master Interlock Trip", poll_ms=250),
        TagDef(G, "INTLK_DRUM_LL", CO, 101, 1.0, "-", "Drum Level Low-Low Trip", poll_ms=250),
        TagDef(G, "INTLK_DRUM_HH", CO, 102, 1.0, "-", "Drum Level High-High Trip", poll_ms=250),
        TagDef(G, "INTLK_PRES_HH", CO, 103, 1.0, "-", "Steam Pressure High-High Trip", poll_ms=250),
        TagDef(G, "INTLK_FW_LL", CO, 104, 1.0, "-", "Feed Water Flow Low-Low Trip", poll_ms=250),
        TagDef(G, "FD_VFD_SEL", CO, 105, 1.0, "-", "FD Fan VFD Selected"),
        TagDef(G, "ID_VFD_SEL", CO, 106, 1.0, "-", "ID Fan VFD Selected"),
        # write_extended:
        TagDef(G, "INTLK_TEMP_HH", CO, 107, 1.0, "-", "MS Temperature High-High Trip", poll_ms=250),
        TagDef(G, "INTLK_DRAUGHT_LL", CO, 108, 1.0, "-", "Draught Low-Low Trip", poll_ms=250),
        TagDef(G, "INTLK_BFP_FAIL", CO, 109, 1.0, "-", "Both BFPs Failed Trip", poll_ms=250),
        TagDef(G, "INTLK_IDFA_FAIL", CO, 110, 1.0, "-", "ID Fan Fail Trip", poll_ms=250),
        TagDef(G, "INTLK_FDFA_FAIL", CO, 111, 1.0, "-", "FD Fan Fail Trip", poll_ms=250),
        TagDef(G, "INTLK_BED_HH", CO, 112, 1.0, "-", "Bed Temperature High-High Trip", poll_ms=250),
        TagDef(G, "INTLK_FW_FLOW_LL", CO, 113, 1.0, "-", "FW Flow Low-Low Trip", poll_ms=250),
        TagDef(G, "INTLK_DEAER_LL", CO, 114, 1.0, "-", "Deaerator Level Low-Low Trip", poll_ms=250),
        TagDef(G, "INTLK_FUEL_LL", CO, 115, 1.0, "-", "Fuel Bin Level Low-Low", poll_ms=500),
        TagDef(G, "INTLK_EMGCY", CO, 116, 1.0, "-", "Emergency Stop"),
        TagDef(G, "INTLK_FAULT_ACK", CO, 117, 1.0, "-", "Fault Acknowledge"),
        TagDef(G, "INTLK_BYPASS_1", CO, 118, 1.0, "-", "Interlock Bypass-1"),
        TagDef(G, "INTLK_BYPASS_2", CO, 119, 1.0, "-", "Interlock Bypass-2"),
        TagDef(G, "INTLK_MASTER_RST", CO, 120, 1.0, "-", "Master Interlock Reset"),
        TagDef(G, "INTLK_BOIL_TRIP", CO, 121, 1.0, "-", "Boiler Trip Active", poll_ms=250),
    ]

    # =========================================================================
    # GROUP: Commands   Coils 00200–00231
    # Sim write_extended(): all initialised False (R/W operator commands)
    # =========================================================================
    G = "Commands"
    CMD_NAMES = [
        "CMD_BFP1_START",
        "CMD_BFP1_STOP",
        "CMD_BFP2_START",
        "CMD_BFP2_STOP",
        "CMD_IDFA_START",
        "CMD_IDFA_STOP",
        "CMD_FDFA_START",
        "CMD_FDFA_STOP",
        "CMD_TG_START",
        "CMD_TG_STOP",
        "CMD_SF1_START",
        "CMD_SF1_STOP",
        "CMD_SF2_START",
        "CMD_SF2_STOP",
        "CMD_SF3_START",
        "CMD_SF3_STOP",
        "CMD_SB_MANUAL",
        "CMD_SB_NEXT",
        "CMD_BLW_OPEN",
        "CMD_BLW_CLOSE",
        "CMD_PRV_OPEN",
        "CMD_PRV_CLOSE",
        "CMD_SAC_START",
        "CMD_SAC_STOP",
        "CMD_LPDP1_START",
        "CMD_LPDP2_START",
        "CMD_HPDP1_START",
        "CMD_HPDP2_START",
        "CMD_ESP_ON",
        "CMD_ESP_OFF",
        "CMD_TRIP_RST",
        "CMD_LOAD_RAMP",
    ]
    CMD_DESC = [
        "Start BFP-1",
        "Stop BFP-1",
        "Start BFP-2",
        "Stop BFP-2",
        "Start ID Fan",
        "Stop ID Fan",
        "Start FD Fan",
        "Stop FD Fan",
        "Start Travelling Grate",
        "Stop Travelling Grate",
        "Start Screw Feeder-1",
        "Stop Screw Feeder-1",
        "Start Screw Feeder-2",
        "Stop Screw Feeder-2",
        "Start Screw Feeder-3",
        "Stop Screw Feeder-3",
        "Manual Soot Blow Trigger",
        "Advance Soot Blower Sequence",
        "Open Blowdown Valve",
        "Close Blowdown Valve",
        "Open PRV",
        "Close PRV",
        "Start Submerged Ash Conveyor",
        "Stop Submerged Ash Conveyor",
        "Start LP Dosing Pump-1",
        "Start LP Dosing Pump-2",
        "Start HP Dosing Pump-1",
        "Start HP Dosing Pump-2",
        "ESP Master ON",
        "ESP Master OFF",
        "Trip Reset",
        "Load Ramp Command",
    ]
    for i in range(32):
        tags.append(TagDef(G, CMD_NAMES[i], CO, 200 + i, 1.0, "-", CMD_DESC[i]))

    # =========================================================================
    # GROUP: Alarms   Discrete Inputs 10001–10064
    # Sim write_extended(): _di() writes — read via FC2
    # =========================================================================
    G = "Alarms"
    tags += [
        TagDef(G, "ALM_MS_TEMP_HH", DI, 10001, 1.0, "-", "MS Temperature High-High Alarm", poll_ms=500),
        TagDef(G, "ALM_MS_TEMP_H", DI, 10002, 1.0, "-", "MS Temperature High Alarm", poll_ms=500),
        TagDef(G, "ALM_MS_TEMP_L", DI, 10003, 1.0, "-", "MS Temperature Low Alarm", poll_ms=500),
        TagDef(G, "ALM_MS_PRES_HH", DI, 10004, 1.0, "-", "MS Pressure High-High Alarm", poll_ms=500),
        TagDef(G, "ALM_MS_PRES_H", DI, 10005, 1.0, "-", "MS Pressure High Alarm", poll_ms=500),
        TagDef(G, "ALM_MS_PRES_L", DI, 10006, 1.0, "-", "MS Pressure Low Alarm", poll_ms=500),
        TagDef(G, "ALM_DRUM_LL", DI, 10007, 1.0, "-", "Drum Level Low-Low Alarm", poll_ms=250),
        TagDef(G, "ALM_DRUM_L", DI, 10008, 1.0, "-", "Drum Level Low Alarm", poll_ms=500),
        TagDef(G, "ALM_DRUM_H", DI, 10009, 1.0, "-", "Drum Level High Alarm", poll_ms=500),
        TagDef(G, "ALM_DRUM_HH", DI, 10010, 1.0, "-", "Drum Level High-High Alarm", poll_ms=250),
        TagDef(G, "ALM_DFT_HH", DI, 10011, 1.0, "-", "Furnace Draught High-High Alarm", poll_ms=500),
        TagDef(G, "ALM_DFT_LL", DI, 10012, 1.0, "-", "Furnace Draught Low-Low Alarm", poll_ms=500),
        TagDef(G, "ALM_FW_FLOW_L", DI, 10013, 1.0, "-", "FW Flow Low Alarm", poll_ms=500),
        TagDef(G, "ALM_FW_FLOW_LL", DI, 10014, 1.0, "-", "FW Flow Low-Low Alarm", poll_ms=250),
        TagDef(G, "ALM_DEAER_LVL_L", DI, 10015, 1.0, "-", "Deaerator Level Low Alarm", poll_ms=500),
        TagDef(G, "ALM_DEAER_LVL_H", DI, 10016, 1.0, "-", "Deaerator Level High Alarm", poll_ms=500),
        TagDef(G, "ALM_DEAER_PRES_H", DI, 10017, 1.0, "-", "Deaerator Pressure High Alarm", poll_ms=500),
        TagDef(G, "ALM_FUEL_BIN_L", DI, 10018, 1.0, "-", "Fuel Bin Level Low Alarm", poll_ms=500),
        TagDef(G, "ALM_FUEL_BIN_LL", DI, 10019, 1.0, "-", "Fuel Bin Level Low-Low Alarm", poll_ms=500),
        TagDef(G, "ALM_FWST_L", DI, 10020, 1.0, "-", "FW Storage Tank Low Alarm", poll_ms=500),
        TagDef(G, "ALM_FWST_LL", DI, 10021, 1.0, "-", "FW Storage Tank Low-Low Alarm", poll_ms=500),
        TagDef(G, "ALM_SSH_TEMP_HH", DI, 10022, 1.0, "-", "SSH Temperature High-High Alarm", poll_ms=500),
        TagDef(G, "ALM_PSH_TEMP_HH", DI, 10023, 1.0, "-", "PSH Temperature High-High Alarm", poll_ms=500),
        TagDef(G, "ALM_ECO_GAS_HH", DI, 10024, 1.0, "-", "Economiser Gas Temp High-High", poll_ms=500),
        TagDef(G, "ALM_APH_GAS_H", DI, 10025, 1.0, "-", "APH Gas Temperature High Alarm", poll_ms=500),
        TagDef(G, "ALM_BED_TEMP_HH", DI, 10026, 1.0, "-", "Bed Temperature High-High Alarm", poll_ms=500),
        TagDef(G, "ALM_BED_TEMP_LL", DI, 10027, 1.0, "-", "Bed Temperature Low-Low Alarm", poll_ms=500),
        TagDef(G, "ALM_ESP_VOLT_L", DI, 10028, 1.0, "-", "ESP Secondary Voltage Low Alarm", poll_ms=500),
        TagDef(G, "ALM_DRUM_LVL_DEV", DI, 10029, 1.0, "-", "Drum Level Transmitter Deviation", poll_ms=500),
        TagDef(G, "ALM_VFD_IDFA_FLT", DI, 10030, 1.0, "-", "ID Fan VFD Fault Alarm", poll_ms=500),
        TagDef(G, "ALM_VFD_FDFA_FLT", DI, 10031, 1.0, "-", "FD Fan VFD Fault Alarm", poll_ms=500),
        TagDef(G, "ALM_ALL_BFP_FAIL", DI, 10032, 1.0, "-", "All BFPs Failed Alarm", poll_ms=250),
        TagDef(G, "ALM_IDFA_FAIL", DI, 10033, 1.0, "-", "ID Fan Failed Alarm", poll_ms=500),
        TagDef(G, "ALM_FDFA_FAIL", DI, 10034, 1.0, "-", "FD Fan Failed Alarm", poll_ms=500),
        TagDef(G, "ALM_SB_TIMEOUT", DI, 10035, 1.0, "-", "Soot Blower Timeout Alarm", poll_ms=5000),
        TagDef(G, "ALM_PRV_OPEN", DI, 10036, 1.0, "-", "Safety Valve Open Alarm", poll_ms=500),
        TagDef(G, "ALM_SAC_FAULT", DI, 10037, 1.0, "-", "Submerged Ash Conveyor Fault", poll_ms=500),
        TagDef(G, "ALM_INST_AIR_L", DI, 10038, 1.0, "-", "Instrument Air Low Alarm", poll_ms=500),
        TagDef(G, "ALM_BFP_DPS_FAIL", DI, 10039, 1.0, "-", "BFP Diff Pressure Switch Fail", poll_ms=500),
        TagDef(G, "ALM_DT401_HH", DI, 10040, 1.0, "-", "DT-401 Draught High-High Alarm", poll_ms=500),
        TagDef(G, "ALM_DT401_LL", DI, 10041, 1.0, "-", "DT-401 Draught Low-Low Alarm", poll_ms=500),
        TagDef(G, "ALM_TE101_HH", DI, 10042, 1.0, "-", "TE-101 (ESP Inlet) Temp HH Alarm", poll_ms=500),
        # Soot blower home switches (10050–10056) + sequence active (10057)
        TagDef(G, "SB1_HOME", DI, 10050, 1.0, "-", "Soot Blower-1 Home Position"),
        TagDef(G, "SB2_HOME", DI, 10051, 1.0, "-", "Soot Blower-2 Home Position"),
        TagDef(G, "SB3_HOME", DI, 10052, 1.0, "-", "Soot Blower-3 Home Position"),
        TagDef(G, "SB4_HOME", DI, 10053, 1.0, "-", "Soot Blower-4 Home Position"),
        TagDef(G, "SB5_HOME", DI, 10054, 1.0, "-", "Soot Blower-5 Home Position"),
        TagDef(G, "SB6_HOME", DI, 10055, 1.0, "-", "Soot Blower-6 Home Position"),
        TagDef(G, "SB7_HOME", DI, 10056, 1.0, "-", "Soot Blower-7 Home Position"),
        TagDef(G, "SB_SEQ_ACTIVE", DI, 10057, 1.0, "-", "Soot Blower Sequence Active"),
        # Utility status (10060–10064)
        TagDef(G, "DPS_BFP1_OK", DI, 10060, 1.0, "-", "BFP-1 Diff Pressure Switch OK"),
        TagDef(G, "DPS_BFP2_OK", DI, 10061, 1.0, "-", "BFP-2 Diff Pressure Switch OK"),
        TagDef(G, "CW_PR_SW_OK", DI, 10062, 1.0, "-", "Cooling Water Pressure Switch OK"),
        TagDef(G, "INST_AIR_SW_OK", DI, 10063, 1.0, "-", "Instrument Air Pressure Switch OK"),
        TagDef(G, "PAF_STATUS", DI, 10064, 1.0, "-", "Pulse Air Fan Status"),
    ]

    return tags


TAG_REGISTRY: List[TagDef] = _build_registry()


# =============================================================================
# BATCH BUILDER
# Groups tags by (RegType, contiguous addresses) to minimise Modbus RTTs.
# Gaps ≤ 10 registers are bridged (read and discard the gap).
# =============================================================================
@dataclass
class ModbusBatch:
    reg_type: RegType
    start_addr: int  # 1-based KEP-style address
    count: int  # number of registers/coils to read
    tags: List[TagDef] = field(default_factory=list)


def _build_batches(tags: List[TagDef], batch_size: int) -> List[ModbusBatch]:
    from itertools import groupby

    sorted_tags = sorted(tags, key=lambda t: (t.reg_type.value, t.address))
    batches: List[ModbusBatch] = []

    for reg_type, group_iter in groupby(sorted_tags, key=lambda t: t.reg_type):
        group_tags = list(group_iter)
        if not group_tags:
            continue

        cur_start = group_tags[0].address
        cur_tags = [group_tags[0]]

        for prev, curr in zip(group_tags, group_tags[1:]):
            gap = curr.address - prev.address
            span = curr.address - cur_start + 1
            if gap > 10 or span > batch_size:
                batches.append(
                    ModbusBatch(
                        reg_type=reg_type,
                        start_addr=cur_start,
                        count=prev.address - cur_start + 1,
                        tags=cur_tags,
                    )
                )
                cur_start = curr.address
                cur_tags = [curr]
            else:
                cur_tags.append(curr)

        batches.append(
            ModbusBatch(
                reg_type=reg_type,
                start_addr=cur_start,
                count=cur_tags[-1].address - cur_start + 1,
                tags=cur_tags,
            )
        )

    return batches


# =============================================================================
# OPC UA NAMESPACE BUILDER
# =============================================================================
class NamespaceBuilder:
    """
    OPC UA address space:

      Objects/
        {plant_id}/
          {device_id}/
            Temperature/        Float tags
            Pressure/           Float tags
            ...
            DigitalStatus/      Bool tags
            Interlocks/         Bool tags
            Alarms/             Bool tags
            Commands/           Bool tags  (writable)
            _Bridge/
              Heartbeat         UInt64 — increments every 1s
              ModbusConnected   Boolean
              LastPollTs        String (ISO-8601)
              TotalTagsOK       UInt32
              TotalTagsBad      UInt32
              TotalTags         UInt32
    """

    def __init__(self, server: Server, ns_idx: int, device_id: str):
        self._server = server
        self._ns = ns_idx
        self._device_id = device_id
        self._group_nodes: Dict[str, Node] = {}
        self.tag_nodes: Dict[str, Node] = {}
        self.node_heartbeat: Optional[Node] = None
        self.node_modbus_ok: Optional[Node] = None
        self.node_last_poll_ts: Optional[Node] = None
        self.node_tags_ok: Optional[Node] = None
        self.node_tags_bad: Optional[Node] = None
        self.node_total_tags: Optional[Node] = None

    async def build(self, tags: List[TagDef]) -> None:
        objects = self._server.nodes.objects

        plant_folder = await objects.add_folder(self._ns, CFG.plant_id)
        device_folder = await plant_folder.add_folder(self._ns, self._device_id)

        for tag in tags:
            grp_node = await self._get_or_create_group(device_folder, tag.group)
            node = await self._add_tag_variable(grp_node, tag)
            self.tag_nodes[f"{tag.group}.{tag.tag}"] = node

        # Bridge diagnostics folder
        bridge_folder = await device_folder.add_folder(self._ns, "_Bridge")
        self.node_heartbeat = await bridge_folder.add_variable(self._ns, "Heartbeat", 0, ua.VariantType.UInt64)
        self.node_modbus_ok = await bridge_folder.add_variable(
            self._ns, "ModbusConnected", False, ua.VariantType.Boolean
        )
        self.node_last_poll_ts = await bridge_folder.add_variable(self._ns, "LastPollTs", "", ua.VariantType.String)
        self.node_tags_ok = await bridge_folder.add_variable(self._ns, "TotalTagsOK", 0, ua.VariantType.UInt32)
        self.node_tags_bad = await bridge_folder.add_variable(self._ns, "TotalTagsBad", 0, ua.VariantType.UInt32)
        self.node_total_tags = await bridge_folder.add_variable(self._ns, "TotalTags", len(tags), ua.VariantType.UInt32)

        log.info(
            "OPC UA namespace built: %d tags in %d groups  (ns_idx=%d)",
            len(tags),
            len(self._group_nodes),
            self._ns,
        )

    async def _get_or_create_group(self, device_node: Node, group_name: str) -> Node:
        if group_name not in self._group_nodes:
            folder = await device_node.add_folder(self._ns, group_name)
            self._group_nodes[group_name] = folder
        return self._group_nodes[group_name]

    async def _add_tag_variable(self, group_node: Node, tag: TagDef) -> Node:
        is_bool = tag.reg_type in (RegType.COIL, RegType.DISCRETE_INPUT)
        if is_bool:
            var = await group_node.add_variable(self._ns, tag.tag, False, ua.VariantType.Boolean)
        else:
            var = await group_node.add_variable(self._ns, tag.tag, 0.0, ua.VariantType.Float)
        # Holding regs and Commands coils are writable (allow SCADA setpoints)
        is_writable = tag.reg_type == RegType.HOLDING_REGISTER or tag.group == "Commands"
        await var.set_writable(is_writable)

        try:
            await var.write_attribute(
                ua.AttributeIds.Description,
                ua.DataValue(
                    ua.Variant(
                        ua.LocalizedText(f"{tag.description} [{tag.unit}]"),
                        ua.VariantType.LocalizedText,
                    )
                ),
            )
        except Exception:
            pass

        return var


# =============================================================================
# TAG HEALTH TRACKER
# =============================================================================
@dataclass
class TagHealth:
    tag_key: str
    last_update_ts: float = 0.0
    good_count: int = 0
    bad_count: int = 0
    last_value: Any = None

    @property
    def is_stale(self) -> bool:
        if self.last_update_ts == 0:
            return True
        return (time.monotonic() - self.last_update_ts) > CFG.stale_threshold


# =============================================================================
# MODBUS POLLER
# =============================================================================
class ModbusPoller:
    """
    Async Modbus TCP client.
    Reads all batches per poll cycle → returns {tag_key: raw_value}.
    """

    def __init__(self, cfg: BridgeConfig, batches: List[ModbusBatch]):
        self._cfg = cfg
        self._batches = batches
        self._client: Optional[AsyncModbusTcpClient] = None
        self._connected = False
        self._retry_delay = cfg.reconnect_base

    async def connect(self) -> bool:
        try:
            self._client = AsyncModbusTcpClient(
                host=self._cfg.modbus_host,
                port=self._cfg.modbus_port,
                timeout=self._cfg.modbus_timeout,
            )
            await self._client.connect()
            if self._client.connected:
                self._connected = True
                self._retry_delay = self._cfg.reconnect_base
                log.info(
                    "Modbus connected -> %s:%d  unit=%d",
                    self._cfg.modbus_host,
                    self._cfg.modbus_port,
                    self._cfg.modbus_unit,
                )
                return True
        except Exception as exc:
            log.warning("Modbus connect failed: %s", exc)
        self._connected = False
        return False

    async def disconnect(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._connected = False

    @property
    def connected(self) -> bool:
        return bool(self._connected and self._client is not None and self._client.connected)

    async def poll_all(self) -> Dict[str, Any]:
        if not self.connected:
            return {}
        results: Dict[str, Any] = {}
        for batch in self._batches:
            batch_result = await self._poll_batch(batch)
            if batch_result is None:
                self._connected = False
                log.warning("Modbus connection lost during batch poll")
                return {}
            results.update(batch_result)
        return results

    async def _poll_batch(self, batch: ModbusBatch) -> Optional[Dict[str, Any]]:
        unit = self._cfg.modbus_unit
        try:
            if batch.reg_type == RegType.INPUT_REGISTER:
                idx = batch.start_addr - 30001
                resp = await self._client.read_input_registers(idx, count=batch.count, slave=unit)

            elif batch.reg_type == RegType.HOLDING_REGISTER:
                idx = batch.start_addr - 40001
                resp = await self._client.read_holding_registers(idx, count=batch.count, slave=unit)

            elif batch.reg_type == RegType.COIL:
                idx = batch.start_addr - 1
                resp = await self._client.read_coils(idx, count=batch.count, slave=unit)

            elif batch.reg_type == RegType.DISCRETE_INPUT:
                # FC2 — discrete inputs (1xxxx)
                # pymodbus index = address - 10001
                idx = batch.start_addr - 10001
                resp = await self._client.read_discrete_inputs(idx, count=batch.count, slave=unit)

            else:
                return {}

        except ModbusException as exc:
            log.warning("Modbus exception batch start=%d: %s", batch.start_addr, exc)
            return None
        except Exception as exc:
            log.error("Unexpected Modbus error batch start=%d: %s", batch.start_addr, exc)
            return None

        if resp.isError():
            log.warning(
                "Modbus error response batch start=%d type=%s",
                batch.start_addr,
                batch.reg_type.name,
            )
            return {}

        raw_map: Dict[str, Any] = {}
        for tag in batch.tags:
            offset = tag.address - batch.start_addr
            key = f"{tag.group}.{tag.tag}"

            if batch.reg_type in (RegType.COIL, RegType.DISCRETE_INPUT):
                try:
                    raw_map[key] = bool(resp.bits[offset])
                except IndexError:
                    pass
            else:
                try:
                    raw_map[key] = resp.registers[offset]
                except IndexError:
                    pass

        return raw_map

    async def reconnect_loop(self) -> None:
        log.info("Modbus reconnect: waiting %.1fs ...", self._retry_delay)
        await asyncio.sleep(self._retry_delay)
        self._retry_delay = min(self._retry_delay * 2, self._cfg.reconnect_max)
        await self.connect()


# =============================================================================
# BRIDGE ENGINE
# =============================================================================
class OpcUaBridge:
    """
    Orchestrates:
      1. OPC UA server startup
      2. Full namespace build
      3. Modbus TCP connection
      4. Async poll → scale → write loop
      5. Heartbeat + diagnostics
    """

    def __init__(self, cfg: BridgeConfig, tags: List[TagDef]):
        self._cfg = cfg
        self._tags = tags
        self._batches = _build_batches(tags, cfg.batch_size)
        self._health: Dict[str, TagHealth] = {f"{t.group}.{t.tag}": TagHealth(f"{t.group}.{t.tag}") for t in tags}
        self._poller: Optional[ModbusPoller] = None
        self._ns: Optional[NamespaceBuilder] = None
        self._stop = asyncio.Event()
        self._hb_count: int = 0

        log.info(
            "Bridge init: %d tags -> %d Modbus batches",
            len(tags),
            len(self._batches),
        )

    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _scale(raw: Any, tag: TagDef) -> Any:
        """Raw uint16 or bool → engineering float / bool."""
        if tag.reg_type in (RegType.COIL, RegType.DISCRETE_INPUT):
            return bool(raw)
        return round(int(raw) / tag.scale + tag.scale_offset, 4)

    @staticmethod
    async def _write_node(
        node: Node,
        eng_value: Any,
        quality_good: bool,
        ts: datetime,
    ) -> None:
        status = ua.StatusCode(ua.StatusCodes.Good) if quality_good else ua.StatusCode(ua.StatusCodes.BadNoData)
        # Explicitly set VariantType to match the node's declared type
        if isinstance(eng_value, bool):
            variant = ua.Variant(eng_value, ua.VariantType.Boolean)
        else:
            # Cast to Python float32 range to match Float node type
            import struct

            f32 = struct.unpack("f", struct.pack("f", float(eng_value)))[0]
            variant = ua.Variant(f32, ua.VariantType.Float)
        dv = ua.DataValue(
            variant,
            StatusCode_=status,
            SourceTimestamp=ts,
            ServerTimestamp=ts,
        )
        await node.write_value(dv)

    def _endpoint_url(self) -> str:
        return f"opc.tcp://{self._cfg.opc_host}:{self._cfg.opc_port}/piccadily/"

    # ──────────────────────────────────────────────────────────────────────────
    async def run(self) -> None:
        # ── 1. OPC UA Server ─────────────────────────────────────────────────
        server = Server()
        await server.init()
        server.set_endpoint(self._endpoint_url())
        server.set_server_name(f"Piccadily Boiler OPC UA Bridge - {self._cfg.plant_id}")
        server.set_security_policy([ua.SecurityPolicyType.NoSecurity])

        ns_idx = await server.register_namespace(self._cfg.opc_ns_uri)
        log.info("OPC UA namespace: idx=%d  uri=%s", ns_idx, self._cfg.opc_ns_uri)

        # ── 2. Build namespace ────────────────────────────────────────────────
        self._ns = NamespaceBuilder(server, ns_idx, self._cfg.device_id)
        await self._ns.build(self._tags)

        # ── 3. Modbus connect ─────────────────────────────────────────────────
        self._poller = ModbusPoller(self._cfg, self._batches)
        await self._poller.connect()

        # ── 4. Run ────────────────────────────────────────────────────────────
        async with server:
            log.info("=" * 66)
            log.info("  PICCADILY OPC UA Bridge RUNNING")
            log.info("  Endpoint  : %s", self._endpoint_url())
            log.info(
                "  Modbus    : %s:%d  unit=%d", self._cfg.modbus_host, self._cfg.modbus_port, self._cfg.modbus_unit
            )
            log.info("  Tags      : %d  |  Batches: %d", len(self._tags), len(self._batches))
            log.info("  Poll ms   : %d  |  Batch sz: %d", self._cfg.poll_ms, self._cfg.batch_size)
            log.info("=" * 66)

            poll_task = asyncio.create_task(self._poll_loop(), name="poll_loop")
            hb_task = asyncio.create_task(self._heartbeat_loop(), name="heartbeat")
            stats_task = asyncio.create_task(self._stats_loop(), name="stats_loop")

            await self._stop.wait()

            for task in (poll_task, hb_task, stats_task):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await self._poller.disconnect()
        log.info("Bridge stopped cleanly.")

    # ──────────────────────────────────────────────────────────────────────────
    async def _poll_loop(self) -> None:
        tag_lookup: Dict[str, TagDef] = {f"{t.group}.{t.tag}": t for t in self._tags}

        while not self._stop.is_set():
            loop_start = time.monotonic()

            # Reconnect if needed
            if not self._poller.connected:
                await self._poller.reconnect_loop()
                if self._ns and self._ns.node_modbus_ok:
                    await self._ns.node_modbus_ok.write_value(ua.DataValue(ua.Variant(False, ua.VariantType.Boolean)))
                continue

            # Poll
            raw_map = await self._poller.poll_all()
            now_ts = datetime.now(timezone.utc)
            now_mono = time.monotonic()
            tags_ok = 0
            tags_bad = 0

            for key, tag in tag_lookup.items():
                node = self._ns.tag_nodes.get(key)
                if node is None:
                    continue

                if key in raw_map:
                    try:
                        eng = self._scale(raw_map[key], tag)
                        await self._write_node(node, eng, quality_good=True, ts=now_ts)
                        h = self._health[key]
                        h.last_update_ts = now_mono
                        h.good_count += 1
                        h.last_value = eng
                        tags_ok += 1
                    except Exception as exc:
                        log.debug("Scale/write error key=%s: %s", key, exc)
                        tags_bad += 1
                else:
                    try:
                        is_bool = tag.reg_type in (RegType.COIL, RegType.DISCRETE_INPUT)
                        default = False if is_bool else 0.0
                        await self._write_node(node, default, quality_good=False, ts=now_ts)
                    except Exception:
                        pass
                    self._health[key].bad_count += 1
                    tags_bad += 1

            # Update diagnostics
            if self._ns:
                try:
                    if self._ns.node_modbus_ok:
                        await self._ns.node_modbus_ok.write_value(
                            ua.DataValue(ua.Variant(True, ua.VariantType.Boolean))
                        )
                    if self._ns.node_last_poll_ts:
                        await self._ns.node_last_poll_ts.write_value(
                            ua.DataValue(ua.Variant(now_ts.isoformat(), ua.VariantType.String))
                        )
                    if self._ns.node_tags_ok:
                        await self._ns.node_tags_ok.write_value(
                            ua.DataValue(ua.Variant(tags_ok, ua.VariantType.UInt32))
                        )
                    if self._ns.node_tags_bad:
                        await self._ns.node_tags_bad.write_value(
                            ua.DataValue(ua.Variant(tags_bad, ua.VariantType.UInt32))
                        )
                except Exception:
                    pass

            # Sleep remainder of poll interval
            elapsed = time.monotonic() - loop_start
            poll_s = self._cfg.poll_ms / 1000.0
            sleep_for = max(0.0, poll_s - elapsed)
            if elapsed > poll_s * 1.5:
                log.warning(
                    "Poll loop overrun: %.0fms (budget %.0fms)",
                    elapsed * 1000,
                    self._cfg.poll_ms,
                )
            await asyncio.sleep(sleep_for)

    async def _heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            self._hb_count += 1
            if self._ns and self._ns.node_heartbeat:
                try:
                    await self._ns.node_heartbeat.write_value(
                        ua.DataValue(ua.Variant(self._hb_count, ua.VariantType.UInt64))
                    )
                except Exception:
                    pass
            await asyncio.sleep(1.0)

    async def _stats_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(60.0)
            stale = [k for k, h in self._health.items() if h.is_stale]
            g_tot = sum(h.good_count for h in self._health.values())
            b_tot = sum(h.bad_count for h in self._health.values())
            log.info(
                "STATS | HB=%d | GoodReads=%d | BadReads=%d | StaleTags=%d",
                self._hb_count,
                g_tot,
                b_tot,
                len(stale),
            )
            if stale:
                log.warning("STALE TAGS (first 10): %s", stale[:10])

    def stop(self) -> None:
        self._stop.set()


# =============================================================================
# CLI
# =============================================================================
def _parse_args() -> BridgeConfig:
    p = argparse.ArgumentParser(description="Piccadily OPC UA Bridge — full 422+ tag coverage")
    p.add_argument("--modbus-host", default=CFG.modbus_host)
    p.add_argument("--modbus-port", type=int, default=CFG.modbus_port)
    p.add_argument("--modbus-unit", type=int, default=CFG.modbus_unit)
    p.add_argument("--opc-host", default=CFG.opc_host)
    p.add_argument("--opc-port", type=int, default=CFG.opc_port)
    p.add_argument("--opc-ns-uri", default=CFG.opc_ns_uri)
    p.add_argument("--poll-ms", type=int, default=CFG.poll_ms)
    p.add_argument("--batch-size", type=int, default=CFG.batch_size)
    p.add_argument("--plant-id", default=CFG.plant_id)
    p.add_argument("--device-id", default=CFG.device_id)
    p.add_argument("--log-level", default=_LOG_LEVEL, choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    return BridgeConfig(
        modbus_host=args.modbus_host,
        modbus_port=args.modbus_port,
        modbus_unit=args.modbus_unit,
        opc_host=args.opc_host,
        opc_port=args.opc_port,
        opc_ns_uri=args.opc_ns_uri,
        poll_ms=args.poll_ms,
        batch_size=args.batch_size,
        plant_id=args.plant_id,
        device_id=args.device_id,
    )


# =============================================================================
# ENTRY POINT
# =============================================================================
async def _async_main() -> None:
    cfg = _parse_args()
    bridge = OpcUaBridge(cfg, TAG_REGISTRY)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, bridge.stop)
        except NotImplementedError:
            # Windows — signal_handler not supported in event loop
            pass

    await bridge.run()


def main() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
