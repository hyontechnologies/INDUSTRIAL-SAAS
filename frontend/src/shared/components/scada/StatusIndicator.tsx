import { cn } from '../../utils/cn';

interface StatusIndicatorProps {
  status: 'good' | 'warning' | 'critical' | 'stale';
  className?: string;
}

export function StatusIndicator({ status, className }: StatusIndicatorProps) {
  return (
    <div className={cn('relative flex items-center justify-center w-3 h-3', className)}>
      {status === 'critical' && (
        <span className="absolute inline-flex h-full w-full rounded-full bg-scada-critical opacity-75 animate-status-blink"></span>
      )}
      <span className={cn(
        "relative inline-flex rounded-full w-2.5 h-2.5 border border-black/20 shadow-sm",
        status === 'good' ? 'bg-scada-good scada-glow-good' :
        status === 'warning' ? 'bg-scada-warning scada-glow-warning' :
        status === 'critical' ? 'bg-scada-critical scada-glow-critical' :
        'bg-scada-stale'
      )}></span>
    </div>
  );
}
