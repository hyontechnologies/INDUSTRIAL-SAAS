import React, { useEffect, useState } from 'react';
import { useTelemetryStore } from '../../stores/useTelemetryStore';
import { formatValue } from '../../utils/formatters';

interface RealtimeValueProps {
  tagName: string;
  decimals?: number;
  unit?: string;
  fallback?: string;
  showQuality?: boolean;
}

export const RealtimeValue: React.FC<RealtimeValueProps> = ({
  tagName,
  decimals = 2,
  unit,
  fallback = '--',
  showQuality = true
}) => {
  const point = useTelemetryStore(state => state.getTagValue(tagName));
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (point) {
      setFlash(true);
      const timer = setTimeout(() => setFlash(false), 300);
      return () => clearTimeout(timer);
    }
  }, [point?.value]);

  if (!point) return <span className="text-slate-400 font-mono">{fallback}</span>;

  const isStale = point.quality === 'STALE';
  const displayUnit = unit || point.unit || '';

  return (
    <div className="inline-flex items-center gap-2">
      <span className={`font-mono transition-colors duration-300 ${
        flash ? 'text-blue-500' : isStale ? 'text-slate-400' : 'text-slate-900'
      }`}>
        {formatValue(point.value, decimals)}
        {displayUnit && <span className="ml-1 text-xs text-slate-500">{displayUnit}</span>}
      </span>

      {showQuality && isStale && (
        <span className="bg-slate-100 text-slate-500 text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider" title="Data is stale">
          Stale
        </span>
      )}

      {showQuality && point.quality === 'BAD' && (
        <span className="bg-rose-100 text-rose-600 text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider" title="Sensor reported bad quality">
          Bad
        </span>
      )}
    </div>
  );
};
