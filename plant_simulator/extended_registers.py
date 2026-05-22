"""Extended register writes for the full 422-tag CSV coverage."""


def write_extended(writer, s, eng_to_raw):
    """Write all Tier-2/3 registers not covered by the original 86-tag write_all."""
    _ir = writer._ir
    _hr = writer._hr
    _coil = writer._coil
    _di = writer._di

    # ── EXTENDED INPUT REGISTERS — TEMPERATURE (30018–30028) ──────────
    _ir(30018, s.bed_temp_3, 0, 400)
    _ir(30019, s.bed_temp_4, 0, 400)
    _ir(30020, s.drum_sat_temp, 0, 300)
    _ir(30021, s.te_ssh_in, 0, 400)
    _ir(30022, s.te_psh_in, 0, 400)
    _ir(30023, s.te_desup_out, 0, 500)
    _ir(30024, s.fw_temp - 5, 0, 150)  # FW pump inlet ≈ deaer-5
    _ir(30025, s.te_ms_header, 0, 500)
    _ir(30026, s.te_cyclone_out, 0, 250)
    _ir(30027, s.te_ash_pit, 0, 200)
    _ir(30028, s.te_aerofoil_vt, 0, 200)

    # ── EXTENDED INPUT REGISTERS — PRESSURE (30104–30114) ─────────────
    _ir(30104, s.drum_pressure, 0, 60.0)  # PT_201_RDN
    _ir(30105, s.ms_pressure, 0, 60.0)  # PT_202_RDN
    _ir(30106, max(0, s.ms_pressure * 0.012), 0, 2.0)  # PT_203_SB
    _ir(30107, s.deaer_pressure, 0, 2.0)  # PT_001_DEAER
    _ir(30108, s.pt_fw_pump_out, 0, 70.0)
    _ir(30109, s.pt_fw_pump_in, 0, 5.0)
    _ir(30110, s.pt_aerofoil_dp, 0, 1.0)
    _ir(30111, s.pt_sa_windbox, 0, 500.0)
    _ir(30112, s.pt_pa_windbox, 0, 500.0)
    _ir(30113, s.pt_spray_line, 0, 60.0)
    _ir(30114, s.pt_lcv_upstrm, 0, 60.0)

    # ── EXTENDED INPUT REGISTERS — LEVEL (30160–30162) ────────────────
    _ir(30160, s.fwst_level + 1.5, 0, 100)  # LT_FWST_2 redundant
    _ir(30161, s.lt_bfp_seal, 0, 100)
    _ir(30162, s.drum_level_avg, 0, 100)  # LT_DRUM_COMP

    # ── EXTENDED INPUT REGISTERS — FLOW (30204–30208) ─────────────────
    _ir(30204, s.fw_flow + 0.1, 0, 50)  # FT_FW_AEROFOIL
    _ir(30205, s.ft_sb_steam, 0, 5)
    _ir(30206, s.ft_spray_flow, 0, 5)
    _ir(30207, s.ft_fw_8hr, 0, 999999.9, 0, 65535)
    _ir(30208, s.ft_ms_8hr, 0, 999999.9, 0, 65535)

    # ── EXTENDED INPUT REGISTERS — DRAUGHT (30251–30257) ──────────────
    _ir(30251, s.furn_draught + 0.3, -30, 30)  # DT_FURN_DFT2
    _ir(30252, s.dt_aph_dp, 0, 100)
    _ir(30253, s.dt_esp_dp, 0, 50)
    _ir(30254, s.dt_eco_dp, 0, 80)
    _ir(30255, s.dt_idfa_inlet, -200, 0)
    _ir(30256, s.dt_fdfa_out, 0, 300)
    _ir(30257, s.dt_boiler_back, -30, 30)

    # ── EXTENDED INPUT REGISTERS — VFD FEEDBACK (30310–30319) ─────────
    _ir(30310, min(100, s.id_fan_rpm / 15.0 * 100), 0, 100)  # VFD_IDFA_FB
    _ir(30311, min(100, s.fd_fan_rpm / 15.0 * 100), 0, 100)  # VFD_FDFA_FB
    _ir(30312, 0.0, 0, 100)  # VFD_SA_FB (SA off)
    _ir(30313, min(100, s.tg_rpm / 15.0 * 100), 0, 100)  # VFD_TG_FB
    _ir(30314, min(60, s.id_fan_rpm / 1500.0 * 50), 0, 60)  # VFD_IDFA_HZ
    _ir(30315, min(60, s.fd_fan_rpm / 1500.0 * 50), 0, 60)  # VFD_FDFA_HZ
    _ir(30316, 0.0, 0, 60)  # VFD_SA_HZ
    _ir(30317, 0.0, 0, 999)  # VFD_IDFA_FAULT (no fault)
    _ir(30318, 0.0, 0, 999)  # VFD_FDFA_FAULT
    _ir(30319, min(200, s.tg_amp / 3.0 * 100), 0, 200)  # VFD_TG_TORQUE

    # ── EXTENDED INPUT REGISTERS — MOTOR CURRENT (30356–30369) ────────
    _ir(30356, s.sf3_amp, 0, 20)
    _ir(30357, s.pf3_rpm * 0.01, 0, 15)  # GM_PF3_AMP
    _ir(30358, s.sa_fan_amp_ext, 0, 50)
    _ir(30359, s.tg_amp, 0, 10)
    _ir(30360, s.sac_amp, 0, 20)
    _ir(30361, s.bfp1_amp, 0, 90)
    _ir(30362, s.bfp2_amp, 0, 90)
    _ir(30363, s.lpdp1_amp, 0, 5)
    _ir(30364, s.lpdp2_amp, 0, 5)
    _ir(30365, s.hpdp1_amp, 0, 5)
    _ir(30366, s.hpdp2_amp, 0, 5)
    _ir(30367, s.lp_agi_amp, 0, 5)
    _ir(30368, s.hp_agi_amp, 0, 5)
    _ir(30369, s.drm_fdr_amp, 0, 30)

    # ── EXTENDED INPUT REGISTERS — MOTOR RPM (30370–30385) ────────────
    _ir(30370, s.drm_fdr_rpm, 0, 1500)
    _ir(30371, s.sf1_rpm, 0, 50)  # GM_M301_RPM (mirror)
    _ir(30372, s.sf2_rpm, 0, 50)
    _ir(30373, s.sf3_rpm, 0, 50)
    _ir(30374, s.tg_rpm, 0, 15)  # GM_M304_RPM
    _ir(30375, s.id_fan_rpm, 0, 1500)  # GM_M305_RPM
    _ir(30376, s.sa_fan_rpm, 0, 1500)  # GM_M306_RPM
    _ir(30377, s.fd_fan_rpm, 0, 1500)  # GM_M307_RPM
    _ir(30378, s.pf1_rpm * 5, 0, 1500)  # GM_M401_RPM
    _ir(30379, s.pf1_rpm, 0, 1500)  # GM_M402_RPM
    _ir(30380, s.pf2_rpm, 0, 1500)  # GM_M403_RPM
    _ir(30381, 0.0, 0, 1500)  # GM_M404_RPM
    _ir(30382, s.gm405_rpm, 0, 1500)  # GM_M405_RPM
    _ir(30383, 0.0, 0, 1500)  # GM_M406_RPM
    _ir(30384, 0.0, 0, 1500)  # GM_M407_RPM
    _ir(30385, 0.0, 0, 1500)  # GM_M408_RPM

    # ── EXTENDED INPUT REGISTERS — CONTROL VALVE FEEDBACK (30400–30405)
    _ir(30400, s.fcv_fw, 0, 100)  # FCV_FW_FB
    _ir(30401, s.tcv_temp, 0, 100)  # TCV_TEMP_FB
    _ir(30402, s.lcv_drum, 0, 100)  # LCV_DRUM_FB
    _ir(30403, s.pcv_ms, 0, 100)  # PCV_MS_FB
    _ir(30404, 0.0, 0, 100)  # PRV_MS_FB
    _ir(30405, 0.0, 0, 100)  # SUV_DRUM_FB

    # ── EXTENDED INPUT REGISTERS — ESP (30453–30468) ──────────────────
    _ir(30453, s.trcc1_curr, 0, 2000)
    _ir(30454, s.trcc2_curr, 0, 2000)
    _ir(30455, s.trcc3_curr, 0, 2000)
    _ir(30456, s.trcc1_pri_volt, 0, 480)
    _ir(30457, s.trcc2_pri_volt, 0, 480)
    _ir(30458, s.trcc3_pri_volt, 0, 480)
    _ir(30459, s.esp_derm1, 0, 100)
    _ir(30460, s.esp_derm2, 0, 100)
    _ir(30461, s.esp_derm3, 0, 100)
    _ir(30462, s.esp_cerm1, 0, 100)
    _ir(30463, s.esp_cerm2, 0, 100)
    _ir(30464, s.esp_cerm3, 0, 100)
    _ir(30465, s.esp_inshtr1, 0, 200)
    _ir(30466, s.esp_inshtr2, 0, 200)
    _ir(30467, s.esp_inshtr3, 0, 200)
    _ir(30468, 1.0, 0, 1)  # ESP_PAF_FLAG

    # ── EXTENDED INPUT REGISTERS — PERFORMANCE (30500–30511) ──────────
    _ir(30500, s.boiler_eff, 0, 100)
    _ir(30501, s.steam_quality, 0, 100)
    _ir(30502, s.heat_rate, 0, 5000)
    _ir(30503, s.spec_steam, 0, 10)
    _ir(30504, s.evap_ratio, 0, 10)
    _ir(30505, s.excess_air, 0, 100)
    _ir(30506, s.co2_loss, 0, 20)
    _ir(30507, s.unburn_loss, 0, 20)
    _ir(30508, s.rad_loss, 0, 5)
    _ir(30509, s.sh_enthalpy, 0, 900)
    _ir(30510, s.fuel_rate, 0, 10000)
    _ir(30511, s.steam_load_pct, 0, 100)

    # ── EXTENDED INPUT REGISTERS — SOOT BLOWER SEQ (30550) ────────────
    sb_active = any(s.mrsb_run)
    sb_step = (s.mrsb_run.index(True) + 1) if sb_active else 0
    _ir(30550, float(sb_step), 0, 10)

    # ── EXTENDED INPUT REGISTERS — SYSTEM STATUS (30560–30573) ────────
    _ir(30560, s.oper_mode, 0, 5)
    _ir(30561, s.steam_load_pct, 0, 100)
    _ir(30562, s.uptime_hr, 0, 9999)
    _ir(30563, s.total_run_hr, 0, 99999)
    _ir(30564, s.start_cnt, 0, 9999)
    _ir(30565, s.trip_cnt, 0, 999)
    _ir(30566, s.last_trip, 0, 30)
    _ir(30567, s.fw_flow, 0, 50)  # PID_FW_PV
    _ir(30568, s.drum_level_avg, 0, 100)  # PID_DRM_PV
    _ir(30569, s.ms_pressure, 0, 60)  # PID_PRES_PV
    _ir(30570, s.ms_temp, 0, 500)  # PID_TEMP_PV
    _ir(30571, s.furn_draught, -30, 30)  # PID_DFT_PV
    _ir(30572, s.fw_flow - s.sp_fw_flow, -50, 50)  # PID_FW_ERR
    _ir(30573, s.drum_level_avg - s.sp_drum_level, -50, 50)  # PID_DRM_ERR

    # ── EXTENDED INPUT REGISTERS — DOSING (30580–30583) ───────────────
    _ir(30580, s.dos_lp_rate, 0, 100)
    _ir(30581, s.dos_hp_rate, 0, 50)
    _ir(30582, s.dos_lp_tank, 0, 100)
    _ir(30583, s.dos_hp_tank, 0, 100)

    # ── EXTENDED INPUT REGISTERS — UTILITIES (30590–30593) ────────────
    _ir(30590, s.util_inst_air, 0, 10)
    _ir(30591, s.util_cw_press, 0, 5)
    _ir(30592, s.util_cw_in, 0, 60)
    _ir(30593, s.util_cw_out, 0, 60)

    # ── EXTENDED INPUT REGISTERS — VIBRATION/BEARING (30600–30610) ────
    _ir(30600, s.vib_idfa_de, 0, 25)
    _ir(30601, s.vib_idfa_nde, 0, 25)
    _ir(30602, s.vib_fdfa_de, 0, 25)
    _ir(30603, s.vib_fdfa_nde, 0, 25)
    _ir(30604, s.vib_bfp1_de, 0, 25)
    _ir(30605, s.vib_bfp2_de, 0, 25)
    _ir(30606, s.temp_idfa_brg, 0, 120)
    _ir(30607, s.temp_fdfa_brg, 0, 120)
    _ir(30608, s.temp_bfp1_brg, 0, 100)
    _ir(30609, s.temp_bfp2_brg, 0, 100)
    _ir(30610, s.temp_sa_brg, 0, 100)

    # ── EXTENDED INPUT REGISTERS — ENERGY (30620–30629) ───────────────
    _ir(30620, s.pwr_idfa_kw, 0, 200)
    _ir(30621, s.pwr_fdfa_kw, 0, 200)
    _ir(30622, s.pwr_sa_kw, 0, 100)
    _ir(30623, s.pwr_bfp1_kw, 0, 100)
    _ir(30624, s.pwr_bfp2_kw, 0, 100)
    _ir(30625, s.pwr_total_kw, 0, 1000)
    _ir(30626, s.pwr_total_kwh, 0, 999999.9, 0, 65535)
    _ir(30627, s.pwr_pf, 0, 1)
    _ir(30628, s.pwr_bus_volt, 0, 480)
    _ir(30629, s.pwr_bus_freq, 45, 55)

    # ── EXTENDED HOLDING REGISTERS — VFD SETPOINTS (40100–40109) ──────
    _hr(40100, s.vfd_idfa_sp, 0, 100)
    _hr(40101, s.vfd_fdfa_sp, 0, 100)
    _hr(40102, s.vfd_sa_sp, 0, 100)
    _hr(40103, s.vfd_tg_sp, 0, 100)
    _hr(40104, s.vfd_sf1_sp, 0, 100)
    _hr(40105, s.vfd_sf2_sp, 0, 100)
    _hr(40106, s.vfd_sf3_sp, 0, 100)
    _hr(40107, s.vfd_pf1_sp, 0, 100)
    _hr(40108, s.vfd_pf2_sp, 0, 100)
    _hr(40109, s.vfd_pf3_sp, 0, 100)

    # ── EXTENDED HOLDING REGISTERS — PID OUTPUTS (40200–40205) ────────
    _hr(40200, s.pid_fw_out, 0, 100)
    _hr(40201, s.pid_drm_out, 0, 100)
    _hr(40202, s.pid_pres_out, 0, 100)
    _hr(40203, s.pid_temp_out, 0, 100)
    _hr(40204, s.pid_dft_out, 0, 100)
    _hr(40205, s.pid_fd_out, 0, 100)

    # ── EXTENDED HOLDING REGISTERS — SETPOINTS (40504–40515) ──────────
    _hr(40504, s.sp_idfa_man, 0, 100)
    _hr(40505, s.sp_fdfa_man, 0, 100)
    _hr(40506, s.sp_sa_man, 0, 100)
    _hr(40507, s.sp_tg_man, 0, 100)
    _hr(40508, s.sp_sf1_man, 0, 100)
    _hr(40509, s.sp_sf2_man, 0, 100)
    _hr(40510, s.sp_sf3_man, 0, 100)
    _hr(40511, s.sp_pf1_man, 0, 100)
    _hr(40512, s.sp_pf2_man, 0, 100)
    _hr(40513, s.sp_pf3_man, 0, 100)
    _hr(40514, s.sp_deaer_lvl, 0, 100)
    _hr(40515, s.sp_fw_flow, 0, 50)

    # ── EXTENDED COILS — MOTOR RUN (00030–00054) ──────────────────────
    _coil(30, s.m301_sf1_run)
    _coil(31, s.m302_sf2_run)
    _coil(32, s.m303_sf3_run)
    _coil(33, s.m304_tg_run)
    _coil(34, s.m305_idfa_run)
    _coil(35, s.m306_sa_run)
    _coil(36, s.m307_fdfa_run)
    _coil(37, s.m401_run)
    _coil(38, s.m402_run)
    _coil(39, s.m403_run)
    _coil(40, s.m404_run)
    _coil(41, s.m405_pa_run)
    _coil(42, s.m406_pa_run)
    _coil(43, s.m407_run)
    _coil(44, s.m408_run)
    _coil(45, s.m210_lpdp_run)
    _coil(46, s.m212_lpdp_run)
    _coil(47, s.m501_hpdp_run)
    _coil(48, s.m502_hpdp_run)
    _coil(49, s.m213_lp_agi_run)
    _coil(50, s.m214_hp_agi_run)
    _coil(51, s.m215_pf2_run)
    _coil(52, s.m216_run)
    _coil(53, s.m218_run)
    _coil(54, s.m219_run)

    # ── EXTENDED COILS — FAULTS (00060–00085) ─────────────────────────
    for i in range(26):
        _coil(60 + i, s.faults[i])

    # ── EXTENDED COILS — INTERLOCKS (00107–00121) ─────────────────────
    _coil(107, s.intlk_temp_hh)
    _coil(108, s.intlk_draught_ll)
    _coil(109, s.intlk_bfp_fail)
    _coil(110, s.intlk_idfa_fail)
    _coil(111, s.intlk_fdfa_fail)
    _coil(112, s.intlk_bed_hh)
    _coil(113, s.intlk_fw_flow_ll)
    _coil(114, s.intlk_deaer_ll)
    _coil(115, s.intlk_fuel_ll)
    _coil(116, False)  # INTLK_EMGCY (operator command)
    _coil(117, False)  # INTLK_FAULT_ACK
    _coil(118, False)  # INTLK_BYPASS_1
    _coil(119, False)  # INTLK_BYPASS_2
    _coil(120, False)  # INTLK_MASTER_RST
    _coil(121, s.intlk_boil_trip)

    # ── EXTENDED COILS — COMMANDS (00200–00231) ───────────────────────
    # Commands are operator-driven (R/W). Initialize to False.
    for addr in range(200, 232):
        _coil(addr, False)

    # ── DISCRETE INPUTS — ALARMS (10001–10042) ────────────────────────
    _di(10001, s.ms_temp > 280.0)  # ALM_MS_TEMP_HH
    _di(10002, s.ms_temp > 260.0)  # ALM_MS_TEMP_H
    _di(10003, s.ms_temp < 200.0)  # ALM_MS_TEMP_L
    _di(10004, s.ms_pressure > 52.0)  # ALM_MS_PRES_HH
    _di(10005, s.ms_pressure > 48.0)  # ALM_MS_PRES_H
    _di(10006, s.ms_pressure < 35.0)  # ALM_MS_PRES_L
    _di(10007, s.drum_level_avg < 15.0)  # ALM_DRUM_LL
    _di(10008, s.drum_level_avg < 25.0)  # ALM_DRUM_L
    _di(10009, s.drum_level_avg > 75.0)  # ALM_DRUM_H
    _di(10010, s.drum_level_avg > 85.0)  # ALM_DRUM_HH
    _di(10011, s.furn_draught > 5.0)  # ALM_DFT_HH
    _di(10012, s.furn_draught < -25.0)  # ALM_DFT_LL
    _di(10013, s.fw_flow < 15.0)  # ALM_FW_FLOW_L
    _di(10014, s.fw_flow < 5.0)  # ALM_FW_FLOW_LL
    _di(10015, s.deaer_level < 30.0)  # ALM_DEAER_LVL_L
    _di(10016, s.deaer_level > 90.0)  # ALM_DEAER_LVL_H
    _di(10017, s.deaer_pressure > 1.5)  # ALM_DEAER_PRES_H
    _di(10018, s.fuel_level < 15.0)  # ALM_FUEL_BIN_L
    _di(10019, s.fuel_level < 8.0)  # ALM_FUEL_BIN_LL
    _di(10020, s.fwst_level < 30.0)  # ALM_FWST_L
    _di(10021, s.fwst_level < 15.0)  # ALM_FWST_LL
    _di(10022, s.te_ssh_out > 280.0)  # ALM_SSH_TEMP_HH
    _di(10023, s.te_psh_out > 270.0)  # ALM_PSH_TEMP_HH
    _di(10024, s.te_eco_out > 200.0)  # ALM_ECO_GAS_HH
    _di(10025, s.te_aph_out > 160.0)  # ALM_APH_GAS_H
    _di(10026, s.bed_temp_1 > 350.0)  # ALM_BED_TEMP_HH
    _di(10027, s.bed_temp_1 < 100.0)  # ALM_BED_TEMP_LL
    _di(10028, s.trcc1_volt < 20.0)  # ALM_ESP_VOLT_L
    _di(10029, abs(s.drum_level_1 - s.drum_level_2) > 10.0)  # ALM_DRUM_LVL_DEV
    _di(10030, False)  # ALM_VFD_IDFA_FLT
    _di(10031, False)  # ALM_VFD_FDFA_FLT
    _di(10032, not s.bfp1_run and not s.bfp2_run)  # ALM_ALL_BFP_FAIL
    _di(10033, s.id_fan_rpm < 10.0)  # ALM_IDFA_FAIL
    _di(10034, s.fd_fan_rpm < 5.0)  # ALM_FDFA_FAIL
    _di(10035, False)  # ALM_SB_TIMEOUT
    _di(10036, False)  # ALM_PRV_OPEN
    _di(10037, False)  # ALM_SAC_FAULT
    _di(10038, s.util_inst_air < 4.0)  # ALM_INST_AIR_L
    _di(10039, False)  # ALM_BFP_DPS_FAIL
    _di(10040, s.furn_draught > 5.0)  # ALM_DT401_HH
    _di(10041, s.furn_draught < -25.0)  # ALM_DT401_LL
    _di(10042, s.te_fg_esp_in > 180.0)  # ALM_TE101_HH

    # ── DISCRETE INPUTS — SOOT BLOWER HOME (10050–10057) ──────────────
    for i in range(7):
        _di(10050 + i, not s.mrsb_run[i])  # Home when not running
    _di(10057, sb_active)  # SB_SEQ_ACTIVE

    # ── DISCRETE INPUTS — UTILITY STATUS (10060–10064) ────────────────
    _di(10060, s.bfp1_run)  # DPS_BFP1_OK
    _di(10061, s.bfp2_run)  # DPS_BFP2_OK
    _di(10062, s.util_cw_press > 1.0)  # CW_PR_SW_OK
    _di(10063, s.util_inst_air > 4.0)  # INST_AIR_SW_OK
    _di(10064, True)  # PAF_STATUS
