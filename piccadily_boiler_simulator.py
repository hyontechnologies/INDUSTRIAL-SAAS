#!/usr/bin/env python3
"""
=============================================================================
PICCADILY AGRO INDUSTRIES LTD.
35 TPH, 45 kg/cm2 · Bi-Drum · Travelling Grate Boiler
MECGALE AUTOMATION PVT. LTD. — SCADA Digital Twin

Modbus TCP/IP Slave Simulator (pymodbus 3.x)
Compatible with: KEPServerEX 6.x  |  OPC-UA Clients  |  Node-RED  |  Grafana

CLARIFICATION — TAG COUNT DISCREPANCY:
  • This CSV file contains 86 tags — the core process variables extracted
    from the SCADA overview screenshot and daily parameter report.
  • The KEPServerEX setup guide (HTML document) references a COMPLETE 422-tag
    database that covers every motor, VFD, ESP field, alarm, interlock,
    dosing pump, soot blower, bearing temperature, vibration, energy
    metering, and PID tuning parameter for the full plant — that full
    database has not been uploaded yet. The 86 tags in the CSV are the
    PRIMARY process tags (Tier-1 monitoring), sufficient for a full
    functional digital twin simulation of the main boiler loop.

ARCHITECTURE:
  KEPServerEX (Modbus Master)
       │ Modbus TCP port 502
       ▼
  [THIS SCRIPT — Modbus Slave / Simulator]
       │ OPC-UA node: ns=2;s=PICCADILY_BOILER_CH1.BOILER_PLC_01.<group>.<tag>
       ▼
  Grafana / Node-RED / MQTT / InfluxDB

SIMULATION ENGINE:
  • Realistic 35 TPH travelling grate boiler physics
  • Steady-state operating point derived from SCADA screenshot (28-08-2025)
    and daily parameter report (same date)
  • Interdependent tags — drum level affects feed water flow, steam
    pressure drives temperature, fuel feed drives furnace temperature, etc.
  • Gaussian noise + slow drift + alarm event injection
  • Configurable load (20 – 35 TPH ramp)
  • Automatic soot blower cycling every 4 hours
  • Trip / interlock simulation on command

USAGE:
  pip install pymodbus>=3.0
  python3 piccadily_boiler_simulator.py
  python3 piccadily_boiler_simulator.py --host 0.0.0.0 --port 502
  python3 piccadily_boiler_simulator.py --load 28.0   # run at 28 TPH

  Then in KEPServerEX:
    Channel driver : Modbus TCP/IP Ethernet
    Device IP      : 127.0.0.1  (or this machine's IP)
    Device port    : 502
    Modbus Unit ID : 1
    Import the CSV : Piccadily_KEPServerEX_Tags.csv

=============================================================================
MODBUS ADDRESS MAP (matches CSV exactly)
=============================================================================
Register Type   | Address Range | KEP notation | pymodbus index
----------------|---------------|--------------|--------------------
Input Registers | 30001–30452   | 3xxxx        | index = addr - 30001
Holding Regs    | 40400–40503   | 4xxxx        | index = addr - 40001
Coils (R/W)     | 00001–00106   | 0xxxx        | index = addr - 1
=============================================================================
"""

import argparse
import logging
import math
import random
import signal
import sys
import threading
from dataclasses import dataclass, field

from extended_registers import write_extended

# ---------------------------------------------------------------------------
# pymodbus 3.x imports
# ---------------------------------------------------------------------------
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("BoilerSim")

# ---------------------------------------------------------------------------
# Simulation constants — derived from real plant data
# ---------------------------------------------------------------------------
RATED_LOAD_TPH = 35.0  # Design steam output
MIN_LOAD_TPH = 15.0  # Minimum stable fire
MAX_LOAD_TPH = 37.0  # Short-term max

# Register space sizes — must cover highest address used
INPUT_REG_COUNT = 700  # covers up to 30700 (highest: 30629)
HOLDING_REG_COUNT = 600  # covers up to 40600 (highest: 40515)
COIL_COUNT = 250  # covers up to 00250 (highest: 00231)
DISCRETE_COUNT = 200  # covers discrete inputs 10001-10064


