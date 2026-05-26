import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  History,
  BellRing,
  Settings,
  Database,
  Users
} from 'lucide-react';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';

const MAIN_NAV = [
  { name: 'Dashboard', to: '/', icon: LayoutDashboard },
  { name: 'Operations', to: '/operations', icon: Activity },
  { name: 'Historian', to: '/historian', icon: History },
  { name: 'Alarms', to: '/alarms', icon: BellRing },
];

const ADMIN_NAV = [
  { name: 'Data Model', to: '/admin/model', icon: Database },
  { name: 'Users', to: '/admin/users', icon: Users },
  { name: 'Settings', to: '/settings', icon: Settings },
];

export const GlobalSidebar: React.FC = () => {
  const { sidebarOpen } = useWorkspaceStore();

  if (!sidebarOpen) return null;

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex-1 py-4 overflow-y-auto">
        <nav className="px-3 space-y-1">
          <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Overview
          </div>
          {MAIN_NAV.map((item) => (
            <NavLink
              key={item.name}
              to={item.to}
              className={({ isActive }) => `
                flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors
                ${isActive
                  ? 'bg-indigo-600/10 text-indigo-400'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'}
              `}
            >
              <item.icon className="w-5 h-5 mr-3 flex-shrink-0" />
              {item.name}
            </NavLink>
          ))}
        </nav>

        <div className="mt-8">
          <nav className="px-3 space-y-1">
            <div className="px-3 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Administration
            </div>
            {ADMIN_NAV.map((item) => (
              <NavLink
                key={item.name}
                to={item.to}
                className={({ isActive }) => `
                  flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors
                  ${isActive
                    ? 'bg-indigo-600/10 text-indigo-400'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'}
                `}
              >
                <item.icon className="w-5 h-5 mr-3 flex-shrink-0" />
                {item.name}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>

      <div className="p-4 border-t border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span className="text-sm text-slate-400">System Online</span>
        </div>
      </div>
    </aside>
  );
};
