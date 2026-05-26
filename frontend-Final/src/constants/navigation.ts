import { NavItem, NavCategory } from '../types/navigation';
import { UserRole } from '../types/auth';

export const CATEGORY_ORDER: NavCategory[] = ['OVERVIEW', 'OPERATIONS', 'ENGINEERING', 'ADMIN'];

export const ALL_NAV_ITEMS: NavItem[] = [
  // OVERVIEW
  { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', path: '/dashboard', category: 'OVERVIEW' },

  // OPERATIONS
  { id: 'plants', label: 'Plants Overview', icon: 'Factory', path: '/plants', category: 'OPERATIONS' },
  { id: 'live-plant', label: 'Live Plant', icon: 'Zap', path: '/plants/live', category: 'OPERATIONS' },

  // ENGINEERING
  { id: 'telemetry', label: 'Telemetry Explorer', icon: 'Radio', path: '/telemetry', category: 'ENGINEERING' },
  { id: 'tags', label: 'Tags', icon: 'GitBranch', path: '/tags', category: 'ENGINEERING' },
  { id: 'devices', label: 'Devices', icon: 'Cpu', path: '/devices', category: 'ENGINEERING' },
  { id: 'agents', label: 'Edge Agents', icon: 'Server', path: '/agents', category: 'ENGINEERING' },

  // ADMIN
  { id: 'organizations', label: 'Organizations', icon: 'Building2', path: '/orgs', category: 'ADMIN' },
  { id: 'users', label: 'Users', icon: 'Users', path: '/users', category: 'ADMIN' },
  { id: 'billing', label: 'Billing', icon: 'CreditCard', path: '/billing', category: 'ADMIN' },
  { id: 'audit-logs', label: 'Audit Logs', icon: 'Shield', path: '/audit-logs', category: 'ADMIN' },
  { id: 'ai-insights', label: 'AI Insights', icon: 'Brain', path: '/ai-insights', category: 'ADMIN' },
  { id: 'settings', label: 'Settings', icon: 'Settings', path: '/settings', category: 'ADMIN' },
];

export const ROLE_LABELS: Record<UserRole, string> = {
  super_admin: 'Super Platform Admin',
  integrator_admin: 'Integrator Admin',
  org_admin: 'Organization Admin',
  plant_admin: 'Plant Admin',
  operator: 'Plant Operator',
  maintenance_engineer: 'Maintenance Engineer',
  auditor: 'Read-only Auditor',
};

export function getNavForRole(role: UserRole): NavItem[] {
  switch (role) {
    case 'super_admin':
    case 'integrator_admin':
      return ALL_NAV_ITEMS;
    case 'org_admin':
    case 'plant_admin':
      return ALL_NAV_ITEMS.filter(n => ['OVERVIEW', 'OPERATIONS', 'ADMIN'].includes(n.category));
    case 'operator':
    case 'maintenance_engineer':
      return ALL_NAV_ITEMS.filter(n => ['OVERVIEW', 'OPERATIONS'].includes(n.category));
    case 'auditor':
      return ALL_NAV_ITEMS.filter(n => n.id === 'dashboard' || n.category === 'ADMIN');
    default:
      return ALL_NAV_ITEMS.filter(n => ['OVERVIEW', 'OPERATIONS'].includes(n.category));
  }
}
