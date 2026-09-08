import { useMarineContext, type OperationalMode } from '../context/MarineContext';
import { Eye, EyeOff, Layers, Check } from 'lucide-react';

interface Props {
  activeMode: string;
  onModeChange: (mode: string) => void;
}

export default function IncoisAlertsSelector({ activeMode, onModeChange }: Props) {
  const { layers, setLayers } = useMarineContext();
  const isOverlayOn = layers.some((l) => ['wind', 'waves', 'currents', 'sst', 'chlorophyll'].includes(l));

  const alertsList: Array<{ id: string; label: string; operationalMode: OperationalMode }> = [
    { id: 'WINDS', label: 'Wind Field Grid', operationalMode: 'WINDS' },
    { id: 'HIGH_WAVES', label: 'High Waves (SWH)', operationalMode: 'HIGH_WAVES' },
    { id: 'SWELL', label: 'Swell Waves', operationalMode: 'OSF' },
    { id: 'CURRENTS', label: 'Ocean Currents', operationalMode: 'CURRENTS' },
    { id: 'OSF', label: 'OSF Composite Alerts', operationalMode: 'OSF' },
  ];

  const handleToggleMaster = () => {
    if (isOverlayOn) {
      onModeChange('NONE');
    } else {
      onModeChange('WINDS');
    }
  };

  return (
    <div className="absolute top-3 right-3 sm:right-4 z-20 bg-slate-900/90 text-white rounded-xl border border-slate-700/80 shadow-2xl p-2 sm:p-2.5 min-w-[170px] max-w-[210px] font-sans select-none backdrop-blur-md transition-all">
      {/* Top Header with Master ON/OFF Switch */}
      <div className="flex items-center justify-between gap-1.5 pb-1.5 mb-1.5 border-b border-slate-800">
        <div className="flex items-center gap-1.5 min-w-0">
          <Layers className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
          <span className="text-[11px] font-extrabold uppercase tracking-wide text-slate-200 truncate">
            Map Grid
          </span>
        </div>

        {/* Master ON/OFF Toggle Button */}
        <button
          onClick={handleToggleMaster}
          className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold flex items-center gap-1 transition-all border ${
            isOverlayOn
              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30'
              : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
          }`}
          title={isOverlayOn ? 'Click to turn off map grid' : 'Click to turn on map grid'}
        >
          {isOverlayOn ? <Eye className="w-3 h-3 text-emerald-400" /> : <EyeOff className="w-3 h-3 text-slate-400" />}
          <span>{isOverlayOn ? 'ON' : 'OFF'}</span>
        </button>
      </div>

      {/* Layer Options List */}
      <div className="space-y-1">
        {alertsList.map((item) => {
          const isSelected = activeMode === item.id && isOverlayOn;
          return (
            <button
              key={item.id}
              onClick={() => onModeChange(item.id)}
              className={`w-full flex items-center justify-between px-2 py-1 rounded-lg text-left transition-all ${
                isSelected
                  ? 'bg-cyan-950/80 text-cyan-200 border border-cyan-500/50 shadow-xs font-semibold'
                  : 'text-slate-300 hover:bg-slate-800/70 hover:text-white border border-transparent'
              }`}
            >
              <span className="text-[11px] leading-tight">{item.label}</span>
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ml-1.5 ${
                isSelected ? 'bg-cyan-400 ring-2 ring-cyan-400/30' : 'bg-slate-600'
              }`} />
            </button>
          );
        })}

        {/* Explicit Turn OFF Button */}
        {isOverlayOn && (
          <button
            onClick={() => onModeChange('NONE')}
            className="w-full mt-1.5 pt-1 border-t border-slate-800/80 flex items-center justify-center gap-1 py-1 rounded-md text-[10px] font-bold text-slate-400 hover:text-red-400 hover:bg-red-950/30 transition-colors"
          >
            <EyeOff className="w-3 h-3" />
            <span>Turn Off All Grid Boxes</span>
          </button>
        )}
      </div>
    </div>
  );
}
