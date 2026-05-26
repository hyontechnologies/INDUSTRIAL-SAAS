import { create } from 'zustand';
import { ThemeMode, DensityMode } from '../lib/theme';

interface UIState {
  commandPaletteOpen: boolean;
  notificationDrawerOpen: boolean;
  activeModal: string | null;
  theme: ThemeMode;
  density: DensityMode;

  setCommandPaletteOpen: (open: boolean) => void;
  setNotificationDrawerOpen: (open: boolean) => void;
  setActiveModal: (modal: string | null) => void;
  setTheme: (theme: ThemeMode) => void;
  setDensity: (density: DensityMode) => void;
}

export const useUIStore = create<UIState>((set) => ({
  commandPaletteOpen: false,
  notificationDrawerOpen: false,
  activeModal: null,
  theme: 'light',
  density: 'comfortable',

  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  setNotificationDrawerOpen: (open) => set({ notificationDrawerOpen: open }),
  setActiveModal: (modal) => set({ activeModal: modal }),
  setTheme: (theme) => set({ theme }),
  setDensity: (density) => set({ density }),
}));
