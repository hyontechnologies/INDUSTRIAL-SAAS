/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        scada: {
          panel: '#1e293b',    // slate-800
          border: '#334155',   // slate-700
          good: '#10b981',     // emerald-500
          warning: '#f59e0b',  // amber-500
          critical: '#ef4444', // red-500
          stale: '#64748b',    // slate-500
          bg: '#020617',       // slate-950
        }
      },
      animation: {
        'status-blink': 'status-blink 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        'status-blink': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        }
      }
    },
  },
  plugins: [],
}