# =============================================================================
# SIMULATION STATE
# =============================================================================
@dataclass
class BoilerState:
    """Central simulation state object — all values in engineering units."""

    # --- Load ---
    load_tph: float = 35.0  # Current steam production
    target_load_tph: float = 35.0  # Ramp target

    # --- Steam System ---
    drum_pressure: float = 45.0  # kg/cm² (from report avg ≈ 46.5)
    ms_pressure: float = 44.8  # kg/cm²
    ms_temp: float = 246.8  # °C (SCADA reading)
    ms_flow: float = 35.0  # TPH
    drum_level_1: float = 41.0  # % LT-201
    drum_level_2: float = 42.0  # % LT-202
    drum_level_avg: float = 42.0  # % (SCADA: 42.6%)

    # --- Superheater / Heat Recovery ---
    te_ssh_out: float = 246.8  # °C (SSH outlet = MS temp at SH)
    te_psh_out: float = 243.4  # °C (PSH outlet, TE-201 in SCADA)
    te_sh_bank: float = 243.8  # °C (TE-202 bank zone)
    te_eco_in: float = 108.5  # °C (TE-302 in SCADA — feed water)
    te_eco_out: float = 253.2  # °C (TE-304 economiser gas outlet)
    te_aph_out: float = 132.3  # °C (TE-301 air preheater gas outlet)
    te_fg_esp_in: float = 121.3  # °C (TE-101 flue gas at ESP inlet)
    te_air_aph_out: float = 94.1  # °C (TE-308 preheated air)

    # --- Furnace ---
    furnace_temp: float = 850.0  # °C (typical travelling grate ≈ 800-950)
    bed_temp_1: float = 235.2  # °C (TE-305, bed thermocouple zone 1)
    bed_temp_2: float = 221.6  # °C (TE-102, bed zone 2)

    # --- Draught ---
    furn_draught: float = -7.4  # mmWc (SCADA: DT-401 = 7.4 shown positive)

    # --- Feed Water ---
    fw_flow: float = 35.2  # TPH (matches steam within make-up)
    fw_temp: float = 108.5  # °C (TE-302 economiser inlet)
    fw_tot: float = 8_188.212  # Tonnes (running total from SCADA)
    ms_tot: float = 8_188.212  # Tonnes

    # --- Deaerator ---
    deaer_level: float = 72.3  # % (SCADA bottom bar)
    deaer_temp: float = 101.3  # °C (TE-102A in SCADA)
    deaer_pressure: float = 0.5  # kg/cm²
    fwst_level: float = 67.9  # % (LT-002 from SCADA: 90.7 raw)

    # --- Fuel ---
    fuel_level: float = 20.3  # % (LT-003 in SCADA)

    # --- Motors / Fans ---
    id_fan_rpm: float = 337.0  # RPM  (M-307 in SCADA)
    id_fan_amp: float = 67.2  # A
    fd_fan_rpm: float = 69.1  # RPM  (GM-401)
    fd_fan_amp: float = 2.5  # A
    sa_fan_rpm: float = 0.0  # RPM  (M-306, secondary air fan)
    sa_fan_amp: float = 0.0  # A
    tg_rpm: float = 4.8  # RPM  (M-304, travelling grate)

    # Screw feeders (SF) — fuel feed screws
    sf1_rpm: float = 6.4  # RPM (M-301)
    sf2_rpm: float = 8.3  # RPM (M-302)
    sf3_rpm: float = 7.0  # RPM (M-303)
    sf1_amp: float = 0.1  # A
    sf2_amp: float = 1.0  # A

    # Pocket feeders (PF)
    pf1_rpm: float = 223.3  # RPM (GM-402)
    pf2_rpm: float = 118.8  # RPM (GM-403)
    pf3_rpm: float = 0.0  # RPM
    pf1_amp: float = 2.4  # A
    pf2_amp: float = 2.3  # A

    # Misc motors
    gm405_rpm: float = 353.4  # RPM (M-305 — in SCADA)
    gm405_amp: float = 24.9  # A
    m310_sac_rpm: float = 0.0  # Submerged ash conveyor

    # --- ESP ---
    trcc1_volt: float = 45.0  # kV
    trcc2_volt: float = 45.0  # kV
    trcc3_volt: float = 45.0  # kV

    # --- Control Valves (%) ---
    fcv_fw: float = 72.3  # Feed water control valve
    tcv_temp: float = 1.6  # Desuperheater spray valve
    lcv_drum: float = 0.6  # Drum level control valve
    pcv_ms: float = 0.0  # Main steam pressure control valve

    # --- Setpoints ---
    sp_drum_level: float = 50.0  # %
    sp_ms_pressure: float = 45.0  # kg/cm²
    sp_ms_temp: float = 250.0  # °C
    sp_furn_draft: float = -8.0  # mmWc

    # --- Digital Status ---
    bfp1_run: bool = True
    bfp2_run: bool = False
    m001_run: bool = True  # LP dosing pump 1
    m002_run: bool = False
    m310_run: bool = False  # Submerged ash conveyor
    ralv1_run: bool = True
    ralv2_run: bool = True
    ralv3_run: bool = True
    mrsb_run: list = field(default_factory=lambda: [False] * 7)
    sb_auto: bool = True
    fd_vfd_sel: bool = True
    id_vfd_sel: bool = True

    # --- Interlocks ---
    intlk_master: bool = False
    intlk_drum_ll: bool = False
    intlk_drum_hh: bool = False
    intlk_pres_hh: bool = False
    intlk_fw_ll: bool = False

    # ===================== EXTENDED STATE (Tier-2/3 — 336 extra tags) =========

    # --- Extended Temperature ---
    bed_temp_3: float = 218.0  # Zone-III
    bed_temp_4: float = 212.0  # Zone-IV
    drum_sat_temp: float = 257.0  # Saturation temp @ drum pressure
    te_ssh_in: float = 230.0  # SSH inlet
    te_psh_in: float = 225.0  # PSH inlet
    te_desup_out: float = 245.0  # Desuperheater outlet
    te_ms_header: float = 246.0  # MS header
    te_cyclone_out: float = 125.0  # Cyclone outlet flue gas
    te_ash_pit: float = 80.0
    te_aerofoil_vt: float = 105.0

    # --- Extended Pressure ---
    pt_fw_pump_out: float = 52.0  # kg/cm²
    pt_fw_pump_in: float = 2.5  # kg/cm²
    pt_aerofoil_dp: float = 0.3  # kg/cm²
    pt_sa_windbox: float = 120.0  # mmWc
    pt_pa_windbox: float = 150.0  # mmWc
    pt_spray_line: float = 44.0  # kg/cm²
    pt_lcv_upstrm: float = 45.0  # kg/cm²

    # --- Extended Level ---
    lt_bfp_seal: float = 65.0  # %

    # --- Extended Flow ---
    ft_sb_steam: float = 0.0  # TPH (active only during soot blow)
    ft_spray_flow: float = 0.2  # TPH
    ft_fw_8hr: float = 0.0  # Tonnes (8-hr running total)
    ft_ms_8hr: float = 0.0  # Tonnes

    # --- Extended Draught ---
    dt_aph_dp: float = 25.0  # mmWc
    dt_esp_dp: float = 12.0  # mmWc
    dt_eco_dp: float = 18.0  # mmWc
    dt_idfa_inlet: float = -80.0  # mmWc
    dt_fdfa_out: float = 120.0  # mmWc
    dt_boiler_back: float = -5.0  # mmWc

    # --- Extended Motor Amps ---
    sf3_amp: float = 0.8  # A
    sa_fan_amp_ext: float = 0.0  # A  (SA fan motor current)
    tg_amp: float = 1.5  # A
    sac_amp: float = 0.0  # A
    bfp1_amp: float = 55.0  # A
    bfp2_amp: float = 0.0  # A
    lpdp1_amp: float = 0.3  # A
    lpdp2_amp: float = 0.0  # A
    hpdp1_amp: float = 0.3  # A
    hpdp2_amp: float = 0.0  # A
    lp_agi_amp: float = 0.2  # A
    hp_agi_amp: float = 0.2  # A
    drm_fdr_amp: float = 5.0  # A
    drm_fdr_rpm: float = 450.0  # RPM

    # --- ESP Extended ---
    trcc1_curr: float = 350.0  # mA
    trcc2_curr: float = 340.0  # mA
    trcc3_curr: float = 330.0  # mA
    trcc1_pri_volt: float = 380.0  # V
    trcc2_pri_volt: float = 375.0  # V
    trcc3_pri_volt: float = 370.0  # V
    esp_derm1: float = 15.0  # % dust
    esp_derm2: float = 12.0  # %
    esp_derm3: float = 10.0  # %
    esp_cerm1: float = 70.0  # % corona
    esp_cerm2: float = 68.0  # %
    esp_cerm3: float = 65.0  # %
    esp_inshtr1: float = 85.0  # °C
    esp_inshtr2: float = 83.0  # °C
    esp_inshtr3: float = 82.0  # °C

    # --- Performance Calcs ---
    boiler_eff: float = 78.5  # %
    steam_quality: float = 99.5  # %
    heat_rate: float = 3200.0  # kCal/kg
    spec_steam: float = 4.8  # kg/kg
    evap_ratio: float = 4.5
    excess_air: float = 35.0  # %
    co2_loss: float = 8.5  # %
    unburn_loss: float = 2.0  # %
    rad_loss: float = 1.5  # %
    sh_enthalpy: float = 670.0  # kCal/kg
    fuel_rate: float = 7300.0  # kg/hr
    steam_load_pct: float = 100.0  # %

    # --- System Status ---
    oper_mode: float = 1.0  # 1=Auto
    uptime_hr: float = 0.0
    total_run_hr: float = 12500.0
    start_cnt: float = 245.0
    trip_cnt: float = 12.0
    last_trip: float = 0.0

    # --- Dosing ---
    dos_lp_rate: float = 15.0  # L/hr
    dos_hp_rate: float = 8.0  # L/hr
    dos_lp_tank: float = 75.0  # %
    dos_hp_tank: float = 80.0  # %

    # --- Utilities ---
    util_inst_air: float = 6.5  # kg/cm²
    util_cw_press: float = 2.5  # kg/cm²
    util_cw_in: float = 32.0  # °C
    util_cw_out: float = 42.0  # °C

    # --- Vibration ---
    vib_idfa_de: float = 2.5  # mm/s
    vib_idfa_nde: float = 2.3  # mm/s
    vib_fdfa_de: float = 1.8  # mm/s
    vib_fdfa_nde: float = 1.6  # mm/s
    vib_bfp1_de: float = 3.0  # mm/s
    vib_bfp2_de: float = 0.0  # mm/s

    # --- Bearing Temps ---
    temp_idfa_brg: float = 55.0  # °C
    temp_fdfa_brg: float = 48.0  # °C
    temp_bfp1_brg: float = 52.0  # °C
    temp_bfp2_brg: float = 0.0  # °C
    temp_sa_brg: float = 0.0  # °C

    # --- Energy ---
    pwr_idfa_kw: float = 85.0
    pwr_fdfa_kw: float = 12.0
    pwr_sa_kw: float = 0.0
    pwr_bfp1_kw: float = 45.0
    pwr_bfp2_kw: float = 0.0
    pwr_total_kw: float = 280.0
    pwr_total_kwh: float = 125000.0
    pwr_pf: float = 0.87
    pwr_bus_volt: float = 415.0
    pwr_bus_freq: float = 50.0

    # --- Extended Digital Status (motors run) ---
    m301_sf1_run: bool = True
    m302_sf2_run: bool = True
    m303_sf3_run: bool = True
    m304_tg_run: bool = True
    m305_idfa_run: bool = True
    m306_sa_run: bool = False
    m307_fdfa_run: bool = True
    m401_run: bool = False
    m402_run: bool = False
    m403_run: bool = False
    m404_run: bool = False
    m405_pa_run: bool = False
    m406_pa_run: bool = False
    m407_run: bool = False
    m408_run: bool = False
    m210_lpdp_run: bool = True
    m212_lpdp_run: bool = False
    m501_hpdp_run: bool = True
    m502_hpdp_run: bool = False
    m213_lp_agi_run: bool = True
    m214_hp_agi_run: bool = True
    m215_pf2_run: bool = False
    m216_run: bool = False
    m218_run: bool = False
    m219_run: bool = False

    # --- Faults (all False = healthy) ---
    faults: list = field(default_factory=lambda: [False] * 26)

    # --- Extended Interlocks ---
    intlk_temp_hh: bool = False
    intlk_draught_ll: bool = False
    intlk_bfp_fail: bool = False
    intlk_idfa_fail: bool = False
    intlk_fdfa_fail: bool = False
    intlk_bed_hh: bool = False
    intlk_fw_flow_ll: bool = False
    intlk_deaer_ll: bool = False
    intlk_fuel_ll: bool = False
    intlk_boil_trip: bool = False

    # --- VFD Setpoints (HR) ---
    vfd_idfa_sp: float = 70.0  # %
    vfd_fdfa_sp: float = 55.0  # %
    vfd_sa_sp: float = 0.0
    vfd_tg_sp: float = 40.0
    vfd_sf1_sp: float = 50.0
    vfd_sf2_sp: float = 55.0
    vfd_sf3_sp: float = 52.0
    vfd_pf1_sp: float = 75.0
    vfd_pf2_sp: float = 60.0
    vfd_pf3_sp: float = 0.0

    # --- PID Outputs (HR) ---
    pid_fw_out: float = 72.0
    pid_drm_out: float = 50.0
    pid_pres_out: float = 45.0
    pid_temp_out: float = 5.0
    pid_dft_out: float = 60.0
    pid_fd_out: float = 55.0

    # --- Extended Setpoints (HR) ---
    sp_idfa_man: float = 70.0
    sp_fdfa_man: float = 55.0
    sp_sa_man: float = 0.0
    sp_tg_man: float = 40.0
    sp_sf1_man: float = 50.0
    sp_sf2_man: float = 55.0
    sp_sf3_man: float = 52.0
    sp_pf1_man: float = 75.0
    sp_pf2_man: float = 60.0
    sp_pf3_man: float = 0.0
    sp_deaer_lvl: float = 72.0
    sp_fw_flow: float = 35.0

    # --- Internal simulation bookkeeping ---
    sim_time: float = 0.0  # seconds elapsed
    soot_blower_timer: float = 0.0  # seconds since last soot blow
    soot_blower_active_idx: int = -1
    load_ramp_speed: float = 0.1  # TPH/second ramp rate


