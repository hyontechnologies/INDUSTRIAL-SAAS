import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../../shared/stores/useAppStore';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
