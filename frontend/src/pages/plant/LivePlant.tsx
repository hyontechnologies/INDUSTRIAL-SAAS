import React, { useEffect, useState, useMemo, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Activity, AlertTriangle, Cpu, TrendingUp, AlertCircle, Box } from 'lucide-react';
import { useTelemetryLatest } from '../../api/hooks/useTelemetry';
import { useActiveAlarms } from '../../api/hooks/useAlarms';
import Boiler3D from '../../components/plant/Boiler3D';

export default function LivePlant() {
  const { plantId } = useParams<{ plantId: string }>();
  const { data: telemetryData, isLoading: isLoadingTelemetry, isError: isErrorTelemetry } = useTelemetryLatest(plantId);
  const { data: alarmsData } = useActiveAlarms(plantId);

  const [activeTab, setActiveTab] = useState<'2d' | '3d'>('3d');

  // Track previous values and update times with Refs to prevent dependency tracking issues and cascading renders
  const prevValuesRef = useRef<Record<string, number>>({});
  const lastUpdateTimeRef = useRef<number | null>(null);

  const [flashTags, setFlashTags] = useState<Record<string, 'up' | 'down'>>({});
  const [updateRateMs, setUpdateRateMs] = useState<number>(0);

  useEffect(() => {
    if (telemetryData?.data) {
      const now = Date.now();
      const lastUpdateTime = lastUpdateTimeRef.current ?? now;
      const currentDiff = now - lastUpdateTime;

      const newFlash: Record<string, 'up' | 'down'> = {};
      const prevValues = prevValuesRef.current;
      const newPrev = { ...prevValues };

      telemetryData.data.forEach(point => {
        if (prevValues[point.tag_name] !== undefined) {
          if (point.value > prevValues[point.tag_name]) {
            newFlash[point.tag_name] = 'up';
          } else if (point.value < prevValues[point.tag_name]) {
            newFlash[point.tag_name] = 'down';
          }
        }
        newPrev[point.tag_name] = point.value;
      });

      lastUpdateTimeRef.current = now;
      prevValuesRef.current = newPrev;

      // Defer state updates to prevent cascading renders
      const timerId = setTimeout(() => {
        setUpdateRateMs(prev => prev === 0 ? currentDiff : (prev * 0.7 + currentDiff * 0.3));
        setFlashTags(newFlash);
      }, 0);

      // Clear flash after 1 second
      if (Object.keys(newFlash).length > 0) {
        const clearTimer = setTimeout(() => setFlashTags({}), 1000);
        return () => {
          clearTimeout(timerId);
          clearTimeout(clearTimer);
        };
      }
      return () => clearTimeout(timerId);
    }
  }, [telemetryData?.data]);

  const criticalAlarms = alarmsData?.alarms.filter(a => a.severity === 'CRITICAL').length || 0;
  const activeTagsCount = telemetryData?.count || 0;

  const telemetryPoints = telemetryData?.data;

  // Calculate Data Quality dynamically
  const dataQuality = useMemo(() => {
    if (!telemetryPoints || telemetryPoints.length === 0) return 100;
    const goodPoints = telemetryPoints.filter(p => p.quality >= 192).length;
    return (goodPoints / telemetryPoints.length) * 100;
  }, [telemetryPoints]);

  // Format update rate
  const formattedUpdateRate = useMemo(() => {
    if (updateRateMs === 0) return 'calc...';
    if (updateRateMs < 1000) return `${Math.round(updateRateMs)}ms`;
    return `${(updateRateMs / 1000).toFixed(1)}s`;
  }, [updateRateMs]);

  if (isErrorTelemetry) {
    return (
      <div className="flex flex-col items-center justify-center py-20 bg-white rounded-2xl border border-red-100 shadow-sm">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">Failed to load telemetry</h2>
        <p className="text-slate-500">Please check your connection and try again.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Live Plant View</h1>
          <p className="text-sm text-slate-500">Real-time telemetry and equipment status</p>
        </div>
        <div className="flex bg-slate-200/50 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('3d')}
            className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
              activeTab === '3d'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50'
                : 'text-slate-500 hover:text-slate-700 hover:bg-white/50'
            }`}
          >
            <Box className="w-4 h-4" />
            3D Digital Twin
          </button>
          <button
            onClick={() => setActiveTab('2d')}
            className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
              activeTab === '2d'
                ? 'bg-white text-slate-900 shadow-sm border border-slate-200/50'
                : 'text-slate-500 hover:text-slate-700 hover:bg-white/50'
            }`}
          >
            <Activity className="w-4 h-4" />
            2D Cards
          </button>
        </div>
      </div>

      {/* KPI Header */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4 transition-all hover:shadow-md">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
            <Activity className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">Active Tags</p>
            <h3 className="text-2xl font-bold text-slate-900">{activeTagsCount}</h3>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4 transition-all hover:shadow-md">
          <div className={`p-3 rounded-xl transition-colors duration-300 ${criticalAlarms > 0 ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'}`}>
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">Critical Alarms</p>
            <h3 className={`text-2xl font-bold transition-colors duration-300 ${criticalAlarms > 0 ? 'text-red-600' : 'text-slate-900'}`}>{criticalAlarms}</h3>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4 transition-all hover:shadow-md">
          <div className={`p-3 rounded-xl transition-colors duration-300 ${dataQuality < 95 ? 'bg-amber-50 text-amber-600' : 'bg-indigo-50 text-indigo-600'}`}>
            <Cpu className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">Data Quality</p>
            <h3 className={`text-2xl font-bold ${dataQuality < 95 ? 'text-amber-600' : 'text-slate-900'}`}>
              {dataQuality.toFixed(1)}%
            </h3>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm flex items-center gap-4 transition-all hover:shadow-md">
          <div className="p-3 bg-violet-50 text-violet-600 rounded-xl">
            <TrendingUp className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">Update Rate</p>
            <h3 className="text-2xl font-bold text-slate-900">{formattedUpdateRate}</h3>
          </div>
        </div>
      </div>

      {activeTab === '3d' ? (
        <div className="mt-2 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <Boiler3D telemetryData={(telemetryData?.data || []).map(d => ({ ...d, unit: d.unit || undefined }))} />
        </div>
      ) : (
        <>
          <h2 className="text-lg font-bold text-slate-800 mt-4">Live Telemetry Streams</h2>

          {isLoadingTelemetry ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : telemetryData?.data.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 bg-white rounded-2xl border border-slate-200 border-dashed">
              <Activity className="w-12 h-12 text-slate-300 mb-3" />
              <h3 className="text-sm font-medium text-slate-900">No telemetry data</h3>
              <p className="text-xs text-slate-500 mt-1">This plant has no active telemetry streams.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
              {telemetryData?.data.map((point) => {
                const isFlashingUp = flashTags[point.tag_name] === 'up';
                const isFlashingDown = flashTags[point.tag_name] === 'down';

                return (
                  <div
                    key={point.tag_name}
                    className={`bg-white p-4 rounded-xl border shadow-sm transition-all duration-500 flex flex-col justify-between h-32 hover:shadow-md
                      ${isFlashingUp ? 'bg-emerald-50 border-emerald-300 scale-[1.02]' : ''}
                      ${isFlashingDown ? 'bg-red-50 border-red-300 scale-[1.02]' : 'border-slate-200'}
                    `}
                  >
                    <div className="flex justify-between items-start">
                      <span className="text-xs font-semibold text-slate-600 break-words line-clamp-2 pr-2 leading-tight" title={point.tag_name}>
                        {point.tag_name}
                      </span>
                      <div
                        className={`w-2.5 h-2.5 rounded-full mt-0.5 flex-shrink-0 shadow-sm ${point.quality >= 192 ? 'bg-emerald-400 shadow-emerald-400/50' : 'bg-amber-400 shadow-amber-400/50 animate-pulse'}`}
                        title={point.quality >= 192 ? "Quality: Good" : "Quality: Uncertain/Bad"}
                      />
                    </div>
                    <div className="mt-2 flex items-baseline gap-1.5">
                      <span className={`text-2xl font-bold tabular-nums tracking-tight transition-colors duration-300
                        ${isFlashingUp ? 'text-emerald-700' : ''}
                        ${isFlashingDown ? 'text-red-700' : 'text-slate-800'}
                      `}>
                        {point.value.toFixed(2)}
                      </span>
                      {point.unit && <span className="text-xs text-slate-400 font-medium truncate max-w-[40px]" title={point.unit}>{point.unit}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
