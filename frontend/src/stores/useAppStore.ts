import { create } from 'zustand';

// ── ROLE HIERARCHY ──
export type UserRole =
  | 'super_admin'
  | 'integrator_admin'
  | 'org_admin'
  | 'plant_admin'
  | 'operator'
  | 'maintenance_engineer'
  | 'auditor';

// ── TENANT HIERARCHY ──
export interface Organization {
  id: string;
  name: string;
  logo?: string;
}

export interface PlantGroup {
  id: string;
  name: string;
  orgId: string;
}

export interface Plant {
  id: string;
  name: string;
  plantGroupId: string;
  orgId: string;
  location?: string;
  status: 'online' | 'offline' | 'maintenance';
}

// ── WORKSPACE CONTEXT ──
export interface WorkspaceContext {
  organization: Organization | null;
  plantGroup: PlantGroup | null;
  plant: Plant | null;
}

// ── USER PROFILE ──
export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatarUrl?: string;
}

// ── SIDEBAR NAV ITEM ──
export type NavCategory = 'OVERVIEW' | 'OPERATIONS' | 'ENGINEERING' | 'ADMIN';

export interface NavItem {
  id: string;
  label: string;
  icon: string; // lucide icon name
  path: string;
  category: NavCategory;
  badge?: number;
  requiredRoles?: UserRole[];
}

// ── APP STORE ──
interface AppState {
  // Auth & Role
  user: UserProfile;
  setUser: (user: UserProfile) => void;
  switchRole: (role: UserRole) => void;

  // Workspace
  workspace: WorkspaceContext;
  setOrganization: (org: Organization) => void;
  setPlantGroup: (pg: PlantGroup) => void;
  setPlant: (plant: Plant) => void;

  // UI State
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  sidebarOpen: boolean;        // mobile drawer
  setSidebarOpen: (open: boolean) => void;

  // Mock Data
  organizations: Organization[];
  plantGroups: PlantGroup[];
  plants: Plant[];
}

// ── SEED DATA (Simulates backend until API is built) ──
const MOCK_ORGANIZATIONS: Organization[] = [
  { id: 'piccadily', name: 'Piccadily Agro Industries', logo: '🏭' },
  { id: 'org-mecgale', name: 'Mecgale Engineering', logo: '⚙️' },
];

const MOCK_PLANT_GROUPS: PlantGroup[] = [
  { id: 'pg-boilers', name: 'Boiler Systems', orgId: 'piccadily' },
  { id: 'pg-wtp', name: 'Water Treatment', orgId: 'piccadily' },
  { id: 'pg-demo', name: 'Demo Systems', orgId: 'org-mecgale' },
];

const MOCK_PLANTS: Plant[] = [
  { id: 'BOILER_PLC_01', name: 'Boiler Plant 01', plantGroupId: 'pg-boilers', orgId: 'piccadily', location: 'Unit-A, Sector-3', status: 'online' },
  { id: 'BOILER_PLC_02', name: 'Boiler Plant 02 (Secondary)', plantGroupId: 'pg-boilers', orgId: 'piccadily', location: 'Unit-B, Sector-3', status: 'maintenance' },
  { id: 'WTP_NODE_01', name: 'Water Treatment 01', plantGroupId: 'pg-wtp', orgId: 'piccadily', location: 'ETP Zone', status: 'online' },
  { id: 'DEMO_PLC_01', name: 'Demo Plant 01', plantGroupId: 'pg-demo', orgId: 'org-mecgale', location: 'Lab Floor', status: 'offline' },
];

