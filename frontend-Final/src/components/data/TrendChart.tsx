import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import { useTelemetryStore } from '../../stores/useTelemetryStore';

interface TrendChartProps {
  title: string;
  tagNames: string[];
  timeRange?: string; // '1h', '24h', etc
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'];

export const TrendChart: React.FC<TrendChartProps> = ({ title, tagNames, timeRange = '1h' }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  // Track data points imperatively to avoid React re-renders on every tick
  const dataBufferRef = useRef<Record<string, { name: string, value: [string, number] }[]>>({});

  // Initialize chart
  useEffect(() => {
    if (!chartRef.current) return;

    chartInstance.current = echarts.init(chartRef.current);

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      legend: {
        data: tagNames,
        bottom: 0,
        icon: 'circle',
        textStyle: { color: '#64748b' }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '5%',
        containLabel: true
      },
      xAxis: {
        type: 'time',
        splitLine: { show: false },
        axisLine: { lineStyle: { color: '#cbd5e1' } }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
        scale: true
      },
      series: tagNames.map((tag, i) => ({
        name: tag,
        type: 'line',
        showSymbol: false,
        smooth: true,
        itemStyle: { color: COLORS[i % COLORS.length] },
        data: []
      }))
    };

    chartInstance.current.setOption(option);

    // Clear buffer on tag change
    dataBufferRef.current = {};
    tagNames.forEach(tag => {
      dataBufferRef.current[tag] = [];
    });

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstance.current?.dispose();
    };
  }, [tagNames]);

  // Subscribe to telemetry store directly to avoid rendering on every tick
  useEffect(() => {
    const unsubscribe = useTelemetryStore.subscribe((state) => {
      if (!chartInstance.current) return;

      let hasUpdates = false;
      const buffer = dataBufferRef.current;

      tagNames.forEach(tag => {
        const point = state.latestValues[tag];
        if (point && point.value !== undefined) {
          const arr = buffer[tag];
          if (!arr) return; // Wait for init

          const lastPoint = arr.length > 0 ? arr[arr.length - 1] : null;

          if (!lastPoint || new Date(point.timestamp).getTime() > new Date(lastPoint.value[0]).getTime()) {
            arr.push({
              name: point.timestamp,
              value: [point.timestamp, point.value]
            });

            // Keep last 150 points for a nice rolling window
            if (arr.length > 150) {
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
            data: buffer[tag] || []
          }))
        });
      }
    });

    return () => unsubscribe();
  }, [tagNames]);

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 w-full h-full flex flex-col min-h-[300px]">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>

        <div className="flex gap-2">
          {['1h', '6h', '24h'].map(t => (
            <button
              key={t}
              className={`px-2 py-1 text-xs rounded font-medium ${timeRange === t ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50'}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 w-full relative min-h-[200px]">
        <div ref={chartRef} className="absolute inset-0" />
      </div>
    </div>
  );
};
