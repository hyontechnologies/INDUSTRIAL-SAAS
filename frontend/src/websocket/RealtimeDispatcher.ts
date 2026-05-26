import { useTelemetryStore } from '../stores/useTelemetryStore';
import { useAlarmStore } from '../stores/useAlarmStore';
import { useNotificationStore } from '../stores/useNotificationStore';
import { WebSocketMessage } from '../types/websocket';

export class RealtimeDispatcher {
  static dispatch(message: WebSocketMessage) {
    try {
      switch (message.type) {
        case 'telemetry':
          useTelemetryStore.getState().updateTelemetry(message);
          break;
        case 'snapshot':
          // Snapshot arrives on connect with all latest values
          // Convert to telemetry frame format: { data: { tagName: { v, q, t } } }
          useTelemetryStore.getState().updateTelemetry({
            type: 'telemetry',
            timestamp: new Date().toISOString(),
            data: message.data,
          });
          break;
        case 'alarm':
          useAlarmStore.getState().addAlarm(message);
          break;
        case 'system':
          useNotificationStore.getState().addNotification({
            title: message.data.event,
            message: message.data.message,
            type: 'info'
          });
          break;
        default:
          console.warn('Unknown websocket message type received', message);
      }
    } catch (err) {
      console.error('Failed to dispatch realtime message', err);
    }
  }
}
