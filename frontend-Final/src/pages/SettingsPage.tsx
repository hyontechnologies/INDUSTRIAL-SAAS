import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <PageHeader
        title="Settings"
        description="Application and user preferences."
        icon={Settings}
      />

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-6">
        <p className="text-slate-600">Settings module under construction.</p>
      </div>
    </div>
  );
}
