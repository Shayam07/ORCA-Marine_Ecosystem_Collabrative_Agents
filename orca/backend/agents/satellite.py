"""ORCA Satellite Agent — Analyzes satellite-derived products.

Analyzes: chlorophyll, ocean color, satellite SST, spatial anomalies.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType
from models.observation import EvidenceType, Observation


class SatelliteAgent(BaseMarineAgent):
    """Analyzes satellite-derived ocean products."""

    def __init__(self):
        super().__init__(AgentType.SATELLITE)

    SATELLITE_VARIABLES = [
        "chlorophyll_concentration",
        "ocean_color_index",
        "sea_surface_temperature",
    ]

    BASELINES = {
        "chlorophyll_concentration": {"mean": 1.5, "std": 0.8},
        "ocean_color_index": {"mean": 0.4, "std": 0.15},
        "sea_surface_temperature": {"mean": 27.3, "std": 1.5},
    }

    async def analyze(self, task: AgentTask):
        variables = task.variables or self.SATELLITE_VARIABLES
        variables = [v for v in variables if v in self.SATELLITE_VARIABLES]

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

        for var_name, obs_list in by_var.items():
            values = [o.value for o in obs_list]
            if not values:
                continue

            mean_val = statistics.mean(values)
            baseline = self.BASELINES.get(var_name)

            finding = AgentFinding(
                variable=var_name,
                description=f"Satellite {var_name}: {mean_val:.2f}",
                value=round(mean_val, 3),
                unit=obs_list[0].unit,
                evidence_type=EvidenceType.OBSERVATION,
                supporting_evidence=obs_list[:20],
            )

            if baseline:
                anomaly = mean_val - baseline["mean"]
                pct_change = (anomaly / baseline["mean"]) * 100

                finding.description = (
                    f"Satellite {var_name}: {mean_val:.2f} "
                    f"(baseline: {baseline['mean']:.2f}, "
                    f"change: {pct_change:+.1f}%)"
                )
                finding.anomaly_detected = abs(pct_change) > 15

                if abs(pct_change) > 30:
                    finding.anomaly_severity = "major"
                elif abs(pct_change) > 20:
                    finding.anomaly_severity = "moderate"
                elif abs(pct_change) > 15:
                    finding.anomaly_severity = "minor"
                else:
                    finding.anomaly_severity = "normal"

                if var_name == "chlorophyll_concentration" and anomaly < -0.3:
                    hypotheses.append(
                        f"Chlorophyll decreased by {abs(pct_change):.0f}%, "
                        "consistent with reduced primary productivity"
                    )
                    finding.anomaly_detected = True

            findings.append(finding)

        # Spatial anomaly detection
        if by_var.get("chlorophyll_concentration"):
            chla_obs = by_var["chlorophyll_concentration"]
            lat_groups = defaultdict(list)
            for obs in chla_obs:
                lat_bin = round(obs.latitude * 2) / 2  # 0.5 degree bins
                lat_groups[lat_bin].append(obs.value)

            if len(lat_groups) > 1:
                lat_means = {k: statistics.mean(v) for k, v in lat_groups.items()}
                overall_mean = statistics.mean(list(lat_means.values()))
                spatial_cv = (
                    statistics.stdev(lat_means.values()) / overall_mean
                    if len(lat_means) > 1 and overall_mean > 0 else 0
                )

                if spatial_cv > 0.3:
                    findings.append(AgentFinding(
                        variable="chla_spatial_variability",
                        description=(
                            f"High spatial variability in chlorophyll "
                            f"(CV: {spatial_cv:.2f})"
                        ),
                        value=round(spatial_cv, 3),
                        evidence_type=EvidenceType.DERIVED_METRIC,
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

        return findings, evidence, hypotheses, confidence
