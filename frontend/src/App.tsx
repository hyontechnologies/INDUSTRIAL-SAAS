import { useState, useEffect, useRef } from 'react';
import {
  Activity,
  AlertTriangle,
  Database,
  Bell,
  TrendingUp,
  Grid,
  Sliders,
  Search,
  CheckCircle,
  X,
  Layers,
  Thermometer,
  Gauge as GaugeIcon,
  Wind
} from 'lucide-react';
import {
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  AreaChart,
  Area
} from 'recharts';
import * as echarts from 'echarts';

// Types matching backend models
interface TagMetadata {
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

interface TelemetryPoint {
  value: number;
  quality: string;
  timestamp: string;
  unit?: string | null;
}

interface Alarm {
  alarm_id: string;
  tag_name: string;
  severity: 'INFO' | 'WARNING' | 'ALARM' | 'CRITICAL';
  alarm_state: 'ACTIVE' | 'ACKNOWLEDGED' | 'CLEARED';
  message: string;
  trigger_value: number;
  occurred_at: string;
  acked_by?: string | null;
  acked_at?: string | null;
}

export default function App() {
  // Navigation & UI States
  const [activeTab, setActiveTab] = useState<'dashboard' | 'history' | 'tags' | 'alarms'>('dashboard');
  const [selectedPlant, setSelectedPlant] = useState('BOILER_PLC_01');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTag, setSelectedTag] = useState<string | null>('TT-201');

  // Simulation vs Live Connection States
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [lastMessageTime, setLastMessageTime] = useState<string | null>(null);

  // Application Data States
  const [tags, setTags] = useState<Record<string, TagMetadata>>({});
  const [latestData, setLatestData] = useState<Record<string, TelemetryPoint>>({});
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [alarms, setAlarms] = useState<Alarm[]>([]);
  const [statistics, setStatistics] = useState({
    pointsProcessed: 0,
    alarmsTriggered: 0,
    activeCriticalCount: 0
  });

  // ECharts Gauge Ref
  const gaugeRef = useRef<HTMLDivElement>(null);
  const gaugeInstance = useRef<echarts.ECharts | null>(null);

  // Setup initial mock data for demo robustness if backend is offline
  useEffect(() => {
    // Seed metadata matching database seeds
    const mockTags: Record<string, TagMetadata> = {
      'TT-201': { tag_name: 'TT-201', description: 'Superheater Outlet Temp 1', engineering_unit: '°C', low_low_limit: 100, low_limit: 150, high_limit: 480, high_high_limit: 520, opc_node_id: 'ns=2;s=BOILER_PLC_01.Temperature.TT-201', is_active: true },
      'TT-202': { tag_name: 'TT-202', description: 'Superheater Outlet Temp 2', engineering_unit: '°C', low_low_limit: 100, low_limit: 150, high_limit: 480, high_high_limit: 520, opc_node_id: 'ns=2;s=BOILER_PLC_01.Temperature.TT-202', is_active: true },
      'TT-301': { tag_name: 'TT-301', description: 'Main Steam Temp', engineering_unit: '°C', low_low_limit: 100, low_limit: 150, high_limit: 490, high_high_limit: 530, opc_node_id: 'ns=2;s=BOILER_PLC_01.Temperature.TT-301', is_active: true },
      'PT-201': { tag_name: 'PT-201', description: 'Main Steam Pressure', engineering_unit: 'bar', low_low_limit: 10, low_limit: 20, high_limit: 95, high_high_limit: 105, opc_node_id: 'ns=2;s=BOILER_PLC_01.Pressure.PT-201', is_active: true },
      'LT-201': { tag_name: 'LT-201', description: 'Steam Drum Level 1', engineering_unit: '%', low_low_limit: 10, low_limit: 20, high_limit: 85, high_high_limit: 95, opc_node_id: 'ns=2;s=BOILER_PLC_01.Level.LT-201', is_active: true },
      'FT-101': { tag_name: 'FT-101', description: 'Feed Water Flow', engineering_unit: 't/h', low_low_limit: 5, low_limit: 10, high_limit: 100, high_high_limit: 120, opc_node_id: 'ns=2;s=BOILER_PLC_01.Flow.FT-101', is_active: true },
      'DT-301': { tag_name: 'DT-301', description: 'Furnace Draught', engineering_unit: 'mmWC', low_low_limit: -20, low_limit: -15, high_limit: -3, high_high_limit: -2, opc_node_id: 'ns=2;s=BOILER_PLC_01.Draught.DT-301', is_active: true }
    };
    setTags(mockTags);

    // Initial values
    const nowIso = new Date().toISOString();
    const initialLatest: Record<string, TelemetryPoint> = {
      'TT-201': { value: 432.5, quality: 'GOOD', timestamp: nowIso, unit: '°C' },
      'TT-202': { value: 429.1, quality: 'GOOD', timestamp: nowIso, unit: '°C' },
      'TT-301': { value: 462.8, quality: 'GOOD', timestamp: nowIso, unit: '°C' },
      'PT-201': { value: 87.2, quality: 'GOOD', timestamp: nowIso, unit: 'bar' },
      'LT-201': { value: 49.5, quality: 'GOOD', timestamp: nowIso, unit: '%' },
      'FT-101': { value: 65.4, quality: 'GOOD', timestamp: nowIso, unit: 't/h' },
      'DT-301': { value: -6.5, quality: 'GOOD', timestamp: nowIso, unit: 'mmWC' }
    };
    setLatestData(initialLatest);

    // Seed mock history
    const history: any[] = [];
    for (let i = 20; i >= 0; i--) {
      const pastTime = new Date(Date.now() - i * 5000);
      history.push({
        time: pastTime.toLocaleTimeString(),
        'TT-201': 420 + Math.random() * 25,
        'TT-202': 415 + Math.random() * 25,
        'TT-301': 450 + Math.random() * 20,
        'PT-201': 85 + Math.random() * 5,
        'LT-201': 48 + Math.random() * 4,
        'FT-101': 60 + Math.random() * 10
      });
    }
    setHistoryData(history);

    // Seed mock alarms
    setAlarms([
      {
        alarm_id: '1',
        tag_name: 'TT-201',
        severity: 'WARNING',
        alarm_state: 'ACTIVE',
        message: 'Superheater Outlet Temp 1 is approaching High Limit (480.0°C)',
        trigger_value: 482.5,
        occurred_at: new Date(Date.now() - 30000).toISOString()
      }
    ]);
  }, []);

