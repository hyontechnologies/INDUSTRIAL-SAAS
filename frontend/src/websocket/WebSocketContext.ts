import { createContext, useContext } from 'react';

export interface WebSocketContextValue {
  reconnect: () => void;
  disconnect: () => void;
}

export const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export const useWebSocketActions = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketActions must be used within a WebSocketProvider');
  }
  return context;
};
