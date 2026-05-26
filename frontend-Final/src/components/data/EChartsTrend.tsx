import React, { useEffect, useRef, useCallback } from 'react';
import * as echarts from 'echarts';
import { useTelemetryStore } from '../../stores/useTelemetryStore';

interface EChartsTrendProps {
  title: string;
  tagNames: string[];
  /** Rolling window size (number of data points to keep) */
  windowSize?: number;
}

const PALETTE = [
  { line: '#3b82f6', areaTop: 'rgba(59,130,246,0.25)', areaBottom: 'rgba(59,130,246,0.02)' },
  { line: '#10b981', areaTop: 'rgba(16,185,129,0.25)', areaBottom: 'rgba(16,185,129,0.02)' },
  { line: '#f59e0b', areaTop: 'rgba(245,158,11,0.20)', areaBottom: 'rgba(245,158,11,0.02)' },
  { line: '#8b5cf6', areaTop: 'rgba(139,92,246,0.20)', areaBottom: 'rgba(139,92,246,0.02)' },
  { line: '#ef4444', areaTop: 'rgba(239,68,68,0.20)',   areaBottom: 'rgba(239,68,68,0.02)' },
];

export const EChartsTrend: React.FC<EChartsTrendProps> = ({
  title,
  tagNames,
  windowSize = 120,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const dataBufferRef = useRef<Record<string, { name: string; value: [string, number] }[]>>({});

  const buildOption = useCallback((): echarts.EChartsOption => ({
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#94a3b8' },
      },
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e2e8f0',
      borderRadius: 12,
      textStyle: { color: '#334155', fontFamily: 'Inter, system-ui, sans-serif' },
      padding: [12, 16],
    },
    legend: {
      data: tagNames,
      bottom: 0,
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: '#64748b', fontFamily: 'Inter, system-ui, sans-serif', fontSize: 11 },
      itemGap: 20,
    },
    grid: {
      left: '2%',
      right: '3%',
      bottom: '15%',
      top: '8%',
      containLabel: true,
    },
    xAxis: {
      type: 'time',
      splitLine: { show: false },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#94a3b8', fontSize: 10, fontFamily: 'Inter, system-ui, sans-serif' },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
      axisLine: { show: false },
      axisLabel: { color: '#94a3b8', fontSize: 10, fontFamily: 'Inter, system-ui, sans-serif' },
      scale: true,
    },
    animationDuration: 500,
    animationEasing: 'cubicOut',
    series: tagNames.map((tag, i) => {
      const palette = PALETTE[i % PALETTE.length];
      return {
        name: tag,
        type: 'line',
        showSymbol: false,
        smooth: 0.3,
        lineStyle: { width: 2.5, color: palette.line },
        itemStyle: { color: palette.line },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: palette.areaTop },
            { offset: 1, color: palette.areaBottom },
          ]),
        },
        emphasis: {
          focus: 'series',
          lineStyle: { width: 3 },
        },
        data: [],
      };
    }),
  }), [tagNames]);

  // Initialize chart
  useEffect(() => {
    if (!chartRef.current) return;

    chartInstance.current = echarts.init(chartRef.current, undefined, {
      renderer: 'canvas',
    });
    chartInstance.current.setOption(buildOption());

    // Reset buffer
    dataBufferRef.current = {};
    tagNames.forEach(tag => {
      dataBufferRef.current[tag] = [];
    });

    const handleResize = () => chartInstance.current?.resize();
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(chartRef.current);
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
      chartInstance.current?.dispose();
      chartInstance.current = null;
    };
  }, [tagNames, buildOption]);

  // Subscribe to telemetry for real-time data push
  useEffect(() => {
    const unsubscribe = useTelemetryStore.subscribe((state) => {
      if (!chartInstance.current) return;

      let hasUpdates = false;
      const buffer = dataBufferRef.current;

      tagNames.forEach(tag => {
        const point = state.latestValues[tag];
        if (point && point.value !== undefined) {
          const arr = buffer[tag];
          if (!arr) return;

          const lastPoint = arr.length > 0 ? arr[arr.length - 1] : null;

          if (!lastPoint || new Date(point.timestamp).getTime() > new Date(lastPoint.value[0]).getTime()) {
            arr.push({
              name: point.timestamp,
              value: [point.timestamp, point.value],
            });

            // Rolling window
            if (arr.length > windowSize) {
              arr.shift();
            }
            hasUpdates = true;
          }
        }
      });

      if (hasUpdates) {
        chartInstance.current.setOption({
          series: tagNames.map(tag => ({
            name: tag,
            data: buffer[tag] || [],
          })),
        });
      }
    });

    return () => unsubscribe();
  }, [tagNames, windowSize]);

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 w-full h-full flex flex-col min-h-[320px] relative overflow-hidden">
      {/* Decorative top border gradient */}
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-blue-500 via-emerald-400 to-violet-500 opacity-60" />

      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-bold text-slate-800 tracking-tight">{title}</h3>
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">Live</span>
        </div>
      </div>

      <div className="flex-1 w-full relative min-h-[240px]">
        <div ref={chartRef} className="absolute inset-0" />
      </div>
    </div>
  );
};
