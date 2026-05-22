import { useState, useMemo } from 'react';
import { useAppStore } from '../../shared/stores/useAppStore';
import { cn } from '../../shared/utils/cn';
import { Tags, Search, Activity } from 'lucide-react';
import type { TelemetryLatest } from '../../shared/types';

export default function TelemetryPage() {
  const latestValues = useAppStore((s) => s.latestValues);
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState<string>('all');

  const tagList = useMemo(() => {
    return Object.values(latestValues)
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
    Object.values(latestValues).forEach((t) => {
      const prefix = t.tag_name.split(/[_-]/)[0]?.toUpperCase();
      if (prefix) g.add(prefix);
    });
    return ['all', ...Array.from(g).sort()];
  }, [latestValues]);

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-50 flex items-center gap-2">
          <Tags className="w-6 h-6 text-cyan-400" />
          Tag Browser
        </h1>
        <p className="text-sm text-slate-500 mt-1">Browse and search all live telemetry tags</p>
      </div>

      {/* Search + Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[250px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search tags..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/50 transition-colors"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {groups.map((g) => (
            <button
              key={g}
              onClick={() => setGroupFilter(g)}
              className={cn(
                'px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors',
                groupFilter === g ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-800/50 text-slate-500 hover:text-slate-300'
              )}
            >
              {g === 'all' ? 'All' : g}
            </button>
          ))}
        </div>
        <span className="text-xs text-slate-600 ml-auto">{tagList.length} tags</span>
      </div>

      {/* Tag Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {tagList.map((tag) => (
          <div
            key={tag.tag_name}
            className="rounded-lg border border-slate-800/50 bg-slate-900/30 p-4 hover:border-slate-700/50 hover:bg-slate-800/20 transition-all"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-mono font-semibold text-slate-200">{tag.tag_name}</span>
              <span className={cn(
                'text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-full',
                tag.quality === 'GOOD' ? 'bg-emerald-500/15 text-emerald-400' :
                tag.quality === 'UNCERTAIN' ? 'bg-amber-500/15 text-amber-400' :
                'bg-red-500/15 text-red-400'
              )}>
                {tag.quality}
              </span>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-xl font-bold tabular-nums text-slate-50">
                {typeof tag.value === 'number' ? tag.value.toFixed(2) : tag.value}
              </span>
              {tag.unit && <span className="text-sm text-slate-500">{tag.unit}</span>}
            </div>
            <p className="text-xs text-slate-600 mt-2">
              {tag.ts ? new Date(tag.ts).toLocaleString() : 'No data'}
            </p>
          </div>
        ))}
      </div>

      {tagList.length === 0 && (
        <div className="py-16 text-center">
          <Activity className="w-10 h-10 text-slate-700 mx-auto mb-3" />
          <p className="text-sm text-slate-500">No tags match your search</p>
        </div>
      )}
    </div>
  );
}
