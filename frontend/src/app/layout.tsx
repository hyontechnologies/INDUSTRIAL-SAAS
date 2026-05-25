import { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import {
  Activity,
  Bell,
  Factory,
  LayoutDashboard,
  Settings,
  History,
  Tags,
  ChevronLeft,
  ChevronRight,
  Wifi,
  WifiOff,
  AlertTriangle,
  Zap,
} from 'lucide-react';
import { useAppStore } from '../shared/stores/useAppStore';
import { cn } from '../shared/utils/cn';
import { useWebSocket } from '../shared/hooks/useWebSocket';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/telemetry', icon: Activity, label: 'Telemetry' },
  { to: '/alarms', icon: Bell, label: 'Alarms' },
  { to: '/historian', icon: History, label: 'Historian' },
  { to: '/tags', icon: Tags, label: 'Tag Browser' },
  { to: '/plants', icon: Factory, label: 'Plants' },
  { to: '/admin', icon: Settings, label: 'Admin' },
];

function ConnectionBadge() {
  const status = useAppStore((s) => s.connectionStatus);
  const statusConfig = {
    connected: { icon: Wifi, color: 'text-emerald-400', bg: 'bg-emerald-400/10', label: 'Live' },
    connecting: { icon: Zap, color: 'text-amber-400', bg: 'bg-amber-400/10', label: 'Connecting' },
    reconnecting: { icon: Zap, color: 'text-amber-400', bg: 'bg-amber-400/10', label: 'Reconnecting' },
    disconnected: { icon: WifiOff, color: 'text-slate-500', bg: 'bg-slate-500/10', label: 'Offline' },
    error: { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-400/10', label: 'Error' },
  };
  const cfg = statusConfig[status];
  const Icon = cfg.icon;

  return (
    <div className={cn('flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium', cfg.bg, cfg.color)}>
      <Icon className="w-3.5 h-3.5" />
      <span>{cfg.label}</span>
      {status === 'connected' && <span className="relative flex h-2 w-2"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" /><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" /></span>}
    </div>
  );
}

function AlarmBadge() {
  const alarmCount = useAppStore((s) => s.alarmCount);
  const criticalCount = useAppStore((s) => s.criticalCount);
  if (alarmCount === 0) return null;

  return (
    <div className={cn(
      'flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-bold',
      criticalCount > 0 ? 'bg-red-500/20 text-red-400 animate-pulse' : 'bg-amber-500/20 text-amber-400'
    )}>
      <Bell className="w-3 h-3" />
      {alarmCount}
    </div>
  );
}

export function Layout() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed);
  const setSidebarCollapsed = useAppStore((s) => s.setSidebarCollapsed);
  const selectedPlantId = useAppStore((s) => s.selectedPlantId);

  const user = useAppStore((s) => s.user);
  const handleWsMessage = useAppStore((s) => s.handleWsMessage);
  const setConnectionStatus = useAppStore((s) => s.setConnectionStatus);

  const [wsTicket, setWsTicket] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    fetch('/api/v1/ticket/ws', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('industrial_auth_token')}` }
    })
    .then(r => r.json())
    .then(d => setWsTicket(d.ticket))
    .catch(err => console.error('Failed to get WS ticket', err));
  }, [user]);

  useWebSocket({
    tenantId: user?.tenant_id || 'piccadily',
    plantId: selectedPlantId || 'BOILER_PLC_01',
    ticket: wsTicket ?? undefined,
    onMessage: handleWsMessage,
    onStatusChange: setConnectionStatus,
    enabled: !!user && !!wsTicket,
  });

  return (
    <div className="flex h-screen bg-slate-950 text-slate-50 font-sans overflow-hidden">
      {/* ── Sidebar ────────────────────────────────────────────── */}
      <aside className={cn(
        'flex flex-col border-r border-slate-800/60 bg-gradient-to-b from-slate-900 to-slate-950 transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-64'
      )}>
        {/* Brand */}
        <div className="flex items-center gap-3 px-4 h-16 border-b border-slate-800/60">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center flex-shrink-0">
            <Zap className="w-4 h-4 text-white" />
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <h1 className="text-sm font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300 truncate">
                Industrial OS
              </h1>
              <p className="text-[10px] text-slate-500 font-medium">Operations Cloud</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-blue-500/15 text-blue-400 shadow-sm shadow-blue-500/5'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50',
                sidebarCollapsed && 'justify-center px-2'
              )}
            >
              <Icon className="w-[18px] h-[18px] flex-shrink-0" />
              {!sidebarCollapsed && <span>{label}</span>}
              {!sidebarCollapsed && label === 'Alarms' && <AlarmBadge />}
            </NavLink>
          ))}
        </nav>

        {/* Bottom Controls */}
        <div className="border-t border-slate-800/60 p-3 space-y-3">
          {!sidebarCollapsed && <ConnectionBadge />}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="w-full flex items-center justify-center p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 transition-colors"
          >
            {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>
      </aside>

      {/* ── Main Content ──────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="h-14 border-b border-slate-800/60 bg-slate-900/50 backdrop-blur-sm flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-semibold text-slate-300">
              {selectedPlantId ? `Plant: ${selectedPlantId}` : 'All Plants'}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <ConnectionBadge />
            <AlarmBadge />
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto bg-slate-950 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