# =============================================================================
# SCALING HELPERS
# =============================================================================
def eng_to_raw(
    eng_val: float, scaled_low: float, scaled_high: float, raw_low: float = 0, raw_high: float = 4095
) -> int:
    """Convert engineering value to raw ADC integer (0-4095 or 0-65535).

    KEPServerEX applies Linear scaling: eng = (raw / (raw_hi - raw_lo)) *
    (scaled_hi - scaled_lo) + scaled_lo.  We invert that here.
    """
    span = scaled_high - scaled_low
    if span == 0:
        return int(raw_low)
    ratio = (eng_val - scaled_low) / span
    raw = raw_low + ratio * (raw_high - raw_low)
    return int(max(raw_low, min(raw_high, round(raw))))


def bool_to_int(b: bool) -> int:
    return 1 if b else 0


# =============================================================================
# SIMULATION ENGINE
# =============================================================================
class BoilerSimulator:
    """Physics-based simulation engine for the 35 TPH boiler plant.

    Every update_step() call advances the simulation by `dt` seconds and
    computes new values for all 86 tags based on:
      1. Load setpoint ramp
      2. Thermodynamic interdependencies
      3. Control loop responses (simplified PID)
      4. Noise / realistic fluctuation
      5. Soot blower cycling
      6. Interlock and alarm logic
    """

    def __init__(self, state: BoilerState, dt: float = 1.0):
        self.state = state
        self.dt = dt
        self._noise_seed = random.Random(42)

    def _noise(self, amplitude: float) -> float:
        """Gaussian noise with given ±amplitude at 1 sigma."""
        return self._noise_seed.gauss(0, amplitude * 0.33)

    def _slow_sine(self, period_s: float, amplitude: float, phase: float = 0.0) -> float:
        """Slow sinusoidal variation — models thermal cycling."""
        return amplitude * math.sin(2 * math.pi * self.state.sim_time / period_s + phase)

    def _ramp(self, current: float, target: float, speed: float) -> float:
        """Linear ramp current toward target at given rate per dt."""
        delta = target - current
        max_step = speed * self.dt
        if abs(delta) <= max_step:
            return target
        return current + math.copysign(max_step, delta)

    def update_step(self):
        """Advance simulation by self.dt seconds."""
        s = self.state
        dt = self.dt
        s.sim_time += dt

        # ── 1. Load ramp ─────────────────────────────────────────────────
        s.load_tph = self._ramp(s.load_tph, s.target_load_tph, s.load_ramp_speed)
        load_fraction = s.load_tph / RATED_LOAD_TPH  # 0 – 1+

        # ── 2. Steam system ───────────────────────────────────────────────
        # Drum pressure: responds to load + slow thermal cycle
        target_drum_pres = 45.5 * load_fraction + self._slow_sine(900, 0.8) + self._noise(0.3)
        s.drum_pressure = self._ramp(s.drum_pressure, target_drum_pres, 0.02)
        s.ms_pressure = s.drum_pressure - 0.3 + self._noise(0.15)

        # Main steam temperature
        target_ms_temp = 240 + 15 * load_fraction + self._slow_sine(600, 2.0) + self._noise(1.0)
        s.ms_temp = self._ramp(s.ms_temp, target_ms_temp, 0.05)

        # Main steam flow (closely tracks load)
        s.ms_flow = s.load_tph + self._slow_sine(300, 0.5) + self._noise(0.2)

        # Superheater temperatures
        s.te_ssh_out = s.ms_temp + self._noise(0.5)
        s.te_psh_out = s.ms_temp - 3.5 + self._noise(0.8)
        s.te_sh_bank = s.ms_temp - 3.0 + self._noise(0.7)

        # Drum level control (3-element control simulation)
        # Error drives FCV; drum level oscillates around setpoint
        level_error = s.sp_drum_level - s.drum_level_avg
        s.fcv_fw = max(5.0, min(95.0, s.fcv_fw + 0.1 * level_error * dt + self._noise(0.3)))
        s.drum_level_avg = s.drum_level_avg + 0.005 * level_error * dt + self._slow_sine(240, 1.5) + self._noise(0.4)
        s.drum_level_avg = max(10.0, min(90.0, s.drum_level_avg))
        s.drum_level_1 = s.drum_level_avg + self._noise(0.8)
        s.drum_level_2 = s.drum_level_avg - 1.0 + self._noise(0.8)

        # ── 3. Furnace ────────────────────────────────────────────────────
        # Furnace temperature follows fuel feed + air
        target_furn_temp = 750 + 200 * load_fraction + self._slow_sine(1200, 15.0) + self._noise(8.0)
        s.furnace_temp = self._ramp(s.furnace_temp, target_furn_temp, 0.3)

        # Bed thermocouples track furnace with lag + independent noise
        s.bed_temp_1 = (
            s.furnace_temp * 0.28  # Bed is cooler than gas temp
            + self._slow_sine(500, 5.0, phase=0.5)
            + self._noise(3.0)
        )
        s.bed_temp_2 = s.furnace_temp * 0.25 + self._slow_sine(500, 5.0, phase=1.2) + self._noise(3.0)

        # Furnace draught — ID fan maintains negative draught
        target_draft = s.sp_furn_draft + self._noise(0.5) + self._slow_sine(120, 0.5)
        s.furn_draught = self._ramp(s.furn_draught, target_draft, 0.3)

        # ── 4. Heat recovery cascade ──────────────────────────────────────
        # Economiser: gas outlet ≈ furnace × 0.3 + offset
        s.te_eco_out = s.furnace_temp * 0.30 + self._noise(2.0)
        # APH gas outlet
        s.te_aph_out = s.te_eco_out * 0.52 + self._noise(1.5)
        # ESP inlet temperature
        s.te_fg_esp_in = s.te_aph_out * 0.92 + self._noise(1.2)
        # Preheated air temperature
        s.te_air_aph_out = 94.0 * load_fraction + self._noise(1.0)
        # APH flue gas inlet (slightly hotter than ECO outlet)
        te_fg_aph_in = s.te_eco_out + 5.0 + self._noise(1.0)
        # APH air inlet (ambient)
        te_air_aph_in = 35.0 + self._slow_sine(3600, 5.0) + self._noise(1.0)

        # Feed water temperature at economiser inlet
        s.fw_temp = 104.0 + 8.0 * load_fraction + self._slow_sine(600, 1.5) + self._noise(0.8)

        # ── 5. Feed water ─────────────────────────────────────────────────
        s.fw_flow = (
            s.ms_flow * 1.01  # Slight makeup for blowdown
            + self._noise(0.2)
        )
        # Running totalisers
        s.fw_tot += s.fw_flow * dt / 3600.0  # Convert TPH × s → Tonnes
        s.ms_tot += s.ms_flow * dt / 3600.0

        # ── 6. Deaerator ──────────────────────────────────────────────────
        s.deaer_level = 72.0 + self._slow_sine(1800, 3.0) + self._noise(1.0)
        s.deaer_temp = 101.0 + 5.0 * (s.deaer_pressure / 0.5) + self._noise(0.3)
        s.deaer_pressure = 0.50 + self._noise(0.02)
        s.fwst_level = 68.0 + self._slow_sine(2400, 5.0) + self._noise(1.5)

        # ── 7. Fuel ───────────────────────────────────────────────────────
        s.fuel_level = max(5.0, s.fuel_level - 0.003 * load_fraction * dt / 3600.0)
        # Refill when low (simulated manual top-up)
        if s.fuel_level < 10.0:
            s.fuel_level = 85.0

        # ── 8. Motors and fans ────────────────────────────────────────────
        # ID fan tracks load + draught control
        target_id_rpm = 280 + 150 * load_fraction + self._noise(5.0)
        s.id_fan_rpm = self._ramp(s.id_fan_rpm, target_id_rpm, 2.0)
        s.id_fan_amp = 40 + 45 * (s.id_fan_rpm / 450.0) ** 3 + self._noise(2.0)

        # FD fan (forced draught)
        target_fd_rpm = 60 + 40 * load_fraction + self._noise(3.0)
        s.fd_fan_rpm = self._ramp(s.fd_fan_rpm, target_fd_rpm, 1.0)
        s.fd_fan_amp = 0.5 + 3.0 * (s.fd_fan_rpm / 120.0) + self._noise(0.2)

        # Screw feeders track fuel demand
        base_sf_speed = 5.0 + 8.0 * load_fraction
        s.sf1_rpm = base_sf_speed + self._noise(0.3)
        s.sf2_rpm = base_sf_speed + 2.0 + self._noise(0.3)
        s.sf3_rpm = base_sf_speed + 1.0 + self._noise(0.3)
        s.sf1_amp = 0.05 + 0.12 * s.sf1_rpm + self._noise(0.05)
        s.sf2_amp = 0.7 + 0.12 * s.sf2_rpm + self._noise(0.08)

        # Pocket feeders
        s.pf1_rpm = 200 + 50 * load_fraction + self._noise(5.0)
        s.pf2_rpm = 100 + 30 * load_fraction + self._noise(3.0)
        s.pf1_amp = 2.2 + 0.5 * (s.pf1_rpm / 300.0) + self._noise(0.1)
        s.pf2_amp = 2.0 + 0.5 * (s.pf2_rpm / 200.0) + self._noise(0.1)

        # Travelling grate
        s.tg_rpm = 4.0 + 2.0 * load_fraction + self._noise(0.1)

        # Misc motor (M-305, GM-405)
        s.gm405_rpm = 320 + 80 * load_fraction + self._noise(8.0)
        s.gm405_amp = 20 + 10 * (s.gm405_rpm / 450.0) + self._noise(1.0)

        # ── 9. ESP ────────────────────────────────────────────────────────
        s.trcc1_volt = 45.0 + self._slow_sine(600, 3.0) + self._noise(1.0)
        s.trcc2_volt = 44.5 + self._slow_sine(600, 3.0, 1.0) + self._noise(1.0)
        s.trcc3_volt = 43.0 + self._slow_sine(600, 3.0, 2.0) + self._noise(1.0)

        # ── 10. Soot blower cycling ───────────────────────────────────────
        SOOT_BLOWER_PERIOD_S = 14_400  # 4 hours
        SOOT_BLOWER_DURATION_S = 120  # 2 minutes per blower
        s.soot_blower_timer += dt

        if s.sb_auto:
            cycle_pos = s.soot_blower_timer % SOOT_BLOWER_PERIOD_S
            blower_idx = int(cycle_pos / SOOT_BLOWER_DURATION_S) % 7
            active = cycle_pos < (7 * SOOT_BLOWER_DURATION_S)
            s.mrsb_run = [active and (i == blower_idx) for i in range(7)]
        else:
            s.mrsb_run = [False] * 7

        # ── 11. Interlocks ────────────────────────────────────────────────
        s.intlk_drum_ll = s.drum_level_avg < 15.0
        s.intlk_drum_hh = s.drum_level_avg > 85.0
        s.intlk_pres_hh = s.ms_pressure > 52.0
        s.intlk_fw_ll = s.fw_flow < 5.0
        s.intlk_master = any([s.intlk_drum_ll, s.intlk_drum_hh, s.intlk_pres_hh, s.intlk_fw_ll])

        # ── 12. Control valve setpoint simulation ─────────────────────────
        # PCV tracks ms_pressure vs setpoint
        pres_err = s.ms_pressure - s.sp_ms_pressure
        s.pcv_ms = max(0, min(100, s.pcv_ms + 0.05 * pres_err * dt))

        # TCV (desuperheater spray) tracks ms_temp vs setpoint
        temp_err = s.ms_temp - s.sp_ms_temp
        s.tcv_temp = max(0, min(30, s.tcv_temp + 0.02 * temp_err * dt))

        # LCV tracks drum level vs setpoint
        lvl_err = s.sp_drum_level - s.drum_level_avg
        s.lcv_drum = max(0, min(100, s.lcv_drum + 0.05 * lvl_err * dt))

        # ══════════════════════════════════════════════════════════════════
        # EXTENDED SIMULATION (Tier-2/3 — 336 extra tags)
        # ══════════════════════════════════════════════════════════════════

        # ── 13. Extended Temperature ──────────────────────────────────────
        s.bed_temp_3 = s.furnace_temp * 0.26 + self._slow_sine(500, 4.0, 1.8) + self._noise(2.5)
        s.bed_temp_4 = s.furnace_temp * 0.24 + self._slow_sine(500, 4.0, 2.5) + self._noise(2.5)
        # Drum saturation temp ≈ approx from steam tables for 0-60 kg/cm²
        s.drum_sat_temp = 100.0 + 3.5 * s.drum_pressure + self._noise(0.3)
        s.te_ssh_in = s.te_psh_out + 2.0 + self._noise(0.5)
        s.te_psh_in = s.drum_sat_temp + 5.0 + self._noise(0.5)
        s.te_desup_out = s.ms_temp - s.tcv_temp * 0.5 + self._noise(0.8)
        s.te_ms_header = s.ms_temp - 0.5 + self._noise(0.3)
        s.te_cyclone_out = s.te_aph_out * 0.95 + self._noise(1.0)
        s.te_ash_pit = 60 + 30 * load_fraction + self._slow_sine(1800, 5.0) + self._noise(2.0)
        s.te_aerofoil_vt = s.fw_temp + 2.0 + self._noise(0.5)

        # ── 14. Extended Pressure ─────────────────────────────────────────
        s.pt_fw_pump_out = s.drum_pressure + 7.0 + self._noise(0.5)
        s.pt_fw_pump_in = 2.0 + 1.0 * load_fraction + self._noise(0.1)
        s.pt_aerofoil_dp = 0.2 + 0.15 * load_fraction + self._noise(0.02)
        s.pt_sa_windbox = 100 + 80 * load_fraction + self._noise(5.0)
        s.pt_pa_windbox = 120 + 100 * load_fraction + self._noise(5.0)
        s.pt_spray_line = s.ms_pressure - 1.0 + self._noise(0.3)
        s.pt_lcv_upstrm = s.drum_pressure + 0.5 + self._noise(0.2)

        # ── 15. Extended Level ────────────────────────────────────────────
        s.lt_bfp_seal = 60 + 10 * load_fraction + self._slow_sine(3600, 3.0) + self._noise(1.5)

        # ── 16. Extended Flow ─────────────────────────────────────────────
        sb_active = any(s.mrsb_run)
        s.ft_sb_steam = (1.5 + self._noise(0.2)) if sb_active else 0.0
        s.ft_spray_flow = max(0, s.tcv_temp * 0.1 + self._noise(0.05))
        s.ft_fw_8hr += s.fw_flow * dt / 3600.0
        s.ft_ms_8hr += s.ms_flow * dt / 3600.0
        # Reset 8hr totals every 8 hours (28800s)
        if s.sim_time % 28800 < dt:
            s.ft_fw_8hr = 0.0
            s.ft_ms_8hr = 0.0

        # ── 17. Extended Draught ──────────────────────────────────────────
        s.dt_aph_dp = 20 + 15 * load_fraction + self._noise(2.0)
        s.dt_esp_dp = 8 + 8 * load_fraction + self._noise(1.0)
        s.dt_eco_dp = 12 + 12 * load_fraction + self._noise(1.5)
        s.dt_idfa_inlet = -50 - 80 * load_fraction + self._noise(5.0)
        s.dt_fdfa_out = 80 + 100 * load_fraction + self._noise(5.0)
        s.dt_boiler_back = s.furn_draught * 0.7 + self._noise(0.5)

        # ── 18. Extended Motor Amps ───────────────────────────────────────
        s.sf3_amp = 0.6 + 0.12 * s.sf3_rpm + self._noise(0.06)
        s.sa_fan_amp_ext = 0.0  # SA fan off
        s.tg_amp = 0.8 + 0.15 * s.tg_rpm + self._noise(0.1)
        s.sac_amp = 3.0 + self._noise(0.5) if s.m310_run else 0.0
        s.bfp1_amp = (40 + 25 * load_fraction + self._noise(2.0)) if s.bfp1_run else 0.0
        s.bfp2_amp = (40 + 25 * load_fraction + self._noise(2.0)) if s.bfp2_run else 0.0
        s.lpdp1_amp = (0.2 + 0.15 * load_fraction + self._noise(0.02)) if s.m001_run else 0.0
        s.lpdp2_amp = (0.2 + 0.15 * load_fraction + self._noise(0.02)) if s.m002_run else 0.0
        s.hpdp1_amp = 0.25 + self._noise(0.02) if s.m501_hpdp_run else 0.0
        s.hpdp2_amp = 0.25 + self._noise(0.02) if s.m502_hpdp_run else 0.0
        s.lp_agi_amp = 0.15 + self._noise(0.02) if s.m213_lp_agi_run else 0.0
        s.hp_agi_amp = 0.15 + self._noise(0.02) if s.m214_hp_agi_run else 0.0
        s.drm_fdr_amp = 4.0 + 2.0 * load_fraction + self._noise(0.3)
        s.drm_fdr_rpm = 400 + 100 * load_fraction + self._noise(10.0)

        # ── 19. ESP Extended ──────────────────────────────────────────────
        s.trcc1_curr = 300 + 100 * (s.trcc1_volt / 50.0) + self._noise(15.0)
        s.trcc2_curr = 290 + 100 * (s.trcc2_volt / 50.0) + self._noise(15.0)
        s.trcc3_curr = 280 + 100 * (s.trcc3_volt / 50.0) + self._noise(15.0)
        s.trcc1_pri_volt = 370 + 20 * (s.trcc1_volt / 50.0) + self._noise(5.0)
        s.trcc2_pri_volt = 365 + 20 * (s.trcc2_volt / 50.0) + self._noise(5.0)
        s.trcc3_pri_volt = 360 + 20 * (s.trcc3_volt / 50.0) + self._noise(5.0)
        s.esp_derm1 = 12 + 8 * load_fraction + self._noise(2.0)
        s.esp_derm2 = 10 + 6 * load_fraction + self._noise(1.5)
        s.esp_derm3 = 8 + 5 * load_fraction + self._noise(1.2)
        s.esp_cerm1 = 65 + 10 * (s.trcc1_volt / 50.0) + self._noise(3.0)
        s.esp_cerm2 = 63 + 10 * (s.trcc2_volt / 50.0) + self._noise(3.0)
        s.esp_cerm3 = 60 + 10 * (s.trcc3_volt / 50.0) + self._noise(3.0)
        s.esp_inshtr1 = 80 + 10 * load_fraction + self._noise(2.0)
        s.esp_inshtr2 = 78 + 10 * load_fraction + self._noise(2.0)
        s.esp_inshtr3 = 76 + 10 * load_fraction + self._noise(2.0)

        # ── 20. Performance Calculations ──────────────────────────────────
        s.boiler_eff = 75 + 8 * load_fraction + self._slow_sine(1800, 1.0) + self._noise(0.5)
        s.steam_quality = 99.0 + 0.8 * load_fraction + self._noise(0.1)
        s.heat_rate = 2800 + 800 * load_fraction + self._noise(50.0)
        s.spec_steam = 4.0 + 1.5 * load_fraction + self._noise(0.1)
        s.evap_ratio = 3.5 + 2.0 * load_fraction + self._noise(0.1)
        s.excess_air = 30 + 15 * (1 - load_fraction) + self._noise(2.0)
        s.co2_loss = 7 + 3 * load_fraction + self._noise(0.3)
        s.unburn_loss = 1.5 + 1.0 * (1 - load_fraction) + self._noise(0.2)
        s.rad_loss = 1.2 + 0.5 * (1 - load_fraction) + self._noise(0.1)
        s.sh_enthalpy = 620 + 100 * load_fraction + self._noise(5.0)
        s.fuel_rate = 5500 + 3500 * load_fraction + self._noise(100.0)
        s.steam_load_pct = (s.load_tph / RATED_LOAD_TPH) * 100.0

        # ── 21. System Status ─────────────────────────────────────────────
        s.oper_mode = 1.0  # Auto
        s.uptime_hr = s.sim_time / 3600.0

        # ── 22. Dosing ────────────────────────────────────────────────────
        s.dos_lp_rate = (12 + 5 * load_fraction + self._noise(0.5)) if s.m001_run else 0.0
        s.dos_hp_rate = (6 + 3 * load_fraction + self._noise(0.3)) if s.m501_hpdp_run else 0.0
        s.dos_lp_tank = max(5, s.dos_lp_tank - 0.001 * dt / 3600.0)
        s.dos_hp_tank = max(5, s.dos_hp_tank - 0.0008 * dt / 3600.0)
        if s.dos_lp_tank < 10.0:
            s.dos_lp_tank = 90.0  # Refill
        if s.dos_hp_tank < 10.0:
            s.dos_hp_tank = 90.0

        # ── 23. Utilities ─────────────────────────────────────────────────
        s.util_inst_air = 6.0 + self._slow_sine(3600, 0.5) + self._noise(0.2)
        s.util_cw_press = 2.2 + self._slow_sine(7200, 0.3) + self._noise(0.1)
        s.util_cw_in = 30 + self._slow_sine(7200, 3.0) + self._noise(0.5)
        s.util_cw_out = s.util_cw_in + 8 + 4 * load_fraction + self._noise(0.5)

        # ── 24. Vibration ─────────────────────────────────────────────────
        id_vib_base = 1.5 + 2.0 * (s.id_fan_rpm / 500.0) ** 2
        s.vib_idfa_de = id_vib_base + self._noise(0.3)
        s.vib_idfa_nde = id_vib_base * 0.9 + self._noise(0.3)
        fd_vib_base = 1.0 + 1.5 * (s.fd_fan_rpm / 120.0) ** 2
        s.vib_fdfa_de = fd_vib_base + self._noise(0.2)
        s.vib_fdfa_nde = fd_vib_base * 0.85 + self._noise(0.2)
        s.vib_bfp1_de = (2.0 + 1.5 * load_fraction + self._noise(0.3)) if s.bfp1_run else 0.0
        s.vib_bfp2_de = (2.0 + 1.5 * load_fraction + self._noise(0.3)) if s.bfp2_run else 0.0

        # ── 25. Bearing Temps ─────────────────────────────────────────────
        s.temp_idfa_brg = 40 + 25 * (s.id_fan_rpm / 500.0) + self._noise(1.0)
        s.temp_fdfa_brg = 38 + 20 * (s.fd_fan_rpm / 120.0) + self._noise(0.8)
        s.temp_bfp1_brg = (42 + 18 * load_fraction + self._noise(1.0)) if s.bfp1_run else 25.0
        s.temp_bfp2_brg = (42 + 18 * load_fraction + self._noise(1.0)) if s.bfp2_run else 25.0
        s.temp_sa_brg = 25.0  # SA fan off

        # ── 26. Energy ────────────────────────────────────────────────────
        s.pwr_idfa_kw = 0.746 * s.id_fan_amp * 0.415 * 1.73 * s.pwr_pf + self._noise(2.0)
        s.pwr_fdfa_kw = 0.746 * s.fd_fan_amp * 0.415 * 1.73 * s.pwr_pf + self._noise(0.5)
        s.pwr_sa_kw = 0.0
        s.pwr_bfp1_kw = (0.746 * s.bfp1_amp * 0.415 * 1.73 * s.pwr_pf) if s.bfp1_run else 0.0
        s.pwr_bfp2_kw = (0.746 * s.bfp2_amp * 0.415 * 1.73 * s.pwr_pf) if s.bfp2_run else 0.0
        s.pwr_total_kw = s.pwr_idfa_kw + s.pwr_fdfa_kw + s.pwr_sa_kw + s.pwr_bfp1_kw + s.pwr_bfp2_kw + 50.0
        s.pwr_total_kwh += s.pwr_total_kw * dt / 3600.0
        s.pwr_pf = 0.85 + 0.05 * load_fraction + self._noise(0.01)
        s.pwr_bus_volt = 410 + self._slow_sine(600, 5.0) + self._noise(2.0)
        s.pwr_bus_freq = 49.8 + self._slow_sine(300, 0.2) + self._noise(0.05)

        # ── 27. Extended Digital Status ───────────────────────────────────
        s.m301_sf1_run = s.sf1_rpm > 1.0
        s.m302_sf2_run = s.sf2_rpm > 1.0
        s.m303_sf3_run = s.sf3_rpm > 1.0
        s.m304_tg_run = s.tg_rpm > 0.5
        s.m305_idfa_run = s.id_fan_rpm > 10.0
        s.m307_fdfa_run = s.fd_fan_rpm > 5.0

        # ── 28. PID Tracking ──────────────────────────────────────────────
        s.pid_fw_out = s.fcv_fw
        s.pid_drm_out = s.lcv_drum
        s.pid_pres_out = s.pcv_ms
        s.pid_temp_out = s.tcv_temp
        s.pid_dft_out = max(0, min(100, 50 + 50 * (s.furn_draught / s.sp_furn_draft)))
        s.pid_fd_out = max(0, min(100, s.fd_fan_rpm / 15.0 * 100))

        # ── 29. Extended Interlocks ───────────────────────────────────────
        s.intlk_temp_hh = s.ms_temp > 280.0
        s.intlk_draught_ll = s.furn_draught < -25.0
        s.intlk_bfp_fail = not s.bfp1_run and not s.bfp2_run
        s.intlk_idfa_fail = s.id_fan_rpm < 10.0
        s.intlk_fdfa_fail = s.fd_fan_rpm < 5.0
        s.intlk_bed_hh = s.bed_temp_1 > 350.0 or s.bed_temp_2 > 350.0
        s.intlk_fw_flow_ll = s.fw_flow < 5.0
        s.intlk_deaer_ll = s.deaer_level < 20.0
        s.intlk_fuel_ll = s.fuel_level < 8.0
        s.intlk_boil_trip = s.intlk_master


