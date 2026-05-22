import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type {
  Alarm,
  Plant,
  TelemetryLatest,
  UserContext,
  WsMessage,
  WsSnapshot,
  WsTelemetryUpdate,
  WsAlarmEvent,
  WsAlarmAck,
  WsAlarmsClear,
} from '../types';

// ── Auth Slice ──────────────────────────────────────────────────────────

interface AuthSlice {
  user: UserContext | null;
  isAuthenticated: boolean;
  setUser: (user: UserContext | null) => void;
  logout: () => void;
}

// ── Plant Slice ─────────────────────────────────────────────────────────

interface PlantSlice {
  plants: Plant[];
  selectedPlantId: string | null;
  setPlants: (plants: Plant[]) => void;
  selectPlant: (plantId: string) => void;
}

// ── Telemetry Slice ─────────────────────────────────────────────────────

interface TelemetrySlice {
  latestValues: Record<string, TelemetryLatest>;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  setConnectionStatus: (status: TelemetrySlice['connectionStatus']) => void;
  handleWsMessage: (msg: WsMessage) => void;
  clearTelemetry: () => void;
}

// ── Alarm Slice ─────────────────────────────────────────────────────────

interface AlarmSlice {
  activeAlarms: Alarm[];
  alarmCount: number;
  criticalCount: number;
  setAlarms: (alarms: Alarm[]) => void;
  addAlarm: (alarm: Alarm) => void;
  acknowledgeAlarm: (alarmId: string, ackedBy: string) => void;
  clearAlarms: (alarmIds?: string[]) => void;
}

// ── UI Slice ────────────────────────────────────────────────────────────

interface UiSlice {
  sidebarOpen: boolean;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

// ── Combined Store ──────────────────────────────────────────────────────

export type AppStore = AuthSlice & PlantSlice & TelemetrySlice & AlarmSlice & UiSlice;

export const useAppStore = create<AppStore>()(
  subscribeWithSelector((set) => ({
    // ── Auth ────────────────────────────────────────────────
    user: null,
    isAuthenticated: false,
    setUser: (user) => set({ user, isAuthenticated: !!user }),
    logout: () => set({ user: null, isAuthenticated: false }),

    // ── Plants ──────────────────────────────────────────────
    plants: [],
    selectedPlantId: null,
    setPlants: (plants) => set({ plants }),
    selectPlant: (plantId) => set({ selectedPlantId: plantId }),

    // ── Telemetry ───────────────────────────────────────────
    latestValues: {},
    connectionStatus: 'disconnected',
    setConnectionStatus: (status) => set({ connectionStatus: status }),
    handleWsMessage: (msg: WsMessage) => {
      switch (msg.type) {
        case 'snapshot': {
          const snap = msg as WsSnapshot;
          const newValues: Record<string, TelemetryLatest> = {};
          for (const [tagName, val] of Object.entries(snap.data)) {
            newValues[tagName] = {
              tag_name: tagName,
              value: val.v,
              quality: val.q,
              ts: val.t,
              unit: val.u,
            };
          }
          set({ latestValues: newValues });
          break;
        }
        case 'telemetry': {
          const update = msg as WsTelemetryUpdate;
          set((state) => {
            const merged = { ...state.latestValues };
            for (const [tagName, val] of Object.entries(update.data)) {
              merged[tagName] = {
                tag_name: tagName,
                value: val.v,
                quality: val.q,
                ts: val.t,
                unit: val.u,
              };
            }
            return { latestValues: merged };
          });
          break;
        }
        case 'alarm': {
          const alarmEvt = msg as WsAlarmEvent;
          const newAlarm: Alarm = {
            alarm_id: alarmEvt.alarm_id,
            plant_id: alarmEvt.plant_id,
            tag_name: alarmEvt.tag_name,
            severity: alarmEvt.severity,
            message: alarmEvt.message,
            trigger_value: alarmEvt.trigger_value,
            occurred_at: new Date().toISOString(),
            alarm_state: 'ACTIVE',
            acked_by: null,
            acked_at: null,
          };
          set((state) => ({
            activeAlarms: [newAlarm, ...state.activeAlarms],
            alarmCount: state.alarmCount + 1,
            criticalCount:
              alarmEvt.severity === 'CRITICAL'
                ? state.criticalCount + 1
                : state.criticalCount,
          }));
          break;
        }
        case 'alarm_ack': {
          const ack = msg as WsAlarmAck;
          set((state) => ({
            activeAlarms: state.activeAlarms.map((a) =>
              a.alarm_id === ack.alarm_id
                ? { ...a, alarm_state: 'ACKNOWLEDGED' as const, acked_by: ack.acked_by, acked_at: new Date().toISOString() }
                : a
            ),
          }));
          break;
        }
        case 'alarms_cleared': {
          const cleared = msg as WsAlarmsClear;
          set((state) => ({
            activeAlarms: state.activeAlarms.filter(
              (a) => !(a.plant_id === cleared.plant_id && a.alarm_state === 'ACKNOWLEDGED')
            ),
          }));
          break;
        }
      }
    },
    clearTelemetry: () => set({ latestValues: {} }),

    // ── Alarms ──────────────────────────────────────────────
    activeAlarms: [],
    alarmCount: 0,
    criticalCount: 0,
    setAlarms: (alarms) =>
      set({
        activeAlarms: alarms,
        alarmCount: alarms.length,
        criticalCount: alarms.filter((a) => a.severity === 'CRITICAL').length,
      }),
    addAlarm: (alarm) =>
      set((state) => ({
        activeAlarms: [alarm, ...state.activeAlarms],
        alarmCount: state.alarmCount + 1,
        criticalCount:
          alarm.severity === 'CRITICAL'
            ? state.criticalCount + 1
            : state.criticalCount,
      })),
    acknowledgeAlarm: (alarmId, ackedBy) =>
      set((state) => ({
        activeAlarms: state.activeAlarms.map((a) =>
          a.alarm_id === alarmId
            ? { ...a, alarm_state: 'ACKNOWLEDGED' as const, acked_by: ackedBy, acked_at: new Date().toISOString() }
            : a
        ),
      })),
    clearAlarms: (alarmIds) =>
      set((state) => {
        const cleared = alarmIds
          ? state.activeAlarms.filter((a) => !alarmIds.includes(a.alarm_id))
          : state.activeAlarms.filter((a) => a.alarm_state !== 'ACKNOWLEDGED');
        return {
          activeAlarms: cleared,
          alarmCount: cleared.length,
          criticalCount: cleared.filter((a) => a.severity === 'CRITICAL').length,
        };
      }),

    // ── UI ───────────────────────────────────────────────────
    sidebarOpen: true,
    sidebarCollapsed: false,
    toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
    setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
  }))
);
