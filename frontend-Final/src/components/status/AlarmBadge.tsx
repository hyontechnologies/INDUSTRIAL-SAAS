import React from 'react';
import { AlarmSeverity } from '../../types/alarm';
import { getAlarmColorClass } from '../../utils/alarmUtils';

export const AlarmBadge: React.FC<{ severity: AlarmSeverity; count?: number; pulse?: boolean }> = ({ severity, count, pulse }) => {
  const colorClass = getAlarmColorClass(severity);
  const shouldPulse = pulse ?? severity === 'CRITICAL';

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold border ${colorClass}`}>
      {shouldPulse && (
        <span className="relative flex h-2 w-2">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-current`}></span>
          <span className={`relative inline-flex rounded-full h-2 w-2 bg-current`}></span>
        </span>
      )}
      {!shouldPulse && <span className="h-2 w-2 rounded-full bg-current" />}

      {count !== undefined ? `${count} ${severity}` : severity}
    </span>
  );
};
