import { RealtimeDispatcher } from './RealtimeDispatcher';
import { useConnectionStore } from '../stores/useConnectionStore';
import { useAuthStore } from '../stores/useAuthStore';

export class SocketManager {
  private pollInterval: ReturnType<typeof setInterval> | null = null;
  private intentionalDisconnect = false;

  async connect(tenantId: string, plantId: string, token: string) {
    this.disconnect();
    this.intentionalDisconnect = false;

    const store = useConnectionStore.getState();
    store.setStatus('connecting');

    const pollData = async () => {
      if (this.intentionalDisconnect) return;
      try {
        const res = await fetch(`/api/v1/latest/${tenantId}/${plantId}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!res.ok) {
          if (res.status === 401 || res.status === 403) {
            useAuthStore.getState().logout();
            return;
          }
          throw new Error('Failed to fetch telemetry');
        }

        const data = await res.json();
        store.setStatus('connected');
        store.recordMessage();
        store.resetReconnect();

        RealtimeDispatcher.dispatch(data);
      } catch (err) {
        console.error('[Polling] Failed to fetch data', err);
        store.setStatus('reconnecting');
      }
    };

    // Initial fetch
    await pollData();

    // Poll every 2 seconds
    this.pollInterval = setInterval(pollData, 2000);
  }

  disconnect() {
    this.intentionalDisconnect = true;
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
    useConnectionStore.getState().setStatus('disconnected');
  }
}
