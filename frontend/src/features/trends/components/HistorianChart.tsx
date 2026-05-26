import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

export interface HistorianDataPoint {
  ts: string; // ISO string
  [tagName: string]: string | number | boolean | null | undefined; // tag values
}

interface HistorianChartProps {
  data: HistorianDataPoint[];
  tags: { name: string; color: string }[];
  yAxisUnit?: string;
  className?: string;
  isLoading?: boolean;
}

export const HistorianChart = React.memo(function HistorianChart({
  data,
  tags,
  yAxisUnit = '',
  className = '',
  isLoading = false
}: HistorianChartProps) {

  const formattedData = useMemo(() => {
    return data.map(d => ({
      ...d,
      timeLabel: new Date(d.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }));
  }, [data]);

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center bg-[#0a0f1c] border border-scada-border rounded-sm ${className}`}>
        <div className="flex flex-col items-center gap-2">
          <div className="w-6 h-6 border-2 border-scada-good border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">Loading Historian Data...</span>
        </div>
      </div>
    );
  }

  if (formattedData.length === 0) {
    return (
      <div className={`flex items-center justify-center bg-[#0a0f1c] border border-scada-border rounded-sm ${className}`}>
        <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">No Data Available</span>
      </div>
    );
  }

  return (
    <div className={`bg-[#0a0f1c] border border-scada-border p-4 rounded-sm ${className}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={formattedData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          {/* Industrial Grid */}
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />

          <XAxis
            dataKey="timeLabel"
            stroke="#64748b"
            fontSize={10}
            tickMargin={10}
            minTickGap={30}
          />

          <YAxis
            stroke="#64748b"
            fontSize={10}
            tickFormatter={(val) => `${val}${yAxisUnit}`}
            domain={['auto', 'auto']}
            width={60}
          />

          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              borderColor: '#334155',
              fontSize: '11px',
              fontFamily: 'monospace'
            }}
            itemStyle={{ color: '#f8fafc' }}
            labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
          />

          <Legend
            wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }}
            iconType="line"
          />

          {tags.map((tag) => (
            <Line
              key={tag.name}
              type="monotone"
              dataKey={tag.name}
              stroke={tag.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              isAnimationActive={false} // Disable animation for performance with high-frequency data
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
});
