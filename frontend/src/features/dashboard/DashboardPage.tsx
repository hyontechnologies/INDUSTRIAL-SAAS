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
import { ScadaPanel } from '../../shared/components/scada/ScadaPanel';
import { StatusIndicator } from '../../shared/components/scada/StatusIndicator';

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


  return (
    <ScadaPanel title={title} className="hover:border-blue-500/50 transition-colors cursor-default">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-baseline gap-1.5">
            <span className={cn(
              "text-3xl font-bold tabular-nums tracking-tight",
              severity === 'critical' ? 'text-scada-critical' : severity === 'warning' ? 'text-scada-warning' : 'text-slate-100'
            )}>{value}</span>
            {unit && <span className="text-sm font-semibold text-slate-500">{unit}</span>}
          </div>
        </div>
        <div className="p-2 rounded bg-[#0a0f1c] border border-scada-border/50 shadow-inner">
          {icon}
        </div>
      </div>
      {trend && (
        <div className="mt-4 flex items-center justify-between border-t border-scada-border/50 pt-2">
           <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider">
             {trend === 'up' && <TrendingUp className="w-3 h-3 text-scada-good" />}
             {trend === 'down' && <TrendingDown className="w-3 h-3 text-scada-critical" />}
             <span className={trend === 'up' ? 'text-scada-good' : trend === 'down' ? 'text-scada-critical' : 'text-slate-500'}>
               {trend === 'stable' ? 'Stable' : trend === 'up' ? 'Rising' : 'Falling'}
             </span>
           </div>
           {severity === 'critical' && <StatusIndicator status="critical" />}
        </div>
      )}
    </ScadaPanel>
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
          { label: 'Temperature', prefix: 'T', icon: <Thermometer className="w-3.5 h-3.5 text-orange-400" />, color: 'text-orange-400' },
          { label: 'Pressure', prefix: 'P', icon: <Gauge className="w-3.5 h-3.5 text-cyan-400" />, color: 'text-cyan-400' },
          { label: 'Level', prefix: 'L', icon: <Droplets className="w-3.5 h-3.5 text-blue-400" />, color: 'text-blue-400' },
          { label: 'Flow', prefix: 'F', icon: <Wind className="w-3.5 h-3.5 text-teal-400" />, color: 'text-teal-400' },
        ].map(({ label, prefix, icon }) => {
          const groupTags = tagList.filter((t) => t.tag_name.startsWith(prefix));
          return (
            <ScadaPanel
              key={label}
              title={label}
              headerRight={
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] font-bold text-slate-500">{groupTags.length} TAGS</span>
                  {icon}
                </div>
              }
            >
              <div className="space-y-0.5">
                {groupTags.slice(0, 5).map((tag) => {
                  const isStale = tag.ts ? Date.now() - new Date(tag.ts).getTime() > 300000 : true;
                  const status = tag.quality === 'GOOD' ? 'good' : tag.quality === 'UNCERTAIN' ? 'warning' : 'critical';
                  return (
                    <div key={tag.tag_name} className="flex items-center justify-between text-xs py-1.5 border-b border-scada-border/30 last:border-0 hover:bg-[#0a0f1c] px-1 rounded-sm cursor-pointer transition-colors">
                      <div className="flex items-center gap-2 overflow-hidden mr-2">
                        <StatusIndicator status={isStale ? 'stale' : status} className="flex-shrink-0 w-2 h-2" />
                        <span className="text-slate-300 font-mono text-[10px] truncate">{tag.tag_name}</span>
                      </div>
                      <div className="flex items-baseline gap-1 flex-shrink-0">
                        <span className={cn("font-bold tabular-nums", isStale ? "text-slate-500" : "text-emerald-400")}>
                          {typeof tag.value === 'number' ? tag.value.toFixed(2) : tag.value}
                        </span>
                        <span className="text-[9px] text-slate-500 font-semibold">{tag.unit || ''}</span>
                      </div>
                    </div>
                  );
                })}
                {groupTags.length > 5 && (
                  <button className="w-full mt-2 py-1.5 bg-[#0a0f1c] hover:bg-slate-800 border border-scada-border rounded-sm text-[9px] font-bold uppercase tracking-wider text-slate-400 transition-colors">
                    View All {groupTags.length} {label} Tags
                  </button>
                )}
                {groupTags.length === 0 && (
                  <p className="text-[10px] text-slate-600 italic text-center py-4">NO TAGS FOUND</p>
                )}
              </div>
            </ScadaPanel>
          );
        })}
      </div>

      <ScadaPanel title={`LIVE TELEMETRY (${tagCount} TAGS)`}>
        <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-[#0a0f1c] shadow-sm z-10">
              <tr className="border-b border-scada-border">
                <th className="py-2.5 px-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Tag Name</th>
                <th className="py-2.5 px-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-right">Value</th>
                <th className="py-2.5 px-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-center">Unit</th>
                <th className="py-2.5 px-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-center">Quality</th>
                <th className="py-2.5 px-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-right">Last Update</th>
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
              <p className="text-sm font-bold text-slate-500 uppercase tracking-wider">No Telemetry Data</p>
              <p className="text-xs text-slate-600 mt-1">Waiting for edge agent...</p>
            </div>
          )}
        </div>
      </ScadaPanel>
    </div>
  );
}
