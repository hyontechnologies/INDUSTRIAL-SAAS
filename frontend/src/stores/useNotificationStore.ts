import { create } from 'zustand';

export interface AppNotification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  timestamp: string;
  read: boolean;
  link?: string;
}

interface NotificationState {
  notifications: AppNotification[];
  unreadCount: number;

  addNotification: (notification: Omit<AppNotification, 'id' | 'timestamp' | 'read'>) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  unreadCount: 0,

  addNotification: (notification) => set((state) => {
    const newNotif: AppNotification = {
      ...notification,
      id: Math.random().toString(36).substring(7),
      timestamp: new Date().toISOString(),
      read: false
    };
    const next = [newNotif, ...state.notifications].slice(0, 50);
    return { notifications: next, unreadCount: next.filter(n => !n.read).length };
  }),

  markRead: (id) => set((state) => {
    const next = state.notifications.map(n => n.id === id ? { ...n, read: true } : n);
    return { notifications: next, unreadCount: next.filter(n => !n.read).length };
  }),

  markAllRead: () => set((state) => {
    const next = state.notifications.map(n => ({ ...n, read: true }));
    return { notifications: next, unreadCount: 0 };
  }),

  clearAll: () => set({ notifications: [], unreadCount: 0 }),
}));
