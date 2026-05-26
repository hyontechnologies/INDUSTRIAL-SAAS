import React from 'react';
import { useMaintenanceStore } from '../../stores/useMaintenanceStore';
import { useNotificationStore } from '../../stores/useNotificationStore';
import { Activity } from 'lucide-react';

export const EquipmentHealthList: React.FC = () => {
  const { equipmentHealth } = useMaintenanceStore();
  const { addNotification } = useNotificationStore();

  const getHealthColor = (score: number) => {
    if (score >= 80) return 'bg-emerald-500';
    if (score >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const handleViewAll = () => {
    addNotification({
      title: 'Equipment List',
      message: 'Opening full equipment health register...',
      type: 'info'
    });
  };

  return (
    <div className="glassmorphism-card rounded-xl border border-white/40 p-4 shadow-[0_8px_32px_0_rgba(0,0,0,0.05)]">
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-white/20">
        <h3 className="font-semibold text-slate-800 flex items-center gap-2">
          <Activity className="w-4 h-4 text-slate-500" />
          Equipment Health
        </h3>
        <button
          onClick={handleViewAll}
          className="text-xs text-blue-600 bg-white/50 px-3 py-1.5 rounded-full font-medium hover:bg-white/80 transition-all border border-white/40 shadow-sm"
        >
          View All
        </button>
      </div>

      <div className="space-y-4">
        {equipmentHealth.map((eq) => (
          <div key={eq.id} className="p-3 bg-white/40 rounded-lg border border-slate-100">
            <div className="flex justify-between items-start mb-2">
              <div>
                <h4 className="text-sm font-medium text-slate-800">{eq.name}</h4>
                <p className="text-xs text-slate-500">{eq.type}</p>
              </div>
              <span className="text-xs font-bold text-slate-700">{eq.healthScore}%</span>
            </div>

            <div className="w-full bg-slate-200 rounded-full h-2 mb-2">
              <div
                className={`${getHealthColor(eq.healthScore)} h-2 rounded-full transition-all duration-500`}
                style={{ width: `${eq.healthScore}%` }}
              ></div>
            </div>

            {eq.predictedFailureDate && (
              <p className="text-xs text-orange-600 font-medium mt-1">
                AI Warning: Failure predicted by {new Date(eq.predictedFailureDate).toLocaleDateString()}
              </p>
            )}

            <div className="flex justify-between text-[10px] text-slate-500 mt-2 pt-2 border-t border-slate-200/50">
              <span>Last: {new Date(eq.lastMaintained).toLocaleDateString()}</span>
              <span>Next: {new Date(eq.nextScheduled).toLocaleDateString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
