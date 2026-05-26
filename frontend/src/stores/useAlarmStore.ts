import { create } from 'zustand';
import { Alarm, AlarmEvent } from '../types/alarm';
import { sortAlarmsByPriority } from '../utils/alarmUtils';

interface AlarmState {
  activeAlarms: Alarm[];
  alarmHistory: Alarm[];

  // Actions
  addAlarm: (event: AlarmEvent) => void;
  acknowledgeAlarm: (alarmId: string, user: string) => void;
  clearAlarm: (alarmId: string) => void;
  setInitialAlarms: (alarms: Alarm[]) => void;

  // Computed
  getActiveCount: () => number;
  getCriticalCount: () => number;
}

export const useAlarmStore = create<AlarmState>((set, get) => ({
  activeAlarms: [],
  alarmHistory: [],

  addAlarm: (event) => set((state) => {
    const newAlarm: Alarm = {
      ...event.data,
      alarm_id: event.data.alarm_id || Math.random().toString(),
      alarm_state: 'ACTIVE',
      occurred_at: event.timestamp
    };

    // Check if already exists, if so update it
    const exists = state.activeAlarms.findIndex(a => a.alarm_id === newAlarm.alarm_id);
    let nextActive = [...state.activeAlarms];

    if (exists >= 0) {
      nextActive[exists] = { ...nextActive[exists], ...newAlarm };
    } else {
      nextActive = [newAlarm, ...nextActive];
    }

    return { activeAlarms: sortAlarmsByPriority(nextActive) };
  }),

  acknowledgeAlarm: (alarmId, user) => set((state) => {
    const nextActive = state.activeAlarms.map(a =>
      a.alarm_id === alarmId
        ? { ...a, alarm_state: 'ACKNOWLEDGED' as const, acked_by: user, acked_at: new Date().toISOString() }
        : a
    );
    return { activeAlarms: sortAlarmsByPriority(nextActive) };
  }),

  clearAlarm: (alarmId) => set((state) => {
    const alarm = state.activeAlarms.find(a => a.alarm_id === alarmId);
    if (!alarm) return state;

    const clearedAlarm = { ...alarm, alarm_state: 'CLEARED' as const };
    return {
      activeAlarms: state.activeAlarms.filter(a => a.alarm_id !== alarmId),
      alarmHistory: [clearedAlarm, ...state.alarmHistory].slice(0, 100) // Keep last 100
    };
  }),

  setInitialAlarms: (alarms) => set({ activeAlarms: sortAlarmsByPriority(alarms) }),

  getActiveCount: () => get().activeAlarms.filter(a => a.alarm_state === 'ACTIVE').length,
  getCriticalCount: () => get().activeAlarms.filter(a => a.severity === 'CRITICAL' && a.alarm_state === 'ACTIVE').length,
}));