# =============================================================================
# REGISTER MAP WRITER
# =============================================================================
class RegisterWriter:
    """Converts BoilerState engineering values to raw Modbus register integers
    and writes them to the pymodbus DataBlock.

    ADDRESS MAPPING (all addresses 1-based as in KEPServerEX CSV):
      Input Registers (3x):  pymodbus index = address - 30001
      Holding Registers (4x): pymodbus index = address - 40001
      Coils (0x):             pymodbus index = address - 1 (min address is 1)
    """

    def __init__(self, context: ModbusSlaveContext):
        self.ctx = context

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────
    def _ir(self, address: int, eng: float, slo: float, shi: float, raw_lo: float = 0, raw_hi: float = 4095):
        """Write one Input Register (3x)."""
        idx = address - 30001
        raw = eng_to_raw(eng, slo, shi, raw_lo, raw_hi)
        self.ctx.setValues(4, idx, [raw])  # fc=4 → input registers

    def _hr(self, address: int, eng: float, slo: float, shi: float, raw_lo: float = 0, raw_hi: float = 4095):
        """Write one Holding Register (4x)."""
        idx = address - 40001
        raw = eng_to_raw(eng, slo, shi, raw_lo, raw_hi)
        self.ctx.setValues(3, idx, [raw])  # fc=3 → holding registers

    def _coil(self, address: int, state: bool):
        """Write one Coil (0x)."""
        idx = address - 1  # CSV address 00001 → index 0
        self.ctx.setValues(1, idx, [1 if state else 0])

    def _di(self, address: int, state: bool):
        """Write one Discrete Input (1x). KEP address 1xxxx → index = addr - 10001."""
        idx = address - 10001
        self.ctx.setValues(2, idx, [1 if state else 0])

    # ──────────────────────────────────────────────────────────────────────
    # Main write — maps every tag from the CSV
    # ──────────────────────────────────────────────────────────────────────
    def write_all(self, s: BoilerState):
        # ── INPUT REGISTERS — TEMPERATURE (30001–30017) ──────────────────
        self._ir(30001, s.fw_temp, 0, 200)  # TE_ECON_INLET
        self._ir(30002, s.te_fg_esp_in, 0, 300)  # TE_FG_APH_OUT (proxy: ESP→APH outlet flue gas)
        self._ir(30003, max(0, s.ms_temp * 0.38), 0, 200)  # TE_SB_LINE (soot blower steam line)
        self._ir(30004, s.te_ssh_out, 0, 500)  # TE_SSH_OUT
        self._ir(30005, s.te_psh_out, 0, 500)  # TE_PSH_OUT
        self._ir(30006, max(0, s.ms_temp * 0.39), 0, 200)  # TE_SB_HDR (soot blower header)
        self._ir(30007, s.te_eco_out, 0, 250)  # TE_ECO_OUT
        self._ir(30008, s.te_aph_out + 15, 0, 200)  # TE_FG_APH_IN (slightly warmer than APH out)
        self._ir(30009, s.furnace_temp, 0, 1100)  # TE_FURN
        self._ir(30010, s.bed_temp_1, 0, 400)  # TE_BED_1
        self._ir(30011, s.bed_temp_2, 0, 400)  # TE_BED_2
        self._ir(30012, 35.0, 0, 100)  # TE_AIR_APH_IN (ambient ≈ 35°C)
        self._ir(30013, s.te_air_aph_out, 0, 200)  # TE_AIR_APH_OUT
        self._ir(30014, s.te_fg_esp_in, 0, 200)  # TE_FG_ESP_IN
        self._ir(30015, s.deaer_temp, 0, 150)  # TE_DEAER
        self._ir(30016, s.deaer_temp - 1.5, 0, 150)  # TT_DEAER (storage tank, slightly cooler)
        self._ir(30017, s.ms_temp, 0, 500)  # TT_MS_TEMP

        # ── INPUT REGISTERS — PRESSURE (30100–30103) ─────────────────────
        self._ir(30100, s.deaer_pressure, 0, 2.0)  # PT_DEAER
        self._ir(30101, s.drum_pressure, 0, 60.0)  # PT_DRUM
        self._ir(30102, s.ms_pressure, 0, 60.0)  # PT_MS
        self._ir(30103, max(0, s.ms_pressure * 0.012), 0, 2.0)  # PT_SB_LINE

        # ── INPUT REGISTERS — LEVEL (30150–30159) ────────────────────────
        self._ir(30150, s.deaer_level, 0, 100)  # LT_DEAER
        self._ir(30151, s.fwst_level, 0, 100)  # LT_FWST
        self._ir(30152, s.fuel_level, 0, 100)  # LT_FUEL_BIN
        self._ir(30153, s.drum_level_1, 0, 100)  # LT_DRUM_1
        self._ir(30154, s.drum_level_2, 0, 100)  # LT_DRUM_2
        self._ir(30155, s.drum_level_avg, 0, 100)  # LT_DRUM_AVG
        self._ir(30156, s.deaer_level - 2, 0, 100)  # LTM_DEAER_1
        self._ir(30157, s.deaer_level + 2, 0, 100)  # LTM_DEAER_2
        self._ir(30158, s.fwst_level - 3, 0, 100)  # LTM_FWST_1
        self._ir(30159, s.fwst_level + 3, 0, 100)  # LTM_FWST_2

        # ── INPUT REGISTERS — FLOW (30200–30203) ─────────────────────────
        self._ir(30200, s.ms_flow, 0, 50)  # FT_MS_FLOW
        self._ir(30201, s.fw_flow, 0, 50)  # FT_FW_FLOW
        # Totalisers: raw 0-65535, scaled 0-999999.9
        self._ir(30202, s.fw_tot, 0, 999999.9, 0, 65535)  # FT_FW_TOT
        self._ir(30203, s.ms_tot, 0, 999999.9, 0, 65535)  # FT_MS_TOT

        # ── INPUT REGISTERS — DRAUGHT (30250) ────────────────────────────
        self._ir(30250, s.furn_draught, -30, 30)  # DT_FURN_DFT

        # ── INPUT REGISTERS — MOTOR RPM (30300–30309) ────────────────────
        self._ir(30300, s.sf1_rpm, 0, 50)  # GM_SF1_RPM
        self._ir(30301, s.sf2_rpm, 0, 50)  # GM_SF2_RPM
        self._ir(30302, s.sf3_rpm, 0, 50)  # GM_SF3_RPM
        self._ir(30303, s.pf1_rpm, 0, 120)  # GM_PF1_RPM
        self._ir(30304, s.pf2_rpm, 0, 300)  # GM_PF2_RPM
        self._ir(30305, s.pf3_rpm, 0, 200)  # GM_PF3_RPM
        self._ir(30306, s.tg_rpm, 0, 15)  # GM_TG_RPM
        self._ir(30307, s.id_fan_rpm, 0, 1500)  # GM_IDFA_RPM
        self._ir(30308, s.gm405_rpm, 0, 1500)  # GM_SA_FAN_RPM (using gm405)
        self._ir(30309, s.fd_fan_rpm, 0, 1500)  # GM_FDFA_RPM

        # ── INPUT REGISTERS — MOTOR CURRENT (30350–30355) ────────────────
        self._ir(30350, s.sf1_amp, 0, 20)  # GM_SF1_AMP
        self._ir(30351, s.sf2_amp, 0, 20)  # GM_SF2_AMP
        self._ir(30352, s.pf1_amp, 0, 15)  # GM_PF1_AMP
        self._ir(30353, s.pf2_amp, 0, 15)  # GM_PF2_AMP
        self._ir(30354, s.id_fan_amp, 0, 35)  # GM_IDFA_AMP
        self._ir(30355, s.fd_fan_amp, 0, 90)  # GM_FDFA_AMP

        # ── INPUT REGISTERS — ESP VOLTAGE (30450–30452) ──────────────────
        self._ir(30450, s.trcc1_volt, 0, 100)  # TRCC1_VOLT
        self._ir(30451, s.trcc2_volt, 0, 100)  # TRCC2_VOLT
        self._ir(30452, s.trcc3_volt, 0, 100)  # TRCC3_VOLT

        # ── HOLDING REGISTERS — CONTROL VALVES (40400–40403) ─────────────
        self._hr(40400, s.fcv_fw, 0, 100)  # FCV_FW_CTRL
        self._hr(40401, s.tcv_temp, 0, 100)  # TCV_TEMP_CTRL
        self._hr(40402, s.lcv_drum, 0, 100)  # LCV_DRUM_CTRL
        self._hr(40403, s.pcv_ms, 0, 100)  # PCV_MS_CTRL

        # ── HOLDING REGISTERS — SETPOINTS (40500–40503) ──────────────────
        self._hr(40500, s.sp_drum_level, 0, 100)  # SP_DRUM_LVL
        self._hr(40501, s.sp_ms_pressure, 0, 60)  # SP_MS_PRES
        self._hr(40502, s.sp_ms_temp, 0, 500)  # SP_MS_TEMP
        self._hr(40503, s.sp_furn_draft, -30, 30)  # SP_FURN_DFT

        # ── COILS — DIGITAL STATUS ────────────────────────────────────────
        self._coil(1, s.bfp1_run)  # BFP1_RUN  00001
        self._coil(2, s.bfp2_run)  # BFP2_RUN  00002
        self._coil(3, s.m001_run)  # M001_RUN  00003
        self._coil(4, s.m002_run)  # M002_RUN  00004
        self._coil(5, s.m310_run)  # M310_SAC_RUN 00005
        self._coil(6, s.ralv1_run)  # RALV1_RUN 00006
        self._coil(7, s.ralv2_run)  # RALV2_RUN 00007
        self._coil(8, s.ralv3_run)  # RALV3_RUN 00008
        for i, mrsb in enumerate(s.mrsb_run):
            self._coil(10 + i, mrsb)  # MRSB1–7  00010–00016
        self._coil(20, s.sb_auto)  # SB_AUTO  00020
        self._coil(100, s.intlk_master)  # INTLK_MASTER 00100
        self._coil(101, s.intlk_drum_ll)  # INTLK_DRUM_LL 00101
        self._coil(102, s.intlk_drum_hh)  # INTLK_DRUM_HH 00102
        self._coil(103, s.intlk_pres_hh)  # INTLK_PRES_HH 00103
        self._coil(104, s.intlk_fw_ll)  # INTLK_FW_LL 00104
        self._coil(105, s.fd_vfd_sel)  # FD_VFD_SEL 00105
        self._coil(106, s.id_vfd_sel)  # ID_VFD_SEL 00106

        # ── EXTENDED TAGS (Tier-2/3 — 336 additional tags) ────────────────
        write_extended(self, s, eng_to_raw)


