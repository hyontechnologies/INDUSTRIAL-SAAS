import { memo, useMemo } from 'react';
import { useAppStore } from '../../shared/stores/useAppStore';
import { cn } from '../../shared/utils/cn';
import {
  Thermometer,
  Gauge,
  Droplets,
  Wind,
  AlertTriangle,
  Activity,
  Zap,
  TrendingUp,
  TrendingDown,
  Wifi,
  WifiOff,
} from 'lucide-react';
import type { TelemetryLatest } from '../../shared/types';

// ── KPI Card Component ──────────────────────────────────────────────────

interface KpiCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  severity?: 'normal' | 'warning' | 'critical';
}

const KpiCard = memo(function KpiCard({ title, value, unit, icon, trend, severity = 'normal' }: KpiCardProps) {
  const severityColors = {
    normal: 'from-slate-800/50 to-slate-900/50 border-slate-700/50',
    warning: 'from-amber-950/30 to-slate-900/50 border-amber-700/30',
    critical: 'from-red-950/30 to-slate-900/50 border-red-700/30 animate-pulse',
  };

  return (
    <div className={cn(
      'relative overflow-hidden rounded-xl border bg-gradient-to-br p-5 backdrop-blur-sm transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:shadow-blue-500/5',
      severityColors[severity]
    )}>
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</p>
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold tabular-nums text-slate-50">{value}</span>
            {unit && <span className="text-sm text-slate-500">{unit}</span>}
          </div>
        </div>
        <div className="p-2.5 rounded-lg bg-slate-800/50">{icon}</div>
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-1 text-xs">
          {trend === 'up' && <TrendingUp className="w-3 h-3 text-emerald-400" />}
          {trend === 'down' && <TrendingDown className="w-3 h-3 text-red-400" />}
          <span className={trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-slate-500'}>
            {trend === 'stable' ? 'Stable' : trend === 'up' ? 'Rising' : 'Falling'}
          </span>
        </div>
      )}
      {/* Subtle glow */}
      <div className="absolute -top-12 -right-12 w-32 h-32 rounded-full bg-blue-500/5 blur-3xl" />
    </div>
  );
});

// ── Tag Value Row (for live telemetry table) ────────────────────────────

const TagRow = memo(function TagRow({ tag }: { tag: TelemetryLatest }) {
  const isStale = useMemo(() => {
    if (!tag.ts) return false;
    // eslint-disable-next-line react-hooks/purity
    const age = Date.now() - new Date(tag.ts).getTime();
    return age > 5 * 60 * 1000; // 5 minutes
  }, [tag.ts]);

  return (
    <tr className="border-b border-slate-800/30 hover:bg-slate-800/20 transition-colors">
      <td className="py-2.5 px-4">
        <span className="text-sm font-mono font-medium text-slate-200">{tag.tag_name}</span>
      </td>
      <td className="py-2.5 px-4 text-right">
        <span className="text-sm font-mono font-bold tabular-nums text-slate-50">
          {typeof tag.value === 'number' ? tag.value.toFixed(2) : tag.value}
        </span>
      </td>
      <td className="py-2.5 px-4 text-center">
        <span className="text-xs text-slate-500">{tag.unit || '—'}</span>
      </td>
      <td className="py-2.5 px-4 text-center">
        <span className={cn(
          'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase',
          tag.quality === 'GOOD' ? 'bg-emerald-500/15 text-emerald-400' :
          tag.quality === 'UNCERTAIN' ? 'bg-amber-500/15 text-amber-400' :
          'bg-red-500/15 text-red-400'
        )}>
          {tag.quality}
        </span>
      </td>
      <td className="py-2.5 px-4 text-right">
        <span className={cn('text-xs', isStale ? 'text-red-400' : 'text-slate-500')}>
          {tag.ts ? new Date(tag.ts).toLocaleTimeString() : '—'}
        </span>
      </td>
    </tr>
  );
});

// ── Dashboard Page ──────────────────────────────────────────────────────

