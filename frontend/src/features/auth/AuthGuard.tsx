import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../../shared/stores/useAppStore';
import { supabase } from '../../shared/api/supabase';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const setUser = useAppStore((s) => s.setUser);
  const location = useLocation();
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        localStorage.setItem('industrial_auth_token', session.access_token);
        const tenant_id = session.user.app_metadata?.tenant_id || session.user.user_metadata?.tenant_id || 'piccadily';
        const role = session.user.app_metadata?.role || 'operator';
        const plant_ids = session.user.app_metadata?.plant_ids || [];

        setUser({
          user_id: session.user.id,
          tenant_id,
          email: session.user.email || '',
          role,
          plant_ids,
          is_edge: false,
        });
      }
      setIsInitializing(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        localStorage.setItem('industrial_auth_token', session.access_token);
        const tenant_id = session.user.app_metadata?.tenant_id || session.user.user_metadata?.tenant_id || 'piccadily';
        const role = session.user.app_metadata?.role || 'operator';
        const plant_ids = session.user.app_metadata?.plant_ids || [];

        setUser({
          user_id: session.user.id,
          tenant_id,
          email: session.user.email || '',
          role,
          plant_ids,
          is_edge: false,
        });
      } else {
        localStorage.removeItem('industrial_auth_token');
        setUser(null);
      }
    });

    return () => subscription.unsubscribe();
  }, [setUser]);

  if (isInitializing) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-950">
        <div className="w-8 h-8 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
