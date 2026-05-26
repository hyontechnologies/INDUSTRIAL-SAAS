import { Cpu, Server, GitBranch, CreditCard, Radio, Brain, Settings, Building2, Users, Shield, Factory, Bell, TrendingUp, FileText } from 'lucide-react';

// Generic skeleton page factory for integrator routes that are not yet built out
export function SkeletonPage({ title, description, icon: Icon }: {
  title: string;
  description?: string;
  icon?: any;
}) {
  const features = [
    'Real-time monitoring dashboard',
    'Configuration management',
    'Historical data analysis',
    'Export & reporting capabilities',
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
          {Icon && (
            <div className="p-2 rounded-lg bg-blue-100">
              <Icon className="h-5 w-5 text-blue-600" />
            </div>
          )}
          {title}
        </h1>
        <p className="text-sm text-slate-500 mt-1">{description}</p>
      </div>

      {/* Under Construction Card */}
      <div className="glassmorphism p-8 rounded-2xl flex flex-col items-center justify-center text-center min-h-[300px]">
        {Icon && (
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center mb-4">
            <Icon className="h-8 w-8 text-blue-600" />
          </div>
        )}
        <h2 className="text-lg font-bold text-slate-800">{title} Module</h2>
        <p className="text-sm text-slate-500 mt-2 max-w-md">
          This module is part of the Industrial Operations Cloud platform architecture.
          It will be fully implemented in the next development phase.
        </p>

        {/* Feature Preview */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
          {features.map((f, i) => (
            <div key={i} className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-500">
              <div className="h-1.5 w-1.5 rounded-full bg-blue-400" />
              {f}
            </div>
          ))}
        </div>

        <div className="mt-6 px-4 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 font-medium">
          🚧 Module under development — Architecture defined in IA Blueprint
        </div>
      </div>
    </div>
  );
}

// ── EXPORTED SKELETON PAGES ──

// ENGINEERING
export function TelemetryPage() {
  return <SkeletonPage title="Telemetry Explorer" description="Browse raw telemetry streams, inspect data quality, and validate tag mappings." icon={Radio} />;
}
export function TagsPage() {
  return <SkeletonPage title="Tag Management" description="Manage I/O tags, scaling, and deadbands." icon={GitBranch} />;
}
export function DevicesPage() {
  return <SkeletonPage title="Device Management" description="Manage and monitor all connected field devices, PLCs, and RTUs." icon={Cpu} />;
}
export function EdgeAgentsPage() {
  return <SkeletonPage title="Edge Agents" description="Deploy, configure, and monitor edge computing agents across plant networks." icon={Server} />;
}

// ADMIN
export function OrganizationsPage() {
  return <SkeletonPage title="Organizations" description="Manage tenants, workspaces, and cross-plant visibility." icon={Building2} />;
}
export function UsersPage() {
  return <SkeletonPage title="User Management" description="Manage roles, access control, and onboarding." icon={Users} />;
}
export function BillingPage() {
  return <SkeletonPage title="Billing & Usage" description="Track platform usage, manage subscriptions, and view invoicing history." icon={CreditCard} />;
}
export function AuditLogsPage() {
  return <SkeletonPage title="Audit Logs" description="Track all user and system actions." icon={Shield} />;
}
export function AIInsightsPage() {
  return <SkeletonPage title="AI Insights" description="Predictive maintenance, anomaly detection, and intelligent alerting powered by ML models." icon={Brain} />;
}
export function SettingsPage() {
  return <SkeletonPage title="Platform Settings" description="Global configuration, API keys, webhooks, and audit log settings." icon={Settings} />;
}

// OPERATIONS (Fallback for un-implemented)
export function PlantsPage() {
  return <SkeletonPage title="Plants Overview" description="Manage plant configurations and high-level status." icon={Factory} />;
}
export function LivePlantPage() {
  return <SkeletonPage title="Live Plant Twin" description="Full-screen real-time plant visualization with interactive P&ID diagrams." icon={Radio} />;
}
export function AlarmsPage() {
  return <SkeletonPage title="Alarms Console" description="Global alarm state, ACK workflow, and history." icon={Bell} />;
}
export function TrendsPage() {
  return <SkeletonPage title="Trend Analysis" description="Advanced multi-variable trend comparison with historian data playback." icon={TrendingUp} />;
}
export function ReportsPage() {
  return <SkeletonPage title="Reporting Engine" description="Generate compliance reports, shift logs, and operational summaries." icon={FileText} />;
}
