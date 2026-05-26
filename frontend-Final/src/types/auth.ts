export type UserRole =
  | 'super_admin'
  | 'integrator_admin'
  | 'org_admin'
  | 'plant_admin'
  | 'operator'
  | 'maintenance_engineer'
  | 'auditor';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatarUrl?: string;
}

export type Permission =
  | 'alarms:acknowledge'
  | 'alarms:clear'
  | 'telemetry:view'
  | 'tags:manage'
  | 'devices:manage'
  | 'agents:manage'
  | 'users:manage'
  | 'billing:view';

export type RolePermissionMap = Record<UserRole, Permission[]>;

export interface AuthState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  token: string | null;
}
