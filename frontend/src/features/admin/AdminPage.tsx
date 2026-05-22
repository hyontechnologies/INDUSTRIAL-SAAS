import { Settings, Users, Key, ClipboardList } from 'lucide-react';

export default function AdminPage() {
  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-50 flex items-center gap-2">
          <Settings className="w-6 h-6 text-slate-400" />
          Administration
        </h1>
        <p className="text-sm text-slate-500 mt-1">User management, API keys, audit logs, and system settings</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { icon: Users, label: 'User Management', desc: 'Manage users, roles, and permissions' },
          { icon: Key, label: 'API Keys', desc: 'Edge agent keys and service accounts' },
          { icon: ClipboardList, label: 'Audit Log', desc: 'System activity and change history' },
        ].map(({ icon: Icon, label, desc }) => (
          <div key={label} className="rounded-xl border border-slate-800/50 bg-slate-900/30 p-6 hover:border-slate-700/50 hover:bg-slate-800/20 transition-all cursor-pointer">
            <Icon className="w-8 h-8 text-slate-500 mb-3" />
            <h3 className="text-sm font-semibold text-slate-200">{label}</h3>
            <p className="text-xs text-slate-500 mt-1">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
