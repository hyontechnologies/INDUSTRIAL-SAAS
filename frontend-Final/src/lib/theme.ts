export type ThemeMode = 'light' | 'dark';
export type DensityMode = 'compact' | 'comfortable' | 'spacious';
export type RoleTheme = 'operator' | 'executive' | 'maintenance' | 'admin';

export function getAlarmColorClass(severity: 'INFO' | 'WARNING' | 'ALARM' | 'CRITICAL'): string {
  switch (severity) {
    case 'CRITICAL':
      return 'bg-rose-100 text-rose-600 border-rose-200';
    case 'ALARM':
    case 'WARNING':
      return 'bg-amber-100 text-amber-600 border-amber-200';
    case 'INFO':
    default:
      return 'bg-sky-100 text-sky-600 border-sky-200';
  }
}
