import React, { useState, useEffect } from 'react';
import {
  Server,
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Wifi,
  ShieldAlert,
  ArrowRight,
  HelpCircle,
  X,
  ExternalLink,
  Laptop,
  Smartphone,
} from 'lucide-react';
import {
  checkBackendHealth,
  getApiBaseUrl,
  setCustomApiBaseUrl,
  DEFAULT_LAN_BACKEND_URL,
  type HealthCheckResult,
} from '../api/config';

interface BackendStatusModalProps {
  open: boolean;
  onClose: () => void;
  onStatusChange?: (connected: boolean) => void;
}

export default function BackendStatusModal({
  open,
  onClose,
  onStatusChange,
}: BackendStatusModalProps) {
  const [currentUrl, setCurrentUrl] = useState<string>(getApiBaseUrl() || DEFAULT_LAN_BACKEND_URL);
  const [testing, setTesting] = useState<boolean>(false);
  const [healthResult, setHealthResult] = useState<HealthCheckResult | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  const runTest = async (urlToTest?: string) => {
    setTesting(true);
    setSaveSuccess(false);
    try {
      const res = await checkBackendHealth(urlToTest !== undefined ? urlToTest : currentUrl);
      setHealthResult(res);
      if (onStatusChange) {
        onStatusChange(res.connected);
      }
    } catch {
      // Handled inside checkBackendHealth
    } finally {
      setTesting(false);
    }
  };

  useEffect(() => {
    if (open) {
      const active = getApiBaseUrl() || DEFAULT_LAN_BACKEND_URL;
      setCurrentUrl(active);
      runTest(active);
    }
  }, [open]);

  if (!open) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = currentUrl.trim();
    setCustomApiBaseUrl(clean);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 2500);
    await runTest(clean);
  };

  const handleResetDefault = () => {
    setCustomApiBaseUrl(null);
    setCurrentUrl(DEFAULT_LAN_BACKEND_URL);
    runTest(DEFAULT_LAN_BACKEND_URL);
  };

  const handlePreset = (url: string) => {
    setCurrentUrl(url);
    setCustomApiBaseUrl(url);
    runTest(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-[#181d25] border border-slate-700/80 rounded-2xl w-full max-w-lg shadow-2xl text-slate-100 flex flex-col max-h-[92vh] overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between bg-[#1f242d]">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl ${healthResult?.connected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white tracking-tight flex items-center gap-2">
                Backend Connection Diagnostics
              </h2>
              <p className="text-xs text-slate-400">
                FastAPI Server Connectivity & Health
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs">
          {/* Status Banner */}
          <div
            className={`p-4 rounded-xl border flex items-start gap-3 transition-all ${
              healthResult?.connected
                ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-200'
                : 'bg-rose-950/40 border-rose-500/40 text-rose-200'
            }`}
          >
            {testing ? (
              <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin flex-shrink-0 mt-0.5" />
            ) : healthResult?.connected ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            )}

            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-sm uppercase tracking-wide">
                  {testing
                    ? 'Probing Backend...'
                    : healthResult?.connected
                    ? 'CONNECTED & OPERATIONAL'
                    : 'BACKEND OFFLINE / UNREACHABLE'}
                </span>
                {healthResult?.latencyMs !== undefined && (
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-black/40 font-mono text-slate-300">
                    {healthResult.latencyMs}ms
                  </span>
                )}
              </div>
              <p className="text-xs mt-1 text-slate-300">
                {testing
                  ? 'Testing GET /health endpoint...'
                  : healthResult?.message || 'Ready to test connection.'}
              </p>
            </div>
          </div>

          {/* Detailed Diagnosis & Troubleshooting (if offline) */}
          {!testing && healthResult && !healthResult.connected && (
            <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-700/60 space-y-2.5">
              <div className="flex items-center gap-2 font-semibold text-amber-300 text-xs">
                <ShieldAlert className="w-4 h-4 text-amber-400" />
                <span>Diagnostic Recommendation</span>
              </div>
              <p className="text-slate-300 text-xs leading-relaxed">
                {healthResult.recommendation}
              </p>

              {/* Troubleshooting Checklist */}
              <div className="pt-2 border-t border-slate-800 space-y-1.5 text-[11px] text-slate-400">
                <div className="font-semibold text-slate-300">Quick Checklist:</div>
                <div className="flex items-start gap-2">
                  <span className="text-cyan-400 font-mono">1.</span>
                  <span>Is backend running? In terminal: <code className="text-cyan-300 bg-slate-950 px-1 py-0.5 rounded">uvicorn main:app --host 0.0.0.0 --port 8000</code></span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-cyan-400 font-mono">2.</span>
                  <span>Are PC & Phone on the same Wi-Fi? Check PC IP in powershell with <code className="text-cyan-300 bg-slate-950 px-1 py-0.5 rounded">ipconfig</code></span>
                </div>
                <div className="flex items-start gap-2">
                  <span className="text-cyan-400 font-mono">3.</span>
                  <span>If on College/Public Wi-Fi, <strong>AP Isolation</strong> prevents phone-to-PC connections. Use a <strong>Mobile Hotspot</strong> or plug USB and run:</span>
                </div>
                <div className="bg-slate-950 p-2 rounded-lg font-mono text-[11px] text-emerald-400 select-all border border-slate-800">
                  adb reverse tcp:8000 tcp:8000
                </div>
              </div>
            </div>
          )}

          {/* Change Server IP Form */}
          <form onSubmit={handleSave} className="space-y-3 pt-1">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Backend Server URL / IP Address:
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={currentUrl}
                  onChange={(e) => setCurrentUrl(e.target.value)}
                  placeholder="e.g. http://192.168.1.48:8000"
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-500 transition-colors"
                />
                <button
                  type="submit"
                  className="px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-xl text-xs transition-colors flex items-center gap-1.5 shadow-md shadow-cyan-900/30"
                >
                  Save
                </button>
              </div>
              {saveSuccess && (
                <p className="text-[11px] text-emerald-400 mt-1">Saved to app storage!</p>
              )}
            </div>

            {/* Quick Presets */}
            <div className="space-y-1.5">
              <span className="text-[11px] text-slate-400 font-medium">Quick Presets:</span>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => handlePreset('http://192.168.1.48:8000')}
                  className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] text-slate-300 transition-colors"
                >
                  Current Wi-Fi (192.168.1.48)
                </button>
                <button
                  type="button"
                  onClick={() => handlePreset('http://10.0.2.2:8000')}
                  className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] text-slate-300 transition-colors"
                >
                  Android Emulator (10.0.2.2)
                </button>
                <button
                  type="button"
                  onClick={() => handlePreset('http://127.0.0.1:8000')}
                  className="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] text-slate-300 transition-colors"
                >
                  ADB Reverse / Localhost
                </button>
                <button
                  type="button"
                  onClick={handleResetDefault}
                  className="px-2 py-1 rounded-lg bg-slate-800/60 hover:bg-slate-700 border border-dashed border-slate-700 text-[11px] text-slate-400 transition-colors"
                >
                  Reset Default
                </button>
              </div>
            </div>
          </form>
        </div>

        {/* Footer Actions */}
        <div className="px-5 py-3 border-t border-slate-800 bg-[#1f242d] flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span>Target: <span className="font-mono text-slate-200">{healthResult?.endpointUrl || `${currentUrl}/health`}</span></span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => runTest()}
              disabled={testing}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium border border-slate-700 transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${testing ? 'animate-spin text-cyan-400' : ''}`} />
              <span>{testing ? 'Testing...' : 'Test Connection'}</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-xs font-semibold transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
