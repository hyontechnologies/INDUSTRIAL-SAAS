import React from 'react';
import { Outlet } from 'react-router-dom';
import { Zap } from 'lucide-react';

export const OnboardingLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-stone-50 flex flex-col">
      {/* Simple Header */}
      <header className="h-16 bg-white border-b border-slate-200 flex items-center px-6 shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center text-white">
            <Zap className="h-4 w-4" />
          </div>
          <span className="font-bold text-slate-800">Plant Onboarding Wizard</span>
        </div>
        <div className="ml-auto text-sm text-slate-500">
          Step <span className="font-semibold text-slate-900">1</span> of 5
        </div>
      </header>

      {/* Progress Bar */}
      <div className="h-1 w-full bg-slate-100">
        <div className="h-full bg-blue-600 w-1/5 transition-all duration-500"></div>
      </div>

      {/* Content */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-2xl bg-white border border-slate-200 rounded-2xl shadow-sm p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
