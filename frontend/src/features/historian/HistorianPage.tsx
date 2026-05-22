import { History, Clock } from 'lucide-react';

export default function HistorianPage() {
  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-50 flex items-center gap-2">
          <History className="w-6 h-6 text-violet-400" />
          Historian Explorer
        </h1>
        <p className="text-sm text-slate-500 mt-1">Query and explore historical telemetry data</p>
      </div>

      <div className="rounded-xl border border-slate-800/50 bg-slate-900/20 p-12 text-center">
        <Clock className="w-12 h-12 text-slate-700 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-slate-400">Coming in Phase 3</h2>
        <p className="text-sm text-slate-600 mt-2 max-w-md mx-auto">
          Time-bucket aggregation queries, trend comparison, multi-tag overlays,
          and CSV/Excel/PDF export capabilities.
        </p>
      </div>
    </div>
  );
}
