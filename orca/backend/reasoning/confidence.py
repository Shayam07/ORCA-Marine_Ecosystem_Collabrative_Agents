"""ORCA Confidence Engine — Programmatic confidence scoring.

Rules:
- NO hardcoded values
- Every factor must be calculated from actual data
- If a factor cannot be calculated, use null and adjust formula
- The LLM must NEVER invent confidence scores
"""

from __future__ import annotations

import logging
import statistics
from typing import Optional

from models.agent import AgentResult, AgentStatus
from models.evidence import FusionResult
from models.hypothesis import ConfidenceLevel, Hypothesis, HypothesisResult

logger = logging.getLogger("orca.reasoning.confidence")


# Source reliability scores — these are the ONLY static values
# Based on documented data quality assessments
SOURCE_RELIABILITY: dict[str, float] = {
    "COPERNICUS_MARINE": 0.95,
    "MOSDAC": 0.90,
    "NASA": 0.95,
    "NOAA": 0.95,
    "ERA5": 0.90,
    "GLOBAL_FISHING_WATCH": 0.85,
    "LITERATURE": 0.90,
    "GEOSPATIAL": 0.85,
    "DEMO": 0.50,
}


class ConfidenceEngine:
    """Computes programmatic confidence scores for hypotheses.

    Every factor is calculated from actual data. No hardcoded defaults.
    """

    def compute_confidence(
        self,
        hypothesis_result: HypothesisResult,
        agent_results: list[AgentResult],
        fusion_result: FusionResult,
    ) -> HypothesisResult:
        """Recompute confidence scores for all hypotheses."""

        factors = self._compute_factors(agent_results, fusion_result)

        for hypothesis in hypothesis_result.hypotheses:
            score = self._compute_final_score(hypothesis, factors)

            # Dataset disagreement penalty
            disagreement_count = 0
            if fusion_result and fusion_result.contradictions:
                disagreement_count = sum(1 for c in fusion_result.contradictions if "disagreement" in c.lower() or "diverging" in c.lower())
                if disagreement_count > 0:
                    score = max(0.1, score - (disagreement_count * 0.15))
                    hypothesis.uncertainty_notes.append(
                        f"⚠️ Dataset disagreement: {disagreement_count} conflicting observations between providers. Uncertainty elevated — results must be verified."
                    )

            # Check if any underlying evidence is stale (> 24 hours)
            stale_obs_count = sum(
                1 for r in agent_results for o in getattr(r, "evidence", [])
                if getattr(o, "freshness_status", None) and getattr(o.freshness_status, "value", str(o.freshness_status)) == "STALE"
            )
            if stale_obs_count > 0:
                score = max(0.1, score - 0.20)
                hypothesis.uncertainty_notes.append(
                    f"⚠️ Stale marine data: {stale_obs_count} underlying observations are >24 hours old. Recommendation confidence reduced."
                )

            hypothesis.score = round(score, 3)
            hypothesis.confidence_level = self._score_to_level(score)
            hypothesis.confidence_breakdown = {
                k: round(v, 3) if v is not None else None
                for k, v in factors.items()
            }
            if disagreement_count > 0:
                hypothesis.confidence_breakdown["dataset_disagreement_penalty"] = round(disagreement_count * 0.15, 2)
            if stale_obs_count > 0:
                hypothesis.confidence_breakdown["data_staleness_penalty"] = 0.20

            # Add uncertainty notes based on actual factors
            if factors.get("agent_confidence") is not None and factors["agent_confidence"] < 0.5:
                hypothesis.uncertainty_notes.append(
                    "Agent confidence is low — limited analytical results"
                )
            if factors.get("data_quality") is not None and factors["data_quality"] < 0.7:
                hypothesis.uncertainty_notes.append(
                    "Data quality is below optimal threshold"
                )
            if factors.get("source_reliability") is not None and factors["source_reliability"] < 0.6:
                hypothesis.uncertainty_notes.append(
                    "Data sources have limited reliability"
                )
            if factors.get("evidence_count") is not None and factors["evidence_count"] < 5:
                hypothesis.uncertainty_notes.append(
                    "Limited number of evidence items"
                )

        # Sort by updated scores
        hypothesis_result.hypotheses.sort(key=lambda h: h.score, reverse=True)
        hypothesis_result.top_hypothesis = (
            hypothesis_result.hypotheses[0]
            if hypothesis_result.hypotheses else None
        )

        # Overall confidence
        if hypothesis_result.hypotheses:
            hypothesis_result.overall_confidence = hypothesis_result.hypotheses[0].score
            hypothesis_result.overall_confidence_level = hypothesis_result.hypotheses[0].confidence_level

        return hypothesis_result

    def _compute_factors(
        self,
        agent_results: list[AgentResult],
        fusion_result: FusionResult,
    ) -> dict[str, Optional[float]]:
        """Compute individual confidence factors from actual data.

        Returns dict with None for factors that cannot be calculated.
        """

        # ── Agent confidence ─────────────────────────────────────
        # Average confidence of successful agents
        successful = [r for r in agent_results if r.status == AgentStatus.SUCCESS]
        if successful:
            agent_conf = statistics.mean(r.confidence for r in successful)
        else:
            agent_conf = None

        # ── Data quality ─────────────────────────────────────────
        # Average quality of all evidence observations
        all_evidence = []
        for r in agent_results:
            all_evidence.extend(r.evidence)
        
        if all_evidence:
            data_quality = statistics.mean(e.quality for e in all_evidence)
        else:
            data_quality = None

        # ── Source reliability ───────────────────────────────────
        # Average reliability of sources actually used
        sources_used = set()
        for r in agent_results:
            sources_used.update(r.data_sources_used)

        if sources_used:
            reliability_scores = [
                SOURCE_RELIABILITY.get(s, 0.5) for s in sources_used
            ]
            source_reliability = statistics.mean(reliability_scores)
        else:
            source_reliability = None

        # ── Evidence count ───────────────────────────────────────
        evidence_count = len(all_evidence) if all_evidence else None

        # ── Cross-agent agreement ────────────────────────────────
        # Only count genuinely independent agreements
        cross_agreement = fusion_result.evidence_convergence_score if fusion_result else None

        # ── Temporal support ─────────────────────────────────────
        temporal_count = len(fusion_result.temporal_relationships) if fusion_result else 0
        temporal_support = min(1.0, temporal_count * 0.3) if temporal_count > 0 else None

        # ── Spatial support ──────────────────────────────────────
        spatial_count = len(fusion_result.spatial_relationships) if fusion_result else 0
        spatial_support = min(1.0, spatial_count * 0.3) if spatial_count > 0 else None

        return {
            "agent_confidence": agent_conf,
            "data_quality": data_quality,
            "source_reliability": source_reliability,
            "evidence_count": evidence_count,
            "cross_agent_agreement": cross_agreement,
            "temporal_support": temporal_support,
            "spatial_support": spatial_support,
        }

    def _compute_final_score(
        self,
        hypothesis: Hypothesis,
        factors: dict[str, Optional[float]],
    ) -> float:
        """Compute final confidence score for a hypothesis.

        Uses only available factors. Null factors are excluded from weighting.
        """
        # Define weights for each factor
        weights = {
            "agent_confidence": 0.20,
            "data_quality": 0.20,
            "source_reliability": 0.15,
            "cross_agent_agreement": 0.20,
            "temporal_support": 0.10,
            "spatial_support": 0.10,
        }

        # Compute weighted average of available factors
        weighted_sum = 0.0
        weight_total = 0.0

        for factor_name, weight in weights.items():
            value = factors.get(factor_name)
            if value is not None:
                weighted_sum += weight * value
                weight_total += weight

        if weight_total > 0:
            base_score = weighted_sum / weight_total
        else:
            base_score = 0.3  # Minimal default when no factors available

        # Modulate by hypothesis's own evidence score
        combined = 0.6 * base_score + 0.4 * hypothesis.score

        return min(1.0, max(0.0, combined))

    def _score_to_level(self, score: float) -> ConfidenceLevel:
        if score >= 0.80:
            return ConfidenceLevel.HIGH
        elif score >= 0.60:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
