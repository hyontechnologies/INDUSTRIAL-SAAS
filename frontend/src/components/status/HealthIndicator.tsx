import React from 'react';

export const HealthIndicator: React.FC<{ health: number; label?: string }> = ({ health, label }) => {
  let color = 'bg-emerald-500';
  if (health < 50) color = 'bg-rose-500';
  else if (health < 80) color = 'bg-amber-500';

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 bg-slate-100 h-2 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${health}%` }} />
      </div>
      <span className="text-xs font-medium font-mono text-slate-600">{health}%</span>
      {label && <span className="text-xs text-slate-500">{label}</span>}
    </div>
  );
};
