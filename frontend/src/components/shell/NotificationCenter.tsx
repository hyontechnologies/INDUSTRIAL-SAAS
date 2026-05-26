import React, { useEffect, useRef } from 'react';
import { X, Check, Bell, Info, AlertTriangle, CheckCircle } from 'lucide-react';
import { useUIStore } from '../../stores/useUIStore';
import { useNotificationStore } from '../../stores/useNotificationStore';
import { formatDuration } from '../../utils/formatters';

export const NotificationCenter: React.FC = () => {
  const { notificationDrawerOpen, setNotificationDrawerOpen } = useUIStore();
  const { notifications, unreadCount, markRead, markAllRead, clearAll } = useNotificationStore();
  const drawerRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = React.useState(() => Date.now());

  useEffect(() => {
    if (notificationDrawerOpen) {
      const startTimer = setTimeout(() => setNow(Date.now()), 0);
      const timer = setInterval(() => setNow(Date.now()), 10000);
      return () => {
        clearTimeout(startTimer);
        clearInterval(timer);
      };
    }
  }, [notificationDrawerOpen]);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (notificationDrawerOpen && drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        setNotificationDrawerOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [notificationDrawerOpen, setNotificationDrawerOpen]);

  if (!notificationDrawerOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm"
        onClick={() => setNotificationDrawerOpen(false)}
      />
      <div
        ref={drawerRef}
        className="relative w-full max-w-sm bg-white h-full shadow-2xl flex flex-col animate-slide-in-right"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Bell className="h-4.5 w-4.5 text-slate-700" />
            <h2 className="font-semibold text-slate-800">Notifications</h2>
            {unreadCount > 0 && (
              <span className="bg-blue-100 text-blue-700 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                {unreadCount} new
              </span>
            )}
          </div>
          <button
            onClick={() => setNotificationDrawerOpen(false)}
            className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100 bg-slate-50 text-xs">
          <button
            onClick={markAllRead}
            disabled={unreadCount === 0}
            className="text-blue-600 font-medium disabled:opacity-50 flex items-center gap-1"
          >
            <Check className="h-3 w-3" /> Mark all read
          </button>
          <button
            onClick={clearAll}
            disabled={notifications.length === 0}
            className="text-slate-500 font-medium disabled:opacity-50"
          >
            Clear all
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 space-y-3 px-6 text-center">
              <Bell className="h-8 w-8 text-slate-300" />
              <p className="text-sm">You're all caught up</p>
              <p className="text-xs">No new notifications right now.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {notifications.map(notif => {
                const Icon = notif.type === 'error' ? AlertTriangle :
                             notif.type === 'success' ? CheckCircle :
                             notif.type === 'warning' ? AlertTriangle : Info;

                const iconColor = notif.type === 'error' ? 'text-rose-500' :
                                  notif.type === 'success' ? 'text-emerald-500' :
                                  notif.type === 'warning' ? 'text-amber-500' : 'text-blue-500';

                return (
                  <div
                    key={notif.id}
                    className={`p-4 flex gap-3 hover:bg-slate-50 transition-colors ${!notif.read ? 'bg-blue-50/30' : ''}`}
                    onClick={() => markRead(notif.id)}
                  >
                    <div className="shrink-0 mt-0.5">
                      <Icon className={`h-4.5 w-4.5 ${iconColor}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm ${!notif.read ? 'font-semibold text-slate-900' : 'font-medium text-slate-700'}`}>
                        {notif.title}
                      </p>
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                        {notif.message}
                      </p>
                      <p className="text-[10px] text-slate-400 mt-2 font-medium">
                        {formatDuration(now - new Date(notif.timestamp).getTime())}
                      </p>
                    </div>
                    {!notif.read && (
                      <div className="shrink-0 mt-1.5">
                        <div className="h-2 w-2 bg-blue-500 rounded-full" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
