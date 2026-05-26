import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useMaintenanceStore } from '../../stores/useMaintenanceStore';
import { WorkOrderPriority } from '../../types/maintenance';
import { X } from 'lucide-react';

interface WorkOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const WorkOrderModal: React.FC<WorkOrderModalProps> = ({ isOpen, onClose }) => {
  const { equipmentHealth, addWorkOrder } = useMaintenanceStore();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [priority, setPriority] = useState<WorkOrderPriority>('low');
  const [dueDate, setDueDate] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const equipment = equipmentHealth.find(eq => eq.id === equipmentId);

    if (equipment && title && dueDate) {
      addWorkOrder({
        title,
        description,
        equipmentId,
        equipmentName: equipment.name,
        priority,
        status: 'pending',
        assignedTo: 'Unassigned',
        dueDate: new Date(dueDate).toISOString(),
      });
      onClose();
      // Reset form
      setTitle('');
      setDescription('');
      setEquipmentId('');
      setPriority('low');
      setDueDate('');
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm transition-opacity">
      <div className="glassmorphism-card w-full max-w-md p-6 rounded-2xl relative shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-slate-600 hover:bg-white/50 rounded-full transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-xl font-bold text-slate-800 mb-6">Create Work Order</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Title</label>
            <input
              required
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-white/50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 outline-none transition-all"
              placeholder="e.g. Inspect Motor Bearings"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Equipment</label>
            <select
              required
              value={equipmentId}
              onChange={(e) => setEquipmentId(e.target.value)}
              className="w-full bg-white/50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 outline-none transition-all"
            >
              <option value="" disabled>Select Equipment...</option>
              {equipmentHealth.map(eq => (
                <option key={eq.id} value={eq.id}>{eq.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-white/50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 outline-none transition-all h-24 resize-none"
              placeholder="Provide details about the issue..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as WorkOrderPriority)}
                className="w-full bg-white/50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 outline-none transition-all"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Due Date</label>
              <input
                required
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full bg-white/50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 outline-none transition-all"
              />
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100/50 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors"
            >
              Create Order
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
};
