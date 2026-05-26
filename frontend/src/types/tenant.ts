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

export type PlantStatus = 'online' | 'offline' | 'maintenance';

export interface Plant {
  id: string;
  name: string;
  plantGroupId: string;
  orgId: string;
  location?: string;
  status: PlantStatus;
}

export interface WorkspaceContext {
  organization: Organization | null;
  plantGroup: PlantGroup | null;
  plant: Plant | null;
}
