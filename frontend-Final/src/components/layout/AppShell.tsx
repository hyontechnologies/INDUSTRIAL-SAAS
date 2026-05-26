import React from 'react';
import { Outlet } from 'react-router-dom';
import { GlobalHeader } from './GlobalHeader';
import { GlobalSidebar } from './GlobalSidebar';
import { ErrorBoundary } from '../common/ErrorBoundary';

export const AppShell: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">
      <GlobalHeader />
      <div className="flex-1 flex overflow-hidden">
        <GlobalSidebar />
        <main className="flex-1 overflow-y-auto bg-slate-50 p-4 sm:p-6 lg:p-8">
          <ErrorBoundary>
            <div className="max-w-7xl mx-auto space-y-6">
              <Outlet />
            </div>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
};
