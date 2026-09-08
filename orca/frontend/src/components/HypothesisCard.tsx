import { TrendingUp, CheckCircle, XCircle } from 'lucide-react';
import type { Hypothesis } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';

interface Props {
  hypothesis: Hypothesis;
  rank: number;
}

export default function HypothesisCard({ hypothesis, rank }: Props) {
  const getLevelConfig = (level: string) => {
    switch (level) {
      case 'HIGH':
        return { badge: 'success' as const, progress: 'bg-emerald-500', text: 'text-emerald-400' };
      case 'MEDIUM':
        return { badge: 'warning' as const, progress: 'bg-amber-500', text: 'text-amber-400' };
      default:
        return { badge: 'destructive' as const, progress: 'bg-red-500', text: 'text-red-400' };
    }
  };

  const config = getLevelConfig(hypothesis.confidence_level);
  const scorePercent = Math.round(hypothesis.score * 100);

  return (
    <Card className={`border-slate-200 bg-white shadow-xs ${rank === 1 ? 'border-cyan-500 ring-1 ring-cyan-500/20' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-800">
              {rank}
            </span>
            <CardTitle className="text-sm font-semibold text-slate-900">{hypothesis.title}</CardTitle>
          </div>
          <Badge variant={config.badge}>{hypothesis.confidence_level}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-slate-700 leading-relaxed">{hypothesis.description}</p>
        
        {/* Score Bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Evidence support</span>
            <span className={`font-semibold ${config.text}`}>{scorePercent}%</span>
          </div>
          <Progress 
            value={scorePercent} 
            className="h-1.5"
            indicatorClassName={config.progress}
          />
        </div>

        {/* Confidence Breakdown */}
        {hypothesis.confidence_breakdown && Object.keys(hypothesis.confidence_breakdown).length > 0 && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="mb-2 text-xs font-bold text-slate-600 uppercase tracking-wider">CONFIDENCE BREAKDOWN</p>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(hypothesis.confidence_breakdown)
                .filter(([key]) => key !== 'hypothesis_specific_score')
                .slice(0, 4)
                .map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">{key.replace(/_/g, ' ')}</span>
                    <span className="text-slate-800 font-medium">{value != null ? Math.round(value * 100) + '%' : 'N/A'}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Supporting/Contradicting Evidence */}
        <div className="flex items-center gap-4 text-xs">
          {hypothesis.supporting_evidence.length > 0 && (
            <div className="flex items-center gap-1 text-emerald-700 font-medium">
              <CheckCircle className="h-3 w-3 text-emerald-600" />
              <span>{hypothesis.supporting_evidence.length} supporting</span>
            </div>
          )}
          {hypothesis.contradicting_evidence.length > 0 && (
            <div className="flex items-center gap-1 text-red-700 font-medium">
              <XCircle className="h-3 w-3 text-red-600" />
              <span>{hypothesis.contradicting_evidence.length} contradicting</span>
            </div>
          )}
        </div>

        {/* Uncertainty Notes */}
        {hypothesis.uncertainty_notes.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-2">
            {hypothesis.uncertainty_notes.map((note, i) => (
              <p key={i} className="text-xs text-amber-800">{note}</p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
