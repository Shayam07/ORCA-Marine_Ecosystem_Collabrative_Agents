import { useState } from 'react';
import {
  Sparkles,
  Mic,
  X,
  Minimize2,
  Maximize2,
  Bot,
  Radio,
} from 'lucide-react';
import { useMarineContext } from '../context/MarineContext';
import { ChatPanel } from './ChatPanel';

export default function FloatingAIAssistant() {
  const { aiAssistantOpen, setAiAssistantOpen, landingCentre } = useMarineContext();
  const [minimized, setMinimized] = useState(false);

  if (!aiAssistantOpen) {
    return (
      <div className="fixed bottom-20 sm:bottom-6 right-4 z-40">
        <button
          onClick={() => setAiAssistantOpen(true)}
          className="group relative flex items-center gap-2.5 px-4 py-3 rounded-full bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 text-white font-bold text-xs shadow-2xl shadow-cyan-600/50 hover:scale-105 active:scale-95 transition-all border border-cyan-400/40"
          title="Open ORCA Marine AI Assistant"
        >
          <div className="relative">
            <span className="text-base">🐋</span>
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-300 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-cyan-400" />
            </span>
          </div>
          <span className="font-extrabold tracking-wide">ORCA AI</span>
          <div className="p-1 rounded-full bg-white/20 text-white">
            <Mic className="w-3.5 h-3.5" />
          </div>
        </button>
      </div>
    );
  }

  return (
    <div
      className={`fixed z-40 transition-all duration-300 ${
        minimized
          ? 'bottom-20 right-4 w-72 h-14'
          : 'inset-0 sm:inset-auto sm:bottom-4 sm:right-4 sm:top-16 w-full sm:w-[460px] md:w-[490px] sm:max-w-[calc(100vw-2rem)]'
      }`}
    >
      <div className="w-full h-full flex flex-col rounded-none sm:rounded-3xl bg-white shadow-2xl border-0 sm:border border-slate-200 overflow-hidden backdrop-blur-2xl pt-safe pb-safe">
        {/* Floating Header */}
        <div className="px-4 py-3 bg-slate-900 border-b border-slate-800 text-white flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="h-7 w-7 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-sm">
              🐋
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs text-white">ORCA Marine AI</span>
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-cyan-950 border border-cyan-500/50 text-cyan-300 font-bold">
                  Bhashini Voice
                </span>
              </div>
              <p className="text-[10px] text-slate-400 truncate max-w-[200px]">
                Active: {landingCentre.name}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setMinimized(!minimized)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title={minimized ? 'Expand' : 'Minimize'}
            >
              {minimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setAiAssistantOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title="Close Assistant"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Chat Body */}
        {!minimized && (
          <div className="flex-1 overflow-hidden bg-slate-50 flex flex-col">
            <ChatPanel />
          </div>
        )}
      </div>
    </div>
  );
}
