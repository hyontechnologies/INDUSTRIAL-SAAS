import { create } from 'zustand';
import { AuthState, UserProfile, UserRole } from '../types/auth';

interface AuthStore extends AuthState {
  login: (token: string, user: UserProfile) => void;
  logout: () => void;
  switchRole: (role: UserRole) => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: {
    id: 'usr-001',
    name: 'Ravi Kumar',
    email: 'ravi@piccadily.com',
    role: 'operator',
  },
  isAuthenticated: true, // Dev default
  token: 'changeme', // Dev API key

  login: (token, user) => set({ token, user, isAuthenticated: true }),
  logout: () => set({ token: null, user: null, isAuthenticated: false }),
  switchRole: (role) => set((state) => ({
    user: state.user ? { ...state.user, role } : null
  })),
}));
