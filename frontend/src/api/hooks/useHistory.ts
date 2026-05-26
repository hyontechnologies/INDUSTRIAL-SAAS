import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../client';

export interface HistoryQueryOptions {
  start_ts?: string;
  end_ts?: string;
  resolution?: '1min' | '5min' | '1hour' | '1day';
}

export function useHistory(plantId?: string, tagName?: string, options?: HistoryQueryOptions) {
  return useQuery({
    queryKey: ['history', plantId, tagName, options],
    queryFn: () => {
      if (!plantId || !tagName) return Promise.resolve({ data: [] });

      const params = new URLSearchParams();
      params.append('plant_id', plantId);
      params.append('tag_name', tagName);

      if (options?.start_ts) params.append('start_ts', options.start_ts);
      if (options?.end_ts) params.append('end_ts', options.end_ts);
      if (options?.resolution) params.append('resolution', options.resolution);

      return fetchApi<any>(`/telemetry/history?${params.toString()}`);
    },
    enabled: !!plantId && !!tagName,
  });
}
