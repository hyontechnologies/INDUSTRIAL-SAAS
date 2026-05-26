import React, { useEffect, useRef } from 'react';
import { SocketManager } from './SocketManager';
import { ConnectionStateManager } from './ConnectionStateManager';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useAuthStore } from '../stores/useAuthStore';
import { WebSocketContext, WebSocketContextValue } from './WebSocketContext';

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const socketManager = useRef(new SocketManager());
  const stateManager = useRef(new ConnectionStateManager());

  const { workspace } = useWorkspaceStore();
  const { token } = useAuthStore();

  useEffect(() => {
    const currentStateManager = stateManager.current;
    currentStateManager.start();
    return () => currentStateManager.stop();
  }, []);

  useEffect(() => {
    const orgId = workspace.organization?.id;
    const plantId = workspace.plant?.id;

    // Only connect if we have full context and auth
    if (orgId && plantId && token) {
      socketManager.current.connect(orgId, plantId, token);
    } else {
      socketManager.current.disconnect();
    }

    return () => {
      // Don't disconnect here on strict mode remounts, SocketManager handles it via connect() overriding
    };
  }, [workspace.organization?.id, workspace.plant?.id, token]);

  const value: WebSocketContextValue = {
    reconnect: () => {
      if (workspace.organization?.id && workspace.plant?.id && token) {
        socketManager.current.connect(workspace.organization.id, workspace.plant.id, token);
      }
    },
    disconnect: () => socketManager.current.disconnect(),
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
