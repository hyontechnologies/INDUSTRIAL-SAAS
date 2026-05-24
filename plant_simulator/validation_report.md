# Piccadily E2E Validation Report

Generated: 2026-05-24T09:44:19.406983

```
PICCADILY AGRO INDUSTRIES - E2E TELEMETRY PIPELINE VALIDATION
Timestamp: 2026-05-24T09:44:11.052736
Components: Simulator(:5022) -> Bridge(:4840) -> Edge Agent

======================================================================
  STEP 1: MODBUS SIMULATOR VALIDATION
======================================================================
PASS: Modbus connected to 127.0.0.1:5022
PASS: Telemetry changing (furnace raw: 3186 -> 3188)
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
  Heartbeat:      16
  ModbusConnected: True
  TotalTagsOK:    422
  TotalTagsBad:   0
  LastPollTs:     2026-05-24T04:14:14.303905+00:00
PASS: Heartbeat incrementing
PASS: Modbus connected

======================================================================
  STEP 3: TELEMETRY & SCALING VALIDATION
======================================================================

Sample tag readings (32 tags):
  PASS: Draught.DT_FURN_DFT                      =      -7.55  (range -20-5)
  PASS: EspElectrical.TRCC1_VOLT                 =      45.49  (range 30-60)
  PASS: EspElectrical.TRCC2_VOLT                 =      47.42  (range 30-60)
  PASS: Flow.FT_FW_FLOW                          =      35.64  (range 15-42)
  PASS: Flow.FT_MS_FLOW                          =      35.25  (range 15-40)
  PASS: Level.LT_DEAER                           =      72.55  (range 40-95)
  PASS: Level.LT_DRUM_AVG                        =      52.92  (range 20-80)
  PASS: Level.LT_FUEL_BIN                        =      20.29  (range 5-100)
  PASS: Level.LT_FWST                            =      68.62  (range 30-95)
  PASS: MotorRPM.GM_FDFA_RPM                     =      91.94  (range 40-130)
  PASS: MotorRPM.GM_IDFA_RPM                     =     383.15  (range 200-600)
  PASS: MotorRPM.GM_TG_RPM                       =       5.97  (range 2-10)
  PASS: Performance.BOILER_EFF                   =      82.86  (range 60-100)
  PASS: Performance.STEAM_QUALITY                =      99.80  (range 95-100)
  PASS: Pressure.PT_DEAER                        =       0.51  (range 0.2-1.5)
  PASS: Pressure.PT_DRUM                         =      45.44  (range 30-55)
  PASS: Pressure.PT_FW_PUMP_IN                   =       3.05  (range 1-5)
  PASS: Pressure.PT_FW_PUMP_OUT                  =      52.67  (range 40-70)
  PASS: Pressure.PT_MS                           =      45.17  (range 30-55)
  PASS: Temperature.TE_AIR_APH_OUT               =      94.07  (range 50-150)
  PASS: Temperature.TE_BED_1                     =     242.15  (range 100-400)
  PASS: Temperature.TE_BED_2                     =     217.73  (range 100-400)
  PASS: Temperature.TE_DEAER                     =     105.93  (range 90-120)
  PASS: Temperature.TE_ECON_INLET                =     112.48  (range 80-150)
  PASS: Temperature.TE_ECO_OUT                   =     250.00  (range 150-350)
  PASS: Temperature.TE_FG_ESP_IN                 =     122.00  (range 80-200)
  PASS: Temperature.TE_FURN                      =     856.63  (range 600-1100)
  PASS: Temperature.TE_PSH_OUT                   =     244.20  (range 200-300)
  PASS: Temperature.TE_SSH_OUT                   =     247.74  (range 200-300)
  PASS: Temperature.TT_MS_TEMP                   =     247.86  (range 200-300)
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
PASS: TE_FURN changing: 856.90 -> 857.44
PASS: PT_DRUM changing: 45.49 -> 45.54
PASS: Negative draught working: DT_FURN_DFT = -7.73 mmWc
PASS: Boolean coil BFP1_RUN = True (type: bool)

======================================================================
  STEP 6: CROSS-CHECK MODBUS vs OPC UA
======================================================================
  TE_FURN: raw=3194, OPC=857.97, expected=857.97, diff=0.00
  PASS: Scaling correct
  PT_DRUM: raw=3108, OPC=45.54, expected=45.54, diff=0.00
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