export default function DashboardPage() {
  const latestValues = useAppStore((s) => s.latestValues);
  const alarmCount = useAppStore((s) => s.alarmCount);
  const criticalCount = useAppStore((s) => s.criticalCount);
  const connectionStatus = useAppStore((s) => s.connectionStatus);

  const tagList = useMemo(() => {
    return Object.values(latestValues).sort((a, b) => a.tag_name.localeCompare(b.tag_name));
  }, [latestValues]);

  const tagCount = tagList.length;
  const goodQualityCount = useMemo(
    () => tagList.filter((t) => t.quality === 'GOOD').length,
    [tagList]
  );

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-50">Operations Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Real-time plant telemetry overview</p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Active Tags"
          value={tagCount}
          icon={<Activity className="w-5 h-5 text-blue-400" />}
          trend="stable"
        />
        <KpiCard
          title="Good Quality"
          value={tagCount > 0 ? `${Math.round((goodQualityCount / tagCount) * 100)}%` : '—'}
          icon={<Zap className="w-5 h-5 text-emerald-400" />}
          trend={goodQualityCount === tagCount ? 'up' : 'down'}
        />
        <KpiCard
          title="Active Alarms"
          value={alarmCount}
          icon={<AlertTriangle className="w-5 h-5 text-amber-400" />}
          severity={criticalCount > 0 ? 'critical' : alarmCount > 0 ? 'warning' : 'normal'}
        />
        <KpiCard
          title="Connection"
          value={connectionStatus === 'connected' ? 'Live' : connectionStatus}
          icon={connectionStatus === 'connected'
            ? <Wifi className="w-5 h-5 text-emerald-400" />
            : <WifiOff className="w-5 h-5 text-red-400" />
          }
          severity={connectionStatus === 'error' ? 'critical' : 'normal'}
        />
      </div>

      {/* Telemetry Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          { label: 'Temperature', prefix: 'T', icon: <Thermometer className="w-4 h-4 text-orange-400" />, color: 'text-orange-400' },
          { label: 'Pressure', prefix: 'P', icon: <Gauge className="w-4 h-4 text-cyan-400" />, color: 'text-cyan-400' },
          { label: 'Level', prefix: 'L', icon: <Droplets className="w-4 h-4 text-blue-400" />, color: 'text-blue-400' },
          { label: 'Flow', prefix: 'F', icon: <Wind className="w-4 h-4 text-teal-400" />, color: 'text-teal-400' },
        ].map(({ label, prefix, icon, color }) => {
          const groupTags = tagList.filter((t) => t.tag_name.startsWith(prefix));
          return (
            <div key={label} className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-4 backdrop-blur-sm">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-md bg-slate-800/50">{icon}</div>
                <h3 className={cn('text-sm font-semibold', color)}>{label}</h3>
                <span className="ml-auto text-xs text-slate-600">{groupTags.length} tags</span>
              </div>
              <div className="space-y-1.5">
                {groupTags.slice(0, 4).map((tag) => (
                  <div key={tag.tag_name} className="flex items-center justify-between text-xs">
                    <span className="text-slate-400 font-mono truncate mr-2">{tag.tag_name}</span>
                    <span className="text-slate-200 font-bold tabular-nums">
                      {tag.value.toFixed(1)} {tag.unit || ''}
                    </span>
                  </div>
                ))}
                {groupTags.length > 4 && (
                  <p className="text-[10px] text-slate-600 text-center mt-1">+{groupTags.length - 4} more</p>
                )}
                {groupTags.length === 0 && (
                  <p className="text-xs text-slate-600 italic">No tags in this group</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Telemetry Table */}
      <div className="rounded-xl border border-slate-800/50 bg-slate-900/20 backdrop-blur-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800/50 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">Live Telemetry</h2>
          <span className="text-xs text-slate-600">{tagCount} tags</span>
        </div>
        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-slate-900/90 backdrop-blur-sm">
              <tr className="border-b border-slate-700/50">
                <th className="py-2.5 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Tag</th>
                <th className="py-2.5 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Value</th>
                <th className="py-2.5 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-center">Unit</th>
                <th className="py-2.5 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-center">Quality</th>
                <th className="py-2.5 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Updated</th>
              </tr>
            </thead>
            <tbody>
              {tagList.map((tag) => (
                <TagRow key={tag.tag_name} tag={tag} />
              ))}
            </tbody>
          </table>
          {tagList.length === 0 && (
            <div className="py-16 text-center">
              <Activity className="w-10 h-10 text-slate-700 mx-auto mb-3" />
              <p className="text-sm text-slate-500">No telemetry data yet</p>
              <p className="text-xs text-slate-600 mt-1">Waiting for edge agent connection...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
