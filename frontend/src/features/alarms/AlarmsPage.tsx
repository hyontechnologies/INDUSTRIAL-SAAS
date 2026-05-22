import { memo, useMemo, useState, useCallback } from 'react';
import { useAppStore } from '../../shared/stores/useAppStore';
import { fetchApi } from '../../shared/api/client';
import { cn } from '../../shared/utils/cn';
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Filter,
  AlertTriangle,
  AlertOctagon,
  Info,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import type { Alarm, AlarmSeverity, AlarmState } from '../../shared/types';

// ── Severity Badge ──────────────────────────────────────────────────────

const severityConfig: Record<AlarmSeverity, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  CRITICAL: { icon: AlertOctagon, color: 'text-red-400', bg: 'bg-red-500/15' },
  ALARM: { icon: ShieldAlert, color: 'text-orange-400', bg: 'bg-orange-500/15' },
  WARNING: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/15' },
  INFO: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/15' },
};

function SeverityBadge({ severity }: { severity: AlarmSeverity }) {
  const cfg = severityConfig[severity];
  const Icon = cfg.icon;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase', cfg.bg, cfg.color)}>
      <Icon className="w-3 h-3" />
      {severity}
    </span>
  );
}

function StateBadge({ state }: { state: AlarmState }) {
  const cfg = {
    ACTIVE: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Active' },
    ACKNOWLEDGED: { color: 'text-amber-400', bg: 'bg-amber-500/10', label: 'Acked' },
    CLEARED: { color: 'text-slate-500', bg: 'bg-slate-500/10', label: 'Cleared' },
  }[state];

  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase', cfg.bg, cfg.color)}>
      {cfg.label}
    </span>
  );
}

// ── Alarm Row ───────────────────────────────────────────────────────────

interface AlarmRowProps {
  alarm: Alarm;
  onAck: (alarmId: string) => void;
}

const AlarmRow = memo(function AlarmRow({ alarm, onAck }: AlarmRowProps) {
  return (
    <tr className={cn(
      'border-b border-slate-800/30 transition-colors',
      alarm.severity === 'CRITICAL' && alarm.alarm_state === 'ACTIVE' && 'bg-red-950/10',
      alarm.alarm_state === 'ACTIVE' ? 'hover:bg-slate-800/30' : 'hover:bg-slate-800/20 opacity-60'
    )}>
      <td className="py-3 px-4"><SeverityBadge severity={alarm.severity} /></td>
      <td className="py-3 px-4 text-sm font-mono font-medium text-slate-200">{alarm.tag_name}</td>
      <td className="py-3 px-4 text-sm text-slate-400 max-w-xs truncate">{alarm.message}</td>
      <td className="py-3 px-4 text-sm font-mono tabular-nums text-slate-300">{alarm.trigger_value.toFixed(2)}</td>
      <td className="py-3 px-4"><StateBadge state={alarm.alarm_state} /></td>
      <td className="py-3 px-4 text-xs text-slate-500">
        {new Date(alarm.occurred_at).toLocaleString()}
      </td>
      <td className="py-3 px-4">
        {alarm.alarm_state === 'ACTIVE' && (
          <button
            onClick={() => onAck(alarm.alarm_id)}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors"
          >
            <Check className="w-3 h-3" />
            Ack
          </button>
        )}
        {alarm.alarm_state === 'ACKNOWLEDGED' && (
          <span className="text-xs text-slate-600">{alarm.acked_by}</span>
        )}
      </td>
    </tr>
  );
});

// ── Alarms Page ─────────────────────────────────────────────────────────

export default function AlarmsPage() {
  const activeAlarms = useAppStore((s) => s.activeAlarms);
  const alarmCount = useAppStore((s) => s.alarmCount);
  const criticalCount = useAppStore((s) => s.criticalCount);
  const acknowledgeAlarm = useAppStore((s) => s.acknowledgeAlarm);

  const [severityFilter, setSeverityFilter] = useState<AlarmSeverity | 'ALL'>('ALL');
  const [stateFilter, setStateFilter] = useState<AlarmState | 'ALL'>('ALL');

  const filteredAlarms = useMemo(() => {
    return activeAlarms.filter((a) => {
      if (severityFilter !== 'ALL' && a.severity !== severityFilter) return false;
      if (stateFilter !== 'ALL' && a.alarm_state !== stateFilter) return false;
      return true;
    });
  }, [activeAlarms, severityFilter, stateFilter]);

  const handleAck = useCallback(async (alarmId: string) => {
    try {
      await fetchApi('/alarms/ack', {
        method: 'POST',
        body: JSON.stringify({ alarm_id: alarmId, acked_by: 'operator' }),
      });
      acknowledgeAlarm(alarmId, 'operator');
    } catch (err) {
      console.error('Failed to acknowledge alarm:', err);
    }
  }, [acknowledgeAlarm]);

  const summaryCards = [
    { label: 'Total', value: alarmCount, color: 'text-slate-300', bg: 'border-slate-700/50' },
    { label: 'Critical', value: criticalCount, color: 'text-red-400', bg: 'border-red-700/30' },
    { label: 'Active', value: activeAlarms.filter((a) => a.alarm_state === 'ACTIVE').length, color: 'text-amber-400', bg: 'border-amber-700/30' },
    { label: 'Acknowledged', value: activeAlarms.filter((a) => a.alarm_state === 'ACKNOWLEDGED').length, color: 'text-blue-400', bg: 'border-blue-700/30' },
  ];

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 flex items-center gap-2">
            <Bell className="w-6 h-6 text-amber-400" />
            Alarm Center
          </h1>
          <p className="text-sm text-slate-500 mt-1">Monitor, acknowledge, and manage plant alarms</p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {summaryCards.map(({ label, value, color, bg }) => (
          <div key={label} className={cn('rounded-xl border bg-slate-900/30 p-4 backdrop-blur-sm', bg)}>
            <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</p>
            <p className={cn('text-2xl font-bold tabular-nums mt-1', color)}>{value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Filter className="w-3.5 h-3.5" />
          <span>Filter:</span>
        </div>
        <div className="flex gap-1">
          {(['ALL', 'CRITICAL', 'ALARM', 'WARNING', 'INFO'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSeverityFilter(s)}
              className={cn(
                'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                severityFilter === s ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-800/50 text-slate-500 hover:text-slate-300'
              )}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="w-px h-5 bg-slate-800" />
        <div className="flex gap-1">
          {(['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'CLEARED'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStateFilter(s)}
              className={cn(
                'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                stateFilter === s ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-800/50 text-slate-500 hover:text-slate-300'
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Alarm Table */}
      <div className="rounded-xl border border-slate-800/50 bg-slate-900/20 backdrop-blur-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-slate-900/90 border-b border-slate-700/50">
              <tr>
                <th className="py-3 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Severity</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Tag</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Message</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Value</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">State</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Time</th>
                <th className="py-3 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredAlarms.map((alarm) => (
                <AlarmRow key={alarm.alarm_id} alarm={alarm} onAck={handleAck} />
              ))}
            </tbody>
          </table>
          {filteredAlarms.length === 0 && (
            <div className="py-16 text-center">
              <BellOff className="w-10 h-10 text-slate-700 mx-auto mb-3" />
              <p className="text-sm text-slate-500">No alarms matching filters</p>
              <p className="text-xs text-slate-600 mt-1">
                {alarmCount === 0 ? 'All systems operating normally' : 'Try adjusting your filters'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
