// ── Telemetry Types ─────────────────────────────────────────────────────

export type TagQuality = 'GOOD' | 'BAD' | 'UNCERTAIN' | 'STALE';

export interface TagMetadata {
  tag_name: string;
  description: string | null;
  engineering_unit: string | null;
  opc_node_id: string | null;
  data_type: string | null;
  low_low_limit: number | null;
  low_limit: number | null;
  high_limit: number | null;
  high_high_limit: number | null;
  deadband: number | null;
  is_active: boolean;
  updated_at: string | null;
}

export interface TelemetryLatest {
  tag_name: string;
  value: number;
  quality: TagQuality;
  ts: string;
  unit: string | null;
}

export interface TelemetryHistoryPoint {
  ts: string;
  value: number | null;
  quality?: TagQuality;
  sample_count?: number;
}

// ── Alarm Types ─────────────────────────────────────────────────────────

export type AlarmSeverity = 'INFO' | 'WARNING' | 'ALARM' | 'CRITICAL';
export type AlarmState = 'ACTIVE' | 'ACKNOWLEDGED' | 'CLEARED';

export interface Alarm {
  alarm_id: string;
  plant_id: string;
  tag_name: string;
  severity: AlarmSeverity;
  message: string;
  trigger_value: number;
  occurred_at: string;
  alarm_state: AlarmState;
  acked_by: string | null;
  acked_at: string | null;
}

// ── Plant Types ─────────────────────────────────────────────────────────

export interface Plant {
  plant_id: string;
  name: string;
  location: string | null;
  plant_type: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
}

export interface PlantSummary {
  plant_id: string;
  active_tags: number;
  active_alarms: number;
  critical_alarms: number;
  ts: string;
}

// ── User / Auth Types ───────────────────────────────────────────────────

export type UserRole = 'viewer' | 'operator' | 'engineer' | 'admin' | 'edge_agent';

export interface UserContext {
  tenant_id: string;
  user_id: string;
  email: string;
  role: UserRole;
  plant_ids: string[];
  is_edge: boolean;
}

// ── WebSocket Message Types ─────────────────────────────────────────────

export interface WsTelemetryUpdate {
  type: 'telemetry';
  plant_id: string;
  data: Record<string, { v: number; q: TagQuality; u: string | null; t: string }>;
}

export interface WsSnapshot {
  type: 'snapshot';
  plant_id: string;
  count: number;
  data: Record<string, { v: number; q: TagQuality; u: string | null; t: string }>;
}

export interface WsAlarmEvent {
  type: 'alarm';
  alarm_id: string;
  plant_id: string;
  tag_name: string;
  severity: AlarmSeverity;
  message: string;
  trigger_value: number;
}

export interface WsAlarmAck {
  type: 'alarm_ack';
  alarm_id: string;
  plant_id: string;
  acked_by: string;
}

export interface WsAlarmsClear {
  type: 'alarms_cleared';
  plant_id: string;
  count: number;
  cleared_by: string;
}

export type WsMessage =
  | WsTelemetryUpdate
  | WsSnapshot
  | WsAlarmEvent
  | WsAlarmAck
  | WsAlarmsClear;

// ── API Response Envelopes ──────────────────────────────────────────────

export interface ApiListResponse<T> {
  count: number;
  data?: T[];
  plants?: T[];
  tags?: T[];
  alarms?: T[];
}

export interface ApiResponse<T> {
  ok: boolean;
  data?: T;
}
