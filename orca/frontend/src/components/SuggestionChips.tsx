interface SuggestionChipsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
}

export function SuggestionChips({ suggestions, onSelect }: SuggestionChipsProps) {
  if (!suggestions.length) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s)}
          className="text-xs px-3 py-1.5 rounded-full bg-white hover:bg-cyan-50 border border-slate-200 text-slate-700 hover:text-cyan-900 transition-all hover:border-cyan-400 shadow-2xs font-medium"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
