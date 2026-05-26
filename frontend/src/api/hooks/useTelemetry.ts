import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../client';

export interface TelemetryPoint {
  tag_name: string;
  value: number;
  quality: number;
  ts: string;
  unit: string | null;
}

export interface TelemetryLatestResponse {
  plant_id: string;
  count: number;
  data: TelemetryPoint[];
}

export function useTelemetryLatest(plantId?: string) {
  return useQuery({
    queryKey: ['telemetry', 'latest', plantId],
    queryFn: () => fetchApi<TelemetryLatestResponse>(`/telemetry/latest?plant_id=${plantId}`),
    enabled: !!plantId,
    refetchInterval: 5000, // Refresh every 5s for live dashboard
  });
}

export interface MultiHistoryResponse {
  plant_id: string;
  tags: string[];
  interval: string;
  count: number;
  data: any[]; // Pivot data {ts: string, [tag_name]: value}
}

export function useTelemetryMultiHistory(plantId?: string, tags: string[] = [], start?: string, end?: string, interval = '5m') {
  return useQuery({
    queryKey: ['telemetry', 'multi-history', plantId, tags, start, end, interval],
    queryFn: () => {
      const tagStr = tags.join(',');
      return fetchApi<MultiHistoryResponse>(
        `/telemetry/multi-history?plant_id=${plantId}&tags=${encodeURIComponent(tagStr)}&start=${encodeURIComponent(start!)}&end=${encodeURIComponent(end!)}&interval=${interval}`
      );
    },
    enabled: !!plantId && tags.length > 0 && !!start && !!end,
  });
}

export interface TagStatsResponse {
  tag_name: string;
  plant_id: string;
  hours: number;
  stats: {
    sample_count: number;
    avg_val: number;
    min_val: number;
    max_val: number;
    std_val: number;
  }
}

export function useTagStats(plantId?: string, tagName?: string, hours = 24) {
  return useQuery({
    queryKey: ['telemetry', 'stats', plantId, tagName, hours],
    queryFn: () => fetchApi<TagStatsResponse>(`/telemetry/stats?plant_id=${plantId}&tag_name=${encodeURIComponent(tagName!)}&hours=${hours}`),
    enabled: !!plantId && !!tagName,
  });
}
