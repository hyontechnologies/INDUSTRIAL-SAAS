import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './layout';
import LoginPage from '../features/auth/LoginPage';
import { AuthGuard } from '../features/auth/AuthGuard';
import DashboardPage from '../features/dashboard/DashboardPage';
import AlarmsPage from '../features/alarms/AlarmsPage';
import TelemetryPage from '../features/telemetry/TelemetryPage';
import HistorianPage from '../features/historian/HistorianPage';
import PlantsPage from '../features/plants/PlantsPage';
import AdminPage from '../features/admin/AdminPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <AuthGuard>
        <Layout />
      </AuthGuard>
    ),
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: 'telemetry',
        element: <TelemetryPage />,
      },
      {
        path: 'alarms',
        element: <AlarmsPage />,
      },
      {
        path: 'historian',
        element: <HistorianPage />,
      },
      {
        path: 'tags',
        element: <TelemetryPage />,
      },
      {
        path: 'plants',
        element: <PlantsPage />,
      },
      {
        path: 'admin',
        element: <AdminPage />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);
