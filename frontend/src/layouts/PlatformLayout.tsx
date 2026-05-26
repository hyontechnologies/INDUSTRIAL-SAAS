import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import GlobalHeader from '../components/GlobalHeader';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';
import { WebSocketProvider } from '../websocket/WebSocketProvider';
import { RealtimeStatusStrip } from '../components/shell/RealtimeStatusStrip';
import { CommandPalette } from '../components/shell/CommandPalette';
import { NotificationCenter } from '../components/shell/NotificationCenter';

export default function PlatformLayout() {
  const { sidebarCollapsed, sidebarOpen, setSidebarOpen } = useWorkspaceStore();

  return (
    <WebSocketProvider>
      <div className="min-h-screen bg-slate-50 font-sans text-slate-900 flex flex-col relative">
        {/* Animated Background Mesh */}
        <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 -left-4 w-96 h-96 bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
          <div className="absolute top-0 -right-4 w-96 h-96 bg-blue-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
          <div className="absolute -bottom-8 left-40 w-96 h-96 bg-indigo-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
        </div>

        {/* Sidebar */}
        <div className="z-40">
          <Sidebar />
        </div>

        {/* Mobile overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/30 z-30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main area — shifts right based on sidebar width */}
        <div
          className={`flex-1 flex flex-col transition-all duration-300 min-h-screen relative z-10 ${
            sidebarCollapsed ? 'lg:ml-[72px]' : 'lg:ml-[260px]'
          }`}
        >
          <GlobalHeader />
          <RealtimeStatusStrip />

          {/* Page Content */}
          <main className="flex-1 p-4 md:p-6 max-w-[1600px] w-full mx-auto relative flex flex-col">
            <Outlet />
          </main>

          {/* Footer */}
          <footer className="border-t border-white/20 glass px-6 py-3 flex flex-col sm:flex-row justify-between items-center gap-2 text-[11px] text-slate-500 mt-auto shadow-sm">
            <span>© 2026 Industrial Operations Cloud. All Rights Reserved.</span>
            <div className="flex gap-4">
              <a href="#" className="hover:text-slate-600 transition-colors">Terms</a>
              <a href="#" className="hover:text-slate-600 transition-colors">Privacy</a>
              <a href="#" className="hover:text-slate-600 transition-colors">Security Audit</a>
            </div>
          </footer>
        </div>

        {/* Global Overlays */}
        <CommandPalette />
        <NotificationCenter />
      </div>
    </WebSocketProvider>
  );
}
