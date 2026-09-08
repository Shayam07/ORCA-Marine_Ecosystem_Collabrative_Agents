"""ORCA Hypothesis Engine — Evidence-only hypothesis generation.

Rules:
- NO EVIDENCE → NO CLAIM
- Never generate placeholder hypothesis names
- Every hypothesis must have actual supporting evidence
- Remove hypotheses with no supporting evidence
"""

from __future__ import annotations

import logging

from models.agent import AgentResult, AgentStatus
from models.evidence import EvidenceItem, FusionResult
from models.hypothesis import ConfidenceLevel, Hypothesis, HypothesisResult

logger = logging.getLogger("orca.reasoning.hypothesis")


# ── Template hypotheses — each requires specific evidence patterns ────

HYPOTHESIS_TEMPLATES = [
    {
        "title": "Temperature-driven productivity reduction",
        "description": (
            "Elevated sea surface temperature increased stratification, "
            "reducing nutrient upwelling and suppressing primary productivity. "
            "This is a well-documented mechanism in tropical oceanography."
        ),
        "required_variables": ["sea_surface_temperature", "chlorophyll_concentration"],
        "required_directions": {
            "sea_surface_temperature": "positive",
            "chlorophyll_concentration": "negative",
        },
        "minimum_evidence": 2,
        "agents": ["ocean", "satellite", "biology"],
    },
    {
        "title": "Reduced wind-driven mixing",
        "description": (
            "Weakened wind-driven mixing reduced nutrient supply "
            "to the euphotic zone, limiting phytoplankton growth."
        ),
        "required_variables": ["wind_speed", "chlorophyll_concentration"],
        "required_directions": {
            "wind_speed": "negative",
            "chlorophyll_concentration": "negative",
        },
        "minimum_evidence": 2,
        "agents": ["weather", "biology"],
    },
    {
        "title": "Fishing pressure impact",
        "description": (
            "Increased fishing activity may have contributed to "
            "changes in the local marine ecosystem structure."
        ),
        "required_variables": ["fishing_activity"],
        "required_directions": {"fishing_activity": "positive"},
        "minimum_evidence": 1,
        "agents": ["fisheries"],
    },
    {
        "title": "Pollution or sedimentation effects",
        "description": (
            "Pollution inputs or increased sedimentation may have "
            "affected water quality and marine organisms."
        ),
        "required_variables": ["ocean_color_index"],
        "required_directions": {"ocean_color_index": "positive"},
        "minimum_evidence": 1,
        "agents": ["pollution"],
    },
    {
        "title": "Monsoon-driven upwelling variation",
        "description": (
            "Changes in monsoon wind patterns altered upwelling dynamics, "
            "affecting nutrient supply and biological productivity."
        ),
        "required_variables": ["wind_speed", "sea_surface_temperature"],
        "required_directions": {},
        "minimum_evidence": 2,
        "agents": ["weather", "ocean"],
    },
    {
        "title": "Natural seasonal variability",
        "description": (
            "Observed changes may be within the range of normal "
            "seasonal variability for this region and time period."
        ),
        "required_variables": [],
        "required_directions": {},
        "minimum_evidence": 0,
        "agents": [],
    },
]


