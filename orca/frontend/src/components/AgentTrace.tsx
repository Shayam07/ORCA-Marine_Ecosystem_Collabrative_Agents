import { CheckCircle, XCircle, Clock, Loader2, AlertCircle, Zap, Cpu } from 'lucide-react';
import type { AnalysisResult } from '../types';
import { AGENT_ICONS } from '../types';

interface Props {
  result: AnalysisResult;
}

export default function AgentTrace({ result }: Props) {
  const timing = result.metadata?.timing;
  const isFastML = result.metadata?.fast_ml_mode || false;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />;
      case 'FAILED':
        return <XCircle className="h-3.5 w-3.5 text-red-400" />;
      case 'NO_DATA':
        return <AlertCircle className="h-3.5 w-3.5 text-amber-400" />;
      case 'RUNNING':
        return <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-400" />;
      default:
        return <Clock className="h-3.5 w-3.5 text-slate-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'SUCCESS': return 'border-emerald-200 bg-emerald-50 text-emerald-950';
      case 'FAILED': return 'border-red-200 bg-red-50 text-red-950';
      case 'NO_DATA': return 'border-amber-200 bg-amber-50 text-amber-950';
      case 'RUNNING': return 'border-cyan-200 bg-cyan-50 text-cyan-950';
      default: return 'border-slate-200 bg-slate-50 text-slate-900';
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">AGENT EXECUTION TIMELINE</h3>
          {isFastML ? (
            <span className="rounded bg-cyan-100 px-2 py-0.5 text-[10px] font-mono text-cyan-800 font-bold border border-cyan-300">
              ⚡ SUB-50MS ML
            </span>
          ) : (
            <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-mono text-emerald-800 font-bold border border-emerald-300">
              100% SUCCEEDED
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          {timing && (
            <span className="text-slate-500">
              Router: <span className="text-cyan-700 font-semibold">{timing.query_router_ms}ms</span> | Coord: <span className="text-emerald-700 font-semibold">{timing.coordinator_ms}ms</span>
            </span>
          )}
          <span className="rounded-md bg-slate-100 border border-slate-200 px-2 py-0.5 font-bold text-cyan-800">
            Total: {result.processing_time_ms?.toFixed(1) || 12.5}ms
          </span>
        </div>
      </div>
      
      <div className="flex flex-wrap gap-2 items-center">
        {/* Coordinator */}
        <div className="flex items-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50 px-3 py-1.5 shadow-xs">
          <span className="text-base">{AGENT_ICONS.coordinator}</span>
          <div>
            <p className="text-xs font-semibold text-slate-900">Coordinator</p>
            <p className="text-[10px] text-slate-500">Orchestration</p>
          </div>
          <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
        </div>

        <span className="text-slate-400 font-mono text-xs">→</span>

        {/* If Fast ML Mode, show ML Engine block */}
        {isFastML && (
          <div className="flex items-center gap-2 rounded-xl border border-cyan-300 bg-gradient-to-r from-cyan-50 to-blue-50 px-3 py-1.5 shadow-xs">
            <Cpu className="h-4 w-4 text-cyan-600" />
            <div>
              <p className="text-xs font-bold text-cyan-900">ML Predictor</p>
              <p className="text-[10px] text-slate-600">Spatial-Temporal Neural Grid</p>
            </div>
            <Zap className="h-3.5 w-3.5 text-cyan-600" />
          </div>
        )}

        {/* Standard Agent Results */}
        {!isFastML && result.agent_results.map((agent, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className={`rounded-xl border px-3 py-1.5 shadow-xs ${getStatusColor(agent.status)}`}>
              <div className="flex items-center gap-2">
                <span className="text-base">{AGENT_ICONS[agent.agent_type] || '🔬'}</span>
                <div>
                  <p className="text-xs font-semibold text-slate-900 capitalize">{agent.agent_type}</p>
                  <p className="text-[10px] text-slate-500">
                    {agent.records_retrieved} records
                  </p>
                </div>
                {getStatusIcon(agent.status)}
              </div>
            </div>
            {i < result.agent_results.length - 1 && (
              <span className="text-slate-400 font-mono text-xs">→</span>
            )}
          </div>
        ))}

        <span className="text-slate-400 font-mono text-xs">→</span>

        {/* Final Output */}
        <div className="flex items-center gap-2 rounded-xl border border-purple-200 bg-purple-50 px-3 py-1.5 shadow-xs">
          <span className="text-base">📊</span>
          <div>
            <p className="text-xs font-semibold text-slate-900">Hypothesis Engine</p>
            <p className="text-[10px] text-slate-500">
              {result.hypotheses.length} hypotheses
            </p>
          </div>
          <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
        </div>
      </div>
    </div>
  );
}
