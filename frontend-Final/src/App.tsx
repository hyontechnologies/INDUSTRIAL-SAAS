import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/useAuthStore';
import { useWorkspaceStore } from './stores/useWorkspaceStore';
import { useUIStore } from './stores/useUIStore';

// Layouts
import { AuthLayout } from './layouts/AuthLayout';
import PlatformLayout from './layouts/PlatformLayout';
import { PlantLayout } from './layouts/PlantLayout';
import { AdminLayout } from './layouts/AdminLayout';
import { OnboardingLayout } from './layouts/OnboardingLayout';

// Guards
import { AuthGuard } from './components/guards/AuthGuard';
import { RoleGuard } from './components/guards/RoleGuard';

// Pages
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import OperationsHub from './pages/OperationsHub';
import PlantsOverview from './pages/PlantsOverview';
import LivePlant from './pages/plant/LivePlant';
import AlarmsConsole from './pages/plant/AlarmsConsole';
import Trends from './pages/plant/Trends';
import Reports from './pages/plant/Reports';
import Maintenance from './pages/plant/Maintenance';
import TagBrowser from './pages/TagBrowser';
import {
  SkeletonPage,
  SettingsPage,
  UsersPage,
  OrganizationsPage,
  BillingPage
} from './pages/SkeletonPages';

function App() {
  const { theme, density } = useUIStore();
  const { user } = useAuthStore();

  // Apply theme classes to body
  useEffect(() => {
    document.body.className = `density-${density} ${theme}`;
    if (user) {
      document.body.classList.add(`theme-${user.role}`);
    }
  }, [theme, density, user?.role]);

  return (
    <Routes>
      {/* Public Routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Onboarding Flow */}
      <Route element={<AuthGuard><OnboardingLayout /></AuthGuard>}>
        <Route path="/onboarding/plant" element={<SkeletonPage title="Plant Onboarding" />} />
      </Route>

      {/* Main Platform Shell */}
      <Route element={<AuthGuard><PlatformLayout /></AuthGuard>}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* Overview */}
        <Route path="/dashboard" element={<OperationsHub />} />

        {/* Operations (Global) */}
        <Route path="/plants" element={<PlantsOverview />} />

        {/* Plant Context (Nested Routing) */}
        <Route path="/plants/:plantId" element={<PlantLayout />}>
          <Route index element={<Navigate to="live" replace />} />
          <Route path="live" element={<LivePlant />} />
          <Route path="alarms" element={<AlarmsConsole />} />
          <Route path="trends" element={<Trends />} />
          <Route path="reports" element={<Reports />} />
          <Route path="maintenance" element={<Maintenance />} />
        </Route>

        {/* Engineering Tools */}
        <Route path="/telemetry" element={<SkeletonPage title="Telemetry Explorer" />} />
        <Route path="/tags" element={<TagBrowser />} />
        <Route path="/devices" element={<SkeletonPage title="Devices & I/O" />} />
        <Route path="/agents" element={<SkeletonPage title="Edge Agents" />} />

        {/* Administration */}
        <Route
          path="/"
          element={
            <RoleGuard roles={['super_admin', 'integrator_admin', 'org_admin']}>
              <AdminLayout />
            </RoleGuard>
          }
        >
          <Route path="/orgs" element={<OrganizationsPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/billing" element={<BillingPage />} />
          <Route path="/audit-logs" element={<SkeletonPage title="Audit Logs" />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        {/* AI Features */}
        <Route path="/ai-insights" element={<SkeletonPage title="AI Insights" />} />

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
