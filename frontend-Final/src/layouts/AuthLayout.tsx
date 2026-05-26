import React from 'react';
import { Outlet } from 'react-router-dom';
import { Zap } from 'lucide-react';

export const AuthLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 opacity-20 pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-blue-600 blur-[120px]"></div>
        <div className="absolute top-[60%] -right-[10%] w-[40%] h-[40%] rounded-full bg-indigo-600 blur-[100px]"></div>
      </div>

      {/* Content */}
      <div className="z-10 w-full max-w-md px-6">
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white shadow-lg shadow-blue-900/50 mb-4">
            <Zap className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Industrial Cloud</h1>
          <p className="text-slate-400 text-sm mt-1">Operations Platform v3.0</p>
        </div>

        <Outlet />
      </div>

      {/* Footer */}
      <div className="absolute bottom-6 z-10 text-[10px] text-slate-500 flex gap-4">
        <a href="#" className="hover:text-slate-300 transition-colors">Terms of Service</a>
        <span>&middot;</span>
        <a href="#" className="hover:text-slate-300 transition-colors">Privacy Policy</a>
      </div>
    </div>
  );
};
