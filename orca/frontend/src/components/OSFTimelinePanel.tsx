import { useState } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  SkipForward,
  SkipBack,
  Waves,
  AlertTriangle,
  Layers,
  Thermometer,
  Wind,
  Compass,
} from 'lucide-react';
import { useMarineContext } from '../context/MarineContext';

export default function OSFTimelinePanel() {
  const {
    forecastHour,
    setForecastHour,
    isPlayingForecast,
    setIsPlayingForecast,
    threatFilter,
    setThreatFilter,
    layers,
    setLayers,
  } = useMarineContext();

  const forecastHours = [0, 6, 12, 24, 48, 72];

  const handleStep = (direction: 'next' | 'prev') => {
    const currentIdx = forecastHours.indexOf(forecastHour);
    if (direction === 'next') {
      const nextIdx = (currentIdx + 1) % forecastHours.length;
      setForecastHour(forecastHours[nextIdx]);
    } else {
      const prevIdx = (currentIdx - 1 + forecastHours.length) % forecastHours.length;
      setForecastHour(forecastHours[prevIdx]);
    }
  };

  const toggleLayer = (layerName: string) => {
    setLayers((prev) => {
      if (prev.includes(layerName)) return prev.filter((l) => l !== layerName);
      // Radio-style: only one full-area OSF overlay is shown at a time
      const fieldKeys = ['sst', 'wind', 'chlorophyll', 'currents', 'waves'];
      if (fieldKeys.includes(layerName)) {
        return [...prev.filter((l) => !fieldKeys.includes(l)), layerName];
      }
      return [...prev, layerName];
    });
  };

  return (
    <div className="absolute bottom-16 sm:bottom-20 left-2 right-2 sm:left-4 sm:right-auto sm:w-[500px] z-20 transition-all duration-200">
      <div className="rounded-2xl bg-slate-900/95 border border-slate-700/80 text-white shadow-2xl backdrop-blur-xl overflow-hidden">
        {/* Top Header */}
        <div className="px-4 py-2.5 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-400">
              <Waves className="w-3.5 h-3.5" />
            </span>
            <span className="font-extrabold text-xs tracking-wide text-white uppercase">
              Ocean State Forecast (OSF)
            </span>
          </div>

          <div className="flex items-center gap-1">
            <span className="text-[10px] text-cyan-400 font-bold px-2 py-0.5 rounded-full bg-cyan-950 border border-cyan-500/30">
              +{forecastHour}h Forecast
            </span>
          </div>
        </div>

        <div className="p-3.5 space-y-3">
          {/* Threat Status Legend Bar */}
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase mb-1.5 flex items-center justify-between">
              <span>Sea State Threat Level</span>
              <span className="text-[9px] text-slate-500">INCOIS Thresholds</span>
            </div>

            <div className="grid grid-cols-4 gap-1.5">
              <button
                onClick={() => setThreatFilter(threatFilter === 'WARNING' ? 'ALL' : 'WARNING')}
                className={`py-1.5 px-2 rounded-xl text-center border transition-all ${
                  threatFilter === 'WARNING' || threatFilter === 'ALL'
                    ? 'bg-rose-950/80 border-rose-500/60 text-rose-300 shadow-sm'
                    : 'bg-slate-950/40 border-slate-800 text-slate-500 opacity-60'
                }`}
              >
                <div className="text-[9px] font-bold uppercase">🔴 Warning</div>
                <div className="text-[10px] font-extrabold">&gt; 3.5 m</div>
              </button>

              <button
                onClick={() => setThreatFilter(threatFilter === 'ALERT' ? 'ALL' : 'ALERT')}
                className={`py-1.5 px-2 rounded-xl text-center border transition-all ${
                  threatFilter === 'ALERT' || threatFilter === 'ALL'
                    ? 'bg-amber-950/80 border-amber-500/60 text-amber-300 shadow-sm'
                    : 'bg-slate-950/40 border-slate-800 text-slate-500 opacity-60'
                }`}
              >
                <div className="text-[9px] font-bold uppercase">🟠 Alert</div>
                <div className="text-[10px] font-extrabold">2.5 - 3.5 m</div>
              </button>

              <button
                onClick={() => setThreatFilter(threatFilter === 'WATCH' ? 'ALL' : 'WATCH')}
                className={`py-1.5 px-2 rounded-xl text-center border transition-all ${
                  threatFilter === 'WATCH' || threatFilter === 'ALL'
                    ? 'bg-yellow-950/80 border-yellow-500/60 text-yellow-300 shadow-sm'
                    : 'bg-slate-950/40 border-slate-800 text-slate-500 opacity-60'
                }`}
              >
                <div className="text-[9px] font-bold uppercase">🟡 Watch</div>
                <div className="text-[10px] font-extrabold">1.8 - 2.5 m</div>
              </button>

              <button
                onClick={() => setThreatFilter(threatFilter === 'NO_THREAT' ? 'ALL' : 'NO_THREAT')}
                className={`py-1.5 px-2 rounded-xl text-center border transition-all ${
                  threatFilter === 'NO_THREAT' || threatFilter === 'ALL'
                    ? 'bg-emerald-950/80 border-emerald-500/60 text-emerald-300 shadow-sm'
                    : 'bg-slate-950/40 border-slate-800 text-slate-500 opacity-60'
                }`}
              >
                <div className="text-[9px] font-bold uppercase">🟢 Safe</div>
                <div className="text-[10px] font-extrabold">&lt; 1.8 m</div>
              </button>
            </div>
          </div>

          {/* Forecast Playback Scrubber */}
          <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setIsPlayingForecast(!isPlayingForecast)}
                  className={`p-1.5 rounded-lg flex items-center justify-center transition-all ${
                    isPlayingForecast
                      ? 'bg-amber-600 text-white shadow-md shadow-amber-600/30'
                      : 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30 hover:bg-cyan-500'
                  }`}
                  title={isPlayingForecast ? 'Pause Playback' : 'Play Forecast Animation'}
                >
                  {isPlayingForecast ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                </button>

                <button
                  onClick={() => handleStep('prev')}
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                  title="Previous Step"
                >
                  <SkipBack className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={() => handleStep('next')}
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                  title="Next Step"
                >
                  <SkipForward className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={() => {
                    setIsPlayingForecast(false);
                    setForecastHour(0);
                  }}
                  className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                  title="Reset to Now"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="text-right">
                <span className="text-[11px] font-mono font-bold text-cyan-300">
                  {forecastHour === 0 ? 'LIVE (Now)' : `+${forecastHour} Hours`}
                </span>
              </div>
            </div>

            {/* Step Pills Timeline */}
            <div className="grid grid-cols-6 gap-1">
              {forecastHours.map((hour) => (
                <button
                  key={hour}
                  onClick={() => {
                    setIsPlayingForecast(false);
                    setForecastHour(hour);
                  }}
                  className={`py-1 rounded-lg text-[10px] font-bold font-mono transition-all ${
                    forecastHour === hour
                      ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/40 font-extrabold'
                      : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                  }`}
                >
                  {hour === 0 ? 'Now' : `+${hour}h`}
                </button>
              ))}
            </div>
          </div>

          {/* Sub-layer toggles (radio: one field overlay at a time) */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
            <button
              onClick={() => toggleLayer('waves')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-colors ${
                layers.includes('waves')
                  ? 'bg-cyan-950/60 border-cyan-500/50 text-cyan-300'
                  : 'bg-slate-950/40 border-slate-800 text-slate-500'
              }`}
            >
              <Waves className="w-3 h-3" />
              <span>Waves</span>
            </button>

            <button
              onClick={() => toggleLayer('sst')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-colors ${
                layers.includes('sst')
                  ? 'bg-amber-950/60 border-amber-500/50 text-amber-300'
                  : 'bg-slate-950/40 border-slate-800 text-slate-500'
              }`}
            >
              <Thermometer className="w-3 h-3" />
              <span>SST Heat</span>
            </button>

            <button
              onClick={() => toggleLayer('wind')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-colors ${
                layers.includes('wind')
                  ? 'bg-blue-950/60 border-blue-500/50 text-blue-300'
                  : 'bg-slate-950/40 border-slate-800 text-slate-500'
              }`}
            >
              <Wind className="w-3 h-3" />
              <span>Wind</span>
            </button>

            <button
              onClick={() => toggleLayer('currents')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-bold border transition-colors ${
                layers.includes('currents')
                  ? 'bg-indigo-950/60 border-indigo-500/50 text-indigo-300'
                  : 'bg-slate-950/40 border-slate-800 text-slate-500'
              }`}
            >
              <Compass className="w-3 h-3" />
              <span>Currents</span>
            </button>
          </div>

          {/* OSF Color Scale Legend for the active field overlay */}
          {layers.includes('waves') && (
            <div className="pt-1">
              <div className="text-[10px] font-bold text-slate-400 uppercase mb-1 flex items-center justify-between">
                <span>Significant Wave Height (m)</span>
                <span className="text-[9px] text-slate-500 font-mono">INCOIS Scale</span>
              </div>
              <div className="w-full h-3.5 rounded-md overflow-hidden flex">
                {[
                  ['#14b8a6', '0'], ['#22d3ee', '0.5'], ['#38bdf8', '1'], ['#818cf8', '1.5'],
                  ['#a855f7', '2'], ['#d946ef', '2.5'], ['#ec4899', '3'], ['#fb7185', '4'],
                  ['#dc2626', '5'], ['#991b1b', '7'], ['#9ca3af', '10'], ['#4b5563', '12+'],
                ].map(([color, label]) => (
                  <div key={label} className="flex-1 relative" style={{ background: color }} title={`≥ ${label} m`}>
                    <span className="absolute left-0.5 top-0.5 text-[7px] font-bold text-white/95 drop-shadow">
                      {label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
