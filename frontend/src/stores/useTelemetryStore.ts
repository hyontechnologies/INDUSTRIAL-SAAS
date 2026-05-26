import { create } from 'zustand';
import { TelemetryPoint, TelemetryFrame } from '../types/telemetry';

interface TelemetryState {
  latestValues: Record<string, TelemetryPoint>;
  staleThresholdMs: number;

  updateTelemetry: (frame: TelemetryFrame) => void;
  getTagValue: (tagName: string) => TelemetryPoint | undefined;
  checkStaleValues: () => void;
}

export const useTelemetryStore = create<TelemetryState>((set, get) => ({
  latestValues: {},
  staleThresholdMs: 15000, // 15 seconds

  updateTelemetry: (frame) => {
    set((state) => {
      const next = { ...state.latestValues };
      for (const [tag, data] of Object.entries(frame.data)) {
        next[tag] = {
          value: data.v,
          quality: data.q,
          timestamp: data.t || frame.timestamp,
        };
      }
      return { latestValues: next };
    });
  },

  getTagValue: (tagName) => get().latestValues[tagName],

  checkStaleValues: () => {
    const now = Date.now();
    const threshold = get().staleThresholdMs;
    let changed = false;

    set((state) => {
      const next = { ...state.latestValues };
      for (const [tag, data] of Object.entries(next)) {
        if (data.quality !== 'STALE' && now - new Date(data.timestamp).getTime() > threshold) {
          next[tag] = { ...data, quality: 'STALE' };
          changed = true;
        }
      }
      return changed ? { latestValues: next } : state;
    });
  },
}));
