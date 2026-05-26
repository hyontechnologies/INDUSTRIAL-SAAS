import { useConnectionStore } from '../stores/useConnectionStore';
import { useWebSocketActions } from './WebSocketContext';

export function useWebSocket() {
  const status = useConnectionStore((state) => state.status);
  const lastMessageTime = useConnectionStore((state) => state.lastMessageTime);
  const reconnectAttempt = useConnectionStore((state) => state.reconnectAttempt);
  const { reconnect, disconnect } = useWebSocketActions();

  return {
    status,
    lastMessageTime,
    reconnectAttempt,
    isConnected: status === 'connected',
    isConnecting: status === 'connecting' || status === 'reconnecting',
    isStale: status === 'stale',
    reconnect,
    disconnect
  };
}
