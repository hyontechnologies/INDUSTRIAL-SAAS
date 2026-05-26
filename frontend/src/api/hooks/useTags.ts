import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../client';
import type { TagMetadata } from '../../types/telemetry';

export interface TagsResponse {
  count: number;
  tags: TagMetadata[];
}

export function useTags(plantId?: string) {
  return useQuery({
    queryKey: ['tags', plantId],
    queryFn: () => {
      if (!plantId) return Promise.resolve({ count: 0, tags: [] });
      return fetchApi<TagsResponse>(`/tags?plant_id=${plantId}`);
    },
    enabled: !!plantId,
  });
}
