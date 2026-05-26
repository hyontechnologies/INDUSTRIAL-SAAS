import type { UserProfile, Permission, RolePermissionMap } from '../types/auth';

export const ROLE_PERMISSIONS: RolePermissionMap = {
  super_admin: ['alarms:acknowledge', 'alarms:clear', 'telemetry:view', 'tags:manage', 'devices:manage', 'agents:manage', 'users:manage', 'billing:view'],
  integrator_admin: ['alarms:acknowledge', 'alarms:clear', 'telemetry:view', 'tags:manage', 'devices:manage', 'agents:manage', 'users:manage', 'billing:view'],
  org_admin: ['alarms:acknowledge', 'alarms:clear', 'telemetry:view', 'tags:manage', 'devices:manage', 'users:manage', 'billing:view'],
  plant_admin: ['alarms:acknowledge', 'alarms:clear', 'telemetry:view', 'tags:manage', 'devices:manage'],
  operator: ['alarms:acknowledge', 'telemetry:view'],
  maintenance_engineer: ['alarms:acknowledge', 'telemetry:view', 'devices:manage'],
  auditor: ['telemetry:view', 'billing:view'],
};

export function hasPermission(user: UserProfile | null, permission: Permission): boolean {
  if (!user) return false;
  const permissions = ROLE_PERMISSIONS[user.role] || [];
  return permissions.includes(permission);
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function hasPlantAccess(user: UserProfile | null, plantId: string): boolean {
  if (!user) return false;
  void plantId;
  // In a real app, this would check if the user is mapped to the plant's org/plant group
  // For MVP, we assume global access for all users
  return true;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function canAccessRoute(user: UserProfile | null, path: string): boolean {
  if (!user) return false;
  void path;
  // In a real app, complex route path checking here
  return true;
}
