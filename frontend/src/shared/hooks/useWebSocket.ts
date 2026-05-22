import { useEffect, useRef, useState, useCallback } from 'react';
import type { WsMessage } from '../types';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error';

interface UseWebSocketOptions {
  tenantId: string;
  plantId: string;
  ticket?: string;
  apiKey?: string;
  onMessage?: (message: WsMessage) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  maxReconnectAttempts?: number;
  baseDelay?: number;
  enabled?: boolean;
}

const MAX_JITTER = 500;

export function useWebSocket({
  tenantId,
  plantId,
  ticket,
  apiKey,
  onMessage,
  onStatusChange,
  maxReconnectAttempts = 10,
  baseDelay = 1000,
  enabled = true,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const heartbeatRef = useRef<ReturnType<typeof setInterval>>();
  const onMessageRef = useRef(onMessage);
  const onStatusRef = useRef(onStatusChange);
  const messageQueueRef = useRef<string[]>([]);

  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onStatusRef.current = onStatusChange; }, [onStatusChange]);

  const updateStatus = useCallback((s: ConnectionStatus) => {
    setStatus(s);
    onStatusRef.current?.(s);
  }, []);

  const buildUrl = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;
    let url = `${proto}://${host}/api/v1/ws/${tenantId}/${plantId}`;
    if (ticket) url += `?ticket=${ticket}`;
    else if (apiKey) url += `?api_key=${apiKey}`;
    return url;
  }, [tenantId, plantId, ticket, apiKey]);

  const startHeartbeat = useCallback((ws: WebSocket) => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    heartbeatRef.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 25_000);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = undefined;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    try {
      const url = buildUrl();
      updateStatus(attemptRef.current > 0 ? 'reconnecting' : 'connecting');

      const ws = new WebSocket(url);

      ws.onopen = () => {
        attemptRef.current = 0;
        updateStatus('connected');
        startHeartbeat(ws);

        // Flush queued messages
        while (messageQueueRef.current.length > 0) {
          const queued = messageQueueRef.current.shift()!;
          ws.send(queued);
        }
      };

      ws.onmessage = (event) => {
        // Ignore pong responses
        if (event.data === 'pong') return;

        try {
          const msg: WsMessage = JSON.parse(event.data);
          onMessageRef.current?.(msg);
        } catch {
          console.warn('[WS] Failed to parse message:', event.data);
        }
      };

      ws.onclose = (event) => {
        stopHeartbeat();
        wsRef.current = null;

        // Auth failure — don't reconnect
        if (event.code === 4401 || event.code === 4403) {
          updateStatus('error');
          return;
        }

        if (attemptRef.current < maxReconnectAttempts) {
          const jitter = Math.random() * MAX_JITTER;
          const delay = baseDelay * Math.pow(2, attemptRef.current) + jitter;
          attemptRef.current += 1;
          updateStatus('reconnecting');
          reconnectTimerRef.current = setTimeout(connect, delay);
        } else {
          updateStatus('error');
        }
      };

      ws.onerror = () => {
        // onclose fires after onerror — reconnect logic handled there
      };

      wsRef.current = ws;
    } catch {
      updateStatus('error');
    }
  }, [enabled, buildUrl, updateStatus, startHeartbeat, stopHeartbeat, maxReconnectAttempts, baseDelay]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    stopHeartbeat();
    if (wsRef.current) {
      wsRef.current.close(1000);
      wsRef.current = null;
    }
    attemptRef.current = 0;
    updateStatus('disconnected');
  }, [stopHeartbeat, updateStatus]);

  const sendMessage = useCallback((data: Record<string, unknown>) => {
    const payload = JSON.stringify(data);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(payload);
    } else {
      // Queue for delivery on reconnect
      messageQueueRef.current.push(payload);
    }
  }, []);

  // Auto-connect on mount / reconnect on param change
  useEffect(() => {
    if (enabled && tenantId && plantId && (ticket || apiKey)) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, tenantId, plantId, ticket, apiKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  return {
    status,
    sendMessage,
    disconnect,
    reconnect: connect,
    isConnected: status === 'connected',
  };
}
