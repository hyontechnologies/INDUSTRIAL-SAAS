import { RealtimeDispatcher } from './RealtimeDispatcher';
import { useConnectionStore } from '../stores/useConnectionStore';

export class SocketManager {
  private ws: WebSocket | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalDisconnect = false;

  connect(tenantId: string, plantId: string, apiKey: string) {
    this.disconnect();
    this.intentionalDisconnect = false;

    const store = useConnectionStore.getState();
    store.setStatus('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Single-origin architecture: connect to the same host
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/${tenantId}/${plantId}?api_key=${apiKey}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        store.setStatus('connected');
        store.resetReconnect();
        this.reconnectDelay = 1000;
        console.log(`[SocketManager] Connected to ${tenantId}/${plantId}`);
      };

      this.ws.onmessage = (event) => {
        store.recordMessage();
        try {
          const payload = JSON.parse(event.data);
          RealtimeDispatcher.dispatch(payload);
        } catch (err) {
          console.error('[SocketManager] Failed to parse message', err);
        }
      };

      this.ws.onclose = (event) => {
        if (!this.intentionalDisconnect) {
          store.setStatus('reconnecting');
          this.scheduleReconnect(tenantId, plantId, apiKey);
        } else {
          store.setStatus('disconnected');
        }
        console.log(`[SocketManager] Disconnected: ${event.reason}`);
      };

      this.ws.onerror = (error) => {
        console.error('[SocketManager] WebSocket Error', error);
        // Will trigger onclose automatically
      };
    } catch (err) {
      console.error('[SocketManager] Failed to construct WebSocket', err);
      store.setStatus('failed');
      this.scheduleReconnect(tenantId, plantId, apiKey);
    }
  }

  disconnect() {
    this.intentionalDisconnect = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null; // Remove handler to prevent reconnect
      this.ws.close();
      this.ws = null;
    }
    useConnectionStore.getState().setStatus('disconnected');
  }

  private scheduleReconnect(tenantId: string, plantId: string, apiKey: string) {
    if (this.intentionalDisconnect) return;

    useConnectionStore.getState().incrementReconnect();

    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
      this.connect(tenantId, plantId, apiKey);
    }, this.reconnectDelay);
  }
}
