import { create } from 'zustand';
import { Organization, PlantGroup, Plant, WorkspaceContext } from '../types/tenant';

// MOCK DATA for now
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

interface WorkspaceState {
  workspace: WorkspaceContext;
  setOrganization: (org: Organization) => void;
  setPlantGroup: (pg: PlantGroup) => void;
  setPlant: (plant: Plant) => void;

  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;

  // Mock data getters
  organizations: Organization[];
  plantGroups: PlantGroup[];
  plants: Plant[];
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  workspace: {
    organization: MOCK_ORGANIZATIONS[0],
    plantGroup: MOCK_PLANT_GROUPS[0],
    plant: MOCK_PLANTS[1],
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

  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  sidebarOpen: false,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  organizations: MOCK_ORGANIZATIONS,
  plantGroups: MOCK_PLANT_GROUPS,
  plants: MOCK_PLANTS,
}));
