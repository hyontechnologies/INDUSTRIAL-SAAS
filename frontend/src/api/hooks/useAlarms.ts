import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchApi } from '../client';
import type { Alarm } from '../../types/alarm';
import { queryClient } from '../queryClient';

export interface AlarmsResponse {
  count: number;
  alarms: Alarm[];
}

export function useActiveAlarms(plantId?: string) {
  return useQuery({
    queryKey: ['alarms', 'active', plantId],
    queryFn: () => {
      if (!plantId) return Promise.resolve({ count: 0, alarms: [] });
      return fetchApi<AlarmsResponse>(`/alarms/active?plant_id=${plantId}`);
    },
    enabled: !!plantId,
    refetchInterval: 5000,
  });
}

export function useAlarmHistory(plantId?: string) {
  return useQuery({
    queryKey: ['alarms', 'history', plantId],
    queryFn: () => {
      if (!plantId) return Promise.resolve({ count: 0, alarms: [] });
      return fetchApi<AlarmsResponse>(`/alarms/history?plant_id=${plantId}&limit=100`);
    },
    enabled: !!plantId,
  });
}

export function useAcknowledgeAlarm() {
  return useMutation({
    mutationFn: (data: { alarm_id: string; acked_by: string; comment?: string }) => {
      return fetchApi<{ ok: boolean; alarm_id: string }>('/alarms/ack', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alarms'] });
    },
  });
}

export function useClearAlarms() {
  return useMutation({
    mutationFn: (data: { plant_id: string; cleared_by: string; comment?: string; alarm_ids?: string[] }) => {
      return fetchApi<{ ok: boolean; cleared: number }>('/alarms/clear', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alarms'] });
    },
  });
}
