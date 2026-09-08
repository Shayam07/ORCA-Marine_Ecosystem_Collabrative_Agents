import { Wind, Compass } from 'lucide-react';
import { useMarineContext } from '../context/MarineContext';

// Bins must mirror the fill colors used by MapView for these overlays.
const WIND_BINS: Array<{ label: string; color: string }> = [
  { label: '0-6', color: '#7e22ce' },
  { label: '6-12', color: '#2563eb' },
  { label: '12-16', color: '#0d9488' },
  { label: '16-18', color: '#16a34a' },
  { label: '18-20', color: '#d97706' },
  { label: '≥20', color: '#dc2626' },
];

const CURRENT_BINS: Array<{ label: string; color: string }> = [
  { label: '0', color: '#1e3a8a' },
  { label: '0.15', color: '#2563eb' },
  { label: '0.3', color: '#0891b2' },
  { label: '0.45', color: '#22c55e' },
  { label: '0.6', color: '#f59e0b' },
  { label: '≥0.75', color: '#dc2626' },
];

export default function VelocityScaleBar() {
  const { operationalMode } = useMarineContext();

  const isCurrents = operationalMode === 'CURRENTS';
  const bins = isCurrents ? CURRENT_BINS : WIND_BINS;

  return (
    <div className="absolute bottom-16 sm:bottom-20 left-2 right-2 sm:left-4 sm:right-auto sm:w-96 z-20 transition-all duration-200">
      <div className="rounded-2xl bg-slate-900/95 border border-slate-700/80 text-white p-3 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center justify-between text-xs mb-1.5 font-bold">
          <span className="flex items-center gap-1.5 text-cyan-300">
            {isCurrents ? <Compass className="w-4 h-4 text-indigo-400" /> : <Wind className="w-4 h-4 text-blue-400" />}
            {isCurrents ? 'Ocean Current Speed' : 'Surface Wind Speed'}
          </span>
          <span className="text-[10px] text-slate-400 font-mono">
            {isCurrents ? 'm/s' : 'm/s'}
          </span>
        </div>

        {/* OSF-style discrete color bins */}
        <div className="flex w-full h-4 rounded-md overflow-hidden border border-slate-800 shadow-inner">
          {bins.map((b) => (
            <div
              key={b.label}
              className="flex-1 flex items-center justify-center text-[9px] font-extrabold text-white"
              style={{ background: b.color }}
            >
              {b.label}
            </div>
          ))}
        </div>

        <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between border-t border-slate-800/80 pt-1.5">
          <span>Animated Vector Flow active</span>
          <span className="text-emerald-400 font-bold">Real-time Particles</span>
        </div>
      </div>
    </div>
  );
}
