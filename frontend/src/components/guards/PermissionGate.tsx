import React from 'react';
import { useAuthStore } from '../../stores/useAuthStore';
import { Permission } from '../../types/auth';
import { hasPermission } from '../../lib/permissions';

interface PermissionGateProps {
  permission: Permission;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({ permission, children, fallback = null }) => {
  const { user } = useAuthStore();

  if (hasPermission(user, permission)) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
};