export const useAppStore = create<AppState>((set) => ({
  // ── DEFAULT USER (Mock — switchable via Role Switcher) ──
  user: {
    id: 'usr-001',
    name: 'Ravi Kumar',
    email: 'ravi@piccadily.com',
    role: 'operator',
  },
  setUser: (user) => set({ user }),
  switchRole: (role) =>
    set((state) => ({ user: { ...state.user, role } })),

  // ── DEFAULT WORKSPACE ──
  workspace: {
    organization: MOCK_ORGANIZATIONS[0],
    plantGroup: MOCK_PLANT_GROUPS[0],
    plant: MOCK_PLANTS[0],
  },
  setOrganization: (org) =>
    set((state) => ({
      workspace: { ...state.workspace, organization: org, plantGroup: null, plant: null },
    })),
  setPlantGroup: (pg) =>
    set((state) => ({
      workspace: { ...state.workspace, plantGroup: pg, plant: null },
    })),
  setPlant: (plant) =>
    set((state) => ({
      workspace: { ...state.workspace, plant },
    })),

  // ── UI STATE ──
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  sidebarOpen: false,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  // ── MOCK SEED DATA ──
  organizations: MOCK_ORGANIZATIONS,
  plantGroups: MOCK_PLANT_GROUPS,
  plants: MOCK_PLANTS,
}));

// ── NAVIGATION CONFIG ──
export const ALL_NAV_ITEMS: NavItem[] = [
  // OVERVIEW
  { id: 'dashboard', label: 'Dashboard', icon: 'LayoutDashboard', path: '/dashboard', category: 'OVERVIEW' },
  { id: 'activity', label: 'Activity', icon: 'Activity', path: '/activity', category: 'OVERVIEW' },

  // OPERATIONS
  { id: 'plants', label: 'Plants', icon: 'Factory', path: '/plants', category: 'OPERATIONS' },
  { id: 'live-plant', label: 'Live Plant', icon: 'Zap', path: '/plants/live', category: 'OPERATIONS' },
  { id: 'alarms', label: 'Alarms', icon: 'Bell', path: '/alarms', category: 'OPERATIONS', badge: 0 },
  { id: 'trends', label: 'Trends', icon: 'TrendingUp', path: '/trends', category: 'OPERATIONS' },
  { id: 'reports', label: 'Reports', icon: 'FileText', path: '/reports', category: 'OPERATIONS' },

  // ENGINEERING
  { id: 'telemetry', label: 'Telemetry', icon: 'Radio', path: '/telemetry', category: 'ENGINEERING' },
  { id: 'tags', label: 'Tags', icon: 'GitBranch', path: '/tags', category: 'ENGINEERING' },
  { id: 'devices', label: 'Devices', icon: 'Cpu', path: '/devices', category: 'ENGINEERING' },
  { id: 'agents', label: 'Agents', icon: 'Server', path: '/agents', category: 'ENGINEERING' },

  // ADMIN
  { id: 'organizations', label: 'Organizations', icon: 'Building2', path: '/orgs', category: 'ADMIN' },
  { id: 'users', label: 'Users', icon: 'Users', path: '/users', category: 'ADMIN' },
  { id: 'billing', label: 'Billing', icon: 'CreditCard', path: '/billing', category: 'ADMIN' },
  { id: 'audit-logs', label: 'Audit Logs', icon: 'Shield', path: '/audit-logs', category: 'ADMIN' },
  { id: 'ai-insights', label: 'AI Insights', icon: 'Brain', path: '/ai-insights', category: 'ADMIN' },
  { id: 'settings', label: 'Settings', icon: 'Settings', path: '/settings', category: 'ADMIN' },
];

// Role-based nav resolver
export function getNavForRole(role: UserRole): NavItem[] {
  // Simple logic for MVP: Show different categories based on role
  // Operator: OVERVIEW, OPERATIONS
  // Integrator: ALL
  // Exec: OVERVIEW, ADMIN
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
      return ALL_NAV_ITEMS.filter(n => n.id === 'dashboard' || n.id === 'reports' || n.category === 'ADMIN');
    default:
      return ALL_NAV_ITEMS.filter(n => ['OVERVIEW', 'OPERATIONS'].includes(n.category));
  }
}

// Role display labels
export const ROLE_LABELS: Record<UserRole, string> = {
  super_admin: 'Super Platform Admin',
  integrator_admin: 'Integrator Admin',
  org_admin: 'Organization Admin',
  plant_admin: 'Plant Admin',
  operator: 'Plant Operator',
  maintenance_engineer: 'Maintenance Engineer',
  auditor: 'Read-only Auditor',
};
