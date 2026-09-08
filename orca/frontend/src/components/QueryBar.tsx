import { useState } from 'react';
import { Search, Loader2, MapPin, Calendar, Sparkles, Zap } from 'lucide-react';
import { runQuery } from '../api/client';
import type { AnalysisResult } from '../types';
import { Button } from './ui/button';

interface Props {
  loading: boolean;
  setLoading: (v: boolean) => void;
  onResult: (r: AnalysisResult) => void;
  bbox: [number, number, number, number];
  fastMlMode: boolean;
}

const PRESET_PROMPTS = [
  { label: "🌿 Chlorophyll Drop Anomaly", text: "Why has chlorophyll decreased near the west coast of India?" },
  { label: "🎣 Goa Fishing Suitability", text: "Recommend optimal fishing grounds near Goa based on current ocean conditions." },
  { label: "⚠️ Ecosystem Threat Analysis", text: "Is this region showing unusual ecosystem anomalies or thermal stress?" },
  { label: "🌡️ SST Baseline Shift", text: "Compare current SST with historical baselines for Indian west coast." },
];

export default function QueryBar({ loading, setLoading, onResult, bbox, fastMlMode }: Props) {
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (overrideText?: string) => {
    const textToSubmit = overrideText || query;
    if (!textToSubmit.trim() || loading) return;
    
    if (overrideText) {
      setQuery(overrideText);
    }

    setLoading(true);
    setError(null);

    try {
      const result = await runQuery({
        question: textToSubmit.trim(),
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [bbox[0], bbox[1]],
            [bbox[2], bbox[1]],
            [bbox[2], bbox[3]],
            [bbox[0], bbox[3]],
            [bbox[0], bbox[1]],
          ]],
        },
        start_date: '2026-08-01T00:00:00Z',
        end_date: '2026-08-28T00:00:00Z',
        fast_ml_mode: fastMlMode,
      });
      onResult(result);
    } catch (e: any) {
      setError(e.message || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border-b border-slate-200 bg-white p-4 shadow-xs">
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-600" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            placeholder="Ask ORCA: Why has chlorophyll decreased near the west coast of India?"
            className="w-full rounded-xl border border-slate-300 bg-slate-50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder-slate-400 shadow-inner focus:border-cyan-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
            disabled={loading}
          />
          {loading && (
            <div className="absolute right-3.5 top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-xs text-cyan-800 font-mono">
              <Loader2 className="h-4 w-4 animate-spin text-cyan-600" />
              <span>Analyzing...</span>
            </div>
          )}
        </div>

        <Button
          onClick={() => handleSubmit()}
          disabled={loading || !query.trim()}
          className="rounded-xl bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 px-5 text-white font-semibold shadow-md shadow-cyan-600/20 hover:from-cyan-500 hover:to-blue-500"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Analyzing
            </>
          ) : (
            <>
              {fastMlMode ? <Zap className="mr-2 h-4 w-4 text-cyan-200" /> : <Search className="mr-2 h-4 w-4" />}
              {fastMlMode ? 'Fast ML Analysis' : 'Run Analysis'}
            </>
          )}
        </Button>
      </div>

      {/* Preset Prompt Chips */}
      <div className="mt-3 flex flex-wrap gap-2">
        {PRESET_PROMPTS.map((preset, idx) => (
          <button
            key={idx}
            onClick={() => handleSubmit(preset.text)}
            disabled={loading}
            className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs text-slate-700 transition-colors hover:border-cyan-400 hover:bg-cyan-50 hover:text-cyan-900 shadow-2xs font-medium"
          >
            <span>{preset.label}</span>
          </button>
        ))}
      </div>

      {/* Region & Filter Footer */}
      <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <MapPin className="h-3.5 w-3.5 text-cyan-600" />
            <span>Region: {bbox[1].toFixed(1)}°–{bbox[3].toFixed(1)}°N, {bbox[0].toFixed(1)}°–{bbox[2].toFixed(1)}°E</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5 text-cyan-600" />
            <span>Period: Aug 2026</span>
          </div>
        </div>

        {fastMlMode && (
          <div className="flex items-center gap-1 text-[11px] font-mono text-cyan-700 font-bold">
            <Sparkles className="h-3 w-3" />
            <span>Sub-50ms Mode Active</span>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-700 shadow-xs">
          {error}
        </div>
      )}
    </div>
  );
}
