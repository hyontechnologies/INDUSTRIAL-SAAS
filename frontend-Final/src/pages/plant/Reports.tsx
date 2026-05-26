import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { FileText, Download, Calendar, Tag as TagIcon, BarChart2, FileJson, Clock } from 'lucide-react';
import { useTags } from '../../api/hooks/useTags';
import { useTagStats } from '../../api/hooks/useTelemetry';
import { useAuthStore } from '../../stores/useAuthStore';

export default function Reports() {
  const { plantId } = useParams<{ plantId: string }>();
  const { token } = useAuthStore();

  // Tag selection
  const { data: tagsData } = useTags(plantId);
  const [selectedTag, setSelectedTag] = useState<string>('');
  const [reportHours, setReportHours] = useState<number>(24);

  // Export settings
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv');
  const [exportRangeType, setExportRangeType] = useState<'preset' | 'custom'>('preset');
  const [exportPresetHours, setExportPresetHours] = useState<number>(24);
  const [customStart, setCustomStart] = useState<string>(() => {
    const d = new Date(); d.setHours(d.getHours() - 24);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  });
  const [customEnd, setCustomEnd] = useState<string>(() => {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  });

  const exportEnd = useMemo(() => exportRangeType === 'preset' ? new Date() : new Date(customEnd), [exportRangeType, customEnd]);
  const exportStart = useMemo(() => {
    if (exportRangeType === 'preset') {
      const d = new Date(exportEnd);
      d.setHours(d.getHours() - exportPresetHours);
      return d;
    }
    return new Date(customStart);
  }, [exportRangeType, exportPresetHours, exportEnd, customStart]);

  // Auto-select first tag if none selected
  React.useEffect(() => {
    if (tagsData?.tags?.length && !selectedTag) {
      setSelectedTag(tagsData.tags[0].tag_name);
    }
  }, [tagsData?.tags, selectedTag]);

  // Fetch stats for selected tag
  const { data: statsData, isLoading: isLoadingStats } = useTagStats(plantId, selectedTag, reportHours);

  const [isExporting, setIsExporting] = useState(false);

  const handleExport = () => {
    if (!plantId || !selectedTag || !token) return;

    setIsExporting(true);

    const url = `/api/v1/telemetry/export?plant_id=${plantId}&tag_name=${encodeURIComponent(selectedTag)}&start=${encodeURIComponent(exportStart.toISOString())}&end=${encodeURIComponent(exportEnd.toISOString())}&fmt=${exportFormat}`;

    fetch(url, {
      headers: {
        'X-API-Key': token,
      }
    })
    .then(response => {
      if (!response.ok) throw new Error("Export failed");
      return response.blob();
    })
    .then(blob => {
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      const extension = exportFormat === 'csv' ? 'csv' : 'json';
      a.download = `${selectedTag}_report.${extension}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    })
    .catch(err => {
      console.error("Export failed:", err);
      alert("Failed to export data. Please try again.");
    })
    .finally(() => {
      setIsExporting(false);
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg shadow-sm">
              <FileText className="w-6 h-6" />
            </div>
            Reporting Engine
          </h1>
          <p className="text-sm text-slate-500 mt-1">Generate compliance reports, statistical summaries, and data exports</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Configuration */}
        <div className="lg:col-span-1 flex flex-col gap-6">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col gap-5">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <TagIcon className="w-4 h-4 text-indigo-500" /> Target Tag
            </h3>

            <select
              value={selectedTag}
              onChange={(e) => setSelectedTag(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 font-medium transition-all"
            >
              <option value="" disabled>Select a tag...</option>
              {tagsData?.tags?.map(t => (
                <option key={t.tag_name} value={t.tag_name}>{t.tag_name}</option>
              ))}
            </select>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Download className="w-4 h-4 text-blue-500" /> Raw Data Export
            </h3>

            <div className="flex flex-col gap-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" /> Export Range
                </label>

                <div className="flex bg-slate-100 p-1 rounded-xl mb-3">
                  <button
                    onClick={() => setExportRangeType('preset')}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                      exportRangeType === 'preset' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    Quick
                  </button>
                  <button
                    onClick={() => setExportRangeType('custom')}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                      exportRangeType === 'custom' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    Custom
                  </button>
                </div>

                {exportRangeType === 'preset' ? (
                  <div className="grid grid-cols-2 gap-2">
                    {[1, 6, 24, 72].map(hours => (
                      <button
                        key={hours}
                        onClick={() => setExportPresetHours(hours)}
                        className={`py-2 text-sm font-medium rounded-xl border transition-all ${
                          exportPresetHours === hours
                            ? 'bg-blue-50 border-blue-200 text-blue-700'
                            : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        {hours >= 24 ? `${hours/24} Days` : `${hours} Hours`}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <input
                      type="datetime-local"
                      value={customStart}
                      onChange={(e) => setCustomStart(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none"
                    />
                    <input
                      type="datetime-local"
                      value={customEnd}
                      onChange={(e) => setCustomEnd(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none"
                    />
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Format</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setExportFormat('csv')}
                    className={`py-2 text-sm font-medium rounded-xl border flex items-center justify-center gap-2 transition-all ${
                      exportFormat === 'csv'
                        ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    <FileText className="w-4 h-4" /> CSV
                  </button>
                  <button
                    onClick={() => setExportFormat('json')}
                    className={`py-2 text-sm font-medium rounded-xl border flex items-center justify-center gap-2 transition-all ${
                      exportFormat === 'json'
                        ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                        : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    <FileJson className="w-4 h-4" /> JSON
                  </button>
                </div>
              </div>

              <button
                onClick={handleExport}
                disabled={isExporting}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-xl shadow-sm shadow-blue-200 transition-all flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed mt-2"
              >
                {isExporting ? (
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                ) : (
                  <><Download className="w-5 h-5" /> Export Data</>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Stats Display */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
              <div>
                <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2">
                  <BarChart2 className="w-5 h-5 text-indigo-500" /> Statistical Summary
                </h3>
                <p className="text-sm text-slate-500 mt-1 font-medium">{selectedTag || 'No tag selected'}</p>
              </div>

              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 p-1 rounded-xl">
                <div className="px-2 text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Horizon
                </div>
                {[1, 6, 24, 72].map(hours => (
                  <button
                    key={hours}
                    onClick={() => setReportHours(hours)}
                    className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${
                      reportHours === hours
                        ? 'bg-white text-indigo-700 shadow-sm border border-slate-200/50'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    {hours >= 24 ? `${hours/24}d` : `${hours}h`}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 flex items-center justify-center min-h-[300px]">
              {isLoadingStats ? (
                <div className="flex flex-col items-center">
                  <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-4"></div>
                  <p className="text-sm text-slate-500 font-medium">Calculating statistics...</p>
                </div>
              ) : !statsData?.stats ? (
                <div className="text-center text-slate-500">
                  <BarChart2 className="w-12 h-12 text-slate-200 mx-auto mb-3" />
                  <p>Select a tag to view statistical summary</p>
                </div>
              ) : (
                <div className="w-full grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200 p-5 rounded-2xl col-span-2 md:col-span-1">
                    <p className="text-sm font-semibold text-slate-500 mb-1">Total Samples</p>
                    <p className="text-3xl font-bold text-slate-900 tabular-nums tracking-tight">{statsData.stats.sample_count.toLocaleString()}</p>
                  </div>
                  <div className="bg-emerald-50/50 hover:bg-emerald-50 transition-colors border border-emerald-100 p-5 rounded-2xl">
                    <p className="text-sm font-semibold text-emerald-600 mb-1">Average Value</p>
                    <p className="text-3xl font-bold text-emerald-900 tabular-nums tracking-tight">{statsData.stats.avg_val}</p>
                  </div>
                  <div className="bg-indigo-50/50 hover:bg-indigo-50 transition-colors border border-indigo-100 p-5 rounded-2xl">
                    <p className="text-sm font-semibold text-indigo-600 mb-1">Std Deviation</p>
                    <div className="flex items-center gap-2">
                      <p className="text-3xl font-bold text-indigo-900 tabular-nums tracking-tight">{statsData.stats.std_val}</p>
                      <span className="text-indigo-400 font-bold ml-auto bg-indigo-100/50 w-8 h-8 rounded-full flex items-center justify-center">σ</span>
                    </div>
                  </div>
                  <div className="bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200 p-5 rounded-2xl">
                    <p className="text-sm font-semibold text-slate-500 mb-1">Maximum Value</p>
                    <p className="text-3xl font-bold text-slate-900 tabular-nums tracking-tight">{statsData.stats.max_val}</p>
                  </div>
                  <div className="bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200 p-5 rounded-2xl">
                    <p className="text-sm font-semibold text-slate-500 mb-1">Minimum Value</p>
                    <p className="text-3xl font-bold text-slate-900 tabular-nums tracking-tight">{statsData.stats.min_val}</p>
                  </div>
                  <div className="bg-slate-50 hover:bg-slate-100 transition-colors border border-slate-200 p-5 rounded-2xl flex flex-col justify-center">
                    <p className="text-sm font-semibold text-slate-500 mb-1">Range (Max - Min)</p>
                    <p className="text-3xl font-bold text-slate-900 tabular-nums tracking-tight">{(statsData.stats.max_val - statsData.stats.min_val).toFixed(2)}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