  // Fetch true metadata and alerts if backend api works
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const response = await fetch(`/api/v1/tags?plant_id=${selectedPlant}`);
        if (response.ok) {
          const data = await response.json();
          // Convert array to record
          const record: Record<string, TagMetadata> = {};
          data.forEach((tag: TagMetadata) => {
            record[tag.tag_name] = tag;
          });
          setTags(record);
        }
      } catch (err) {
        console.log("Using local database simulation (API offline/local-first)");
      }
    };
    fetchMetadata();
  }, [selectedPlant]);

  // WebSocket Connection for Real-Time Stream
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: any = null;

    const connectWS = () => {
      setConnectionStatus('connecting');
      const wsUrl = `ws://${window.location.host}/api/v1/ws/live?tenant_id=piccadily&plant_id=${selectedPlant}`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnectionStatus('connected');
        console.log("WebSocket linked successfully to live stream.");
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setLastMessageTime(new Date().toLocaleTimeString());
          if (payload.type === 'telemetry' && payload.data) {
            // Update latest readings
            setLatestData(prev => {
              const updated = { ...prev };
              Object.entries(payload.data).forEach(([tag, valObj]: [string, any]) => {
                updated[tag] = {
                  value: valObj.v,
                  quality: valObj.q,
                  timestamp: valObj.t || new Date().toISOString()
                };
              });
              return updated;
            });

            // Update history chart data
            setHistoryData(prev => {
              const now = new Date();
              const newEntry: any = { time: now.toLocaleTimeString() };
              Object.entries(payload.data).forEach(([tag, valObj]: [string, any]) => {
                newEntry[tag] = valObj.v;
              });
              const sliced = prev.length > 25 ? prev.slice(1) : prev;
              return [...sliced, newEntry];
            });

            // Update internal statistics
            setStatistics(prev => ({
              ...prev,
              pointsProcessed: prev.pointsProcessed + payload.count,
              alarmsTriggered: prev.alarmsTriggered + (payload.alarm_events?.length || 0)
            }));
          }

          // Handle incoming live alarm triggers
          if (payload.alarm_events && payload.alarm_events.length > 0) {
            setAlarms(prev => {
              const incoming = payload.alarm_events.map((a: any, idx: number) => ({
                alarm_id: `${Date.now()}-${idx}`,
                tag_name: a.tag,
                severity: a.severity,
                alarm_state: 'ACTIVE',
                message: a.msg,
                trigger_value: a.val,
                occurred_at: new Date().toISOString()
              }));
              return [...incoming, ...prev];
            });
          }
        } catch (err) {
          console.error("Error decoding WS frame: ", err);
        }
      };

      ws.onerror = () => {
        setConnectionStatus('disconnected');
      };

      ws.onclose = () => {
        setConnectionStatus('disconnected');
        // Auto-reconnect every 5 seconds
        reconnectTimer = setTimeout(connectWS, 5000);
      };
    };

    connectWS();

    return () => {
      if (ws) ws.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [selectedPlant]);

  // Simulation Interval when offline/disconnected to keep UI highly dynamic
  useEffect(() => {
    if (connectionStatus === 'connected') return;

    const timer = setInterval(() => {
      const nowIso = new Date().toISOString();
      const timeStr = new Date().toLocaleTimeString();

      // Slightly perturb values
      setLatestData(prev => {
        const next = { ...prev };

        // Temperature fluctuates around 430
        const tt201 = 430 + Math.sin(Date.now() / 10000) * 15 + (Math.random() - 0.5) * 2;
        next['TT-201'] = { value: parseFloat(tt201.toFixed(1)), quality: 'GOOD', timestamp: nowIso };

        const tt202 = 425 + Math.cos(Date.now() / 12000) * 12 + (Math.random() - 0.5) * 1.8;
        next['TT-202'] = { value: parseFloat(tt202.toFixed(1)), quality: 'GOOD', timestamp: nowIso };

        const tt301 = 460 + Math.sin(Date.now() / 15000) * 18 + (Math.random() - 0.5) * 2.5;
        next['TT-301'] = { value: parseFloat(tt301.toFixed(1)), quality: 'GOOD', timestamp: nowIso };

        // Pressure fluctuates around 85
        const pt201 = 85 + Math.sin(Date.now() / 8000) * 4 + (Math.random() - 0.5) * 0.5;
        next['PT-201'] = { value: parseFloat(pt201.toFixed(1)), quality: 'GOOD', timestamp: nowIso };

        // Level fluctuates around 50
        const lt201 = 50 + Math.sin(Date.now() / 5000) * 2 + (Math.random() - 0.5) * 0.2;
        next['LT-201'] = { value: parseFloat(lt201.toFixed(1)), quality: 'GOOD', timestamp: nowIso };

        // Flow fluctuates around 65
        const ft101 = 65 + Math.sin(Date.now() / 7000) * 5 + (Math.random() - 0.5) * 0.8;
        next['FT-101'] = { value: parseFloat(ft101.toFixed(1)), quality: 'GOOD', timestamp: nowIso };

        // Draught
        const dt301 = -6.5 + Math.sin(Date.now() / 6000) * 1.5;
        next['DT-301'] = { value: parseFloat(dt301.toFixed(2)), quality: 'GOOD', timestamp: nowIso };

        return next;
      });

      // Update history
      setHistoryData(prev => {
        const newEntry = {
          time: timeStr,
          'TT-201': 430 + Math.sin(Date.now() / 10000) * 15 + (Math.random() - 0.5) * 2,
          'TT-202': 425 + Math.cos(Date.now() / 12000) * 12 + (Math.random() - 0.5) * 1.8,
          'TT-301': 460 + Math.sin(Date.now() / 15000) * 18 + (Math.random() - 0.5) * 2.5,
          'PT-201': 85 + Math.sin(Date.now() / 8000) * 4 + (Math.random() - 0.5) * 0.5,
          'LT-201': 50 + Math.sin(Date.now() / 5000) * 2 + (Math.random() - 0.5) * 0.2,
          'FT-101': 65 + Math.sin(Date.now() / 7000) * 5 + (Math.random() - 0.5) * 0.8
        };
        const sliced = prev.length > 25 ? prev.slice(1) : prev;
        return [...sliced, newEntry];
      });

      setStatistics(prev => ({
        ...prev,
        pointsProcessed: prev.pointsProcessed + 7
      }));

      // Randomly trigger warning alarm once in a while in mock mode
      if (Math.random() > 0.95 && alarms.length < 5) {
        const warningTags = ['TT-201', 'PT-201', 'LT-201'];
        const tag = warningTags[Math.floor(Math.random() * warningTags.length)];
        const limit = tag === 'TT-201' ? 480 : tag === 'PT-201' ? 95 : 85;
        const val = limit + Math.random() * 5;

        setAlarms(prev => [
          {
            alarm_id: Math.random().toString(),
            tag_name: tag,
            severity: val > limit + 3 ? 'CRITICAL' : 'ALARM',
            alarm_state: 'ACTIVE',
            message: `${tag} High limit exceeded! Current value: ${val.toFixed(1)}`,
            trigger_value: parseFloat(val.toFixed(1)),
            occurred_at: new Date().toISOString()
          },
          ...prev
        ]);
      }

    }, 3000);

    return () => clearInterval(timer);
  }, [connectionStatus, alarms]);

  // ECharts Gauge render and update
  useEffect(() => {
    if (!gaugeRef.current) return;

    if (!gaugeInstance.current) {
      gaugeInstance.current = echarts.init(gaugeRef.current);
    }

    const currentVal = latestData[selectedTag || 'TT-201']?.value || 0;
    const tagMeta = tags[selectedTag || 'TT-201'];
    const maxLimit = tagMeta?.high_high_limit || 600;
    const unit = tagMeta?.engineering_unit || '';

    const option = {
      series: [
        {
          type: 'gauge',
          center: ['50%', '55%'],
          startAngle: 200,
          endAngle: -20,
          min: 0,
          max: maxLimit * 1.2,
          splitNumber: 8,
          itemStyle: {
            color: '#6366f1' // Indigo 500
          },
          progress: {
            show: true,
            width: 12
          },
          pointer: {
            show: true,
            length: '60%',
            width: 6,
            itemStyle: {
              color: '#f43f5e' // Rose 500
            }
          },
          axisLine: {
            lineStyle: {
              width: 12,
              color: [
                [0.7, '#10b981'], // Safe - Green
                [0.9, '#f59e0b'], // Warning - Amber
                [1, '#ef4444']    // Critical - Red
              ]
            }
          },
          axisTick: {
            distance: -12,
            splitNumber: 5,
            lineStyle: {
              width: 2,
              color: '#999'
            }
          },
          splitLine: {
            distance: -12,
            length: 12,
            lineStyle: {
              width: 3,
              color: '#fff'
            }
          },
          axisLabel: {
            distance: 14,
            color: '#94a3b8',
            fontSize: 10
          },
          anchor: {
            show: true,
            showAbove: true,
            size: 16,
            itemStyle: {
              borderWidth: 10,
              borderColor: '#6366f1'
            }
          },
          title: {
            show: false
          },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, '70%'],
            fontSize: 22,
            fontWeight: 'bold',
            formatter: `{value} ${unit}`,
            color: '#f8fafc'
          },
          data: [
            {
              value: currentVal
            }
          ]
        }
      ]
    };

    gaugeInstance.current.setOption(option);

    const handleResize = () => {
      gaugeInstance.current?.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [latestData, selectedTag, tags]);

  // Acknowledge Alarm handler
  const acknowledgeAlarm = async (alarmId: string) => {
    try {
      const response = await fetch('/api/v1/alarms/acknowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alarm_id: alarmId,
          acked_by: 'Operator_App',
          comment: 'Acknowledged via SCADA panel'
        })
      });
      if (response.ok) {
        setAlarms(prev => prev.map(a => a.alarm_id === alarmId ? { ...a, alarm_state: 'ACKNOWLEDGED', acked_by: 'Operator_App', acked_at: new Date().toISOString() } : a));
      }
    } catch (err) {
      // Fallback update in mock mode
      setAlarms(prev => prev.map(a => a.alarm_id === alarmId ? { ...a, alarm_state: 'ACKNOWLEDGED', acked_by: 'Operator_App', acked_at: new Date().toISOString() } : a));
    }
  };

  // Clear Alarm handler
  const clearAlarm = async (alarmId: string) => {
    try {
      const response = await fetch('/api/v1/alarms/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plant_id: selectedPlant,
          alarm_ids: [alarmId],
          cleared_by: 'Operator_App',
          comment: 'Cleared via SCADA panel'
        })
      });
      if (response.ok) {
        setAlarms(prev => prev.filter(a => a.alarm_id !== alarmId));
      }
    } catch (err) {
      // Fallback remove in mock mode
      setAlarms(prev => prev.filter(a => a.alarm_id !== alarmId));
    }
  };

  // Filter tags list based on search query
  const filteredTags = Object.values(tags).filter(tag =>
    tag.tag_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (tag.description && tag.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-slate-950 font-sans text-slate-100">

      {/* ── HEADER ── */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md px-6 py-4 flex flex-wrap justify-between items-center gap-4 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600/20 text-indigo-400 p-2 rounded-lg border border-indigo-500/30">
            <Activity className="h-6 w-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              PICCADILY HISTORIAN <span className="text-[10px] uppercase bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded">v3.0</span>
            </h1>
            <p className="text-xs text-slate-400">Industrial SCADA & Digital Twin Platform</p>
          </div>
        </div>

        {/* System Diagnostics Panel */}
        <div className="flex items-center gap-6 text-sm">
          {/* Connection status */}
          <div className="flex items-center gap-2 bg-slate-950/60 px-3 py-1.5 rounded-full border border-slate-800">
            <span className={`h-2.5 w-2.5 rounded-full ${
              connectionStatus === 'connected' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' :
              connectionStatus === 'connecting' ? 'bg-amber-500 animate-pulse' : 'bg-rose-500'
            }`} />
            <span className="text-xs font-medium text-slate-300">
              {connectionStatus === 'connected' ? `LIVE PIPELINE (${lastMessageTime || 'Wait...'})` :
               connectionStatus === 'connecting' ? 'CONNECTING...' : 'LOCAL SIMULATOR'}
            </span>
          </div>

          {/* Plant selector */}
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-slate-400" />
            <select
              value={selectedPlant}
              onChange={(e) => setSelectedPlant(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="BOILER_PLC_01">Boiler PLC 01</option>
              <option value="BOILER_PLC_02">Boiler PLC 02 (Secondary)</option>
              <option value="WTP_NODE_01">Water Treatment 01</option>
            </select>
          </div>

          {/* Points counter */}
          <div className="hidden sm:flex flex-col items-end text-[10px] text-slate-400">
            <span>TOTAL SAMPLES</span>
            <span className="font-mono text-xs font-semibold text-slate-200">{statistics.pointsProcessed.toLocaleString()}</span>
          </div>
        </div>
      </header>

      {/* ── MAIN LAYOUT ── */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 flex flex-col gap-6">

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800/80 gap-6">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`pb-3 text-sm font-semibold transition-all border-b-2 flex items-center gap-2 ${
              activeTab === 'dashboard' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Grid className="h-4 w-4" />
            Digital Twin
          </button>
          <button
            onClick={() => setActiveTab('alarms')}
            className={`pb-3 text-sm font-semibold transition-all border-b-2 flex items-center gap-2 relative ${
              activeTab === 'alarms' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Bell className="h-4 w-4" />
            Live Alarms
            {alarms.filter(a => a.alarm_state === 'ACTIVE').length > 0 && (
              <span className="absolute -top-1 -right-2 bg-rose-500 text-white text-[9px] font-bold h-4 w-4 flex items-center justify-center rounded-full">
                {alarms.filter(a => a.alarm_state === 'ACTIVE').length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('tags')}
            className={`pb-3 text-sm font-semibold transition-all border-b-2 flex items-center gap-2 ${
              activeTab === 'tags' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="h-4 w-4" />
            Tag Browser
          </button>
        </div>

        {/* ── TAB CONTENT: DASHBOARD (SCADA / DIGITAL TWIN) ── */}
        {activeTab === 'dashboard' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Left/Middle Columns: SCADA Layout and Trends */}
            <div className="lg:col-span-2 flex flex-col gap-6">

              {/* Telemetry Quick Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="glassmorphism-card p-4 rounded-xl">
                  <div className="flex justify-between items-start text-slate-400 text-xs">
                    <span>MAIN STEAM PRESS</span>
                    <GaugeIcon className="h-4 w-4 text-indigo-400" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-2xl font-bold font-mono tracking-tight text-white">{latestData['PT-201']?.value ?? '--'}</span>
                    <span className="text-xs text-slate-400">bar</span>
                  </div>
                  <div className="mt-2 text-[10px] text-emerald-400 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Quality: GOOD
                  </div>
                </div>

                <div className="glassmorphism-card p-4 rounded-xl">
                  <div className="flex justify-between items-start text-slate-400 text-xs">
                    <span>SUPERHEATER TEMP 1</span>
                    <Thermometer className="h-4 w-4 text-rose-400" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-2xl font-bold font-mono tracking-tight text-white">{latestData['TT-201']?.value ?? '--'}</span>
                    <span className="text-xs text-slate-400">°C</span>
                  </div>
                  <div className="mt-2 text-[10px] text-emerald-400 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Quality: GOOD
                  </div>
                </div>

                <div className="glassmorphism-card p-4 rounded-xl">
                  <div className="flex justify-between items-start text-slate-400 text-xs">
                    <span>STEAM DRUM LVL</span>
                    <Layers className="h-4 w-4 text-sky-400" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-2xl font-bold font-mono tracking-tight text-white">{latestData['LT-201']?.value ?? '--'}</span>
                    <span className="text-xs text-slate-400">%</span>
                  </div>
                  <div className="mt-2 text-[10px] text-emerald-400 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Quality: GOOD
                  </div>
                </div>

                <div className="glassmorphism-card p-4 rounded-xl">
                  <div className="flex justify-between items-start text-slate-400 text-xs">
                    <span>FEEDWATER FLOW</span>
                    <Wind className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-2xl font-bold font-mono tracking-tight text-white">{latestData['FT-101']?.value ?? '--'}</span>
                    <span className="text-xs text-slate-400">t/h</span>
                  </div>
                  <div className="mt-2 text-[10px] text-emerald-400 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Quality: GOOD
                  </div>
                </div>
              </div>

              {/* Graphic representation of Boiler Digital Twin */}
              <div className="glassmorphism p-6 rounded-2xl border border-slate-800 relative overflow-hidden flex flex-col justify-between min-h-[350px]">
                {/* Visual grid background */}
                <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f172a_1px,transparent_1px),linear-gradient(to_bottom,#0f172a_1px,transparent_1px)] bg-[size:24px_24px] opacity-25" />

                <div className="relative z-10 flex justify-between items-center w-full">
                  <div>
                    <h3 className="text-md font-semibold text-slate-200">Piccadily Boiler Plant 01</h3>
                    <p className="text-xs text-slate-400">Real-Time Fluid & Thermal Balance</p>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-300 bg-slate-900 border border-slate-800 px-2 py-1 rounded">
                    SYS STATE: NORMAL
                  </span>
                </div>

                {/* SVG Digital Twin Schema */}
                <div className="relative z-10 my-6 flex justify-center items-center">
                  <div className="w-full max-w-lg h-52 flex justify-between items-center gap-4 relative">

                    {/* Left: Feed Water Preheater */}
                    <div className="flex flex-col items-center flex-1 bg-slate-900/80 border border-slate-800 p-3 rounded-lg text-center shadow-lg relative">
                      <div className="absolute -right-4 top-1/2 -translate-y-1/2 w-4 h-1 border-t border-slate-600" />
                      <span className="text-[9px] uppercase tracking-wider text-slate-400">Feed Water</span>
                      <span className="text-lg font-bold font-mono text-emerald-400 mt-1">{latestData['FT-101']?.value ?? '--'} <span className="text-[10px]">t/h</span></span>
                      <div className="w-full bg-slate-800 h-2 rounded overflow-hidden mt-2 border border-slate-700">
                        <div className="bg-emerald-500 h-full w-[65%] animate-pulse" />
                      </div>
                      <span className="text-[10px] mt-1 text-slate-500">FT-101</span>
                    </div>

                    {/* Middle: Steam Drum (Level Indicator) */}
                    <div className="flex flex-col items-center flex-1 bg-slate-900/80 border border-indigo-500/20 p-3 rounded-lg text-center shadow-lg relative min-h-[120px] justify-between">
                      <span className="text-[9px] uppercase tracking-wider text-indigo-300">Steam Drum</span>
                      <div className="relative w-16 h-16 rounded-full border-4 border-indigo-500/30 flex items-center justify-center bg-slate-950">
                        <div
                          className="absolute bottom-0 w-full bg-indigo-500/20 rounded-b-full transition-all duration-500"
                          style={{ height: `${latestData['LT-201']?.value ?? 50}%` }}
                        />
                        <span className="text-sm font-bold font-mono text-white relative z-10">{latestData['LT-201']?.value ?? '--'}%</span>
                      </div>
                      <span className="text-[10px] text-slate-500 mt-1">LT-201 Level</span>
                    </div>

                    {/* Right: Superheater Outlet (Temp & Pressure) */}
                    <div className="flex flex-col items-center flex-1 bg-slate-900/80 border border-rose-500/20 p-3 rounded-lg text-center shadow-lg relative">
                      <span className="text-[9px] uppercase tracking-wider text-rose-300">Superheater</span>
                      <div className="flex flex-col gap-1 mt-2">
                        <span className="text-md font-bold font-mono text-rose-400">{latestData['TT-201']?.value ?? '--'} °C</span>
                        <span className="text-md font-bold font-mono text-indigo-400">{latestData['PT-201']?.value ?? '--'} bar</span>
                      </div>
                      <div className="flex gap-2 justify-center mt-2 w-full text-[8px] text-slate-400">
                        <span>TT-201</span>
                        <span>PT-201</span>
                      </div>
                    </div>

                  </div>
                </div>

                <div className="relative z-10 flex justify-between text-xs text-slate-500 border-t border-slate-900 pt-3">
                  <span>Modbus Address Mapping: Input Regs 30001-30629</span>
                  <span>OPC Endpoint: opc.tcp://localhost:4840/piccadily/</span>
                </div>
              </div>

              {/* Time Series Trends (Recharts) */}
              <div className="glassmorphism p-6 rounded-2xl border border-slate-800">
                <div className="flex justify-between items-center mb-6">
                  <div>
                    <h3 className="text-md font-semibold text-slate-200 flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-indigo-400" />
                      Live Process Variable Trends
                    </h3>
                    <p className="text-xs text-slate-400">Continuous 5s sampling interval</p>
                  </div>
                </div>

                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={historyData}>
                      <defs>
                        <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorPress" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="time" stroke="#64748b" fontSize={10} />
                      <YAxis stroke="#64748b" fontSize={10} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
                      <Legend wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
                      <Area name="Superheater Temp (TT-201)" type="monotone" dataKey="TT-201" stroke="#f43f5e" fillOpacity={1} fill="url(#colorTemp)" strokeWidth={2} />
                      <Area name="Steam Pressure (PT-201)" type="monotone" dataKey="PT-201" stroke="#6366f1" fillOpacity={1} fill="url(#colorPress)" strokeWidth={2} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>

            {/* Right Column: Gauges, Controls & Latest Status */}
            <div className="flex flex-col gap-6">

              {/* ECharts Radial Gauge */}
              <div className="glassmorphism p-6 rounded-2xl border border-slate-800 flex flex-col items-center">
                <div className="w-full flex justify-between items-center mb-4">
                  <h3 className="text-sm font-semibold text-slate-200">Process Precision Gauge</h3>

                  {/* Gauge Tag Select */}
                  <select
                    value={selectedTag || 'TT-201'}
                    onChange={(e) => setSelectedTag(e.target.value)}
                    className="bg-slate-900 border border-slate-800 text-[11px] text-slate-400 rounded px-2 py-1"
                  >
                    <option value="TT-201">TT-201 (Superheater 1)</option>
                    <option value="TT-202">TT-202 (Superheater 2)</option>
                    <option value="TT-301">TT-301 (Main Steam Temp)</option>
                    <option value="PT-201">PT-201 (Steam Pressure)</option>
                    <option value="LT-201">LT-201 (Drum Level)</option>
                  </select>
                </div>

                {/* Gauge Container */}
                <div ref={gaugeRef} className="w-full h-64" />

                <div className="text-center mt-2 w-full border-t border-slate-900 pt-3">
                  <span className="text-xs text-slate-400 block font-semibold">{tags[selectedTag || 'TT-201']?.description}</span>
                  <span className="text-[10px] text-slate-500 font-mono">OPC Address: {tags[selectedTag || 'TT-201']?.opc_node_id}</span>
                </div>
              </div>

              {/* Tag limits and Alarm boundaries */}
              <div className="glassmorphism p-6 rounded-2xl border border-slate-800">
                <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
                  <Sliders className="h-4 w-4 text-indigo-400" />
                  Configured Threshold Limits
                </h3>

                <div className="flex flex-col gap-3 text-xs">
                  <div className="flex justify-between items-center border-b border-slate-900 pb-2">
                    <span className="text-slate-400">Critical High (HiHi)</span>
                    <span className="font-mono text-rose-500 font-bold">{tags[selectedTag || 'TT-201']?.high_high_limit ?? '--'}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-slate-900 pb-2">
                    <span className="text-slate-400">Alarm High (High)</span>
                    <span className="font-mono text-amber-500 font-semibold">{tags[selectedTag || 'TT-201']?.high_limit ?? '--'}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-slate-900 pb-2">
                    <span className="text-slate-400">Alarm Low (Low)</span>
                    <span className="font-mono text-amber-500 font-semibold">{tags[selectedTag || 'TT-201']?.low_limit ?? '--'}</span>
                  </div>
                  <div className="flex justify-between items-center border-b border-slate-900 pb-2">
                    <span className="text-slate-400">Critical Low (LoLo)</span>
                    <span className="font-mono text-rose-500 font-bold">{tags[selectedTag || 'TT-201']?.low_low_limit ?? '--'}</span>
                  </div>
                </div>

                <div className="mt-4 p-3 bg-indigo-500/5 border border-indigo-500/10 rounded-lg text-[10px] text-slate-400 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-indigo-400 shrink-0" />
                  <span>These thresholds trigger automatic alarm engine events asynchronously and push notification payloads to active WebSocket rooms.</span>
                </div>
              </div>

            </div>
          </div>
        )}

        {/* ── TAB CONTENT: ALARMS MONITOR ── */}
        {activeTab === 'alarms' && (
          <div className="glassmorphism p-6 rounded-2xl border border-slate-800 flex flex-col gap-6">
            <div className="flex flex-wrap justify-between items-center gap-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-rose-500" />
                  Active System Alarms
                </h2>
                <p className="text-xs text-slate-400">Historian alarm engine monitoring in real-time</p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setAlarms([])}
                  className="bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all"
                >
                  <X className="h-3.5 w-3.5" />
                  Clear Visual History
                </button>
              </div>
            </div>

            {alarms.length === 0 ? (
              <div className="py-12 flex flex-col items-center justify-center text-center text-slate-500 border border-slate-900 rounded-xl bg-slate-950/20">
                <CheckCircle className="h-10 w-10 text-emerald-500 mb-3" />
                <p className="font-semibold text-slate-300">All Systems Clear</p>
                <p className="text-xs mt-1">No alarm incidents active or unacknowledged</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400">
                      <th className="py-3 px-4">Severity</th>
                      <th className="py-3 px-4">Tag</th>
                      <th className="py-3 px-4">Event Message</th>
                      <th className="py-3 px-4">Trigger Value</th>
                      <th className="py-3 px-4">Timestamp</th>
                      <th className="py-3 px-4">State</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alarms.map((alarm) => (
                      <tr key={alarm.alarm_id} className="border-b border-slate-900 text-xs hover:bg-slate-900/20 transition-all">
                        <td className="py-4 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            alarm.severity === 'CRITICAL' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                            alarm.severity === 'ALARM' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                            'bg-sky-500/10 text-sky-400 border border-sky-500/20'
                          }`}>
                            {alarm.severity}
                          </span>
                        </td>
                        <td className="py-4 px-4 font-mono font-semibold text-slate-200">{alarm.tag_name}</td>
                        <td className="py-4 px-4 text-slate-300">{alarm.message}</td>
                        <td className="py-4 px-4 font-mono text-slate-300">{alarm.trigger_value}</td>
                        <td className="py-4 px-4 text-slate-400">{new Date(alarm.occurred_at).toLocaleString()}</td>
                        <td className="py-4 px-4">
                          <span className={`text-[10px] ${
                            alarm.alarm_state === 'ACTIVE' ? 'text-rose-400 font-bold animate-pulse' : 'text-slate-400'
                          }`}>
                            {alarm.alarm_state}
                          </span>
                        </td>
                        <td className="py-4 px-4 text-right flex justify-end gap-2">
                          {alarm.alarm_state === 'ACTIVE' && (
                            <button
                              onClick={() => acknowledgeAlarm(alarm.alarm_id)}
                              className="bg-indigo-600/10 text-indigo-400 hover:bg-indigo-600 hover:text-white px-2.5 py-1 border border-indigo-500/20 rounded text-[10px] font-semibold transition-all"
                            >
                              Acknowledge
                            </button>
                          )}
                          <button
                            onClick={() => clearAlarm(alarm.alarm_id)}
                            className="bg-slate-900 text-slate-400 hover:bg-rose-600 hover:text-white px-2.5 py-1 border border-slate-800 rounded text-[10px] font-semibold transition-all"
                          >
                            Clear
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── TAB CONTENT: TAG BROWSER ── */}
        {activeTab === 'tags' && (
          <div className="glassmorphism p-6 rounded-2xl border border-slate-800 flex flex-col gap-6">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Database className="h-5 w-5 text-indigo-400" />
                  Industrial Tag Metadata Browser
                </h2>
                <p className="text-xs text-slate-400">Search and verify all database-configured historian tags</p>
              </div>

              {/* Tag search bar */}
              <div className="relative w-full md:w-72">
                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Filter by tag or description..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs focus:outline-none focus:border-indigo-500 text-slate-200"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400">
                    <th className="py-3 px-4">Tag Name</th>
                    <th className="py-3 px-4">Description</th>
                    <th className="py-3 px-4">Engineering Unit</th>
                    <th className="py-3 px-4">OPC Node Id</th>
                    <th className="py-3 px-4">Alarm Thresholds</th>
                    <th className="py-3 px-4 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTags.map((tag) => (
                    <tr key={tag.tag_name} className="border-b border-slate-900 text-xs hover:bg-slate-900/20 transition-all">
                      <td className="py-4 px-4 font-mono font-bold text-indigo-400">{tag.tag_name}</td>
                      <td className="py-4 px-4 text-slate-300">{tag.description || '--'}</td>
                      <td className="py-4 px-4 text-slate-400 font-semibold">{tag.engineering_unit || '--'}</td>
                      <td className="py-4 px-4 text-slate-500 font-mono text-[10px]">{tag.opc_node_id || '--'}</td>
                      <td className="py-4 px-4 text-slate-300 font-mono">
                        {tag.low_limit !== null ? (
                          <div className="flex gap-2">
                            <span className="text-[10px] text-slate-500">Limits:</span>
                            <span>{tag.low_low_limit}/{tag.low_limit}/{tag.high_limit}/{tag.high_high_limit}</span>
                          </div>
                        ) : '--'}
                      </td>
                      <td className="py-4 px-4 text-center">
                        <span className={`px-2 py-0.5 rounded text-[10px] ${
                          tag.is_active ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-500'
                        }`}>
                          {tag.is_active ? 'ACTIVE' : 'INACTIVE'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </main>

      {/* ── FOOTER ── */}
      <footer className="mt-auto border-t border-slate-900 bg-slate-950 px-6 py-4 flex flex-col sm:flex-row justify-between items-center gap-2 text-xs text-slate-500 text-center">
        <span>© 2026 Piccadily Agro Industries. All Rights Reserved.</span>
        <div className="flex gap-4">
          <a href="#" className="hover:text-slate-300">Terms of Service</a>
          <a href="#" className="hover:text-slate-300">Privacy Policy</a>
          <a href="#" className="hover:text-slate-300">SCADA Security audit</a>
        </div>
      </footer>

    </div>
  );
}
