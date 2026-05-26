import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { BellRing } from 'lucide-react';
import { AlarmTable } from '../components/data/AlarmTable';

export default function AlarmsPage() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <PageHeader
        title="Alarms & Events"
        description="Monitor, acknowledge, and analyze system alarms."
        icon={BellRing}
      />

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-6">
          <AlarmTable />
        </div>
      </div>
    </div>
  );
}
