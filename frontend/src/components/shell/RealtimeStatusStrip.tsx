import React from 'react';
import { useWebSocket } from '../../websocket/useWebSocket';
import { useAlarmStore } from '../../stores/useAlarmStore';
import { formatTimeOnly } from '../../utils/formatters';

export const RealtimeStatusStrip: React.FC = () => {
  const { status, lastMessageTime, reconnectAttempt } = useWebSocket();
  const activeCount = useAlarmStore(state => state.getActiveCount());

  const getStatusColor = () => {
    switch (status) {
      case 'connected': return 'bg-emerald-500';
      case 'connecting':
      case 'reconnecting': return 'bg-amber-400 animate-pulse';
      case 'stale': return 'bg-slate-400';
      case 'failed':
      case 'disconnected': return 'bg-rose-500';
      default: return 'bg-slate-300';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'connected': return `Live Data — Last message: ${lastMessageTime ? formatTimeOnly(lastMessageTime.toISOString()) : 'Waiting...'}`;
      case 'connecting': return 'Connecting to server...';
      case 'reconnecting': return `Reconnecting (Attempt ${reconnectAttempt})...`;
      case 'stale': return 'Connection stale — Displaying last known values';
      case 'failed': return 'Connection failed';
      case 'disconnected': return 'Disconnected';
      default: return 'Unknown state';
    }
  };

  return (
    <div className={`h-6 w-full flex items-center px-4 text-[10px] font-semibold tracking-wider text-white ${status === 'connected' ? 'bg-slate-800' : 'bg-slate-700'}`}>
      <div className="flex items-center gap-2 flex-1">
        <span className={`h-1.5 w-1.5 rounded-full ${getStatusColor()}`} />
        <span>{getStatusText()}</span>
      </div>

      {activeCount > 0 && (
        <div className="flex items-center gap-1.5 text-rose-300">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-rose-500"></span>
          </span>
          <span>{activeCount} ACTIVE ALARMS</span>
        </div>
      )}
    </div>
  );
};
