import { useState, useEffect } from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';
import { useMarineContext } from '../context/MarineContext';

interface Props {
  activeMode: string;
}

export default function IncoisTimelineBar({ activeMode }: Props) {
  const { operationalMode, isPlayingForecast, setIsPlayingForecast, forecastHour, setForecastHour } =
    useMarineContext();

  // INCOIS 3-hourly forecast time offsets
  const forecastHours = [0, 3, 6, 9, 12, 18, 24, 36, 48, 72];
  const [currentIdx, setCurrentIdx] = useState(0);

  // Synchronize with parent forecastHour
  useEffect(() => {
    const idx = forecastHours.indexOf(forecastHour);
    if (idx !== -1) setCurrentIdx(idx);
  }, [forecastHour]);

  const handleStep = (direction: 'prev' | 'next') => {
    let nextIdx = direction === 'next' ? currentIdx + 1 : currentIdx - 1;
    if (nextIdx >= forecastHours.length) nextIdx = 0;
    if (nextIdx < 0) nextIdx = forecastHours.length - 1;
    setCurrentIdx(nextIdx);
    setForecastHour(forecastHours[nextIdx]);
  };

  const togglePlay = () => {
    setIsPlayingForecast(!isPlayingForecast);
  };

  // Compute realistic timestamp matching screenshot format: "01/09/2026, 17:30:00 IST"
  const baseDate = new Date(2026, 8, 1, 14, 30, 0); // 01 Sep 2026 14:30
  const activeDate = new Date(baseDate.getTime() + (forecastHours[currentIdx] || 0) * 3600 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  const formattedTimestamp = `${pad(activeDate.getDate())}/${pad(activeDate.getMonth() + 1)}/${activeDate.getFullYear()}, ${pad(activeDate.getHours())}:${pad(activeDate.getMinutes())}:${pad(activeDate.getSeconds())} IST`;

  const isWind = activeMode === 'WINDS' || operationalMode === 'WINDS';

  const windScale = [
    { label: '0-6', color: '#5c6bc0' },
    { label: '6-12', color: '#26a69a' },
    { label: '12-16', color: '#66bb6a' },
    { label: '16-18', color: '#c0ca33' },
    { label: '18-20', color: '#8d6e63' },
    { label: '>=20', color: '#b71c1c' },
  ];

  const waveScale = [
    { label: '0', color: '#80cbc4' },
    { label: '0.5', color: '#4dd0e1' },
    { label: '1', color: '#29b6f6' },
    { label: '1.5', color: '#3f51b5' },
    { label: '2', color: '#ab47bc' },
    { label: '2.5', color: '#e91e63' },
    { label: '3', color: '#ad1457' },
    { label: '4', color: '#c2185b' },
    { label: '5', color: '#d32f2f' },
    { label: '7', color: '#8d6e63' },
    { label: '10', color: '#bdbdbd' },
    { label: '>=12', color: '#616161' },
  ];

  const activeScale = isWind ? windScale : waveScale;
  const activeTitle = isWind ? 'Winds\n(m/s):' : 'Significant\nWave\nHeight (m):';

  return (
    <div className="absolute bottom-0 left-0 right-0 z-20 flex flex-col font-sans select-none pointer-events-auto">
      {/* Upper sub-bar: "Unavailable" badge on left, Timeline Player in center, Esri Attribution on right */}
      <div className="flex items-end justify-between px-2 pb-1 text-xs">
        {/* Left: "Unavailable" disclaimer pill matching screenshot */}
        <div className="bg-white/90 text-slate-800 px-2 py-0.5 text-[11px] rounded-sm border border-slate-300 shadow-xs font-serif italic mb-1">
          Unavailable
        </div>

        {/* Center/Left: Playback Controller & Timestamp */}
        <div className="flex items-center shadow-md border border-slate-700/60 rounded overflow-hidden mb-1">
          {/* Controls Box */}
          <div className="flex items-center bg-white px-2 py-1 gap-3 border-r border-slate-400">
            <button
              onClick={() => handleStep('prev')}
              className="text-slate-800 hover:text-black transition-colors"
              title="Previous Timestep"
            >
              <SkipBack className="w-3.5 h-3.5 fill-current" />
            </button>

            <button
              onClick={togglePlay}
              className="text-red-600 hover:text-red-700 transition-colors"
              title={isPlayingForecast ? 'Pause' : 'Play'}
            >
              {isPlayingForecast ? (
                <Pause className="w-4 h-4 fill-current text-slate-900" />
              ) : (
                <Play className="w-4 h-4 fill-current text-red-600" />
              )}
            </button>

            <button
              onClick={() => handleStep('next')}
              className="text-slate-800 hover:text-black transition-colors"
              title="Next Timestep"
            >
              <SkipForward className="w-3.5 h-3.5 fill-current" />
            </button>
          </div>

          {/* Timestamp Pill */}
          <div className="bg-black/95 text-white px-3 py-1 font-mono text-[11.5px] tracking-tight font-medium flex items-center">
            {formattedTimestamp}
          </div>
        </div>

        {/* Right: Esri Attribution Pill */}
        <div className="bg-white/90 text-slate-800 px-2 py-0.5 text-[10px] rounded-sm border border-slate-300 shadow-xs font-sans mb-1 hidden sm:block">
          Tiles © Esri – Source: Esri
        </div>
      </div>

      {/* Bottom Color Scale Bar: Integrated edge-to-edge as shown in screenshots */}
      <div className="w-full flex items-stretch border-t border-black/30 shadow-lg text-white font-sans text-[11px] h-8 sm:h-9">
        {/* Left Label Box */}
        <div className="bg-black/95 text-white px-2 sm:px-3 flex items-center justify-center text-center font-bold text-[10px] sm:text-[11px] leading-tight border-r border-slate-700 flex-shrink-0 min-w-[70px] sm:min-w-[95px] whitespace-pre-line">
          {activeTitle}
        </div>

        {/* Discrete Color Bands */}
        <div className="flex-1 flex items-stretch">
          {activeScale.map((item) => (
            <div
              key={item.label}
              className="flex-1 flex items-center justify-center font-bold text-[10px] sm:text-[11.5px] border-r border-black/15 last:border-r-0 text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)] select-none px-0.5"
              style={{ backgroundColor: item.color }}
            >
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
