import React from 'react';

import { useAlarmStore } from '../../stores/useAlarmStore';
import { formatTimeOnly } from '../../utils/formatters';

export const RealtimeStatusStrip: React.FC = () => {
  const activeCount = useAlarmStore(state => state.getActiveCount());

  return (
    <div className={`h-6 w-full flex items-center px-4 text-[10px] font-semibold tracking-wider text-white bg-slate-800`}>
      <div className="flex items-center gap-2 flex-1">
        <span className={`h-1.5 w-1.5 rounded-full bg-emerald-500`} />
        <span>HTTP Polling Active</span>
      </div>

      {activeCount > 0 && (
        <div className="flex items-center gap-1.5 text-rose-300">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-rose-500"></span>
          </span>
          <span>{activeCount} ACTIVE ALARMS</span>
        </div>
      )}
    </div>
  );
};
