import React from 'react';
import { useMaintenanceStore } from '../../stores/useMaintenanceStore';
import { Wrench, AlertTriangle, CalendarClock } from 'lucide-react';

export const MaintenanceMetrics: React.FC = () => {
  const { workOrders, equipmentHealth } = useMaintenanceStore();
  const [now] = React.useState(() => Date.now());

  const openWorkOrders = workOrders.filter(wo => wo.status !== 'completed' && wo.status !== 'cancelled').length;
  const criticalEquipment = equipmentHealth.filter(eq => eq.status === 'critical').length;

  // Equipment with AI predicted failure in the next 7 days
  const upcomingFailures = equipmentHealth.filter(eq => {
    if (!eq.predictedFailureDate) return false;
    const daysUntilFailure = (new Date(eq.predictedFailureDate).getTime() - now) / 86400000;
    return daysUntilFailure > 0 && daysUntilFailure <= 7;
  }).length;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div className="glassmorphism-card p-4 rounded-xl flex items-center gap-4">
        <div className="p-3 bg-blue-500/10 text-blue-600 rounded-lg">
          <Wrench className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500">Open Work Orders</p>
          <p className="text-2xl font-bold text-slate-800">{openWorkOrders}</p>
        </div>
      </div>

      <div className="glassmorphism-card p-4 rounded-xl flex items-center gap-4">
        <div className="p-3 bg-red-500/10 text-red-600 rounded-lg">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500">Critical Equipment</p>
          <p className="text-2xl font-bold text-slate-800">{criticalEquipment}</p>
        </div>
      </div>

      <div className="glassmorphism-card p-4 rounded-xl flex items-center gap-4">
        <div className="p-3 bg-purple-500/10 text-purple-600 rounded-lg">
          <CalendarClock className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500">AI Predicted Failures (7d)</p>
          <p className="text-2xl font-bold text-slate-800">{upcomingFailures}</p>
        </div>
      </div>
    </div>
  );
};
