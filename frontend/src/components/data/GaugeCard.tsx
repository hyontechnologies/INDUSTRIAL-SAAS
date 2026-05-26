import React, { useEffect, useRef, useCallback } from 'react';
import * as echarts from 'echarts';
import { useTelemetryStore } from '../../stores/useTelemetryStore';

interface GaugeCardProps {
  title: string;
  tagName: string;
  unit: string;
  min?: number;
  max?: number;
  /** Optional threshold zones: [lowLow, low, high, highHigh] */
  thresholds?: [number, number, number, number];
  children?: React.ReactNode;
}

/**
 * Build the color stops for the gauge arc.
 * Green = normal, Amber = warning, Red = critical
 */
function buildAxisLineColors(
  min: number,
  max: number,
  thresholds?: [number, number, number, number]
): [number, string][] {
  if (!thresholds) {
    // Default: bottom 20% amber, middle 60% green, top 20% amber
    return [
      [0.15, '#ef4444'],   // red – critical low
      [0.30, '#f59e0b'],   // amber – warning low
      [0.70, '#10b981'],   // green – normal
      [0.85, '#f59e0b'],   // amber – warning high
      [1,    '#ef4444'],   // red – critical high
    ];
  }

  const [lowLow, low, high, highHigh] = thresholds;
  const range = max - min;
  if (range <= 0) {
    return [[1, '#10b981']];
  }

  const normalize = (v: number) => Math.max(0, Math.min(1, (v - min) / range));

  return [
    [normalize(lowLow),  '#ef4444'],   // critical low
    [normalize(low),     '#f59e0b'],   // warning low
    [normalize(high),    '#10b981'],   // normal
    [normalize(highHigh),'#f59e0b'],   // warning high
    [1,                  '#ef4444'],   // critical high
  ];
}

export const GaugeCard: React.FC<GaugeCardProps> = ({
  title,
  tagName,
  unit,
  min = 0,
  max = 100,
  thresholds,
  children,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const currentValueRef = useRef<number>(min);

  // Build initial ECharts option
  const buildOption = useCallback(
    (value: number): echarts.EChartsOption => ({
      series: [
        {
          type: 'gauge',
          radius: '90%',
          center: ['50%', '55%'],
          startAngle: 220,
          endAngle: -40,
          min,
          max,
          splitNumber: 5,
          pointer: {
            icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
            length: '55%',
            width: 8,
            offsetCenter: [0, '-10%'],
            itemStyle: {
              color: 'auto',
              shadowColor: 'rgba(0,0,0,0.25)',
              shadowBlur: 6,
              shadowOffsetY: 2,
            },
          },
          axisLine: {
            lineStyle: {
              width: 16,
              color: buildAxisLineColors(min, max, thresholds),
            },
            roundCap: true,
          },
          axisTick: {
            distance: -18,
            length: 6,
            lineStyle: { color: '#cbd5e1', width: 1 },
          },
          splitLine: {
            distance: -22,
            length: 12,
            lineStyle: { color: '#94a3b8', width: 2 },
          },
          axisLabel: {
            distance: 28,
            color: '#64748b',
            fontSize: 10,
            fontFamily: 'Inter, system-ui, sans-serif',
            formatter: (v: number) => {
              if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k`;
              return Number.isInteger(v) ? v.toString() : v.toFixed(1);
            },
          },
          progress: {
            show: true,
            width: 16,
            roundCap: true,
            itemStyle: { color: 'auto' },
          },
          detail: {
            valueAnimation: true,
            formatter: (v: number) => {
              const display = Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(1);
              return `{value|${display}}\n{unit|${unit}}`;
            },
            rich: {
              value: {
                fontSize: 28,
                fontWeight: 700,
                fontFamily: 'Inter, system-ui, sans-serif',
                color: '#1e293b',
                padding: [0, 0, 4, 0],
              },
              unit: {
                fontSize: 12,
                fontWeight: 500,
                fontFamily: 'Inter, system-ui, sans-serif',
                color: '#94a3b8',
              },
            },
            offsetCenter: [0, '40%'],
          },
          title: { show: false },
          data: [{ value }],
          animationDuration: 800,
          animationEasingUpdate: 'cubicOut',
        },
      ],
    }),
    [min, max, unit, thresholds]
  );

  // Initialize chart
  useEffect(() => {
    if (!chartRef.current) return;

    chartInstance.current = echarts.init(chartRef.current, undefined, {
      renderer: 'canvas',
    });
    chartInstance.current.setOption(buildOption(min));

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
  }, [buildOption, min]);

  // Subscribe to telemetry store for real-time updates (imperative, no re-renders)
  useEffect(() => {
    const unsubscribe = useTelemetryStore.subscribe((state) => {
      if (!chartInstance.current) return;
      const point = state.latestValues[tagName];
      if (point && point.value !== undefined && point.value !== currentValueRef.current) {
        currentValueRef.current = point.value;
        chartInstance.current.setOption({
          series: [{ data: [{ value: point.value }] }],
        });
      }
    });
    return () => unsubscribe();
  }, [tagName]);

  return (
    <div className="glassmorphism-card rounded-xl p-4 flex flex-col relative overflow-hidden group">
      {/* Subtle decorative glow */}
      <div className="absolute -right-8 -top-8 w-28 h-28 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-colors duration-700" />

      <div className="flex justify-between items-center mb-1 relative z-10">
        <h3 className="text-sm font-semibold text-slate-700 tracking-tight">{title}</h3>
        <div className="text-[10px] text-slate-400 font-mono bg-slate-50 px-2 py-0.5 rounded-md border border-slate-100">
          {min} – {max} {unit}
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center min-h-[200px] relative z-10">
        {children || <div ref={chartRef} className="w-full h-full min-h-[200px]" />}
      </div>
    </div>
  );
};
