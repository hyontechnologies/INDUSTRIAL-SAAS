import React from 'react';
import { Wifi } from 'lucide-react';

export const ConnectionBadge: React.FC = () => {
  return (
    <div className="flex items-center gap-1.5 text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-md text-xs font-medium border border-emerald-100">
      <Wifi className="h-3.5 w-3.5" />
      Polling
    </div>
  );
};
