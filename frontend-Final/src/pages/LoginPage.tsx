import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/useAuthStore';
import { ROLE_LABELS } from '../constants/navigation';
import { UserRole } from '../types/auth';
import { Zap } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [role, setRole] = useState<UserRole>('operator');

  const from = location.state?.from?.pathname || '/dashboard';

  const handleDevLogin = (e: React.FormEvent) => {
    e.preventDefault();
    login('dev-api-key', {
      id: `dev-${role}`,
      name: `Dev ${ROLE_LABELS[role]}`,
      email: `${role}@example.com`,
      role,
    });
    navigate(from, { replace: true });
  };

  return (
    <div className="bg-white/10 backdrop-blur-md border border-white/20 p-8 rounded-2xl shadow-2xl w-full">
      <div className="text-center mb-8">
        <h2 className="text-xl font-semibold text-white">Sign In to Workspace</h2>
        <p className="text-sm text-slate-300 mt-2">Enter your credentials to access operations</p>
      </div>

      <form onSubmit={handleDevLogin} className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">Email</label>
          <input
            type="email"
            value="dev@example.com"
            disabled
            className="w-full bg-slate-900/50 border border-slate-700 text-slate-300 rounded-lg px-4 py-2.5 outline-none focus:border-blue-500 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-300 mb-1">Password</label>
          <input
            type="password"
            value="********"
            disabled
            className="w-full bg-slate-900/50 border border-slate-700 text-slate-300 rounded-lg px-4 py-2.5 outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        {/* DEV MODE ROLE SELECTOR */}
        <div className="pt-4 mt-4 border-t border-slate-800">
          <label className="block text-[10px] font-bold text-amber-500 uppercase tracking-wider mb-2">
            Dev Mode: Login As
          </label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="w-full bg-amber-500/10 border border-amber-500/30 text-amber-200 text-sm rounded-lg px-4 py-2 outline-none focus:border-amber-500 transition-colors"
          >
            {Object.entries(ROLE_LABELS).map(([key, label]) => (
              <option key={key} value={key} className="bg-slate-900 text-slate-200">
                {label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg transition-colors shadow-lg shadow-blue-900/50 mt-6 flex items-center justify-center gap-2"
        >
          Access Platform
          <Zap className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
