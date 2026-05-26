import React, { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Bell, CheckCircle, ShieldAlert, AlertTriangle, Info, Clock, CheckCircle2, Filter, Search } from 'lucide-react';
import { useActiveAlarms, useAlarmHistory, useAcknowledgeAlarm, useClearAlarms } from '../../api/hooks/useAlarms';
import { useAuthStore } from '../../stores/useAuthStore';
import { useAlarmStore } from '../../stores/useAlarmStore';
import { Alarm } from '../../types/alarm';

export default function AlarmsConsole() {
  const { plantId } = useParams<{ plantId: string }>();
  const [activeTab, setActiveTab] = useState<'active' | 'history'>('active');

  // Filtering state
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');
  const [filterTag, setFilterTag] = useState<string>('');

  const liveAlarms = useAlarmStore(s => s.activeAlarms);
  const activeAlarmsData = useMemo(() => {
    return { alarms: liveAlarms, count: liveAlarms.length };
  }, [liveAlarms]);
  const isLoadingActive = false;
  const { data: historyAlarmsData, isLoading: isLoadingHistory } = useAlarmHistory(plantId);

  const { user } = useAuthStore();
  const ackAlarm = useAcknowledgeAlarm();
  const clearAlarms = useClearAlarms();

  const handleAck = (alarmId: string) => {
    ackAlarm.mutate({ alarm_id: alarmId, acked_by: user?.name || user?.email || 'Unknown User' });
  };

  const handleClearAll = () => {
    if (plantId) {
      clearAlarms.mutate({ plant_id: plantId, cleared_by: user?.name || user?.email || 'Unknown User' });
    }
  };

  const getSeverityStyle = (severity: string) => {
    switch(severity) {
      case 'CRITICAL': return 'bg-red-100 text-red-700 border-red-200';
      case 'ALARM': return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'WARNING': return 'bg-amber-100 text-amber-700 border-amber-200';
      default: return 'bg-blue-100 text-blue-700 border-blue-200';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch(severity) {
      case 'CRITICAL': return <ShieldAlert className="w-4 h-4" />;
      case 'ALARM': return <AlertTriangle className="w-4 h-4" />;
      case 'WARNING': return <AlertTriangle className="w-4 h-4" />;
      default: return <Info className="w-4 h-4" />;
    }
  };

  const activeCount = activeAlarmsData?.count || 0;
  const historyCount = historyAlarmsData?.count || 0;

  // Apply filters
  const filteredActive = useMemo(() => {
    let list: Alarm[] = activeAlarmsData?.alarms || [];
    if (filterSeverity !== 'ALL') {
      list = list.filter((a: Alarm) => a.severity === filterSeverity);
    }
    if (filterTag.trim() !== '') {
      const lowerTag = filterTag.toLowerCase();
      list = list.filter((a: Alarm) => a.tag_name.toLowerCase().includes(lowerTag) || a.message.toLowerCase().includes(lowerTag));
    }
    return list;
  }, [activeAlarmsData?.alarms, filterSeverity, filterTag]);

  const filteredHistory = useMemo(() => {
    let list: Alarm[] = historyAlarmsData?.alarms || [];
    if (filterSeverity !== 'ALL') {
      list = list.filter((a: Alarm) => a.severity === filterSeverity);
    }
    if (filterTag.trim() !== '') {
      const lowerTag = filterTag.toLowerCase();
      list = list.filter((a: Alarm) => a.tag_name.toLowerCase().includes(lowerTag) || a.message.toLowerCase().includes(lowerTag));
    }
    return list;
  }, [historyAlarmsData?.alarms, filterSeverity, filterTag]);

  const currentFilteredData = activeTab === 'active' ? filteredActive : filteredHistory;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
            <div className="p-2 bg-red-50 text-red-600 rounded-lg shadow-sm">
              <Bell className="w-6 h-6" />
            </div>
            Alarms Console
          </h1>
          <p className="text-sm text-slate-500 mt-1">Manage and acknowledge plant alarms</p>
        </div>
        {activeTab === 'active' && activeCount > 0 && (
          <button
            onClick={handleClearAll}
            className="px-4 py-2 bg-white border border-slate-200 text-slate-700 font-medium rounded-xl hover:bg-slate-50 hover:text-emerald-700 hover:border-emerald-200 shadow-sm transition-all flex items-center gap-2"
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            Clear Acknowledged
          </button>
        )}
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm flex flex-col min-h-[500px]">
        {/* Top bar with Tabs and Filters */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-slate-200 bg-slate-50/80 p-3 gap-4">
          <div className="flex bg-slate-200/50 p-1 rounded-xl">
            <button
              onClick={() => setActiveTab('active')}
              className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                activeTab === 'active'
                  ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-white/50'
              }`}
            >
              Active Alarms
              <span className={`py-0.5 px-2 rounded-full text-xs transition-colors ${activeTab === 'active' ? 'bg-red-100 text-red-600' : 'bg-slate-200 text-slate-500'}`}>{activeCount}</span>
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                activeTab === 'history'
                  ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-white/50'
              }`}
            >
              <Clock className="w-4 h-4" />
              History
              <span className={`py-0.5 px-2 rounded-full text-xs transition-colors ${activeTab === 'history' ? 'bg-slate-200 text-slate-700' : 'bg-slate-200 text-slate-500'}`}>{historyCount}</span>
            </button>
          </div>

          <div className="flex flex-1 sm:flex-none w-full sm:w-auto items-center gap-3">
            <div className="relative w-full sm:w-64">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search tag or message..."
                value={filterTag}
                onChange={(e) => setFilterTag(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors"
              />
            </div>
            <div className="relative shrink-0">
              <Filter className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <select
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value)}
                className="appearance-none bg-white border border-slate-200 rounded-xl pl-9 pr-8 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-colors cursor-pointer"
              >
                <option value="ALL">All Severities</option>
                <option value="CRITICAL">Critical</option>
                <option value="ALARM">Alarm</option>
                <option value="WARNING">Warning</option>
                <option value="INFO">Info</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-x-auto overflow-y-auto max-h-[600px]">
          <table className="w-full text-sm text-left relative">
            <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-200 sticky top-0 z-10">
              <tr>
                <th className="px-6 py-4 font-semibold">Severity</th>
                <th className="px-6 py-4 font-semibold">Time</th>
                <th className="px-6 py-4 font-semibold">Tag</th>
                <th className="px-6 py-4 font-semibold">Message</th>
                <th className="px-6 py-4 font-semibold">State</th>
                <th className="px-6 py-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {activeTab === 'active' && isLoadingActive && (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-500"><div className="flex justify-center"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div></div></td></tr>
              )}
              {activeTab === 'history' && isLoadingHistory && (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-500"><div className="flex justify-center"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div></div></td></tr>
              )}

              {!isLoadingActive && !isLoadingHistory && currentFilteredData.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-16 text-center">
                    <div className="flex flex-col items-center justify-center">
                      <div className="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mb-3">
                        {filterTag || filterSeverity !== 'ALL' ? (
                          <Filter className="w-6 h-6 text-slate-400" />
                        ) : (
                          <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                        )}
                      </div>
                      <h3 className="text-sm font-medium text-slate-900">
                        {filterTag || filterSeverity !== 'ALL' ? 'No alarms match filters' : 'No alarms found'}
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        {filterTag || filterSeverity !== 'ALL' ? 'Try adjusting your search criteria.' : 'Everything is running smoothly.'}
                      </p>
                    </div>
                  </td>
                </tr>
              )}

              {currentFilteredData.map((alarm: Alarm) => (
                <tr key={alarm.alarm_id} className="hover:bg-blue-50/30 transition-colors group">
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${getSeverityStyle(alarm.severity)}`}>
                      {getSeverityIcon(alarm.severity)} {alarm.severity}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-500 whitespace-nowrap">
                    {new Date(alarm.occurred_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 font-mono text-slate-700 bg-slate-50/50 group-hover:bg-transparent transition-colors">{alarm.tag_name}</td>
                  <td className="px-6 py-4 text-slate-900 font-medium">{alarm.message}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 rounded-md text-xs font-semibold ${
                      alarm.alarm_state === 'ACTIVE' ? 'bg-red-50 text-red-600' :
                      alarm.alarm_state === 'ACKNOWLEDGED' ? 'bg-amber-50 text-amber-600' :
                      'bg-slate-100 text-slate-600'
                    }`}>
                      {alarm.alarm_state}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    {activeTab === 'active' ? (
                      <>
                        {alarm.alarm_state === 'ACTIVE' && (
                          <button
                            onClick={() => handleAck(alarm.alarm_id)}
                            className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg font-medium shadow-sm shadow-blue-200 transition-colors"
                          >
                            Acknowledge
                          </button>
                        )}
                        {alarm.alarm_state === 'ACKNOWLEDGED' && (
                          <span className="text-xs text-slate-400 flex items-center justify-end gap-1.5">
                            <CheckCircle className="w-3.5 h-3.5 text-amber-500" /> Acked by <span className="font-medium text-slate-600">{alarm.acked_by}</span>
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-xs text-slate-400">
                        {alarm.acked_at ? `Acked ${new Date(alarm.acked_at).toLocaleTimeString()}` : '-'}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
