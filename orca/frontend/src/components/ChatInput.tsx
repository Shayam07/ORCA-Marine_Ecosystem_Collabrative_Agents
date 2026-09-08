import { useState, useRef, useEffect } from 'react';
import { Button } from './ui/button';
import { Mic, MicOff, Loader2, Send, Sparkles } from 'lucide-react';
import { getApiUrl } from '../api/client';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

type VoiceState = 'idle' | 'recording' | 'processing';

const SUPPORTED_LANGS = [
  { code: 'ta', bcp47: 'ta-IN', label: 'தமிழ்', flag: '🇮🇳' },
  { code: 'te', bcp47: 'te-IN', label: 'తెలుగు', flag: '🇮🇳' },
  { code: 'hi', bcp47: 'hi-IN', label: 'हिंदी', flag: '🇮🇳' },
  { code: 'ml', bcp47: 'ml-IN', label: 'മലയാളം', flag: '🇮🇳' },
  { code: 'gu', bcp47: 'gu-IN', label: 'ગુજરાતી', flag: '🇮🇳' },
  { code: 'mr', bcp47: 'mr-IN', label: 'मराठी', flag: '🇮🇳' },
  { code: 'bn', bcp47: 'bn-IN', label: 'বাংলা', flag: '🇮🇳' },
  { code: 'kn', bcp47: 'kn-IN', label: 'ಕನ್ನಡ', flag: '🇮🇳' },
  { code: 'en', bcp47: 'en-IN', label: 'English', flag: '🌐' },
];

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [selectedLang, setSelectedLang] = useState('ta');
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

  const handleSubmit = () => {
    if (value.trim() && !disabled) {
      onSend(value.trim());
      setValue('');
      setInterimTranscript('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Start Real-Time Web Speech Recognition or MediaRecorder fallback
  const startRecording = async () => {
    const activeLang = SUPPORTED_LANGS.find((l) => l.code === selectedLang) || SUPPORTED_LANGS[0];
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognition.lang = activeLang.bcp47;
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onstart = () => {
          setVoiceState('recording');
          setInterimTranscript('');
        };

        recognition.onresult = (event: any) => {
          let currentInterim = '';
          let finalTranscript = '';

          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              currentInterim += event.results[i][0].transcript;
            }
          }

          if (finalTranscript) {
            setValue((prev) => (prev ? `${prev} ${finalTranscript}` : finalTranscript));
            setInterimTranscript('');
          } else {
            setInterimTranscript(currentInterim);
          }
        };

        recognition.onerror = (event: any) => {
          console.warn('Speech recognition notice:', event.error);
          if (event.error === 'network') {
            // Google speech server unreachable — try MediaRecorder fallback
            console.warn('Web Speech API network error, falling back to MediaRecorder');
            try { recognition.abort(); } catch {}
            recognitionRef.current = null;
            startMediaRecorderFallback(activeLang.bcp47);
          } else if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
            alert('Microphone access denied. Please allow microphone permission in your browser settings.');
            setVoiceState('idle');
          } else if (event.error !== 'no-speech') {
            stopRecording();
          }
        };

        recognition.onend = () => {
          setVoiceState('idle');
          setInterimTranscript('');
        };

        recognitionRef.current = recognition;
        recognition.start();
        return;
      } catch (err) {
        console.warn('Native speech recognition fallback triggered:', err);
      }
    }

    // If no Web Speech API at all, go directly to MediaRecorder fallback
    await startMediaRecorderFallback(activeLang.bcp47);
  };

  const startMediaRecorderFallback = async (langBcp47: string) => {
    setVoiceState('recording');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setVoiceState('processing');
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const reader = new FileReader();

        reader.onloadend = async () => {
          const base64 = (reader.result as string).split(',')[1];
          try {
            const res = await fetch(getApiUrl('/api/v1/chat/voice/process'), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ audio_base64: base64, language_code: selectedLang }),
            });
            const data = await res.json();
            const recognized = data.translated_english_query || data.recognized_text || '';
            if (recognized) {
              setValue((prev) => (prev ? `${prev} ${recognized}` : recognized));
            }
            inputRef.current?.focus();
          } catch (err) {
            console.error('Voice transcription failed:', err);
            // Don't set hardcoded text — let user know it failed
            setVoiceState('idle');
            return;
          } finally {
            setVoiceState('idle');
          }
        };
        reader.readAsDataURL(blob);
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setVoiceState('recording');
    } catch (err) {
      console.error('Audio capture error:', err);
      setVoiceState('idle');
    }
  };

  const stopRecording = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setVoiceState('idle');
  };

  const toggleRecording = () => {
    if (voiceState === 'idle') startRecording();
    else stopRecording();
  };

  const activeLangLabel = SUPPORTED_LANGS.find((l) => l.code === selectedLang);

  return (
    <div className="space-y-2.5">
      {/* Voice controls & Language selector bar */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-cyan-800 font-semibold tracking-wide uppercase flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-cyan-600 animate-spin-slow" />
            Voice Intelligence:
          </span>
          <div className="relative">
            <button
              onClick={() => setShowLangPicker((p) => !p)}
              className="text-xs px-2.5 py-1 rounded-lg border border-cyan-200 bg-white text-cyan-900 hover:border-cyan-400 transition-colors flex items-center gap-1.5 shadow-xs"
            >
              <span>{activeLangLabel?.flag}</span>
              <span className="font-medium">{activeLangLabel?.label}</span>
              <span className="text-slate-500 text-[10px] ml-0.5">▾</span>
            </button>
            {showLangPicker && (
              <div className="absolute bottom-9 left-0 z-50 bg-white border border-slate-200 rounded-xl shadow-2xl py-1.5 w-48 backdrop-blur-xl">
                {SUPPORTED_LANGS.map((l) => (
                  <button
                    key={l.code}
                    onClick={() => {
                      setSelectedLang(l.code);
                      setShowLangPicker(false);
                    }}
                    className={`w-full text-left px-3.5 py-2 text-xs hover:bg-slate-100 flex items-center justify-between transition-colors ${
                      selectedLang === l.code ? 'text-cyan-800 font-bold bg-cyan-50' : 'text-slate-700'
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <span>{l.flag}</span>
                      <span>{l.label}</span>
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">{l.code.toUpperCase()}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {voiceState === 'recording' && (
          <span className="text-xs text-red-700 flex items-center gap-2 font-medium bg-red-50 px-2.5 py-0.5 rounded-full border border-red-200 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block animate-ping" />
            Listening in {activeLangLabel?.label}… Speak naturally
          </span>
        )}
        {voiceState === 'processing' && (
          <span className="text-xs text-amber-800 flex items-center gap-1.5 font-medium bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Transcribing speech…
          </span>
        )}
      </div>

      {/* Live Interim Transcript Bubble */}
      {interimTranscript && (
        <div className="text-xs text-cyan-900 bg-cyan-50 border border-cyan-200 rounded-lg px-3 py-1.5 italic animate-fade-in flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-600 animate-pulse" />
          "{interimTranscript}"
        </div>
      )}

      {/* Input box + Action buttons */}
      <div className="flex items-end gap-2.5">
        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask in English or speak in Tamil, Telugu, Hindi, Malayalam, Gujarati..."
            disabled={disabled}
            rows={1}
            className="w-full bg-white border border-slate-300 hover:border-cyan-400 focus:border-cyan-600 rounded-xl px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/20 shadow-xs resize-none min-h-[44px] max-h-[140px] transition-all"
            style={{ height: 'auto' }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = 'auto';
              target.style.height = Math.min(target.scrollHeight, 140) + 'px';
            }}
          />
        </div>

        {/* Real-time Voice Mic button */}
        <button
          id="voice-record-btn"
          onClick={toggleRecording}
          disabled={disabled || voiceState === 'processing'}
          title={
            voiceState === 'recording'
              ? 'Stop Recording'
              : `Speak in ${activeLangLabel?.label} (${activeLangLabel?.bcp47})`
          }
          className={`flex-shrink-0 h-11 w-11 flex items-center justify-center rounded-xl border transition-all duration-200 shadow-sm ${
            voiceState === 'recording'
              ? 'border-red-500 bg-red-100 text-red-600 shadow-red-500/20 scale-105 animate-pulse'
              : voiceState === 'processing'
              ? 'border-amber-300 bg-amber-50 text-amber-700'
              : 'border-slate-300 bg-white text-cyan-700 hover:border-cyan-500 hover:bg-cyan-50 hover:scale-105'
          }`}
        >
          {voiceState === 'recording' ? (
            <MicOff className="w-5 h-5 text-red-600" />
          ) : voiceState === 'processing' ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Mic className="w-5 h-5 text-cyan-600" />
          )}
        </button>

        {/* Send message button */}
        <Button
          id="send-message-btn"
          onClick={handleSubmit}
          disabled={!value.trim() || disabled}
          className="bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold px-4 py-3 rounded-xl h-11 flex-shrink-0 shadow-md shadow-cyan-600/20 hover:scale-105 transition-all"
        >
          <Send className="w-4 h-4 text-white font-bold" />
        </Button>
      </div>
    </div>
  );
}
