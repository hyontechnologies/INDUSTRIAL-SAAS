import { Building2, Users, Globe, TrendingUp, ArrowUpRight, Shield } from 'lucide-react';
import { useAppStore } from '../stores/useAppStore';

export default function AdminOverview() {
  const { organizations, plants } = useAppStore();

  const onlinePlants = plants.filter(p => p.status === 'online').length;
  const totalPlants = plants.length;

  const stats = [
    { label: 'Organizations', value: organizations.length, icon: Building2, color: 'blue', change: '+2 this month' },
    { label: 'Total Plants', value: totalPlants, icon: Globe, color: 'indigo', change: `${onlinePlants} online` },
    { label: 'Active Users', value: 24, icon: Users, color: 'emerald', change: '3 new today' },
    { label: 'Uptime', value: '99.7%', icon: TrendingUp, color: 'amber', change: 'Last 30 days' },
  ];

  const colorMap: Record<string, { bg: string; text: string; iconBg: string }> = {
    blue:    { bg: 'bg-blue-50',    text: 'text-blue-600',    iconBg: 'bg-blue-100' },
    indigo:  { bg: 'bg-indigo-50',  text: 'text-indigo-600',  iconBg: 'bg-indigo-100' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', iconBg: 'bg-emerald-100' },
    amber:   { bg: 'bg-amber-50',   text: 'text-amber-600',   iconBg: 'bg-amber-100' },
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Platform Overview</h1>
        <p className="text-sm text-slate-500 mt-1">Infrastructure-wide monitoring and management</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => {
          const colors = colorMap[stat.color];
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="glassmorphism-card p-5 rounded-xl group cursor-pointer">
              <div className="flex items-start justify-between">
                <div className={`p-2.5 rounded-lg ${colors.iconBg}`}>
                  <Icon className={`h-5 w-5 ${colors.text}`} />
                </div>
                <ArrowUpRight className="h-4 w-4 text-slate-300 group-hover:text-slate-500 transition-colors" />
              </div>
              <div className="mt-4">
                <p className="text-2xl font-bold text-slate-900">{stat.value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{stat.label}</p>
              </div>
              <p className="text-[10px] text-slate-400 mt-2">{stat.change}</p>
            </div>
          );
        })}
      </div>

      {/* Organizations Table */}
      <div className="glassmorphism p-6 rounded-2xl border border-slate-200">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-md font-semibold text-slate-900 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-blue-500" />
            Registered Organizations
          </h2>
          <button className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors shadow-sm shadow-blue-600/20">
            + Add Organization
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-400">
                <th className="py-3 px-4">Organization</th>
                <th className="py-3 px-4">Plants</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {organizations.map(org => {
                const orgPlants = plants.filter(p => p.orgId === org.id);
                const orgOnline = orgPlants.filter(p => p.status === 'online').length;
                return (
                  <tr key={org.id} className="border-b border-slate-100 text-sm hover:bg-blue-50/30 transition-all">
                    <td className="py-4 px-4 flex items-center gap-3">
                      <span className="text-lg">{org.logo}</span>
                      <span className="font-semibold text-slate-800">{org.name}</span>
                    </td>
                    <td className="py-4 px-4 text-slate-600">{orgOnline}/{orgPlants.length} online</td>
                    <td className="py-4 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-600 border border-emerald-200">
                        ACTIVE
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <button className="text-xs text-blue-600 hover:underline">Manage →</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Plant Registry */}
      <div className="glassmorphism p-6 rounded-2xl border border-slate-200">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-md font-semibold text-slate-900 flex items-center gap-2">
            <Shield className="h-4 w-4 text-indigo-500" />
            Plant Registry
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {plants.map(plant => (
            <div key={plant.id} className="glassmorphism-card p-4 rounded-xl">
              <div className="flex items-center gap-3">
                <span className={`h-3 w-3 rounded-full ${
                  plant.status === 'online' ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' :
                  plant.status === 'maintenance' ? 'bg-amber-400' : 'bg-slate-300'
                }`} />
                <div>
                  <p className="text-sm font-semibold text-slate-800">{plant.name}</p>
                  <p className="text-[10px] text-slate-400">{plant.location}</p>
                </div>
              </div>
              <div className="mt-3 flex justify-between items-center">
                <span className={`text-[10px] font-semibold uppercase ${
                  plant.status === 'online' ? 'text-emerald-600' :
                  plant.status === 'maintenance' ? 'text-amber-600' : 'text-slate-400'
                }`}>
                  {plant.status}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">{plant.id}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
