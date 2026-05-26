import React, { useState } from 'react';
import { useMaintenanceStore } from '../../stores/useMaintenanceStore';
import { WorkOrderStatus, WorkOrderPriority } from '../../types/maintenance';
import { CheckCircle2, Clock, XCircle, AlertCircle } from 'lucide-react';
import { WorkOrderModal } from './WorkOrderModal';

const statusColors: Record<WorkOrderStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  completed: 'bg-green-100 text-green-700 border-green-200',
  cancelled: 'bg-slate-100 text-slate-700 border-slate-200',
};

const statusIcons = {
  pending: Clock,
  in_progress: AlertCircle,
  completed: CheckCircle2,
  cancelled: XCircle,
};

const priorityColors: Record<WorkOrderPriority, string> = {
  low: 'text-slate-500',
  medium: 'text-blue-500',
  high: 'text-orange-500',
  critical: 'text-red-500',
};

export const WorkOrderTable: React.FC = () => {
  const { workOrders, updateWorkOrderStatus } = useMaintenanceStore();
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      <div className="glassmorphism-card rounded-xl border border-white/40 overflow-hidden shadow-[0_8px_32px_0_rgba(0,0,0,0.05)]">
        <div className="p-4 border-b border-white/20 flex justify-between items-center bg-white/20">
          <h3 className="font-semibold text-slate-800">Active Work Orders</h3>
          <button
            onClick={() => setIsModalOpen(true)}
            className="text-sm bg-blue-600/90 hover:bg-blue-600 text-white px-4 py-1.5 rounded-full font-medium transition-colors shadow-sm"
          >
            + New Order
          </button>
        </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-slate-500 uppercase bg-slate-50/50">
            <tr>
              <th className="px-4 py-3 font-medium">Order ID</th>
              <th className="px-4 py-3 font-medium">Title & Equipment</th>
              <th className="px-4 py-3 font-medium">Priority</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Due Date</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {workOrders.map((wo) => {
              const StatusIcon = statusIcons[wo.status];
              return (
                <tr key={wo.id} className="hover:bg-white/40 transition-colors">
                  <td className="px-4 py-3 font-mono text-slate-500">{wo.id}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800">{wo.title}</p>
                    <p className="text-xs text-slate-500">{wo.equipmentName}</p>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`capitalize font-medium ${priorityColors[wo.priority]}`}>
                      {wo.priority}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${statusColors[wo.status]}`}>
                      <StatusIcon className="w-3 h-3" />
                      {wo.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {new Date(wo.dueDate).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <select
                      value={wo.status}
                      onChange={(e) => updateWorkOrderStatus(wo.id, e.target.value as WorkOrderStatus)}
                      className="text-xs bg-white/50 border border-slate-200 rounded-md px-2 py-1 outline-none focus:ring-2 focus:ring-blue-500/20"
                    >
                      <option value="pending">Pending</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                  </td>
                </tr>
              );
            })}
            {workOrders.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No work orders found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
    <WorkOrderModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
};
