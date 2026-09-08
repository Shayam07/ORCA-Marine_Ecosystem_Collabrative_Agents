"""ORCA Biology Agent — Interprets biological/ecological indicators.

Uses cautious scientific language. Never makes unsupported causal claims.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType
from models.observation import EvidenceType, Observation


class BiologyAgent(BaseMarineAgent):
    """Interprets ecological indicators from available data.

    Uses SST, chlorophyll, and environmental variables as proxies
    for ecological conditions.
    """

    def __init__(self):
        super().__init__(AgentType.BIOLOGY)

    ECOLOGICAL_VARIABLES = [
        "chlorophyll_concentration",
        "sea_surface_temperature",
        "ocean_color_index",
    ]

    async def analyze(self, task: AgentTask):
        variables = task.variables or self.ECOLOGICAL_VARIABLES

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

        # Analyze chlorophyll as primary productivity proxy
        chla_obs = by_var.get("chlorophyll_concentration", [])
        sst_obs = by_var.get("sea_surface_temperature", [])

        chla_mean = statistics.mean([o.value for o in chla_obs]) if chla_obs else None
        sst_mean = statistics.mean([o.value for o in sst_obs]) if sst_obs else None

        if chla_mean is not None:
            # Ecological interpretation
            if chla_mean < 0.5:
                finding = AgentFinding(
                    variable="ecological_status",
                    description=(
                        f"Low chlorophyll ({chla_mean:.2f} mg/m³) suggests "
                        "reduced primary productivity. The observed reduction "
                        "in chlorophyll is consistent with reduced primary "
                        "productivity, although additional biological "
                        "observations would be required to confirm "
                        "population-level effects."
                    ),
                    value=chla_mean,
                    unit="mg/m3",
                    evidence_type=EvidenceType.MODEL_INFERENCE,
                    supporting_evidence=chla_obs[:10],
                )
                findings.append(finding)
                hypotheses.append(
                    "Reduced primary productivity indicated by low chlorophyll"
                )

            elif chla_mean > 5.0:
                finding = AgentFinding(
                    variable="ecological_status",
                    description=(
                        f"High chlorophyll ({chla_mean:.2f} mg/m³) suggests "
                        "active phytoplankton growth, potentially indicating "
                        "nutrient availability or upwelling-driven productivity."
                    ),
                    value=chla_mean,
                    unit="mg/m3",
                    evidence_type=EvidenceType.MODEL_INFERENCE,
                    supporting_evidence=chla_obs[:10],
                )
                findings.append(finding)

        # Temperature-biology interaction
        if chla_mean is not None and sst_mean is not None:
            if sst_mean > 29.0 and chla_mean < 1.0:
                finding = AgentFinding(
                    variable="thermal_productivity_interaction",
                    description=(
                        f"Elevated SST ({sst_mean:.1f}°C) combined with "
                        f"low chlorophyll ({chla_mean:.2f} mg/m³) is "
                        "consistent with thermal stratification reducing "
                        "nutrient supply to the euphotic zone."
                    ),
                    value=round(sst_mean - 27.3, 2),  # anomaly
                    unit="degC anomaly",
                    evidence_type=EvidenceType.MODEL_INFERENCE,
                    supporting_evidence=(chla_obs + sst_obs)[:15],
                )
                findings.append(finding)
                hypotheses.append(
                    "Thermal stratification may be suppressing nutrient mixing"
                )

        # Temporal biological trend
        if chla_obs and len(chla_obs) >= 5:
            sorted_obs = sorted(chla_obs, key=lambda o: o.timestamp)
            first_quarter = [o.value for o in sorted_obs[:len(sorted_obs)//4]]
            last_quarter = [o.value for o in sorted_obs[-len(sorted_obs)//4:]]
            bio_trend = statistics.mean(last_quarter) - statistics.mean(first_quarter)

            if abs(bio_trend) > 0.2:
                direction = "declining" if bio_trend < 0 else "increasing"
                finding = AgentFinding(
                    variable="biological_trend",
                    description=(
                        f"Chlorophyll trend: {direction} "
                        f"({bio_trend:+.2f} mg/m³ over analysis period)"
                    ),
                    value=round(bio_trend, 3),
                    unit="mg/m3/period",
                    evidence_type=EvidenceType.DERIVED_METRIC,
                )
                findings.append(finding)

        avg_quality = (
            statistics.mean([o.quality for o in evidence])
            if evidence else 0.0
        )
        confidence = self._compute_basic_confidence(
            num_evidence=len(evidence),
            avg_quality=avg_quality,
            num_findings=len(findings),
        )
        # Biology agent is more conservative with confidence
        confidence = round(confidence * 0.8, 3)

        return findings, evidence, hypotheses, confidence
