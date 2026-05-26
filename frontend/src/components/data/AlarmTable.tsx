import React from 'react';
import { useAlarmStore } from '../../stores/useAlarmStore';
import { AlarmBadge } from '../status/AlarmBadge';
import { formatTimestamp, formatDuration } from '../../utils/formatters';
import { CheckCircle2, ShieldAlert } from 'lucide-react';
import { PermissionGate } from '../guards/PermissionGate';

export const AlarmTable: React.FC = () => {
  const alarms = useAlarmStore(state => state.activeAlarms);
  const [now, setNow] = React.useState(() => Date.now());

  React.useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10000);
    return () => clearInterval(timer);
  }, []);

  if (alarms.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-400 bg-white rounded-xl border border-slate-200">
        <ShieldAlert className="w-12 h-12 mb-3 text-emerald-400" />
        <p className="font-medium text-slate-600">No active alarms</p>
        <p className="text-sm">All systems operating within normal parameters.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden w-full">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <th className="p-3">State</th>
              <th className="p-3">Severity</th>
              <th className="p-3">Tag</th>
              <th className="p-3">Message</th>
              <th className="p-3">Value</th>
              <th className="p-3">Time</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {alarms.map((alarm) => (
              <tr key={alarm.alarm_id} className={`hover:bg-slate-50/50 transition-colors ${alarm.alarm_state === 'ACTIVE' ? 'bg-rose-50/20' : ''}`}>
                <td className="p-3">
                  {alarm.alarm_state === 'ACTIVE' ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold text-rose-600">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                      </span>
                      ACTIVE
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-600">
                      <CheckCircle2 className="w-3 h-3" />
                      ACKED
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <AlarmBadge severity={alarm.severity} pulse={false} />
                </td>
                <td className="p-3">
                  <span className="font-mono text-sm text-slate-700 font-medium">{alarm.tag_name}</span>
                </td>
                <td className="p-3">
                  <span className="text-sm text-slate-600">{alarm.message}</span>
                </td>
                <td className="p-3">
                  <span className="font-mono text-sm font-medium">{alarm.trigger_value}</span>
                </td>
                <td className="p-3">
                  <div className="flex flex-col">
                    <span className="text-sm text-slate-700">{formatDuration(now - new Date(alarm.occurred_at).getTime())}</span>
                    <span className="text-[10px] text-slate-400">{formatTimestamp(alarm.occurred_at)}</span>
                  </div>
                </td>
                <td className="p-3 text-right">
                  {alarm.alarm_state === 'ACTIVE' ? (
                    <PermissionGate
                      permission="alarms:acknowledge"
                      fallback={<button disabled className="px-3 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-md cursor-not-allowed">ACK</button>}
                    >
                      <button
                        onClick={() => useAlarmStore.getState().acknowledgeAlarm(alarm.alarm_id, 'CurrentUser')}
                        className="px-3 py-1.5 bg-blue-50 text-blue-600 hover:bg-blue-100 text-xs font-bold rounded-md transition-colors"
                      >
                        ACK
                      </button>
                    </PermissionGate>
                  ) : (
                    <PermissionGate
                      permission="alarms:clear"
                      fallback={<button disabled className="px-3 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-md cursor-not-allowed">CLEAR</button>}
                    >
                      <button
                        onClick={() => useAlarmStore.getState().clearAlarm(alarm.alarm_id)}
                        className="px-3 py-1.5 bg-slate-100 text-slate-600 hover:bg-slate-200 text-xs font-medium rounded-md transition-colors"
                      >
                        CLEAR
                      </button>
                    </PermissionGate>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
