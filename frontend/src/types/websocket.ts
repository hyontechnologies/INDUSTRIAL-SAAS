import { TelemetryFrame, DataQuality } from './telemetry';
import { AlarmEvent } from './alarm';

export type ConnectionState = 'connected' | 'reconnecting' | 'failed' | 'stale' | 'disconnected' | 'connecting';

export interface SystemMessage {
  type: 'system';
  timestamp: string;
  data: {
    event: string;
    message: string;
    [key: string]: unknown;
  };
}

export interface SnapshotMessage {
  type: 'snapshot';
  plant_id: string;
  count: number;
  data: Record<string, {
    v: number;
    q: DataQuality;
    u?: string;
    t: string;
  }>;
}

export type WebSocketMessage = TelemetryFrame | AlarmEvent | SystemMessage | SnapshotMessage;
