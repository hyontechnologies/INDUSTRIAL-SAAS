import React from 'react';
import { MaintenanceMetrics } from '../../components/maintenance/MaintenanceMetrics';
import { WorkOrderTable } from '../../components/maintenance/WorkOrderTable';
import { EquipmentHealthList } from '../../components/maintenance/EquipmentHealthList';
import { useNotificationStore } from '../../stores/useNotificationStore';

const Maintenance: React.FC = () => {
  const { addNotification } = useNotificationStore();

  const handleGenerateReport = () => {
    addNotification({
      title: 'Report Generated',
      message: 'The plant maintenance report has been generated and sent to your email.',
      type: 'success'
    });
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto pr-2 pb-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Plant Maintenance</h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage work orders, track equipment health, and review AI maintenance predictions.
          </p>
        </div>
        <button
          onClick={handleGenerateReport}
          className="bg-white/60 backdrop-blur-md border border-white/40 text-slate-700 px-5 py-2 rounded-full text-sm font-medium hover:bg-white/80 transition-all shadow-sm"
        >
          Generate Report
        </button>
      </div>

      <MaintenanceMetrics />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <WorkOrderTable />
        </div>
        <div>
          <EquipmentHealthList />
        </div>
      </div>
    </div>
  );
};

export default Maintenance;
