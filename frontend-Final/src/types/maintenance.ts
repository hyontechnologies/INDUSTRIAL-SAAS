export type WorkOrderStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';
export type WorkOrderPriority = 'low' | 'medium' | 'high' | 'critical';

export interface WorkOrder {
  id: string;
  title: string;
  description: string;
  equipmentId: string;
  equipmentName: string;
  status: WorkOrderStatus;
  priority: WorkOrderPriority;
  assignedTo: string;
  dueDate: string;
  createdAt: string;
}

export type HealthStatus = 'healthy' | 'warning' | 'critical' | 'offline';

export interface EquipmentHealth {
  id: string;
  name: string;
  type: string;
  healthScore: number; // 0 to 100
  status: HealthStatus;
  lastMaintained: string;
  nextScheduled: string;
  predictedFailureDate?: string; // AI prediction
}
