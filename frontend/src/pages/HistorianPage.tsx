import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { History } from 'lucide-react';
import { TrendChart } from '../components/data/TrendChart';

export default function HistorianPage() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <PageHeader
        title="Historian"
        description="Historical data analysis and trends."
        icon={History}
      />

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden p-6">
        <TrendChart
          title="Line 1 Production Trends"
          tagNames={['plant.line1.speed', 'plant.line1.prod_count']}
          timeRange="24h"
        />
      </div>
    </div>
  );
}
