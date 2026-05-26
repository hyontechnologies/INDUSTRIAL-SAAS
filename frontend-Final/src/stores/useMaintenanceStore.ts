import { create } from 'zustand';
import { WorkOrder, EquipmentHealth, WorkOrderStatus } from '../types/maintenance';

interface MaintenanceState {
  workOrders: WorkOrder[];
  equipmentHealth: EquipmentHealth[];

  // Actions
  updateWorkOrderStatus: (id: string, status: WorkOrderStatus) => void;
  addWorkOrder: (workOrder: Omit<WorkOrder, 'id' | 'createdAt'>) => void;
}

// Mock Data
const mockWorkOrders: WorkOrder[] = [
  {
    id: 'wo-101',
    title: 'Replace Conveyor Belt Motor',
    description: 'Motor M-402 is showing high vibration and temperature readings.',
    equipmentId: 'eq-402',
    equipmentName: 'Conveyor Motor M-402',
    status: 'pending',
    priority: 'high',
    assignedTo: 'John Davis',
    dueDate: new Date(Date.now() + 86400000 * 2).toISOString(),
    createdAt: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: 'wo-102',
    title: 'Quarterly Pump Calibration',
    description: 'Perform standard Q2 calibration on main water pumps.',
    equipmentId: 'eq-105',
    equipmentName: 'Main Water Pump P-1',
    status: 'in_progress',
    priority: 'medium',
    assignedTo: 'Sarah Jenkins',
    dueDate: new Date(Date.now() + 86400000 * 5).toISOString(),
    createdAt: new Date(Date.now() - 86400000 * 3).toISOString(),
  },
  {
    id: 'wo-103',
    title: 'Fix Hydraulic Leak on Press 3',
    description: 'Hydraulic fluid pooling near the base of Press 3.',
    equipmentId: 'eq-303',
    equipmentName: 'Hydraulic Press 3',
    status: 'pending',
    priority: 'critical',
    assignedTo: 'Mike Ross',
    dueDate: new Date(Date.now() + 3600000 * 4).toISOString(),
    createdAt: new Date().toISOString(),
  }
];

const mockEquipmentHealth: EquipmentHealth[] = [
  {
    id: 'eq-402',
    name: 'Conveyor Motor M-402',
    type: 'Motor',
    healthScore: 45,
    status: 'warning',
    lastMaintained: new Date(Date.now() - 86400000 * 45).toISOString(),
    nextScheduled: new Date(Date.now() + 86400000 * 15).toISOString(),
    predictedFailureDate: new Date(Date.now() + 86400000 * 7).toISOString(), // AI prediction
  },
  {
    id: 'eq-303',
    name: 'Hydraulic Press 3',
    type: 'Press',
    healthScore: 22,
    status: 'critical',
    lastMaintained: new Date(Date.now() - 86400000 * 120).toISOString(),
    nextScheduled: new Date(Date.now() + 86400000 * 5).toISOString(),
    predictedFailureDate: new Date(Date.now() + 86400000 * 2).toISOString(),
  },
  {
    id: 'eq-105',
    name: 'Main Water Pump P-1',
    type: 'Pump',
    healthScore: 92,
    status: 'healthy',
    lastMaintained: new Date(Date.now() - 86400000 * 10).toISOString(),
    nextScheduled: new Date(Date.now() + 86400000 * 80).toISOString(),
  },
  {
    id: 'eq-201',
    name: 'Cooling Fan Unit A',
    type: 'HVAC',
    healthScore: 78,
    status: 'healthy',
    lastMaintained: new Date(Date.now() - 86400000 * 30).toISOString(),
    nextScheduled: new Date(Date.now() + 86400000 * 60).toISOString(),
  }
];

export const useMaintenanceStore = create<MaintenanceState>((set) => ({
  workOrders: mockWorkOrders,
  equipmentHealth: mockEquipmentHealth,

  updateWorkOrderStatus: (id, status) => set((state) => ({
    workOrders: state.workOrders.map((wo) =>
      wo.id === id ? { ...wo, status } : wo
    )
  })),

  addWorkOrder: (workOrder) => set((state) => ({
    workOrders: [
      ...state.workOrders,
      {
        ...workOrder,
        id: `wo-${Math.floor(Math.random() * 10000)}`,
        createdAt: new Date().toISOString()
      }
    ]
  }))
}));
