import { useState } from 'react';
import { X, Key, Globe, Server, CheckCircle, XCircle } from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

interface Props {
  open: boolean;
  onClose: () => void;
}

const PROVIDERS = [
  { name: 'Copernicus Marine', env: 'COPERNICUS', description: 'European ocean monitoring (SST, chlorophyll, salinity)' },
  { name: 'Global Fishing Watch', env: 'FISHING_API_KEY', description: 'Vessel activity and fishing effort data' },
  { name: 'NASA Earthdata', env: 'NASA_API_KEY', description: 'Satellite ocean color and SST data' },
  { name: 'NOAA', env: 'NOAA_API_KEY', description: 'Ocean and atmospheric observations' },
  { name: 'ISRO / MOSDAC', env: 'MOSDAC', description: 'Indian Earth observation data' },
];

export default function SettingsDialog({ open, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<'providers' | 'about'>('providers');

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      
      {/* Dialog */}
      <div className="relative z-10 w-full max-w-2xl rounded-2xl border border-slate-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Settings</h2>
            <p className="text-sm text-slate-500">Configure data providers and API keys</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="text-slate-500 hover:text-slate-800">
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-200 px-6">
          <button
            onClick={() => setActiveTab('providers')}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'providers'
                ? 'border-cyan-600 text-cyan-800 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Key className="mr-2 inline h-4 w-4" />
            Data Providers
          </button>
          <button
            onClick={() => setActiveTab('about')}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'about'
                ? 'border-cyan-600 text-cyan-800 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Globe className="mr-2 inline h-4 w-4" />
            About ORCA
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[60vh] overflow-y-auto p-6">
          {activeTab === 'providers' && (
            <div className="space-y-4">
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm text-amber-900">
                  <strong>How it works:</strong> ORCA tries real data providers first, then falls back to demo data.
                  Add API keys below to enable live data from real sources.
                </p>
              </div>

              {PROVIDERS.map((provider) => (
                <div key={provider.name} className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">{provider.name}</h3>
                      <p className="text-sm text-slate-500">{provider.description}</p>
                    </div>
                    <Badge variant="outline" className="text-xs bg-white border-slate-200 text-slate-700">
                      {provider.env}
                    </Badge>
                  </div>
                  <div className="mt-3">
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      API Key / Credentials
                    </label>
                    <input
                      type="password"
                      placeholder={`Enter ${provider.name} credentials...`}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
                    />
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Add to <code className="rounded bg-slate-200 px-1 text-slate-800 font-mono">.env</code> file: {provider.env}=your_key
                  </p>
                </div>
              ))}

              <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
                <h3 className="font-semibold text-slate-900 mb-1">LLM Configuration (Optional)</h3>
                <p className="text-sm text-slate-500 mb-3">
                  Enable AI-powered natural language explanations
                </p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      OpenAI API Key
                    </label>
                    <input
                      type="password"
                      placeholder="sk-..."
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Model
                    </label>
                    <select className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-cyan-500 focus:outline-none">
                      <option>gpt-4o-mini</option>
                      <option>gpt-4o</option>
                      <option>gpt-3.5-turbo</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'about' && (
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-md">
                    <span className="text-2xl">🌊</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">ORCA v0.1.0</h3>
                    <p className="text-sm text-slate-500">Marine EcOsystem Reasoning with Collaborative Agents</p>
                  </div>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">
                  ORCA is a multi-agent marine intelligence platform built for SIH 2026 Problem Statement 176.
                  It combines real environmental data with specialized AI agents that independently analyze evidence,
                  then fuse their findings into explainable ecosystem hypotheses.
                </p>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
                <h4 className="font-semibold text-slate-900 mb-2">Architecture</h4>
                <div className="space-y-2 text-sm text-slate-600">
                  <div className="flex items-center gap-2">
                    <Server className="h-4 w-4 text-cyan-600" />
                    <span>FastAPI backend with 7 specialized agents</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-cyan-600" />
                    <span>React + TypeScript + MapLibre frontend</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Key className="h-4 w-4 text-cyan-600" />
                    <span>9 data providers with automatic fallback</span>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
                <h4 className="font-semibold text-slate-900 mb-2">Data Sources</h4>
                <div className="grid grid-cols-2 gap-2 text-sm text-slate-600">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-emerald-600" />
                    <span>Copernicus Marine</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-emerald-600" />
                    <span>Global Fishing Watch</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-emerald-600" />
                    <span>ERA5 Weather</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-emerald-600" />
                    <span>Semantic Scholar</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-slate-400" />
                    <span>NASA (needs API key)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-slate-400" />
                    <span>NOAA (needs API key)</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-200 px-6 py-4">
          <Button variant="outline" onClick={onClose} className="border-slate-200 text-slate-700 hover:bg-slate-100">
            Close
          </Button>
          <Button className="bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold">
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
}
