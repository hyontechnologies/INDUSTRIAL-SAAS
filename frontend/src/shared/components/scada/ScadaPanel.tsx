import React from 'react';
import { cn } from '../../utils/cn';

interface ScadaPanelProps {
  title: string;
  children: React.ReactNode;
  className?: string;
  headerRight?: React.ReactNode;
  glow?: boolean;
}

export function ScadaPanel({ title, children, className, headerRight, glow }: ScadaPanelProps) {
  return (
    <div className={cn(
      "flex flex-col rounded-sm overflow-hidden",
      glow ? "scada-panel-glow" : "scada-panel",
      className
    )}>
      {/* Panel Header */}
      <div className="h-8 bg-[#151d2b] border-b border-scada-border/50 flex items-center justify-between px-3">
        <h3 className="text-[11px] font-bold tracking-wider text-slate-300 uppercase">
          {title}
        </h3>
        {headerRight && (
          <div className="flex items-center gap-2">
            {headerRight}
          </div>
        )}
      </div>

      {/* Panel Body */}
      <div className="flex-1 p-3 bg-scada-panel">
        {children}
      </div>
    </div>
  );
}
