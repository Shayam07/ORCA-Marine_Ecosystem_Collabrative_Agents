"""ORCA Pollution Agent — Analyzes pollution indicators.

Never claims pollution caused an event without sufficient evidence.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType
from models.observation import EvidenceType, Observation


class PollutionAgent(BaseMarineAgent):
    """Analyzes available pollution indicators.

    Uses turbidity, sediment, ocean-color anomalies, proximity
    to coastal/industrial areas as proxies.
    """

    def __init__(self):
        super().__init__(AgentType.POLLUTION)

    POLLUTION_VARIABLES = [
        "ocean_color_index",
        "chlorophyll_concentration",  # for turbidity proxy
    ]

    async def analyze(self, task: AgentTask):
        variables = task.variables or self.POLLUTION_VARIABLES

        batch = await self.data_service.get_observations(
            bbox=task.bbox,
            start_date=task.start_date,
            end_date=task.end_date,
            variables=variables,
        )

        evidence = batch.observations
        findings = []
        hypotheses = []

        by_var: dict[str, list[Observation]] = defaultdict(list)
        for obs in evidence:
            by_var[obs.variable].append(obs)

        # Check for ocean color anomalies (turbidity proxy)
        color_obs = by_var.get("ocean_color_index", [])
        if color_obs:
            values = [o.value for o in color_obs]
            mean_val = statistics.mean(values)

            if mean_val > 0.7:
                finding = AgentFinding(
                    variable="turbidity_proxy",
                    description=(
                        f"Elevated ocean color index ({mean_val:.2f}) may indicate "
                        "increased turbidity. This could be associated with sediment "
                        "runoff, phytoplankton blooms, or other processes. "
                        "Pollution is a possible contributing hypothesis with "
                        "medium confidence."
                    ),
                    value=mean_val,
                    unit="index",
                    evidence_type=EvidenceType.MODEL_INFERENCE,
                    supporting_evidence=color_obs[:10],
                )
                findings.append(finding)
                hypotheses.append(
                    "Elevated turbidity may indicate sediment runoff or "
                    "other water quality changes"
                )
            else:
                findings.append(AgentFinding(
                    variable="turbidity_proxy",
                    description=f"Ocean color index within normal range ({mean_val:.2f})",
                    value=mean_val,
                    unit="index",
                    evidence_type=EvidenceType.OBSERVATION,
                ))

        # Note: in a real system, we'd check proximity to industrial
        # outflows, river discharge data, etc.
        findings.append(AgentFinding(
            variable="pollution_data_availability",
            description=(
                "Direct pollution measurements (heavy metals, plastics, "
                "chemical contaminants) were not available for this region "
                "and time period. Pollution assessment is based on indirect "
                "indicators only."
            ),
            evidence_type=EvidenceType.MODEL_INFERENCE,
        ))

        avg_quality = (
            statistics.mean([o.quality for o in evidence])
            if evidence else 0.0
        )
        confidence = self._compute_basic_confidence(
            num_evidence=len(evidence),
            avg_quality=avg_quality,
            num_findings=len(findings),
        )
        # Pollution agent is very conservative
        confidence = round(confidence * 0.5, 3)

        return findings, evidence, hypotheses, confidence
