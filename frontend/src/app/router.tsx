/* eslint-disable react-refresh/only-export-components */
import React, { Suspense } from 'react';
import { createBrowserRouter, Navigate, useRouteError } from 'react-router-dom';
import { Layout } from './layout';

const DashboardPage = React.lazy(() => import('../features/dashboard/DashboardPage'));
const AlarmsPage = React.lazy(() => import('../features/alarms/AlarmsPage'));
const TelemetryPage = React.lazy(() => import('../features/telemetry/TelemetryPage'));
const HistorianPage = React.lazy(() => import('../features/historian/HistorianPage'));
const PlantsPage = React.lazy(() => import('../features/plants/PlantsPage'));
const AdminPage = React.lazy(() => import('../features/admin/AdminPage'));

const TrendCenterPage = React.lazy(() => import('../features/trends/TrendCenterPage'));
const ReportsPage = React.lazy(() => import('../features/reports/ReportsPage'));

// Generic loading fallback
function PageLoader() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-slate-950">
      <div className="flex flex-col items-center gap-4">
        <div className="relative flex h-10 w-10">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-20"></span>
          <span className="relative inline-flex rounded-full h-10 w-10 bg-blue-500/40"></span>
        </div>
        <p className="text-sm font-medium text-slate-400 animate-pulse">Loading Module...</p>
      </div>
    </div>
  );
}

// Generic Error Boundary for React Router
function ErrorBoundary() {
  const error = useRouteError();
  console.error("Router Boundary Error:", error);
  return (
    <div className="flex h-full w-full flex-col items-center justify-center p-8 text-center">
      <div className="mb-4 rounded-full bg-red-500/10 p-4">
        <div className="h-8 w-8 text-red-400">⚠️</div>
      </div>
      <h2 className="mb-2 text-xl font-bold text-slate-200">Failed to load module</h2>
      <p className="mb-6 text-sm text-slate-400">
        There was an error loading this section of the application.
      </p>
      <button
        onClick={() => window.location.reload()}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
      >
        Reload Application
      </button>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const withSuspense = (Component: React.LazyExoticComponent<any>) => (
  <Suspense fallback={<PageLoader />}>
    <Component />
  </Suspense>
);

// eslint-disable-next-line react-refresh/only-export-components
export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    errorElement: <ErrorBoundary />,
    children: [
      {
        index: true,
        element: withSuspense(DashboardPage),
      },
      {
        path: 'telemetry',
        element: withSuspense(TelemetryPage),
      },
      {
        path: 'alarms',
        element: withSuspense(AlarmsPage),
      },
      {
        path: 'historian',
        element: withSuspense(HistorianPage),
      },
      {
        path: 'tags',
        element: withSuspense(TelemetryPage),
      },
      {
        path: 'trends/*',
        element: withSuspense(TrendCenterPage),
      },
      {
        path: 'reports/*',
        element: withSuspense(ReportsPage),
      },
      {
        path: 'plants',
        element: withSuspense(PlantsPage),
      },
      {
        path: 'admin',
        element: withSuspense(AdminPage),
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);
