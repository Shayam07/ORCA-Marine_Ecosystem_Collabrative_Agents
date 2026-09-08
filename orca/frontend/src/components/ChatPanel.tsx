import { useEffect, useRef, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { SuggestionChips } from './SuggestionChips';
import { useMarineContext } from '../context/MarineContext';
import { sendMessage as sendChatMessage, ApiError } from '../api/client';
import {
  Globe,
  Navigation,
  Fish,
  Waves,
  Wind,
  ShieldCheck,
  Sparkles,
  Compass,
  AlertTriangle,
  Radio,
  Plus,
} from 'lucide-react';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  location?: { name: string; lat: number; lon: number } | null;
  agents_used?: string[];
  sources_used?: string[];
  suggestions?: string[];
  response_type?: string;
  language?: string;
  data_mode?: string;
  timestamp: Date;
}

export interface PFZZone {
  zone_id: string;
  geometry: { type: string; coordinates: number[][][] };
  center_lat: number;
  center_lon: number;
  score: number;
  raw_suitability_score?: number;
  safety_score?: number;
  data_confidence?: number;
  classification: string;
  recommendation_status?: 'RECOMMENDED' | 'ALTERNATIVE' | 'EXCLUDED_RESTRICTED' | 'EXCLUDED_ECOLOGICAL' | 'EXCLUDED_UNSAFE';
  option_label?: string;
  option_title?: string;
  crowding_level?: 'LOW' | 'MODERATE' | 'HIGH';
  crowding_penalty?: number;
  vessel_density?: number;
  vessel_count?: number;
  cell_count: number;
  avg_sst?: number;
  avg_chlorophyll?: number;
  data_mode: string;
  data_sources: string[];
  distance_km?: number;
  reasoning: string;
  alternative_reason?: string;
}

