import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { LayoutDashboard, Activity, Package, Bell, Zap } from 'lucide-react';
import { KpiCard } from '../components/data/KpiCard';
import { GaugeCard } from '../components/data/GaugeCard';
import { TelemetryTable } from '../components/data/TelemetryTable';

export default function DashboardPage() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <PageHeader
        title="Plant Overview"
        description="High-level overview of critical plant operations and KPIs."
        icon={LayoutDashboard}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Overall OEE"
          tagName="plant.calc.oee"
          unit="%"
          icon={Activity}
        />
        <KpiCard
          title="Total Production"
          tagName="plant.line1.prod_count"
          unit="units"
          icon={Package}
        />
        <KpiCard
          title="Active Alarms"
          tagName="plant.status.active_alarms"
          unit="count"
          icon={Bell}
        />
        <KpiCard
          title="Power Usage"
          tagName="plant.power.total_kw"
          unit="kW"
          icon={Zap}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TelemetryTable />
        </div>
        <div className="space-y-6">
          <GaugeCard
            title="Line 1 Speed"
            tagName="plant.line1.speed"
            unit="units/min"
            min={0}
            max={200}
          />
          <GaugeCard
            title="System Pressure"
            tagName="plant.utilities.air_pressure"
            unit="psi"
            min={0}
            max={150}
          />
        </div>
      </div>
    </div>
  );
}
