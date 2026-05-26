import React from 'react';
import { Calendar } from 'lucide-react';

export const DateRangePicker: React.FC = () => {
  return (
    <button className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors shadow-sm">
      <Calendar className="w-4 h-4 text-slate-400" />
      <span>Last 24 Hours</span>
    </button>
  );
};
