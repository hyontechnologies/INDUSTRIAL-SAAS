import { useState, useEffect, useMemo } from 'react';
import { Download, FileText } from 'lucide-react';
import type { ColumnDef } from '@tanstack/react-table';
import { DailyReportTable } from './components/DailyReportTable';
import { useAppStore } from '../../shared/stores/useAppStore';

const REPORT_TAGS = ['DT-401', 'TE-201', 'LT-201', 'PT-201', 'FT-101'];
const REPORT_LABELS: Record<string, string> = {
  'DT-401': 'Furnace Draught',
  'TE-201': 'Main Steam Temp',
  'LT-201': 'Drum Level 1',
  'PT-201': 'Drum Pressure',
  'FT-101': 'Feed Water Flow',
};

export default function ReportsPage() {
  const selectedPlantId = useAppStore(s => s.selectedPlantId) || 'PICCADILY_PLANT_01';

  const [data, setData] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      try {
        const end = new Date();
        const start = new Date(end.getTime() - 24 * 60 * 60 * 1000); // 24 hours ago

        const params = new URLSearchParams({
          plant_id: selectedPlantId,
          tags: REPORT_TAGS.join(','),
          start: start.toISOString(),
          end: end.toISOString(),
          interval: '15m',
          agg: 'avg'
        });

        const res = await fetch(`/api/v1/telemetry/multi-history?${params}`);
        if (res.ok) {
          const json = await res.json();
          setData(json.data);
        }
      } catch (err) {
        console.error("Failed to load report", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [selectedPlantId]);

  const columns = useMemo<ColumnDef<any, any>[]>(() => {
    const cols: ColumnDef<any, any>[] = [
      {
        accessorKey: 'ts',
        header: 'TIMESTAMP',
        cell: (info) => {
          const date = new Date(info.getValue());
          return date.toLocaleString();
        }
      }
    ];

    REPORT_TAGS.forEach(tag => {
      cols.push({
        accessorKey: tag,
        header: REPORT_LABELS[tag] || tag,
        cell: (info) => {
          const val = info.getValue();
          return val !== undefined && val !== null ? Number(val).toFixed(2) : '—';
        }
      });
    });

    return cols;
  }, []);

  return (
    <div className="space-y-4 max-w-[1600px] mx-auto h-full flex flex-col">
      <div className="flex items-center justify-between border-b border-scada-border pb-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2 uppercase tracking-wide">
            <FileText className="w-5 h-5 text-indigo-400" />
            Daily Report
          </h1>
          <p className="text-xs text-slate-500 mt-1 uppercase tracking-wider">Tabular Historian Data Export</p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-sm transition-colors uppercase tracking-wider">
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-[400px]">
        <DailyReportTable
          data={data}
          columns={columns}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