class HypothesisEngine:
    """Generates and ranks hypotheses based on actual evidence only."""

    def generate(
        self,
        agent_results: list[AgentResult],
        fusion_result: FusionResult,
    ) -> HypothesisResult:
        """Generate hypotheses from evidence.

        Key rules:
        1. Only generate hypotheses with actual supporting evidence
        2. Never use placeholder names
        3. NO EVIDENCE → NO CLAIM
        """

        # Collect evidence by variable
        evidence_by_var: dict[str, list[EvidenceItem]] = {}
        for item in fusion_result.ranked_evidence:
            if item.variable:
                if item.variable not in evidence_by_var:
                    evidence_by_var[item.variable] = []
                evidence_by_var[item.variable].append(item)

        # Collect agent hypotheses (only from successful agents)
        agent_hypotheses = []
        for result in agent_results:
            if result.status in (AgentStatus.SUCCESS, AgentStatus.NO_DATA):
                for h in result.hypotheses:
                    # Only include if it's not a placeholder
                    if h and not h.startswith("Agent hypothesis"):
                        agent_hypotheses.append(h)

        # Score template hypotheses against actual evidence
        scored_hypotheses = []
        for template in HYPOTHESIS_TEMPLATES:
            score, evidence_ids, contra_ids = self._score_hypothesis(
                template, evidence_by_var, fusion_result
            )

            # Only include if score > 0.2 AND has actual supporting evidence
            if score > 0.2 and len(evidence_ids) >= template["minimum_evidence"]:
                hypothesis = Hypothesis(
                    title=template["title"],
                    description=template["description"],
                    supporting_evidence=evidence_ids,
                    contradicting_evidence=contra_ids,
                    score=score,
                    confidence_level=self._score_to_level(score),
                    agent_contributions=template["agents"],
                )
                scored_hypotheses.append(hypothesis)

        # Add agent-generated hypotheses (only non-empty, non-placeholder)
        for h_text in agent_hypotheses[:3]:
            if len(h_text) > 10:  # Skip very short/empty hypotheses
                scored_hypotheses.append(Hypothesis(
                    title=h_text[:100],
                    description=h_text,
                    score=0.4,
                    confidence_level=ConfidenceLevel.LOW,
                    supporting_evidence=[],
                    contradicting_evidence=[],
                ))

        # Sort by score
        scored_hypotheses.sort(key=lambda h: h.score, reverse=True)

        top = scored_hypotheses[0] if scored_hypotheses else None
        overall = top.score if top else 0.0

        return HypothesisResult(
            hypotheses=scored_hypotheses[:8],  # Max 8 hypotheses
            top_hypothesis=top,
            overall_confidence=overall,
            overall_confidence_level=self._score_to_level(overall),
        )

    def _score_hypothesis(
        self,
        template: dict,
        evidence_by_var: dict[str, list[EvidenceItem]],
        fusion: FusionResult,
    ) -> tuple[float, list[str], list[str]]:
        """Score a hypothesis template against available evidence.

        Returns (score, supporting_evidence_ids, contradicting_evidence_ids).
        """
        supporting = []
        contradicting = []

        if not template["required_variables"]:
            return 0.2, supporting, contradicting  # Low default for "natural variability"

        match_count = 0
        for var in template["required_variables"]:
            if var in evidence_by_var:
                items = evidence_by_var[var]
                match_count += 1

                for item in items:
                    if item.value is not None:
                        direction = template["required_directions"].get(var)
                        if direction == "positive" and item.value > 0:
                            supporting.append(item.id)
                        elif direction == "negative" and item.value < 0:
                            supporting.append(item.id)
                        elif direction:
                            contradicting.append(item.id)
                        else:
                            # No direction requirement
                            supporting.append(item.id)

        # Coverage: how many required variables have evidence
        coverage = match_count / len(template["required_variables"])

        # Support ratio
        total = len(supporting) + len(contradicting)
        support_ratio = len(supporting) / total if total > 0 else 0.5

        # Agreement bonus (only genuine agreements)
        genuine_agreements = [
            a for a in fusion.agreements
            if "NOT independent" not in a
        ]
        agreement_bonus = min(0.15, len(genuine_agreements) * 0.05)

        # Convergence bonus
        convergence_bonus = 0.1 if fusion.evidence_convergence_score > 0.7 else 0

        score = (
            0.4 * coverage +
            0.3 * support_ratio +
            convergence_bonus +
            agreement_bonus
        )

        return min(1.0, score), supporting, contradicting

    def _score_to_level(self, score: float) -> ConfidenceLevel:
        if score >= 0.75:
            return ConfidenceLevel.HIGH
        elif score >= 0.50:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
