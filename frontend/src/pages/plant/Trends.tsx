import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingUp, Clock, Tag as TagIcon, X, Calendar } from 'lucide-react';
import { useTags } from '../../api/hooks/useTags';
import { useTelemetryMultiHistory } from '../../api/hooks/useTelemetry';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

export default function Trends() {
  const { plantId } = useParams<{ plantId: string }>();

  // Time range selection
  const [rangeType, setRangeType] = useState<'preset' | 'custom'>('preset');
  const [presetHours, setPresetHours] = useState<number>(1);
  const [customStart, setCustomStart] = useState<string>(() => {
    const d = new Date(); d.setHours(d.getHours() - 24);
    // Format for datetime-local: YYYY-MM-DDThh:mm
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  });
  const [customEnd, setCustomEnd] = useState<string>(() => {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  });

  const end = useMemo(() => rangeType === 'preset' ? new Date() : new Date(customEnd), [rangeType, customEnd]);
  const start = useMemo(() => {
    if (rangeType === 'preset') {
      const d = new Date(end);
      d.setHours(d.getHours() - presetHours);
      return d;
    }
    return new Date(customStart);
  }, [rangeType, presetHours, end, customStart]);

  const durationHours = (end.getTime() - start.getTime()) / (1000 * 60 * 60);
  const interval = durationHours <= 1 ? '1m' : durationHours <= 24 ? '5m' : durationHours <= 168 ? '15m' : '1h';

  // Tag selection
  const { data: tagsData } = useTags(plantId);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagSearch, setTagSearch] = useState('');

  // Auto-select first tag if none selected and tags loaded
  React.useEffect(() => {
    if (tagsData?.tags?.length && selectedTags.length === 0) {
      setSelectedTags([tagsData.tags[0].tag_name]);
    }
  }, [tagsData?.tags, selectedTags.length]);

  // Fetch chart data
  const { data: chartData, isLoading } = useTelemetryMultiHistory(
    plantId,
    selectedTags,
    start.toISOString(),
    end.toISOString(),
    interval
  );

  const toggleTag = (tagName: string) => {
    if (selectedTags.includes(tagName)) {
      setSelectedTags(prev => prev.filter(t => t !== tagName));
    } else {
      if (selectedTags.length < 5) {
        setSelectedTags(prev => [...prev, tagName]);
      } else {
        alert("Maximum 5 tags can be compared at once.");
      }
    }
  };

  const filteredTags = tagsData?.tags?.filter(t => t.tag_name.toLowerCase().includes(tagSearch.toLowerCase())) || [];

  return (
    <div className="flex flex-col gap-6 h-[calc(100vh-12rem)]">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center shrink-0 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg shadow-sm">
              <TrendingUp className="w-6 h-6" />
            </div>
            Trend Analysis
          </h1>
          <p className="text-sm text-slate-500 mt-1">Multi-variable historical telemetry comparison</p>
        </div>

        <div className="flex flex-col sm:flex-row items-end sm:items-center gap-3">
          <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
            <button
              onClick={() => setRangeType('preset')}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all ${
                rangeType === 'preset' ? 'bg-slate-100 text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Quick Select
            </button>
            <button
              onClick={() => setRangeType('custom')}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
                rangeType === 'custom' ? 'bg-slate-100 text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Calendar className="w-4 h-4" /> Custom
            </button>
          </div>

          {rangeType === 'preset' ? (
            <div className="flex bg-slate-100 p-1 rounded-xl shadow-inner">
              {[1, 6, 24, 168].map(hours => (
                <button
                  key={hours}
                  onClick={() => setPresetHours(hours)}
                  className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-all ${
                    presetHours === hours
                      ? 'bg-white text-blue-600 shadow-sm border border-slate-200/50'
                      : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200/50'
                  }`}
                >
                  {hours === 168 ? '7D' : hours >= 24 ? `${hours/24}D` : `${hours}H`}
                </button>
              ))}
            </div>
          ) : (
          <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-xl p-1.5 shadow-sm">
              <input
                type="datetime-local"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="text-sm px-2 py-1 outline-none text-slate-700 bg-transparent"
              />
              <span className="text-slate-400 font-medium px-1">to</span>
              <input
                type="datetime-local"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="text-sm px-2 py-1 outline-none text-slate-700 bg-transparent"
              />
            </div>
          )}

          <button
            onClick={async () => {
              if (selectedTags.length === 0) return alert("Select at least one tag to export");
              const token = localStorage.getItem('auth-storage') ? JSON.parse(localStorage.getItem('auth-storage')!).state.token : 'changeme';

              for (const tag of selectedTags) {
                try {
                  const res = await fetch(`/api/v1/telemetry/export?plant_id=${plantId}&tag_name=${encodeURIComponent(tag)}&start=${start.toISOString()}&end=${end.toISOString()}&fmt=csv`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                  });
                  if (!res.ok) throw new Error("Export failed");

                  const blob = await res.blob();
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${tag}_export_${new Date().toISOString().slice(0,10)}.csv`;
                  document.body.appendChild(a);
                  a.click();
                  window.URL.revokeObjectURL(url);
                  document.body.removeChild(a);
                } catch (e) {
                  console.error("Export error for tag", tag, e);
                  alert(`Failed to export data for ${tag}`);
                }
              }
            }}
            disabled={selectedTags.length === 0}
            className="px-4 py-1.5 ml-2 text-sm font-medium rounded-lg transition-all bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed shadow-sm flex items-center gap-2"
          >
            Export CSV
          </button>
        </div>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Left Sidebar: Tag Selector */}
        <div className="w-72 bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col shrink-0 overflow-hidden">
          <div className="p-4 border-b border-slate-100 bg-slate-50/50">
            <h3 className="font-semibold text-slate-800 flex items-center gap-2 mb-3">
              <TagIcon className="w-4 h-4 text-blue-500" />
              Available Tags
              <span className={`ml-auto text-xs font-bold px-2 py-0.5 rounded-full ${selectedTags.length === 5 ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-600'}`}>
                {selectedTags.length}/5
              </span>
            </h3>
            <input
              type="text"
              placeholder="Search tags..."
              value={tagSearch}
              onChange={(e) => setTagSearch(e.target.value)}
              className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all shadow-sm"
            />
          </div>
          <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
            {filteredTags.map(tag => {
              const isSelected = selectedTags.includes(tag.tag_name);
              return (
                <button
                  key={tag.tag_name}
                  onClick={() => toggleTag(tag.tag_name)}
                  className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition-all mb-1 flex items-center justify-between group
                    ${isSelected ? 'bg-blue-50 border border-blue-200/50 text-blue-800 shadow-sm' : 'hover:bg-slate-50 text-slate-600 border border-transparent'}
                  `}
                >
                  <span className={`truncate pr-2 ${isSelected ? 'font-semibold' : 'font-medium'}`}>{tag.tag_name}</span>
                  {isSelected ? (
                    <div className="bg-blue-100 p-1 rounded-md">
                      <X className="w-3 h-3 text-blue-600" />
                    </div>
                  ) : (
                    <div className="w-4 h-4 rounded-md border-2 border-slate-300 group-hover:border-blue-400 transition-colors" />
                  )}
                </button>
              );
            })}
            {filteredTags.length === 0 && (
              <div className="text-center py-8 text-slate-400 text-sm">
                No tags found matching search.
              </div>
            )}
          </div>
        </div>

        {/* Right Area: Chart */}
        <div className="flex-1 bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col min-w-0">
          {selectedTags.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 m-2">
              <TrendingUp className="w-16 h-16 text-slate-300 mb-4" />
              <h3 className="text-lg font-semibold text-slate-700 mb-1">No tags selected</h3>
              <p className="text-sm">Select up to 5 tags from the sidebar to view their historical trends.</p>
            </div>
          ) : isLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-4"></div>
              <p className="text-slate-500 text-sm font-medium animate-pulse">Loading trend data...</p>
            </div>
          ) : (
            <>
              <div className="flex justify-between items-center mb-6 px-2">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-600 bg-slate-100/80 px-3 py-1.5 rounded-lg border border-slate-200">
                  <Clock className="w-4 h-4 text-blue-500" />
                  Resolution: <span className="text-slate-900 font-bold">{interval}</span> buckets
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                  <span className="text-sm font-medium text-slate-500">
                    {chartData?.count || 0} data points
                  </span>
                </div>
              </div>

              <div className="flex-1 w-full min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData?.data || []} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                      dataKey="ts"
                      tickFormatter={(ts) => {
                        const d = new Date(ts);
                        return durationHours > 24
                          ? d.toLocaleDateString([], { month: 'short', day: 'numeric' })
                          : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                      }}
                      stroke="#94a3b8"
                      fontSize={12}
                      tickMargin={12}
                      minTickGap={40}
                      axisLine={{ stroke: '#cbd5e1' }}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      fontSize={12}
                      tickMargin={12}
                      domain={['auto', 'auto']}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      labelFormatter={(ts) => {
                        const d = new Date(ts as string);
                        return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
                      }}
                      contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)' }}
                      itemStyle={{ fontWeight: 600 }}
                    />
                    <Legend
                      iconType="circle"
                      wrapperStyle={{ paddingTop: '20px' }}
                      formatter={(value) => <span className="text-slate-700 font-medium ml-1">{value}</span>}
                    />

                    {selectedTags.map((tag, idx) => (
                      <Line
                        key={tag}
                        type="monotone"
                        dataKey={tag}
                        stroke={COLORS[idx % COLORS.length]}
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 6, strokeWidth: 0, fill: COLORS[idx % COLORS.length] }}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
