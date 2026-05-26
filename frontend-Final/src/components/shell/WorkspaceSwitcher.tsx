import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';

export const WorkspaceSwitcher: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { workspace, organizations, plants, setOrganization, setPlant, sidebarCollapsed } = useWorkspaceStore();
  const [isOpen, setIsOpen] = useState(false);

  if (sidebarCollapsed) return null;

  return (
    <div className="px-3 py-3 border-b border-slate-100 relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200 transition-colors text-left"
      >
        <span className="text-lg">{workspace.organization?.logo || '🏭'}</span>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-slate-800 truncate">{workspace.organization?.name || 'Select Org'}</p>
          <p className="text-[10px] text-slate-400 truncate flex items-center gap-1">
            {workspace.plant && (
              <span className={`h-1.5 w-1.5 rounded-full ${workspace.plant.status === 'online' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            )}
            {workspace.plant?.name || 'No Plant Selected'}
          </p>
        </div>
        <ChevronDown className={`h-3.5 w-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setIsOpen(false)} />
          <div className="absolute top-full left-3 right-3 mt-1 bg-white border border-slate-200 rounded-lg shadow-xl overflow-hidden max-h-64 overflow-y-auto z-20">
            {organizations.map(org => (
              <div key={org.id}>
                <div className="px-3 py-2 text-[10px] uppercase tracking-wider text-slate-400 font-semibold bg-slate-50 border-b border-slate-100">
                  {org.logo} {org.name}
                </div>
                {plants.filter(p => p.orgId === org.id).map(plant => (
                  <button
                    key={plant.id}
                    onClick={() => {
                      setOrganization(org);
                      setPlant(plant);
                      setIsOpen(false);

                      const pathParts = location.pathname.split('/');
                      if (pathParts[1] === 'plants' && pathParts.length > 2) {
                        pathParts[2] = plant.id;
                        navigate(pathParts.join('/'));
                      } else {
                        navigate(`/plants/${plant.id}/live`);
                      }
                    }}
                    className={`w-full text-left px-4 py-2 text-xs hover:bg-blue-50 transition-colors flex items-center gap-2 ${
                      workspace.plant?.id === plant.id ? 'bg-blue-50 text-blue-700 font-semibold' : 'text-slate-600'
                    }`}
                  >
                    <span className={`h-2 w-2 rounded-full ${
                      plant.status === 'online' ? 'bg-emerald-500' : plant.status === 'maintenance' ? 'bg-amber-500' : 'bg-slate-300'
                    }`} />
                    {plant.name}
                    <span className="ml-auto text-[9px] text-slate-400">{plant.status.toUpperCase()}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
