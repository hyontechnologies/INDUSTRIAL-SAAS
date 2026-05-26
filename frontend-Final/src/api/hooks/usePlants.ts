import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../client';

export interface PlantSummary {
  plant_id: string;
  active_tags: number;
  active_alarms: number;
  critical_alarms: number;
  ts: string;
}

export interface Plant {
  plant_id: string;
  name: string;
  location: string;
  plant_type: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
}

export interface PlantsResponse {
  count: number;
  plants: Plant[];
}

export function usePlants() {
  return useQuery({
    queryKey: ['plants'],
    queryFn: () => fetchApi<PlantsResponse>('/plants'),
  });
}

export function usePlantSummary(plantId?: string) {
  return useQuery({
    queryKey: ['plants', plantId, 'summary'],
    queryFn: () => fetchApi<PlantSummary>(`/plants/${plantId}/summary`),
    enabled: !!plantId,
    refetchInterval: 10000, // Refresh summary every 10s
  });
}
