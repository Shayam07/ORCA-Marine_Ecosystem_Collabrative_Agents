export default function IncoisThreatLegend() {
  const threatLevels = [
    { label: 'Warning', color: '#e53935' }, // Red
    { label: 'Alert', color: '#fb8c00' },   // Orange
    { label: 'Watch', color: '#fdd835' },   // Yellow
    { label: 'No Threat', color: '#2e7d32' }, // Green
  ];

  return (
    <div className="absolute bottom-16 right-3 sm:right-4 z-20 bg-slate-900/90 text-white rounded-xl border border-slate-700/80 shadow-2xl p-2 min-w-[125px] font-sans select-none backdrop-blur-md">
      <div className="text-[10.5px] font-extrabold text-slate-300 tracking-wider uppercase mb-1 border-b border-slate-800 pb-0.5">
        Threat Status
      </div>

      <div className="space-y-1">
        {threatLevels.map((t) => (
          <div key={t.label} className="flex items-center gap-1.5 text-[11px] text-slate-200">
            <span
              className="w-2.5 h-2.5 rounded-xs flex-shrink-0 shadow-xs"
              style={{ backgroundColor: t.color }}
            />
            <span className="font-medium">{t.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
