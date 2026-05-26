import { useEffect } from 'react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useTelemetryLatest } from '../api/hooks/useTelemetry';
import { useActiveAlarms } from '../api/hooks/useAlarms';
import { useTelemetryStore } from '../stores/useTelemetryStore';
import { useAlarmStore } from '../stores/useAlarmStore';
import { DataQuality } from '../types/telemetry';

function mapQuality(q: number | string): DataQuality {
  if (typeof q === 'string') return q as DataQuality;
  if (q >= 192) return 'GOOD';
  if (q >= 64) return 'UNCERTAIN';
  return 'BAD';
}

export function useDataPoller() {
  const { plant } = useWorkspaceStore(s => s.workspace);
  const plantId = plant?.id;

  // React Query will automatically refetch these every 5s due to the hook defaults
  const { data: telemetryData } = useTelemetryLatest(plantId);
  const { data: alarmsData } = useActiveAlarms(plantId);

  // Sync Telemetry
  useEffect(() => {
    if (telemetryData?.data) {
      const payload: Record<string, any> = {};
      telemetryData.data.forEach(pt => {
        payload[pt.tag_name] = {
          v: pt.value,
          q: mapQuality(pt.quality),
          t: pt.ts,
          unit: pt.unit
        };
      });

      useTelemetryStore.getState().updateTelemetry({
        type: 'telemetry',
        timestamp: new Date().toISOString(),
        data: payload
      });
    }
  }, [telemetryData]);

  // Sync Alarms
  useEffect(() => {
    if (alarmsData?.alarms) {
      useAlarmStore.getState().setInitialAlarms(alarmsData.alarms);
    }
  }, [alarmsData]);
}
