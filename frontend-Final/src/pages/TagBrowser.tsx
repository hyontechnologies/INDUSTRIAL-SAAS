import { useState, useMemo } from 'react';
import { useTelemetryStore } from '../stores/useTelemetryStore';
import { TelemetryPoint } from '../types/telemetry';
import { Tags, Search, Activity } from 'lucide-react';

export default function TagBrowser() {
  const latestValues = useTelemetryStore((s) => s.latestValues);
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState<string>('all');

  const tagList = useMemo(() => {
    return Object.entries(latestValues)
      .map(([tag_name, point]) => ({ tag_name, ts: point.timestamp, ...point } as TelemetryPoint & { tag_name: string; ts: string }))
      .filter((t) => {
        if (search && !t.tag_name.toLowerCase().includes(search.toLowerCase())) return false;
        if (groupFilter !== 'all') {
          const prefix = t.tag_name.split(/[_-]/)[0]?.toUpperCase() || '';
          if (prefix !== groupFilter) return false;
        }
        return true;
      })
      .sort((a, b) => a.tag_name.localeCompare(b.tag_name));
  }, [latestValues, search, groupFilter]);

  const groups = useMemo(() => {
    const g = new Set<string>();
    Object.keys(latestValues).forEach((tag_name) => {
      const prefix = tag_name.split(/[_-]/)[0]?.toUpperCase();
      if (prefix) g.add(prefix);
    });
    return ['all', ...Array.from(g).sort()];
  }, [latestValues]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg shadow-sm">
            <Tags className="w-6 h-6" />
          </div>
          Tag Browser
        </h1>
        <p className="text-sm text-slate-500 mt-1">Browse and search all live telemetry tags</p>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 flex-wrap bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
        <div className="relative flex-1 min-w-[250px] max-w-md w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search tags..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors shadow-sm"
          />
        </div>
        <div className="flex gap-2 flex-wrap flex-1">
          {groups.map((g) => (
            <button
              key={g}
              onClick={() => setGroupFilter(g)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                groupFilter === g
                  ? 'bg-blue-50 border-blue-200 text-blue-700 shadow-sm'
                  : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              {g === 'all' ? 'All Tags' : g}
            </button>
          ))}
        </div>
        <span className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
          {tagList.length} tags total
        </span>
      </div>

      {/* Tag Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 animate-in fade-in duration-500">
        {tagList.map((tag) => {
          const isGood = typeof tag.quality === 'number' ? tag.quality >= 192 : tag.quality === 'GOOD';

          return (
            <div
              key={tag.tag_name}
              className="rounded-2xl border border-slate-200 bg-white p-5 hover:shadow-md hover:border-slate-300 transition-all flex flex-col justify-between group"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-mono font-bold text-slate-700 group-hover:text-blue-600 transition-colors truncate pr-2">{tag.tag_name}</span>
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full flex-shrink-0 border ${
                  isGood ? 'bg-emerald-50 text-emerald-600 border-emerald-200' :
                  'bg-amber-50 text-amber-600 border-amber-200 animate-pulse'
                }`}>
                  {isGood ? 'GOOD' : 'UNCERTAIN'}
                </span>
              </div>
              <div className="flex items-baseline gap-1.5 mb-3">
                <span className={`text-2xl font-bold tabular-nums tracking-tight ${isGood ? 'text-slate-900' : 'text-slate-700'}`}>
                  {typeof tag.value === 'number' ? tag.value.toFixed(2) : tag.value}
                </span>
                {tag.unit && <span className="text-xs font-semibold text-slate-400">{tag.unit}</span>}
              </div>
              <div className="pt-3 border-t border-slate-100 mt-auto">
                <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  {tag.ts ? new Date(tag.ts).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}) : 'No data'}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {tagList.length === 0 && (
        <div className="py-20 text-center bg-white rounded-2xl border border-slate-200 border-dashed">
          <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Activity className="w-8 h-8 text-slate-300" />
          </div>
          <p className="text-base font-semibold text-slate-800">No tags found</p>
          <p className="text-sm text-slate-500 mt-1">Try adjusting your search or filters.</p>
        </div>
      )}
    </div>
  );
}
