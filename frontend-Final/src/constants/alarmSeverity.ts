import { AlarmSeverity } from '../types/alarm';

export const ALARM_PRIORITY: Record<AlarmSeverity, number> = {
  CRITICAL: 1,
  ALARM: 2,
  WARNING: 3,
  INFO: 4,
};

export const ALARM_COLORS: Record<AlarmSeverity, string> = {
  CRITICAL: 'rose',
  ALARM: 'amber',
  WARNING: 'amber', // Can be differentiated later
  INFO: 'sky',
};
