export type AlarmSeverity = 'INFO' | 'WARNING' | 'ALARM' | 'CRITICAL';
export type AlarmState = 'ACTIVE' | 'ACKNOWLEDGED' | 'CLEARED';

export interface Alarm {
  alarm_id: string;
  tag_name: string;
  severity: AlarmSeverity;
  alarm_state: AlarmState;
  message: string;
  trigger_value: number;
  occurred_at: string;
  acked_by?: string | null;
  acked_at?: string | null;
}

export interface AlarmEvent {
  type: 'alarm';
  timestamp: string;
  data: Omit<Alarm, 'acked_by' | 'acked_at'>;
}
