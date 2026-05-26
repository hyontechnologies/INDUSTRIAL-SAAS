import React, { useEffect } from 'react';
import { useParams, Navigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/useAuthStore';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import { hasPlantAccess } from '../../lib/permissions';

interface PlantGuardProps {
  children: React.ReactNode;
}

export const PlantGuard: React.FC<PlantGuardProps> = ({ children }) => {
  const { plantId } = useParams<{ plantId: string }>();
  const { user } = useAuthStore();
  const { plants, setPlant } = useWorkspaceStore();

  // If plantId is present in URL, verify access and sync to workspace context
  useEffect(() => {
    if (plantId) {
      const targetPlant = plants.find(p => p.id === plantId);
      if (targetPlant && hasPlantAccess(user, plantId)) {
        setPlant(targetPlant);
      }
    }
  }, [plantId, plants, setPlant, user]);

  if (!plantId) {
    return <Navigate to="/plants" replace />;
  }

  if (!hasPlantAccess(user, plantId)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center p-6">
        <div className="w-16 h-16 bg-rose-100 text-rose-500 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-xl font-bold text-slate-800">Access Denied</h2>
        <p className="text-slate-500 mt-2">You do not have permission to view plant: {plantId}</p>
      </div>
    );
  }

  return <>{children}</>;
};
