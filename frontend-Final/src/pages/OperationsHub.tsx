import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { SectionHeader } from '../components/layout/SectionHeader';
import { KpiCard } from '../components/data/KpiCard';
import { GaugeCard } from '../components/data/GaugeCard';
import { EChartsTrend } from '../components/data/EChartsTrend';
import { AlarmTable } from '../components/data/AlarmTable';
import { DateRangePicker } from '../components/controls/DateRangePicker';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { useAlarmStore } from '../stores/useAlarmStore';
import { LayoutDashboard, Thermometer, Gauge, Wind, Droplets } from 'lucide-react';

export default function OperationsHub() {
  const { workspace } = useWorkspaceStore();
  const activeCount = useAlarmStore(state => state.getActiveCount());

  return (
    <div className="flex flex-col gap-6 animate-fade-in">
      <PageHeader
        title={`${workspace.plant?.name || 'Global'} Overview`}
        description="Real-time telemetry and operational status across all systems."
        icon={LayoutDashboard}
        actions={<DateRangePicker />}
      />

      {/* Primary KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Main Steam Temp"
          tagName="TT-201"
          unit="°C"
          icon={Thermometer}
          trend="up"
          trendValue="+1.2%"
        />
        <KpiCard
          title="Steam Pressure"
          tagName="PT-201"
          unit="bar"
          icon={Gauge}
          trend="stable"
        />
        <KpiCard
          title="Feedwater Flow"
          tagName="FT-101"
          unit="t/h"
          icon={Droplets}
          trend="down"
          trendValue="-0.5%"
        />
        <KpiCard
          title="FD Fan Vibration"
          tagName="FD_RPM"
          unit="mm/s"
          icon={Wind}
          trend="up"
          trendValue="+4.2%"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Main Trend */}
        <div className="xl:col-span-2 flex flex-col">
          <SectionHeader title="Process Trends" />
          <div className="flex-1 min-h-[400px]">
            <EChartsTrend
              title="Boiler Performance Metrics"
              tagNames={['TT-201', 'PT-201', 'FT-101']}
            />
          </div>
        </div>

        {/* Gauges */}
        <div className="flex flex-col">
          <SectionHeader title="Critical Limits" />
          <div className="flex flex-col gap-4 flex-1">
            <GaugeCard
              title="Drum Level"
              tagName="LT-201"
              unit="%"
              min={-100}
              max={100}
            />
            <GaugeCard
              title="Furnace Pressure"
              tagName="DT-401"
              unit="mmwc"
              min={-50}
              max={50}
            />
          </div>
        </div>
      </div>

      {/* Alarms */}
      <div className="flex flex-col mt-4">
        <SectionHeader title="Active Alarms" count={activeCount} />
        <AlarmTable />
      </div>
    </div>
  );
}
