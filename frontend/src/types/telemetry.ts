export interface TagMetadata {
  tag_name: string;
  description: string | null;
  engineering_unit: string | null;
  low_low_limit: number | null;
  low_limit: number | null;
  high_limit: number | null;
  high_high_limit: number | null;
  opc_node_id: string | null;
  is_active: boolean;
}

export type DataQuality = 'GOOD' | 'BAD' | 'UNCERTAIN' | 'STALE';

export interface TelemetryPoint {
  value: number;
  quality: DataQuality;
  timestamp: string;
  unit?: string | null;
}

export interface TelemetryFrame {
  type: 'telemetry';
  timestamp: string;
  data: Record<string, { v: number; q: DataQuality; t: string }>;
}
