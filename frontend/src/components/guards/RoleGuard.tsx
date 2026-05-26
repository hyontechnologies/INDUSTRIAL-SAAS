import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/useAuthStore';
import { UserRole } from '../../types/auth';

interface RoleGuardProps {
  roles: UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({ roles, children, fallback }) => {
  const { user } = useAuthStore();

  if (!user || !roles.includes(user.role)) {
    if (fallback !== undefined) return <>{fallback}</>;
    // Default to redirect to dashboard if unauthorized
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
