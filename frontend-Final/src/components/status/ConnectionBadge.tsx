import React from 'react';
import { Wifi, WifiOff } from 'lucide-react';
import { useWebSocket } from '../../websocket/useWebSocket';

export const ConnectionBadge: React.FC = () => {
  const { status } = useWebSocket();

  if (status === 'connected') {
    return (
      <div className="flex items-center gap-1.5 text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-md text-xs font-medium border border-emerald-100">
        <Wifi className="h-3.5 w-3.5" />
        Connected
      </div>
    );
  }

  if (status === 'connecting' || status === 'reconnecting') {
    return (
      <div className="flex items-center gap-1.5 text-amber-600 bg-amber-50 px-2.5 py-1 rounded-md text-xs font-medium border border-amber-100">
        <Wifi className="h-3.5 w-3.5 animate-pulse" />
        Connecting...
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-rose-600 bg-rose-50 px-2.5 py-1 rounded-md text-xs font-medium border border-rose-100">
      <WifiOff className="h-3.5 w-3.5" />
      Offline
    </div>
  );
};
