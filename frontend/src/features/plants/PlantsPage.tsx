import { Factory, Plus, MapPin } from 'lucide-react';

export default function PlantsPage() {
  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 flex items-center gap-2">
            <Factory className="w-6 h-6 text-emerald-400" />
            Plant Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">Manage plants, equipment, and configurations</p>
        </div>
        <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" />
          Add Plant
        </button>
      </div>

      <div className="rounded-xl border border-slate-800/50 bg-slate-900/20 p-12 text-center">
        <MapPin className="w-12 h-12 text-slate-700 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-slate-400">Coming in Phase 3</h2>
        <p className="text-sm text-slate-600 mt-2 max-w-md mx-auto">
          Plant CRUD, equipment hierarchy, asset management, and configuration workflows.
        </p>
      </div>
    </div>
  );
}
