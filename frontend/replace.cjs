const fs = require('fs');

const path = 'src/App.tsx';
let content = fs.readFileSync(path, 'utf8');

// Global Background & Text
content = content.replace(/bg-slate-950/g, 'bg-stone-50');
content = content.replace(/text-slate-100/g, 'text-slate-900');
content = content.replace(/text-white/g, 'text-slate-900');
content = content.replace(/text-slate-200/g, 'text-slate-900');
content = content.replace(/text-slate-300/g, 'text-slate-700');
content = content.replace(/text-slate-400/g, 'text-slate-500');

// Cards & Borders
content = content.replace(/border-slate-800/g, 'border-slate-200');
content = content.replace(/border-slate-700/g, 'border-slate-300');
content = content.replace(/border-slate-900/g, 'border-slate-200');
content = content.replace(/bg-slate-900\/60/g, 'bg-white/80');
content = content.replace(/bg-slate-900\/80/g, 'bg-white');
content = content.replace(/bg-slate-900/g, 'bg-white');
content = content.replace(/bg-slate-800/g, 'bg-slate-50');
content = content.replace(/border-t border-slate-900/g, 'border-t border-slate-200');
content = content.replace(/border-b border-slate-800\/80/g, 'border-b border-slate-200');

// Grid Background in Boiler Diagram
content = content.replace(/#0f172a_1px/g, '#e2e8f0_1px');

// Recharts Config
content = content.replace(/stroke="#1e293b"/g, 'stroke="#e2e8f0"');
content = content.replace(/backgroundColor: '#0f172a'/g, "backgroundColor: '#ffffff'");
content = content.replace(/borderColor: '#334155'/g, "borderColor: '#e2e8f0'");

// ECharts Config
content = content.replace(/color: '#94a3b8'/g, "color: '#64748b'"); // axisLabel
content = content.replace(/color: '#f8fafc'/g, "color: '#1e293b'"); // detail value

// specific fix for active alarm badge (keep white text on red)
content = content.replace(/bg-rose-500 text-slate-900/g, 'bg-rose-500 text-white');
// active connection status (keep white on emerald)
// wait, text is not specified there.

// Fix buttons text color (Acknowledge / Clear)
content = content.replace(/text-slate-900 hover:bg-slate-700/g, 'text-slate-100 hover:bg-slate-600');

fs.writeFileSync(path, content, 'utf8');
console.log('App.tsx theme replaced successfully.');
