import React from 'react';
import { Outlet, NavLink, useParams } from 'react-router-dom';
import { Zap, Bell, TrendingUp, FileText, Wrench } from 'lucide-react';
import { PlantGuard } from '../components/guards/PlantGuard';
import { ROUTES } from '../constants/routes';

export const PlantLayout: React.FC = () => {
  const { plantId } = useParams<{ plantId: string }>();

  if (!plantId) return null;

  const navItems = [
    { label: 'Live', path: ROUTES.PLANT_LIVE(plantId), icon: Zap },
    { label: 'Alarms', path: ROUTES.PLANT_ALARMS(plantId), icon: Bell },
    { label: 'Trends', path: ROUTES.PLANT_TRENDS(plantId), icon: TrendingUp },
    { label: 'Reports', path: ROUTES.PLANT_REPORTS(plantId), icon: FileText },
    { label: 'Maintenance', path: ROUTES.PLANT_MAINTENANCE(plantId), icon: Wrench },
  ];

  return (
    <PlantGuard>
      <div className="flex flex-col h-full gap-4">
        {/* Plant Sub-navigation */}
        <div className="glass border border-white/20 rounded-xl p-2 flex overflow-x-auto shadow-sm">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                    isActive
                      ? 'bg-white/40 text-blue-800 shadow-sm'
                      : 'text-slate-700 hover:bg-white/20 hover:text-slate-900'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </NavLink>
            );
          })}
        </div>

        {/* Plant Content */}
        <div className="flex-1">
          <Outlet />
        </div>
      </div>
    </PlantGuard>
  );
};
