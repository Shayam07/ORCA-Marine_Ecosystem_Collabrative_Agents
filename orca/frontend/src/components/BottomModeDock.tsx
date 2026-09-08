import {
  Fish,
  Waves,
  Wind,
  Compass,
  AlertTriangle,
  ShieldCheck,
  Route,
} from 'lucide-react';
import { useMarineContext, type OperationalMode } from '../context/MarineContext';

export default function BottomModeDock() {
  const { operationalMode, setOperationalMode } = useMarineContext();

  const dockItems: Array<{
    id: OperationalMode;
    label: string;
    shortLabel: string;
    icon: any;
    color: string;
    activeBg: string;
  }> = [
    {
      id: 'PFZ',
      label: 'PFZ Advisory',
      shortLabel: 'PFZ',
      icon: Fish,
      color: 'text-emerald-400',
      activeBg: 'bg-emerald-600 text-white shadow-emerald-900/40',
    },
    {
      id: 'OSF',
      label: 'Ocean Forecast',
      shortLabel: 'OSF',
      icon: Waves,
      color: 'text-cyan-400',
      activeBg: 'bg-cyan-600 text-white shadow-cyan-900/40',
    },
    {
      id: 'WINDS',
      label: 'Wind Flow',
      shortLabel: 'Winds',
      icon: Wind,
      color: 'text-blue-400',
      activeBg: 'bg-blue-600 text-white shadow-blue-900/40',
    },
    {
      id: 'CURRENTS',
      label: 'Currents',
      shortLabel: 'Currents',
      icon: Compass,
      color: 'text-indigo-400',
      activeBg: 'bg-indigo-600 text-white shadow-indigo-900/40',
    },
    {
      id: 'HIGH_WAVES',
      label: 'Wave Alert',
      shortLabel: 'Alerts',
      icon: AlertTriangle,
      color: 'text-amber-400',
      activeBg: 'bg-amber-600 text-white shadow-amber-900/40',
    },
    {
      id: 'ROUTE',
      label: 'Space-Time Route',
      shortLabel: 'Route',
      icon: Route,
      color: 'text-cyan-300',
      activeBg: 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-cyan-900/40',
    },
    {
      id: 'SAFETY',
      label: 'IMBL Safety',
      shortLabel: 'IMBL',
      icon: ShieldCheck,
      color: 'text-rose-400',
      activeBg: 'bg-rose-600 text-white shadow-rose-900/40',
    },
  ];

  return (
    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-30 max-w-[95vw]">
      <div className="flex items-center gap-1 sm:gap-1.5 p-1.5 rounded-2xl bg-slate-950/90 border border-slate-700/80 shadow-2xl backdrop-blur-xl">
        {dockItems.map((item) => {
          const Icon = item.icon;
          const isActive = operationalMode === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setOperationalMode(item.id)}
              className={`flex items-center gap-1.5 px-2.5 sm:px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                isActive
                  ? `${item.activeBg} shadow-lg scale-105`
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-850'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-white' : item.color}`} />
              <span className="hidden md:inline">{item.label}</span>
              <span className="inline md:hidden text-[11px]">{item.shortLabel}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
