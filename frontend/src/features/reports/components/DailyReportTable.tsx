
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table';

interface DailyReportTableProps {
  data: any[];
  columns: ColumnDef<any, any>[];
  isLoading?: boolean;
}

export function DailyReportTable({ data, columns, isLoading }: DailyReportTableProps) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="rounded-sm border border-scada-border overflow-hidden bg-[#0a0f1c] flex flex-col h-full">
      <div className="overflow-auto flex-1 scada-scrollbar">
        <table className="w-full text-left text-xs whitespace-nowrap">
          <thead className="sticky top-0 bg-scada-panel z-10 shadow-sm border-b border-scada-border">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-2 font-bold text-slate-300 uppercase tracking-wider border-r border-scada-border last:border-0"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="h-32 text-center text-slate-500">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                    Loading Report Data...
                  </div>
                </td>
              </tr>
            ) : table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="h-32 text-center text-slate-500 uppercase tracking-widest font-bold text-[10px]">
                  No Data Found
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b border-scada-border hover:bg-slate-800/30 transition-colors">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-1.5 border-r border-scada-border/50 last:border-0 text-slate-200 tabular-nums">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
