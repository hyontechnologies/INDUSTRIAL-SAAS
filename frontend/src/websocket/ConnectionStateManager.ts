import { useConnectionStore } from '../stores/useConnectionStore';
import { useTelemetryStore } from '../stores/useTelemetryStore';

export class ConnectionStateManager {
  private staleCheckInterval: ReturnType<typeof setInterval> | null = null;
  private readonly CHECK_INTERVAL_MS = 5000;

  start() {
    this.stop();
    this.staleCheckInterval = setInterval(() => this.checkStaleState(), this.CHECK_INTERVAL_MS);
  }

  stop() {
    if (this.staleCheckInterval) {
      clearInterval(this.staleCheckInterval);
      this.staleCheckInterval = null;
    }
  }

  private checkStaleState() {
    const connStore = useConnectionStore.getState();
    const telStore = useTelemetryStore.getState();

    // Check if entire connection is stale
    if (connStore.status === 'connected' && connStore.lastMessageTime) {
      const msSinceLastMsg = Date.now() - connStore.lastMessageTime.getTime();
      if (msSinceLastMsg > telStore.staleThresholdMs) {
        connStore.setStatus('stale');
      }
    } else if (connStore.status === 'stale' && connStore.lastMessageTime) {
      const msSinceLastMsg = Date.now() - connStore.lastMessageTime.getTime();
      if (msSinceLastMsg <= telStore.staleThresholdMs) {
        connStore.setStatus('connected');
      }
    }

    // Tell telemetry store to mark individual tags as stale if needed
    telStore.checkStaleValues();
  }
}