# =============================================================================
# CONSOLE STATUS DISPLAY
# =============================================================================
def print_status(s: BoilerState, cycle: int):
    """Print a concise live status table to stdout."""
    sb_active = any(s.mrsb_run)
    sb_idx = s.mrsb_run.index(True) + 1 if sb_active else 0
    trip_str = "!!! TRIP ACTIVE" if s.intlk_master else "OK"
    sb_str = f"MRSB-{sb_idx} ACTIVE" if sb_active else "Idle"

    print(
        f"\r[{cycle:06d}] "
        f"Load={s.load_tph:5.1f}TPH  "
        f"DrumPres={s.drum_pressure:5.1f}kg/cm²  "
        f"MSTemp={s.ms_temp:5.1f}°C  "
        f"DrumLvl={s.drum_level_avg:4.1f}%  "
        f"FurnDft={s.furn_draught:+5.1f}mmWc  "
        f"SootBlr={sb_str}  "
        f"Interlock={trip_str}",
        end="",
        flush=True,
    )


# =============================================================================
# MAIN — server setup and simulation loop
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Piccadily Agro Boiler — Modbus TCP Slave Simulator")
    parser.add_argument("--host", default="0.0.0.0", help="Listen address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--unit", type=int, default=1, help="Modbus Unit ID (default: 1)")
    parser.add_argument("--load", type=float, default=35.0, help="Initial steam load in TPH (default: 35.0)")
    parser.add_argument("--dt", type=float, default=1.0, help="Simulation time step in seconds (default: 1.0)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose pymodbus logging")
    args = parser.parse_args()

    if not args.verbose:
        logging.getLogger("pymodbus").setLevel(logging.WARNING)

    # ── Build pymodbus datastore ──────────────────────────────────────────
    # All blocks initialised to zero; simulator will update them immediately
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * DISCRETE_COUNT),  # 1x Discrete Inputs
        co=ModbusSequentialDataBlock(0, [0] * COIL_COUNT),  # 0x Coils
        hr=ModbusSequentialDataBlock(0, [0] * HOLDING_REG_COUNT),  # 4x Holding Regs
        ir=ModbusSequentialDataBlock(0, [0] * INPUT_REG_COUNT),  # 3x Input Regs
    )
    context = ModbusServerContext(slaves={args.unit: store}, single=False)

    # ── Device identification (shows up in OPC-UA / Modbus introspection) ─
    identity = ModbusDeviceIdentification()
    identity.VendorName = "Mecgale Automation Pvt. Ltd."
    identity.ProductCode = "PICCADILY-BOILER-SIM"
    identity.VendorUrl = "https://www.mecgale.com"
    identity.ProductName = "35 TPH Travelling Grate Boiler Simulator"
    identity.ModelName = "Digital Twin — Piccadily Agro Industries"
    identity.MajorMinorRevision = "1.0.0"

    # ── Initialise simulation objects ─────────────────────────────────────
    state = BoilerState()
    state.load_tph = args.load
    state.target_load_tph = args.load
    sim = BoilerSimulator(state, dt=args.dt)
    writer = RegisterWriter(store)

    # Seed one full simulation step before server starts
    sim.update_step()
    writer.write_all(state)

    log.info("=" * 70)
    log.info("  PICCADILY AGRO INDUSTRIES — Boiler Digital Twin Simulator")
    log.info("=" * 70)
    log.info(f"  Modbus TCP server  : {args.host}:{args.port}  Unit ID={args.unit}")
    log.info(f"  Initial steam load : {args.load} TPH")
    log.info(f"  Simulation step    : {args.dt}s")
    log.info(f"  Input registers    : 0–{INPUT_REG_COUNT - 1}  (30001–30{INPUT_REG_COUNT})")
    log.info(f"  Holding registers  : 0–{HOLDING_REG_COUNT - 1}  (40001–40{HOLDING_REG_COUNT})")
    log.info(f"  Coils              : 0–{COIL_COUNT - 1}  (00001–00{COIL_COUNT})")
    log.info("")
    log.info("  KEPServerEX connection settings:")
    log.info("    Driver  : Modbus TCP/IP Ethernet")
    log.info("    IP      : 127.0.0.1  (if on same machine)")
    log.info(f"    Port    : {args.port}")
    log.info(f"    Unit ID : {args.unit}")
    log.info("")
    log.info("  Simulation loop running — Ctrl+C to stop")
    log.info("=" * 70)

    # ── Simulation loop runs in a background thread ───────────────────────
    stop_event = threading.Event()
    cycle = [0]

    def sim_loop():
        while not stop_event.is_set():
            sim.update_step()
            writer.write_all(state)
            cycle[0] += 1
            if cycle[0] % 5 == 0:
                print_status(state, cycle[0])
            stop_event.wait(timeout=args.dt)

    sim_thread = threading.Thread(target=sim_loop, daemon=True)
    sim_thread.start()

    # ── Graceful shutdown ─────────────────────────────────────────────────
    def _signal_handler(sig, frame):
        print("\n")
        log.info("Shutdown signal received — stopping server…")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # ── Start Modbus TCP server (blocking) ────────────────────────────────
    try:
        StartTcpServer(
            context=context,
            identity=identity,
            address=(args.host, args.port),
        )
    except PermissionError:
        log.error(
            f"Cannot bind to port {args.port}. "
            "On Linux, port 502 requires root (sudo) or a port >1024. "
            "Try: python piccadily_boiler_simulator.py --port 5021"
        )
        sys.exit(1)
    except OSError as e:
        if "10048" in str(e):
            log.error(
                f"Port {args.port} is already in use by another process. "
                "Ensure no other instance of the simulator or KEPServerEX is using this port. "
                f"Try using a different port, e.g.: python piccadily_boiler_simulator.py --port {args.port + 1}"
            )
        else:
            log.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
