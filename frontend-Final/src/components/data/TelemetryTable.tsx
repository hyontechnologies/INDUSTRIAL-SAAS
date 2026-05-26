import React, { useState } from 'react';
import { RealtimeValue } from '../status/RealtimeValue';
import { Search, Filter } from 'lucide-react';

interface TagData {
  tag_name: string;
  description: string;
  unit: string;
  group: string;
}

// Mock tags since we don't have TanStack query data wired up in this component directly yet
const MOCK_TAGS: TagData[] = [
  { tag_name: 'TT-201', description: 'Boiler 1 Main Steam Temp', unit: '°C', group: 'Boiler 1' },
  { tag_name: 'PT-202', description: 'Boiler 1 Main Steam Press', unit: 'bar', group: 'Boiler 1' },
  { tag_name: 'FT-203', description: 'Boiler 1 Feedwater Flow', unit: 't/h', group: 'Boiler 1' },
  { tag_name: 'LT-204', description: 'Boiler 1 Drum Level', unit: '%', group: 'Boiler 1' },
];

export const TelemetryTable: React.FC = () => {
  const [search, setSearch] = useState('');

  const filteredTags = MOCK_TAGS.filter(t =>
    t.tag_name.toLowerCase().includes(search.toLowerCase()) ||
    t.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden w-full flex flex-col h-full">
      <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row gap-4 justify-between items-center bg-slate-50/50">
        <h3 className="font-semibold text-slate-800">Telemetry Explorer</h3>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search tags..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-shadow"
            />
          </div>
          <button className="p-1.5 border border-slate-200 rounded-lg bg-white text-slate-600 hover:bg-slate-50 transition-colors">
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead className="sticky top-0 bg-slate-50 z-10 shadow-sm">
            <tr className="border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <th className="p-3 w-1/4">Tag Name</th>
              <th className="p-3 w-1/3">Description</th>
              <th className="p-3">Group</th>
              <th className="p-3 text-right">Live Value</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredTags.map((tag) => (
              <tr key={tag.tag_name} className="hover:bg-slate-50/50 transition-colors group">
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-blue-600 bg-blue-50 px-2 py-1 rounded">
                      {tag.tag_name}
                    </span>
                  </div>
                </td>
                <td className="p-3 text-sm text-slate-600 truncate max-w-[200px]" title={tag.description}>
                  {tag.description}
                </td>
                <td className="p-3">
                  <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">
                    {tag.group}
                  </span>
                </td>
                <td className="p-3 text-right">
                  <div className="font-bold text-base">
                    <RealtimeValue tagName={tag.tag_name} unit={tag.unit} />
                  </div>
                </td>
              </tr>
            ))}
            {filteredTags.length === 0 && (
              <tr>
                <td colSpan={4} className="p-8 text-center text-slate-500">
                  No tags found matching "{search}"
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
