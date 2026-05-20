# Piccadily E2E Validation Report

Generated: 2026-05-16T14:10:43.125223

```
PICCADILY AGRO INDUSTRIES - E2E TELEMETRY PIPELINE VALIDATION
Timestamp: 2026-05-16T14:10:34.774162
Components: Simulator(:5022) -> Bridge(:4840) -> Edge Agent

======================================================================
  STEP 1: MODBUS SIMULATOR VALIDATION
======================================================================
PASS: Modbus connected to 127.0.0.1:5022
PASS: Telemetry changing (furnace raw: 3481 -> 3479)
  PASS: Input Regs 30001-30028 (Temp)
  PASS: Input Regs 30100-30114 (Pres)
  PASS: Input Regs 30150-30162 (Level)
  PASS: Input Regs 30200-30208 (Flow)
  PASS: Input Regs 30250-30257 (Draught)
  PASS: Input Regs 30300-30309 (MotorRPM)
  PASS: Input Regs 30350-30369 (MotorAmp)
  PASS: Input Regs 30450-30468 (ESP)
  PASS: Input Regs 30500-30511 (Perf)
  PASS: Input Regs 30600-30629 (Vib/Pwr)
  PASS: HR 40100-40109
  PASS: HR 40200-40205
  PASS: HR 40400-40403
  PASS: HR 40500-40515
  PASS: Coils 1-20
  PASS: Coils 30-54
  PASS: Coils 100-121
  PASS: Coils 200-231
  PASS: Discrete Inputs 10001-10064

Modbus register validation: 19/19 passed

======================================================================
  STEP 2: OPC UA BRIDGE VALIDATION
======================================================================
PASS: OPC UA connected to opc.tcp://localhost:4840/piccadily/
PASS: Namespace index=2 URI=urn:piccadily:boilerbridge
PASS: Plant/Device node found: PICCADILY_PLANT_01/BOILER_PLC_01

OPC UA Namespace Report:
  Total groups: 28
  Total tags:   428
    Alarms                   :  55 tags
    Commands                 :  32 tags
    ControlValveFB           :   6 tags
    ControlValves            :   4 tags
    DigitalStatus            :  41 tags
    Dosing                   :   4 tags
    Draught                  :   8 tags
    EspElectrical            :  19 tags
    Faults                   :  26 tags
    Flow                     :   9 tags
    Interlocks               :  22 tags
    Level                    :  13 tags
    MotorCurrent             :  20 tags
    MotorRPM                 :  10 tags
    MotorRPMExt              :  16 tags
    Performance              :  12 tags
    PidOutputs               :   6 tags
    PowerMetering            :  10 tags
    Pressure                 :  15 tags
    Setpoints                :  16 tags
    SootBlower               :   1 tags
    SystemStatus             :  14 tags
    Temperature              :  28 tags
    Utilities                :   4 tags
    VfdFeedback              :  10 tags
    VfdSetpoints             :  10 tags
    VibrationBearing         :  11 tags
    _Bridge                  :   6 tags

_Bridge Diagnostics:
  Heartbeat:      561
  ModbusConnected: True
  TotalTagsOK:    422
  TotalTagsBad:   0
  LastPollTs:     2026-05-16T08:40:38.219041+00:00
PASS: Heartbeat incrementing
PASS: Modbus connected

======================================================================
  STEP 3: TELEMETRY & SCALING VALIDATION
======================================================================

Sample tag readings (32 tags):
  PASS: Draught.DT_FURN_DFT                      =      -7.71  (range -20-5)
  PASS: EspElectrical.TRCC1_VOLT                 =      46.35  (range 30-60)
  PASS: EspElectrical.TRCC2_VOLT                 =      42.08  (range 30-60)
  PASS: Flow.FT_FW_FLOW                          =      35.05  (range 15-42)
  PASS: Flow.FT_MS_FLOW                          =      34.65  (range 15-40)
  PASS: Level.LT_DEAER                           =      72.04  (range 40-95)
  PASS: Level.LT_DRUM_AVG                        =      68.99  (range 20-80)
  PASS: Level.LT_FUEL_BIN                        =      20.29  (range 5-100)
  PASS: Level.LT_FWST                            =      71.33  (range 30-95)
  PASS: MotorRPM.GM_FDFA_RPM                     =     100.00  (range 40-130)
  PASS: MotorRPM.GM_IDFA_RPM                     =     431.50  (range 200-600)
  PASS: MotorRPM.GM_TG_RPM                       =       6.08  (range 2-10)
  PASS: Performance.BOILER_EFF                   =      83.17  (range 60-100)
  PASS: Performance.STEAM_QUALITY                =      99.78  (range 95-100)
  PASS: Pressure.PT_DEAER                        =       0.51  (range 0.2-1.5)
  PASS: Pressure.PT_DRUM                         =      45.32  (range 30-55)
  PASS: Pressure.PT_FW_PUMP_IN                   =       3.01  (range 1-5)
  PASS: Pressure.PT_FW_PUMP_OUT                  =      52.38  (range 40-70)
  PASS: Pressure.PT_MS                           =      45.03  (range 30-55)
  PASS: Temperature.TE_AIR_APH_OUT               =      93.68  (range 50-150)
  PASS: Temperature.TE_BED_1                     =     258.27  (range 100-400)
  PASS: Temperature.TE_BED_2                     =     233.75  (range 100-400)
  PASS: Temperature.TE_DEAER                     =     106.30  (range 90-120)
  PASS: Temperature.TE_ECON_INLET                =     112.38  (range 80-150)
  PASS: Temperature.TE_ECO_OUT                   =     250.00  (range 150-350)
  PASS: Temperature.TE_FG_ESP_IN                 =     134.80  (range 80-200)
  PASS: Temperature.TE_FURN                      =     933.99  (range 600-1100)
  PASS: Temperature.TE_PSH_OUT                   =     252.38  (range 200-300)
  PASS: Temperature.TE_SSH_OUT                   =     255.56  (range 200-300)
  PASS: Temperature.TT_MS_TEMP                   =     255.80  (range 200-300)
  PASS: VfdFeedback.VFD_FDFA_SPD_FB              =     100.00  (range 0-100)
  PASS: VfdFeedback.VFD_IDFA_SPD_FB              =     100.00  (range 0-100)

Industrial QA: 32 PASS / 0 FAIL / 0 WARN

======================================================================
  STEP 4: FULL TAG VALIDATION
======================================================================
  PASS: Group 'Temperature' present (28 tags)
  PASS: Group 'Pressure' present (15 tags)
  PASS: Group 'Level' present (13 tags)
  PASS: Group 'Flow' present (9 tags)
  PASS: Group 'Draught' present (8 tags)
  PASS: Group 'MotorRPM' present (10 tags)
  PASS: Group 'MotorRPMExt' present (16 tags)
  PASS: Group 'MotorCurrent' present (20 tags)
  PASS: Group 'VfdFeedback' present (10 tags)
  PASS: Group 'ControlValveFB' present (6 tags)
  PASS: Group 'EspElectrical' present (19 tags)
  PASS: Group 'Performance' present (12 tags)
  PASS: Group 'SootBlower' present (1 tags)
  PASS: Group 'SystemStatus' present (14 tags)
  PASS: Group 'Dosing' present (4 tags)
  PASS: Group 'Utilities' present (4 tags)
  PASS: Group 'VibrationBearing' present (11 tags)
  PASS: Group 'PowerMetering' present (10 tags)
  PASS: Group 'ControlValves' present (4 tags)
  PASS: Group 'VfdSetpoints' present (10 tags)
  PASS: Group 'PidOutputs' present (6 tags)
  PASS: Group 'Setpoints' present (16 tags)
  PASS: Group 'DigitalStatus' present (41 tags)
  PASS: Group 'Faults' present (26 tags)
  PASS: Group 'Interlocks' present (22 tags)
  PASS: Group 'Commands' present (32 tags)
  PASS: Group 'Alarms' present (55 tags)

======================================================================
  STEP 5: TELEMETRY CHANGE VALIDATION
======================================================================
PASS: TE_FURN changing: 933.99 -> 934.26
PASS: PT_DRUM changing: 45.27 -> 45.32
PASS: Negative draught working: DT_FURN_DFT = -7.58 mmWc
PASS: Boolean coil BFP1_RUN = True (type: bool)

======================================================================
  STEP 6: CROSS-CHECK MODBUS vs OPC UA
======================================================================
  TE_FURN: raw=3476, OPC=933.46, expected=933.72, diff=0.27
  PASS: Scaling correct
  PT_DRUM: raw=3091, OPC=45.32, expected=45.29, diff=0.03
  PASS: Scaling correct

======================================================================
  FINAL COMMISSIONING VERDICT
======================================================================
  Modbus Simulator:     PASS
  OPC UA Bridge:        PASS (428 tags)
  Industrial QA:        32 PASS / 0 FAIL / 0 WARN
  Missing Groups:       0
  Edge Agent:           PASS (422 subscriptions active)

  OVERALL: READY FOR PRODUCTION
```
