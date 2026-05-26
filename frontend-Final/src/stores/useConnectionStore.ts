import { create } from 'zustand';
import { ConnectionState } from '../types/websocket';

interface ConnectionStore {
  status: ConnectionState;
  lastMessageTime: Date | null;
  reconnectAttempt: number;

  setStatus: (status: ConnectionState) => void;
  recordMessage: () => void;
  incrementReconnect: () => void;
  resetReconnect: () => void;
}

export const useConnectionStore = create<ConnectionStore>((set) => ({
  status: 'disconnected',
  lastMessageTime: null,
  reconnectAttempt: 0,

  setStatus: (status) => set({ status }),
  recordMessage: () => set({ lastMessageTime: new Date() }),
  incrementReconnect: () => set((state) => ({ reconnectAttempt: state.reconnectAttempt + 1 })),
  resetReconnect: () => set({ reconnectAttempt: 0 }),
}));