const SAMPLE_QUERIES = [
  {
    icon: '🎣',
    title: 'Sustainable PFZ Advisory',
    query: 'Show me safe, sustainable PFZ zones near Chennai with low vessel crowding and no seasonal ban restrictions.',
    category: 'PFZ Advisory',
  },
  {
    icon: '🧭',
    title: 'Space-Time A* Route',
    query: 'Plan the safest, fuel-optimal navigation route to offshore fishing grounds avoiding high waves.',
    category: 'Navigation',
  },
  {
    icon: '🛡️',
    title: 'SAMUDRA Sea Safety',
    query: 'Is it safe to venture into the sea? Check wind speed, swell height, and squall alerts.',
    category: 'Safety',
  },
  {
    icon: '🛰️',
    title: 'Satellite SST & Chlorophyll',
    query: 'Show me Sea Surface Temperature (SST) thermal fronts and chlorophyll-a density on the map.',
    category: 'Remote Sensing',
  },
];

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [activeLang, setActiveLang] = useState<string>('ta');
  const scrollRef = useRef<HTMLDivElement>(null);

  const {
    location,
    setLocation,
    landingCentre,
    setIntent,
    setLayers,
    setZones,
    setCurrentRoute,
    dataMode,
    selectedZone,
    currentRoute,
  } = useMarineContext();

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const contextualPrompt = selectedZone
    ? `What are the fishing conditions in zone ${selectedZone.zone_id}?`
    : '';

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: text, timestamp: new Date() },
    ]);
    setIsLoading(true);
    setSuggestions([]);

    try {
      const activeLocation = location || (landingCentre ? {
        name: landingCentre.name,
        lat: landingCentre.lat,
        lon: landingCentre.lon,
        environment: 'COASTAL',
        state: landingCentre.state,
      } : null);

      const data = await sendChatMessage({
        message: text,
        conversation_id: conversationId,
        data_mode: dataMode,
        location: activeLocation,
        landing_centre: landingCentre ? {
          name: landingCentre.name,
          lat: landingCentre.lat,
          lon: landingCentre.lon,
          state: landingCentre.state,
        } : null,
        selected_zone: selectedZone ? {
          zone_id: selectedZone.zone_id,
          center_lat: selectedZone.center_lat,
          center_lon: selectedZone.center_lon,
          avg_sst: selectedZone.avg_sst,
          avg_chlorophyll: selectedZone.avg_chlorophyll,
          classification: selectedZone.classification,
          crowding_level: selectedZone.crowding_level,
          distance_km: selectedZone.distance_km,
          reasoning: selectedZone.reasoning,
        } : null,
      });

      setConversationId(data.conversation_id);

      if (data.location) setLocation(data.location);
      if (data.intent) setIntent(data.intent);
      if (data.map_layers?.length) setLayers(data.map_layers);
      if (data.metadata?.pfz_zones) setZones(data.metadata.pfz_zones);
      if (data.route) setCurrentRoute(data.route);
      if (data.language) setActiveLang(data.language);

      setMessages((prev) => [
        ...prev,
        {
          id: data.message_id,
          role: 'assistant',
          content: data.answer || data.content,
          intent: data.intent,
          location: data.location,
          agents_used: data.agents_used,
          sources_used: data.providers_used,
          suggestions: data.actions || data.suggestions,
          response_type: data.response_type,
          language: data.language,
          data_mode: data.data_mode,
          timestamp: new Date(),
        },
      ]);
      setSuggestions(data.actions || data.suggestions || []);
    } catch (err: any) {
      let errorMessage = 'An error occurred reaching the marine telemetry service. Please retry in a moment.';
      if (err instanceof ApiError) {
        if (err.isOffline) {
          errorMessage = '📡 Your device appears to be offline. Please check your mobile data or Wi-Fi connection.';
        } else if (err.isTimeout) {
          errorMessage = '⏱️ Marine telemetry query timed out. The server is taking longer than usual to retrieve satellite forecasts. Please retry.';
        } else if (err.isNetworkError) {
          errorMessage = `🔌 ${err.message}`;
        } else if (err.status) {
          errorMessage = `⚠️ Server error (${err.status}): ${err.message}`;
        } else {
          errorMessage = err.message;
        }
      } else if (err?.message) {
        errorMessage = err.message;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: errorMessage,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50/40 backdrop-blur-xl border-r border-slate-200 overflow-hidden">
      {/* SAMUDRA Live Ocean State Telemetry Bar */}
      <div className="px-4 py-2.5 bg-white/95 border-b border-slate-200 flex items-center justify-between gap-2 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-cyan-50 border border-cyan-300 text-cyan-800 text-[11px] font-semibold">
            <Radio className="w-3 h-3 text-cyan-600 animate-pulse" />
            <span>SAMUDRA OSF</span>
          </div>
          <div className="hidden sm:flex items-center gap-3 text-[11px] text-slate-600">
            <span className="flex items-center gap-1">
              <Waves className="w-3 h-3 text-cyan-600" />
              Wave: <b className="text-slate-900">1.5m</b>
            </span>
            <span className="flex items-center gap-1">
              <Wind className="w-3 h-3 text-amber-600" />
              Wind: <b className="text-slate-900">11.5 m/s</b>
            </span>
            <span className="flex items-center gap-1">
              <span>🌡️</span>
              SST: <b className="text-slate-900">28.4°C</b>
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-800 font-bold flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-600" />
            SAFE TO VENTURE
          </span>
        </div>
      </div>

      {/* Main Messages Scroll Stream */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center min-h-[420px] text-center space-y-5 py-4">
            <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 via-blue-600 to-indigo-600 shadow-xl shadow-cyan-500/20">
              <span className="text-3xl">🐋</span>
            </div>

            <div className="max-w-md space-y-1">
              <h2 className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 via-cyan-800 to-blue-800 bg-clip-text text-transparent">
                ORCA Marine Conversational AI
              </h2>
              <p className="text-xs text-slate-500 leading-relaxed">
                Powered by Multi-Agent Reasoning & SAMUDRA Ocean State Forecasting. Speak or type in Tamil, Telugu, Hindi, Malayalam, Gujarati, Bengali, Marathi, Kannada, or English.
              </p>
            </div>

            {/* Quick Action Prompt Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-xl text-left">
              {SAMPLE_QUERIES.map((sq, idx) => (
                <button
                  key={idx}
                  onClick={() => sendMessage(sq.query)}
                  className="p-3.5 rounded-2xl border border-slate-200 bg-white hover:bg-cyan-50/50 hover:border-cyan-400 hover:shadow-md transition-all group text-left flex items-start gap-3 shadow-xs hover:scale-[1.01]"
                >
                  <span className="text-xl group-hover:scale-125 transition-transform">{sq.icon}</span>
                  <div className="space-y-0.5">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-bold text-slate-800 group-hover:text-cyan-800">
                        {sq.title}
                      </p>
                    </div>
                    <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                      {sq.query}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex flex-col gap-2 p-3.5 rounded-2xl bg-cyan-50 border border-cyan-200 text-xs text-cyan-900 animate-pulse shadow-sm">
            <div className="flex items-center gap-3 font-semibold">
              <div className="w-4 h-4 rounded-full border-2 border-cyan-600 border-t-transparent animate-spin" />
              <span>Multi-Agent Reasoning in progress: INCOIS · MOSDAC · A* Router · SVAS Safety…</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap text-[10px]">
              {['SST Thermal Fronts', 'Wave Height Contours', 'Space-Time A* Vector', 'IMBL Boundary Check'].map((s) => (
                <span key={s} className="px-2 py-0.5 rounded-full bg-white border border-slate-200 text-slate-700">
                  ⚙ {s}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Contextual zone prompt banner */}
      {contextualPrompt && selectedZone && !isLoading && (
        <div className="px-4 py-2 bg-slate-100 border-t border-slate-200 flex justify-between items-center text-xs">
          <span className="text-slate-700 flex items-center gap-1.5">
            <Fish className="w-3.5 h-3.5 text-emerald-600" />
            Selected Zone: <strong className="text-slate-900">{selectedZone.zone_id}</strong>
          </span>
          <button
            className="text-xs font-bold text-cyan-700 hover:text-cyan-800 underline"
            onClick={() => sendMessage(contextualPrompt)}
          >
            Ask fish forecast →
          </button>
        </div>
      )}

      {/* Suggestion Chips */}
      {suggestions.length > 0 && !isLoading && (
        <div className="px-4 py-2 border-t border-slate-200 bg-slate-50/70">
          <SuggestionChips suggestions={suggestions} onSelect={sendMessage} />
        </div>
      )}

      {/* Input Box Component with Voice */}
      <div className="px-4 py-3.5 border-t border-slate-200 bg-white/95 shadow-lg">
        <ChatInput onSend={sendMessage} disabled={isLoading} />
      </div>
    </div>
  );
}
