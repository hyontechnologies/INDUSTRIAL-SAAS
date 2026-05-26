import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { Building2, Users, CreditCard, Shield, Settings } from 'lucide-react';
import { ROUTES } from '../constants/routes';

export const AdminLayout: React.FC = () => {
  const navItems = [
    { label: 'Organizations', path: ROUTES.ORGS, icon: Building2 },
    { label: 'Users & Roles', path: ROUTES.USERS, icon: Users },
    { label: 'Billing', path: ROUTES.BILLING, icon: CreditCard },
    { label: 'Audit Logs', path: ROUTES.AUDIT_LOGS, icon: Shield },
    { label: 'Global Settings', path: ROUTES.SETTINGS, icon: Settings },
  ];

  return (
    <div className="flex flex-col h-full gap-6 max-w-5xl mx-auto w-full">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Administration</h1>
        <p className="text-sm text-slate-500 mt-1">Manage platform settings, security, and billing</p>
      </div>

      <div className="flex flex-col md:flex-row gap-6 items-start">
        {/* Admin Nav Sidebar */}
        <div className="w-full md:w-64 shrink-0 flex flex-col gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700 font-semibold'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon className={`w-4 h-4`} />
                {item.label}
              </NavLink>
            );
          })}
        </div>

        {/* Admin Content Area */}
        <div className="flex-1 bg-white border border-slate-200 rounded-xl shadow-sm p-6 w-full">
          <Outlet />
        </div>
      </div>
    </div>
  );
};
