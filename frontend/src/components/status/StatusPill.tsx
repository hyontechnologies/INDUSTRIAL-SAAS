import React from 'react';

type StatusType = 'online' | 'offline' | 'maintenance' | 'stale' | 'critical';

export const StatusPill: React.FC<{ status: StatusType; label?: string }> = ({ status, label }) => {
  const styles = {
    online: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    offline: 'bg-slate-100 text-slate-600 border-slate-200',
    maintenance: 'bg-amber-100 text-amber-700 border-amber-200',
    stale: 'bg-slate-200 text-slate-500 border-slate-300',
    critical: 'bg-rose-100 text-rose-700 border-rose-200',
  };

  const dots = {
    online: 'bg-emerald-500',
    offline: 'bg-slate-400',
    maintenance: 'bg-amber-500',
    stale: 'bg-slate-400',
    critical: 'bg-rose-500',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${styles[status]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dots[status]}`} />
      {label || status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};
