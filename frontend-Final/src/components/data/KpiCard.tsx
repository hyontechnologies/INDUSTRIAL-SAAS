import React from 'react';
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { RealtimeValue } from '../status/RealtimeValue';

interface KpiCardProps {
  title: string;
  tagName: string;
  unit: string;
  icon: LucideIcon;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  decimals?: number;
}

export const KpiCard: React.FC<KpiCardProps> = ({
  title,
  tagName,
  unit,
  icon: Icon,
  trend,
  trendValue,
  decimals = 2
}) => {
  return (
    <div className="glassmorphism-card rounded-xl p-5 flex flex-col relative overflow-hidden group">
      {/* Decorative gradient blob */}
      <div className="absolute -right-6 -top-6 w-24 h-24 bg-blue-500/10 rounded-full blur-2xl group-hover:bg-blue-500/20 transition-colors" />

      <div className="flex justify-between items-start mb-4 relative z-10">
        <h3 className="text-sm font-semibold text-slate-600 flex items-center gap-2">
          <div className="p-1.5 bg-blue-50 text-blue-600 rounded-lg">
            <Icon className="w-4 h-4" />
          </div>
          {title}
        </h3>

        {trend && (
          <div className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md ${
            trend === 'up' ? 'text-rose-600 bg-rose-50' :
            trend === 'down' ? 'text-emerald-600 bg-emerald-50' :
            'text-slate-500 bg-slate-50'
          }`}>
            {trend === 'up' && <TrendingUp className="w-3.5 h-3.5" />}
            {trend === 'down' && <TrendingDown className="w-3.5 h-3.5" />}
            {trend === 'stable' && <Minus className="w-3.5 h-3.5" />}
            {trendValue && <span>{trendValue}</span>}
          </div>
        )}
      </div>

      <div className="mt-auto relative z-10">
        <div className="text-3xl font-bold tracking-tight text-slate-800">
          <RealtimeValue tagName={tagName} unit={unit} decimals={decimals} />
        </div>
      </div>
    </div>
  );
};
