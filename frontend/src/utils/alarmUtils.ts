import { AlarmSeverity, Alarm } from '../types/alarm';
import { ALARM_PRIORITY, ALARM_COLORS } from '../constants/alarmSeverity';

export function getAlarmColorClass(severity: AlarmSeverity): string {
  const colorName = ALARM_COLORS[severity];
  return `bg-${colorName}-100 text-${colorName}-600 border-${colorName}-200`;
}

export function getAlarmPriority(severity: AlarmSeverity): number {
  return ALARM_PRIORITY[severity] || 99;
}

export function isAlarmCritical(alarm: Alarm): boolean {
  return alarm.severity === 'CRITICAL';
}

export function sortAlarmsByPriority(alarms: Alarm[]): Alarm[] {
  return [...alarms].sort((a, b) => {
    // 1. Sort by ACTIVE vs non-active first
    if (a.alarm_state === 'ACTIVE' && b.alarm_state !== 'ACTIVE') return -1;
    if (a.alarm_state !== 'ACTIVE' && b.alarm_state === 'ACTIVE') return 1;

    // 2. Sort by severity
    const diff = getAlarmPriority(a.severity) - getAlarmPriority(b.severity);
    if (diff !== 0) return diff;

    // 3. Sort by time (newest first)
    return new Date(b.occurred_at).getTime() - new Date(a.occurred_at).getTime();
  });
}
