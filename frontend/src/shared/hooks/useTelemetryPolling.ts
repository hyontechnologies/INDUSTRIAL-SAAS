import { useEffect, useRef, useState, useCallback } from 'react';
import type { WsMessage } from '../types';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error';

interface UseTelemetryPollingOptions {
  tenantId: string;
  plantId: string;
  onMessage?: (message: WsMessage) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  pollingInterval?: number;
  enabled?: boolean;
}

export function useTelemetryPolling({
  tenantId,
  plantId,
  onMessage,
  onStatusChange,
  pollingInterval = 2000,
  enabled = true,
}: UseTelemetryPollingOptions) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const onMessageRef = useRef(onMessage);
  const onStatusRef = useRef(onStatusChange);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onStatusRef.current = onStatusChange; }, [onStatusChange]);

  const updateStatus = useCallback((s: ConnectionStatus) => {
    setStatus(s);
    onStatusRef.current?.(s);
  }, []);

  const poll = useCallback(async () => {
    try {
      // Assuming frontend proxy or direct backend access handles /api routes
      const url = `/api/v1/latest/${tenantId}/${plantId}`;
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        onMessageRef.current?.(data);
        updateStatus('connected');
      } else {
        updateStatus('error');
      }
    } catch (e) {
      console.warn("Polling error", e);
      updateStatus('error');
    }
  }, [tenantId, plantId, updateStatus]);

  useEffect(() => {
    let active = true;
    let startTimer: ReturnType<typeof setTimeout> | undefined;

    if (enabled && tenantId && plantId) {
      startTimer = setTimeout(() => {
        if (active) {
          updateStatus('connecting');
          poll();
        }
      }, 0);
      intervalRef.current = setInterval(poll, pollingInterval);
    } else {
      startTimer = setTimeout(() => {
        if (active) updateStatus('disconnected');
      }, 0);
    }

    return () => {
      active = false;
      if (startTimer) {
        clearTimeout(startTimer);
      }
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled, tenantId, plantId, pollingInterval, poll, updateStatus]);

  return {
    status,
    isConnected: status === 'connected',
  };
}
