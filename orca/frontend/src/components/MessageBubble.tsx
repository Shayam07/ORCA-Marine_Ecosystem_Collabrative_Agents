import { useState } from 'react';
import { Badge } from './ui/badge';
import type { ChatMessage } from './ChatPanel';
import { Volume2, VolumeX, Sparkles, Navigation, MapPin } from 'lucide-react';

const INTENT_ICONS: Record<string, string> = {
  FISHING_LOCATION_RECOMMENDATION: '🎣',
  SAFETY_ASSESSMENT: '🛡️',
  WEATHER_QUERY: '⛅',
  MARINE_CONDITION: '🌊',
  TIDE_QUERY: '🌊',
  PFZ_ANALYSIS: '🐟',
  ROUTE_OPTIMIZATION: '🧭',
  NAVIGATION_QUERY: '🧭',
  ANOMALY_DETECTION: '⚠️',
  CAUSE_ANALYSIS: '🔍',
  GENERAL_MARINE_QUERY: '🔬',
  GENERAL_QUERY: '💬',
};

const RESPONSE_TYPE_STYLES: Record<string, string> = {
  fishing_recommendation: 'border-l-4 border-l-emerald-500 shadow-emerald-950/20',
  safety_alert: 'border-l-4 border-l-amber-500 shadow-amber-950/20',
  marine_conditions: 'border-l-4 border-l-cyan-500 shadow-cyan-950/20',
  route: 'border-l-4 border-l-indigo-500 shadow-indigo-950/20',
  anomaly: 'border-l-4 border-l-red-500 shadow-red-950/20',
  text: '',
};

function renderCleanContent(content: string) {
  if (!content) return null;
  // Clean stray asterisks, backticks, and internal prompt markers
  const clean = content
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*\*/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^draft(?:ing)? (?:the )?response:?\s*/i, '')
    .replace(/^generate response:?\s*/i, '');

  const paragraphs = clean.split('\n\n');
  return paragraphs.map((para, pIdx) => {
    const lines = para.split('\n').filter((l) => l.trim().length > 0);
    const isBulletList = lines.length > 0 && lines.every((l) => l.trim().startsWith('•') || l.trim().startsWith('-'));

    if (isBulletList) {
      return (
        <ul key={pIdx} className="space-y-1.5 my-2">
          {lines.map((line, lIdx) => {
            const text = line.replace(/^[•\-]\s*/, '').trim();
            const colonIdx = text.indexOf(':');
            if (colonIdx > 0 && colonIdx < 30) {
              const label = text.slice(0, colonIdx + 1);
              const rest = text.slice(colonIdx + 1);
              return (
                <li key={lIdx} className="flex items-start gap-2 text-slate-700">
                  <span className="text-cyan-600 font-bold select-none">•</span>
                  <span>
                    <strong className="font-semibold text-slate-900">{label}</strong>
                    {rest}
                  </span>
                </li>
              );
            }
            return (
              <li key={lIdx} className="flex items-start gap-2 text-slate-700">
                <span className="text-cyan-600 font-bold select-none">•</span>
                <span>{text}</span>
              </li>
            );
          })}
        </ul>
      );
    }

    return (
      <p key={pIdx} className="leading-relaxed text-slate-800">
        {para}
      </p>
    );
  });
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  // Text-To-Speech playback toggle
  const toggleSpeech = () => {
    if (!('speechSynthesis' in window)) {
      alert('Speech synthesis is not supported in this browser.');
      return;
    }

    if (isPlayingAudio) {
      window.speechSynthesis.cancel();
      setIsPlayingAudio(false);
      return;
    }

    window.speechSynthesis.cancel();
    // Clean markdown symbols for cleaner voice reading
    const cleanText = message.content
      .replace(/[*#`_~>]/g, '')
      .replace(/\n+/g, '. ');

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    // Detect language or voice
    if (message.language && message.language !== 'en') {
      const langMap: Record<string, string> = {
        ta: 'ta-IN',
        te: 'te-IN',
        hi: 'hi-IN',
        ml: 'ml-IN',
        gu: 'gu-IN',
        mr: 'mr-IN',
        bn: 'bn-IN',
        kn: 'kn-IN',
      };
      if (langMap[message.language]) {
        utterance.lang = langMap[message.language];
      }
    }

    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => setIsPlayingAudio(false);

    setIsPlayingAudio(true);
    window.speechSynthesis.speak(utterance);
  };

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] bg-gradient-to-r from-cyan-600 to-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-3 shadow-md">
          <p className="text-sm font-medium text-white tracking-wide">{message.content}</p>
        </div>
      </div>
    );
  }

  // Assistant message
  const intentIcon = message.intent ? INTENT_ICONS[message.intent] || '🌊' : '🌊';
  const responseStyle = RESPONSE_TYPE_STYLES[message.response_type || 'text'] || '';

  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0 mt-0.5 shadow-md shadow-cyan-500/20">
        🐋
      </div>
      <div className={`max-w-[88%] bg-white border border-slate-200/90 rounded-2xl rounded-tl-sm px-4 py-3.5 shadow-md ${responseStyle}`}>
        {/* Header bar with Intent badge and TTS readout button */}
        <div className="flex items-center justify-between gap-2 mb-2.5">
          <div className="flex items-center gap-1.5 flex-wrap">
            {message.intent && (
              <Badge variant="outline" className="text-[10px] bg-slate-100 border-slate-200 text-cyan-800 font-mono">
                {intentIcon} {message.intent.replace(/_/g, ' ')}
              </Badge>
            )}
            {message.location && (
              <Badge variant="outline" className="text-[10px] bg-slate-100 border-slate-200 text-slate-700 flex items-center gap-1">
                <MapPin className="w-2.5 h-2.5 text-cyan-600" />
                {message.location.name}
              </Badge>
            )}
          </div>

          {/* TTS Speaker button */}
          <button
            onClick={toggleSpeech}
            title={isPlayingAudio ? 'Stop speaking' : 'Read aloud in regional voice'}
            className={`p-1.5 rounded-lg border transition-all ${
              isPlayingAudio
                ? 'border-cyan-500 bg-cyan-100 text-cyan-800 animate-pulse'
                : 'border-slate-200 bg-slate-50 text-slate-600 hover:text-cyan-700 hover:border-cyan-400 hover:bg-cyan-50'
            }`}
          >
            {isPlayingAudio ? <VolumeX className="w-3.5 h-3.5 text-cyan-700" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Content */}
        <div className="text-sm text-slate-800 space-y-2">
          {renderCleanContent(message.content)}
        </div>

        {/* Telemetry data source footer (verified oceanographic feeds only) */}
        {message.sources_used && message.sources_used.length > 0 && (
          <div className="mt-3.5 pt-2 border-t border-slate-100 flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] text-slate-400 font-medium">Verified Sources:</span>
            {message.sources_used.map((s) => (
              <Badge key={s} variant="outline" className="text-[9px] bg-slate-50 border-slate-200 text-slate-600">
                🛰️ {s}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
