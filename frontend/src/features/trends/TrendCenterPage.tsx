import { useState, useEffect } from 'react';
import { Activity } from 'lucide-react';
import { HistorianChart } from './components/HistorianChart';
import type { HistorianDataPoint } from './components/HistorianChart';
import { useAppStore } from '../../shared/stores/useAppStore';

const DEFAULT_TAGS = ['PT-201', 'PT-202'];

export default function TrendCenterPage() {
  const selectedPlantId = useAppStore(s => s.selectedPlantId) || 'PICCADILY_PLANT_01';


  const [data, setData] = useState<HistorianDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const end = new Date();
        const start = new Date(end.getTime() - 60 * 60 * 1000); // 1 hour ago

        const params = new URLSearchParams({
          plant_id: selectedPlantId,
          tags: DEFAULT_TAGS.join(','),
          start: start.toISOString(),
          end: end.toISOString(),
          interval: '1m',
          agg: 'avg'
        });

        const res = await fetch(`/api/v1/telemetry/multi-history?${params}`);
        if (res.ok) {
          const json = await res.json();
          // The API returns data sorted newest to oldest. Recharts needs oldest to newest.
          setData([...json.data].reverse());
        }
      } catch (err) {
        console.error("Failed to load history", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [selectedPlantId]);

  const chartTags = [
    { name: 'PT-201', color: '#38bdf8' },
    { name: 'PT-202', color: '#f43f5e' }
  ];

  return (
    <div className="space-y-4 max-w-[1600px] mx-auto h-full flex flex-col">
      <div className="flex items-center justify-between border-b border-scada-border pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2 uppercase tracking-wide">
            <Activity className="w-5 h-5 text-blue-400" />
            Trend Center
          </h1>
          <p className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Industrial Historian Visualization</p>
        </div>
        <div className="flex gap-2">
          {['15m', '1h', '8h', '24h'].map(t => (
            <button key={t} className={`px-3 py-1 text-xs font-bold rounded-sm border ${t === '1h' ? 'bg-blue-500/20 text-blue-400 border-blue-500/50' : 'bg-scada-panel text-slate-400 border-scada-border hover:bg-slate-800'}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-[400px]">
        <HistorianChart
          data={data}
          tags={chartTags}
          yAxisUnit=" kg/cm2"
          isLoading={isLoading}
          className="h-full"
        />
      </div>
    </div>
  );
}
