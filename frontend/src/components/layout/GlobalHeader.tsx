import React from 'react';
import { Menu, Search, Bell, Shield, User } from 'lucide-react';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import { useAuthStore } from '../../stores/useAuthStore';

export const GlobalHeader: React.FC = () => {
  const { workspace, toggleSidebar } = useWorkspaceStore();
  const { user } = useAuthStore();

  return (
    <header className="h-16 bg-slate-900 text-white flex items-center justify-between px-4 sticky top-0 z-50 border-b border-slate-800">
      <div className="flex items-center gap-4">
        <button
          onClick={toggleSidebar}
          className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
        >
          <Menu className="w-5 h-5 text-slate-300" />
        </button>

        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <span className="font-bold text-lg">I</span>
          </div>
          <span className="font-semibold text-lg tracking-tight hidden sm:block">IndustrialOS</span>
        </div>

        {workspace.organization && (
          <div className="hidden md:flex items-center gap-2 ml-4 px-3 py-1.5 bg-slate-800 rounded-lg border border-slate-700">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-medium">{workspace.organization.name}</span>
            <span className="text-xs px-2 py-0.5 bg-slate-700 rounded text-slate-300">
              {workspace.plant?.name || 'Global'}
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <div className="hidden md:flex relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search tags, assets..."
            className="pl-9 pr-4 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-slate-200 placeholder-slate-400 w-64"
          />
        </div>

        <button className="p-2 hover:bg-slate-800 rounded-lg transition-colors relative">
          <Bell className="w-5 h-5 text-slate-300" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full"></span>
        </button>

        <div className="flex items-center gap-3 pl-2 sm:pl-4 border-l border-slate-700">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-sm font-medium leading-none">{user?.name || 'User'}</span>
            <span className="text-xs text-slate-400 mt-1">{user?.role || 'operator'}</span>
          </div>
          <div className="w-8 h-8 bg-slate-800 rounded-full flex items-center justify-center border border-slate-700">
            <User className="w-4 h-4 text-slate-300" />
          </div>
        </div>
      </div>
    </header>
  );
};
