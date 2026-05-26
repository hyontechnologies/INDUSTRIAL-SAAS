import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import * as Icons from 'lucide-react';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useAuthStore } from '../stores/useAuthStore';
import { getNavForRole } from '../constants/navigation';
import { WorkspaceSwitcher } from './shell/WorkspaceSwitcher';

export default function Sidebar() {
  const { sidebarCollapsed, sidebarOpen, setSidebarOpen } = useWorkspaceStore();
  const { user } = useAuthStore();
  const location = useLocation();

  const navItems = user ? getNavForRole(user.role) : [];

  // Group nav items by category
  const groupedNav = navItems.reduce((acc, item) => {
    if (!acc[item.category]) acc[item.category] = [];
    acc[item.category].push(item);
    return acc;
  }, {} as Record<string, typeof navItems>);

  return (
    <aside
      className={`fixed top-0 left-0 h-screen glass border-r border-white/20 z-40 transition-all duration-300 flex flex-col shadow-[4px_0_24px_rgba(0,0,0,0.02)] ${
        sidebarCollapsed ? 'w-[72px]' : 'w-[260px]'
      } ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
    >
      {/* Brand / Logo Area */}
      <div className="h-16 flex items-center px-4 border-b border-white/20 shrink-0">
        <div className={`flex items-center gap-3 overflow-hidden ${sidebarCollapsed ? 'justify-center w-full' : ''}`}>
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shrink-0 shadow-sm shadow-blue-500/20">
            <Icons.Zap className="w-5 h-5 text-white" />
          </div>
          {!sidebarCollapsed && (
            <div className="flex flex-col">
              <span className="font-bold text-slate-800 text-sm tracking-tight leading-tight">Industrial Cloud</span>
              <span className="text-[10px] font-medium text-slate-400">OPERATIONS PLATFORM</span>
            </div>
          )}
        </div>
      </div>

      <WorkspaceSwitcher />

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto py-4 scrollbar-thin">
        {Object.entries(groupedNav).map(([category, items]) => (
          <div key={category} className="mb-6 last:mb-0">
            {!sidebarCollapsed && (
              <h3 className="px-5 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                {category}
              </h3>
            )}

            <nav className="space-y-0.5 px-3">
              {items.map((item) => {
                const IconComponent = (Icons as Record<string, React.ComponentType<{ className?: string }>>)[item.icon];

                return (
                  <NavLink
                    key={item.id}
                    to={item.path}
                    onClick={() => {
                      if (window.innerWidth < 1024) setSidebarOpen(false);
                    }}
                    className={({ isActive }) => {
                      // Check if the current route starts with this nav item's path, but avoid partial matches
                      // Example: path="/plants" should match "/plants" and "/plants/123/live"
                      // but not match "/" when path is "/"
                      const isPathActive = isActive || (
                        item.path !== '/' &&
                        location.pathname.startsWith(item.path)
                      );

                      return `flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 group relative ${
                        isPathActive
                          ? 'bg-white/40 text-blue-800 font-semibold shadow-sm'
                          : 'text-slate-700 hover:bg-white/20 hover:text-slate-900'
                      } ${sidebarCollapsed ? 'justify-center' : ''}`;
                    }}
                  >
                    <IconComponent className={`w-[18px] h-[18px] shrink-0 transition-colors ${
                      location.pathname.startsWith(item.path) ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'
                    }`} />

                    {!sidebarCollapsed && (
                      <div className="flex-1 flex justify-between items-center">
                        <span className="text-sm truncate">{item.label}</span>
                        {item.badge && (
                          <span className="bg-blue-100 text-blue-700 text-[10px] font-bold px-2 py-0.5 rounded-full">
                            {item.badge}
                          </span>
                        )}
                      </div>
                    )}

                    {sidebarCollapsed && (
                      <div className="absolute left-14 bg-slate-800 text-white text-xs px-2.5 py-1.5 rounded-md opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50 shadow-lg pointer-events-none">
                        {item.label}
                        <div className="absolute -left-1 top-1/2 -translate-y-1/2 border-4 border-transparent border-r-slate-800" />
                      </div>
                    )}
                  </NavLink>
                );
              })}
            </nav>
          </div>
        ))}
      </div>
    </aside>
  );
}
