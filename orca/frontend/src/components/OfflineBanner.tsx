import React from 'react';
import { WifiOff, ShieldCheck, Compass, Radio } from 'lucide-react';

interface Props {
  isOffline: boolean;
}

export default function OfflineBanner({ isOffline }: Props) {
  if (!isOffline) return null;

  return (
    <div className="absolute top-14 sm:top-16 left-3 right-3 sm:left-1/2 sm:-translate-x-1/2 sm:w-auto z-30 bg-slate-900/95 border border-amber-500/80 rounded-2xl p-2.5 sm:px-4 sm:py-2 text-white shadow-2xl backdrop-blur-xl flex flex-col sm:flex-row items-center gap-2 sm:gap-4 animate-in fade-in duration-200">
      <div className="flex items-center gap-2 text-amber-400 font-bold text-xs">
        <WifiOff className="w-4 h-4 animate-pulse flex-shrink-0" />
        <span>Offline Safety Mode — Live marine data is unavailable</span>
      </div>

      <div className="flex items-center gap-3 text-[10px] text-slate-300">
        <span className="flex items-center gap-1 text-emerald-300">
          <Compass className="w-3 h-3 text-emerald-400" />
          GPS Tracking Active
        </span>
        <span className="flex items-center gap-1 text-emerald-300">
          <ShieldCheck className="w-3 h-3 text-emerald-400" />
          Local Geofence Active
        </span>
        <span className="flex items-center gap-1 text-cyan-300">
          <Radio className="w-3 h-3 text-cyan-400" />
          Cached Boundaries
        </span>
      </div>
    </div>
  );
}
