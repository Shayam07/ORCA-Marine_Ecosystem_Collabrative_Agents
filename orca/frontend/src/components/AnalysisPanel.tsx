import { useState } from 'react';
import { AlertTriangle, CheckCircle, Info, TrendingUp, ChevronDown, ChevronRight, Fish, Target, Activity } from 'lucide-react';
import type { AnalysisResult } from '../types';
import { INTENT_LABELS, PIPELINE_LABELS } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Button } from './ui/button';
import { Separator } from './ui/separator';
import HypothesisCard from './HypothesisCard';

interface Props {
  result: AnalysisResult;
}

export default function AnalysisPanel({ result }: Props) {
  const [showTechnical, setShowTechnical] = useState(false);

  const intent = result.metadata?.intent || 'GENERAL_MARINE_QUERY';
  const pipeline = result.metadata?.pipeline || 'GENERAL';
  const isFishing = intent === 'FISHING_LOCATION_RECOMMENDATION';
  const isAnomaly = intent === 'ANOMALY_DETECTION';
  const isCause = intent === 'CAUSE_ANALYSIS';
  const isSimpleData = pipeline === 'SIMPLE_DATA';

  const getStatusConfig = (status: string) => {
    if (status.includes('fishing')) return { color: 'text-cyan-400', bg: 'bg-cyan-500/10 border-cyan-500', icon: Fish, text: 'Fishing Recommendation' };
    if (status.includes('major')) return { color: 'text-red-400', bg: 'bg-red-500/10 border-red-500', icon: AlertTriangle, text: 'Major Anomaly' };
    if (status.includes('moderate')) return { color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500', icon: AlertTriangle, text: 'Moderate Anomaly' };
    if (status.includes('minor')) return { color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500', icon: Info, text: 'Minor Anomaly' };
    if (status.includes('cause')) return { color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500', icon: Target, text: 'Cause Analysis' };
    if (status.includes('data')) return { color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500', icon: Activity, text: 'Data Query' };
    return { color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500', icon: CheckCircle, text: 'Normal' };
  };

  const statusConfig = getStatusConfig(result.ecosystem_status);
  const StatusIcon = statusConfig.icon;

  const getConfidenceColor = (level: string) => {
    switch (level) {
      case 'HIGH': return 'text-emerald-400';
      case 'MEDIUM': return 'text-amber-400';
      default: return 'text-red-400';
    }
  };

  return (
    <div className="space-y-4 p-4">
      {/* Intent Banner */}
      <div className={`rounded-xl border p-3 ${statusConfig.bg}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StatusIcon className={`h-5 w-5 ${statusConfig.color}`} />
            <span className={`text-sm font-semibold ${statusConfig.color}`}>
              {INTENT_LABELS[intent] || intent}
            </span>
          </div>
          <Badge variant="outline" className="text-xs">
            {PIPELINE_LABELS[pipeline] || pipeline}
          </Badge>
        </div>
      </div>

      {/* Demo Banner */}
      {result.data_sources?.some(s => s.status === 'DEMO') && (
        <div className="rounded-lg border border-amber-700 bg-amber-900/30 px-4 py-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <span className="text-sm font-medium text-amber-300">DEMO DATA</span>
          </div>
          <p className="mt-1 text-xs text-amber-400/80">
            Synthetic data — not live satellite observations
          </p>
        </div>
      )}

      {/* Summary */}
      <Card className="border-slate-200 bg-white shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-xs font-bold text-slate-700 uppercase tracking-wider">ANALYSIS SUMMARY</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-slate-800">{result.summary}</p>
        </CardContent>
      </Card>

      {/* Confidence */}
      <Card className="border-slate-200 bg-white shadow-sm">
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">CONFIDENCE</p>
              <p className={`text-3xl font-bold ${getConfidenceColor(result.confidence_level)}`}>
                {Math.round(result.confidence * 100)}%
              </p>
            </div>
            <Badge variant={result.confidence_level === 'HIGH' ? 'success' : result.confidence_level === 'MEDIUM' ? 'warning' : 'destructive'}>
              {result.confidence_level}
            </Badge>
          </div>
          <div className="mt-3">
            <Progress value={result.confidence * 100} className="h-2" />
          </div>
        </CardContent>
      </Card>

      {/* Fishing Suitability (if applicable) */}
      {isFishing && result.metadata?.suitability && (
        <FishingRecommendationCard suitability={result.metadata.suitability} />
      )}

      {/* Anomaly Assessment (if applicable) */}
      {isAnomaly && result.metadata?.anomaly_assessment && (
        <AnomalyAssessmentCard assessment={result.metadata.anomaly_assessment} />
      )}

      {/* Key Findings */}
      {result.agent_results.length > 0 && (
        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-xs font-bold text-slate-700 uppercase tracking-wider">KEY FINDINGS</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {result.agent_results
                .flatMap((ar) => ar.findings.filter((f) => f.anomaly_detected))
                .slice(0, 6)
                .map((f, i) => (
                  <div key={i} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-bold text-slate-700 uppercase">{f.variable}</p>
                    <p className="mt-1 text-sm text-slate-800">{f.description}</p>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Hypotheses (for cause analysis) */}
      {isCause && result.hypotheses.length > 0 && (
        <div>
          <h3 className="mb-3 text-xs font-bold text-slate-700 uppercase tracking-wider">HYPOTHESES</h3>
          <div className="space-y-3">
            {result.hypotheses.slice(0, 5).map((h, i) => (
              <HypothesisCard key={h.id || i} hypothesis={h} rank={i + 1} />
            ))}
          </div>
        </div>
      )}

      {/* Technical Details (expandable) */}
      <Card className="border-slate-200 bg-white shadow-sm">
        <CardHeader 
          className="cursor-pointer pb-3"
          onClick={() => setShowTechnical(!showTechnical)}
        >
          <div className="flex items-center justify-between">
            <CardTitle className="text-xs font-bold text-slate-700 uppercase tracking-wider">TECHNICAL DETAILS</CardTitle>
            {showTechnical ? (
              <ChevronDown className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-slate-400" />
            )}
          </div>
        </CardHeader>
        {showTechnical && (
          <CardContent className="pt-0 space-y-4">
            {/* Agent Execution */}
            <div>
              <p className="text-xs font-semibold text-slate-600 mb-2">AGENT EXECUTION</p>
              <div className="space-y-2">
                {result.agent_results.map((agent, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-slate-800 capitalize font-medium">{agent.agent_type}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">{agent.records_retrieved} records</span>
                      <Badge variant={agent.status === 'SUCCESS' ? 'success' : agent.status === 'NO_DATA' ? 'secondary' : 'destructive'} className="text-xs">
                        {agent.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <Separator className="bg-slate-200" />

            {/* Data Sources */}
            <div>
              <p className="text-xs font-semibold text-slate-600 mb-2">DATA SOURCES</p>
              <div className="space-y-1">
                {result.data_sources?.map((source, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-slate-800 font-medium">{source.name}</span>
                    <Badge variant={source.status === 'LIVE' ? 'success' : 'secondary'} className="text-xs">
                      {source.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>

            <Separator className="bg-slate-200" />

            {/* Processing Info */}
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Processing time: {result.processing_time_ms?.toFixed(0)}ms</span>
              <span>Agents: {result.agents_used.length}</span>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Uncertainties */}
      {result.uncertainties.length > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-4">
            <p className="text-xs font-bold text-amber-900 mb-2">UNCERTAINTIES</p>
            <ul className="space-y-1">
              {result.uncertainties.map((u, i) => (
                <li key={i} className="text-xs text-amber-800 flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-3 w-3 flex-shrink-0 text-amber-600" />
                  {u}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────

function FishingRecommendationCard({ suitability }: { suitability: any }) {
  return (
    <Card className="border-cyan-200 bg-cyan-50/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-xs font-bold text-cyan-900 uppercase tracking-wider">
          🎣 FISHING SUITABILITY ESTIMATE
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {suitability.top_recommendations?.map((rec: any, i: number) => (
          <div key={i} className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-slate-900">{rec.label}</span>
              <Badge variant={rec.suitability_score > 0.8 ? 'success' : rec.suitability_score > 0.6 ? 'warning' : 'secondary'}>
                {Math.round(rec.suitability_score * 100)}% suitability
              </Badge>
            </div>
            <div className="space-y-1">
              {rec.factor_descriptions?.map((desc: string, j: number) => (
                <p key={j} className="text-xs text-slate-600">• {desc}</p>
              ))}
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
              <span>Quality: {Math.round(rec.data_quality * 100)}%</span>
              <span>•</span>
              <span>{rec.data_freshness}</span>
            </div>
          </div>
        ))}
        <p className="text-xs text-cyan-800 italic">{suitability.disclaimer}</p>
      </CardContent>
    </Card>
  );
}

function AnomalyAssessmentCard({ assessment }: { assessment: any }) {
  const severityColors: Record<string, string> = {
    normal: 'text-emerald-700',
    minor: 'text-yellow-700',
    moderate: 'text-amber-700',
    major: 'text-red-700',
    extreme: 'text-red-800',
  };

  return (
    <Card className="border-amber-200 bg-amber-50/40">
      <CardHeader className="pb-3">
        <CardTitle className="text-xs font-bold text-amber-900 uppercase tracking-wider">
          ⚠️ ANOMALY ASSESSMENT
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-700">Overall Severity</span>
          <span className={`font-bold uppercase ${severityColors[assessment.overall_severity] || 'text-slate-600'}`}>
            {assessment.overall_severity}
          </span>
        </div>
        
        {assessment.variables?.map((v: any, i: number) => (
          <div key={i} className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold text-slate-900">{v.display_name}</span>
              <span className={`text-xs font-semibold uppercase ${severityColors[v.severity] || 'text-slate-600'}`}>
                {v.severity}
              </span>
            </div>
            <p className="text-xs text-slate-600">{v.description}</p>
            <p className="mt-1 text-xs text-slate-400">{v.methodology}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
