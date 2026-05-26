import React from 'react';
import { Menu, Search, Bell, Shield, User } from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useUIStore } from '../stores/useUIStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useNotificationStore } from '../stores/useNotificationStore';
import { ConnectionBadge } from './status/ConnectionBadge';

export default function GlobalHeader() {
  const { toggleSidebar } = useWorkspaceStore();
  const { setCommandPaletteOpen, setNotificationDrawerOpen } = useUIStore();
  const { user } = useAuthStore();
  const unreadCount = useNotificationStore(state => state.unreadCount);

  return (
    <header className="h-16 glass border-b border-white/20 flex items-center justify-between px-4 sticky top-0 z-20 shadow-sm transition-all duration-300">
      <div className="flex items-center gap-4">
        <button
          onClick={toggleSidebar}
          className="p-2 -ml-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        >
          <Menu className="w-5 h-5" />
        </button>

        <ConnectionBadge />
      </div>

      <div className="flex items-center gap-3">
        {/* Command Palette Trigger */}
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors group mr-2"
        >
          <Search className="w-4 h-4 text-slate-400 group-hover:text-slate-600 transition-colors" />
          <span className="text-xs font-medium">Search...</span>
          <div className="flex items-center gap-0.5 ml-8">
            <kbd className="bg-white border border-slate-200 rounded px-1.5 py-0.5 text-[10px] font-mono shadow-sm">Ctrl</kbd>
            <kbd className="bg-white border border-slate-200 rounded px-1.5 py-0.5 text-[10px] font-mono shadow-sm">K</kbd>
          </div>
        </button>

        {/* Mobile search icon */}
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="sm:hidden p-2 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <Search className="w-5 h-5" />
        </button>

        {/* Notifications */}
        <button
          onClick={() => setNotificationDrawerOpen(true)}
          className="relative p-2 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-blue-500 rounded-full border-2 border-white"></span>
          )}
        </button>

        <div className="h-6 w-px bg-slate-200 mx-1 hidden sm:block"></div>

        {/* User Profile Dropdown (Simplified for now) */}
        <div className="flex items-center gap-3 pl-1">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-sm font-semibold text-slate-700 leading-none">{user?.name || 'User'}</span>
            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mt-1">{user?.role?.replace('_', ' ') || 'Role'}</span>
          </div>
          <div className="h-9 w-9 bg-gradient-to-br from-slate-100 to-slate-200 border border-slate-300 rounded-full flex items-center justify-center shadow-inner text-slate-600">
            {user?.role === 'super_admin' ? <Shield className="w-4 h-4" /> : <User className="w-4 h-4" />}
          </div>
        </div>
      </div>
    </header>
  );
}
