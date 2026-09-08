"""ORCA Fisheries Agent — Analyzes fishing activity and vessel data.

Clearly distinguishes vessel presence from estimated fishing activity.
"""

from __future__ import annotations

import statistics

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType
from models.observation import EvidenceType


class FisheriesAgent(BaseMarineAgent):
    """Analyzes fishing activity and vessel presence data."""

    def __init__(self):
        super().__init__(AgentType.FISHERIES)

    FISHERIES_VARIABLES = ["fishing_activity"]

    BASELINES = {
        "fishing_activity": {"mean": 0.8, "std": 0.4},
    }

    async def analyze(self, task: AgentTask):
        variables = task.variables or self.FISHERIES_VARIABLES

        batch = await self.data_service.get_observations(
            bbox=task.bbox,
            start_date=task.start_date,
            end_date=task.end_date,
            variables=variables,
        )

        evidence = batch.observations
        findings = []
        hypotheses = []

        fishing_obs = [o for o in evidence if o.variable == "fishing_activity"]

        if fishing_obs:
            values = [o.value for o in fishing_obs]
            mean_val = statistics.mean(values)
            baseline = self.BASELINES["fishing_activity"]

            anomaly = mean_val - baseline["mean"]
            pct_change = (anomaly / baseline["mean"]) * 100

            finding = AgentFinding(
                variable="fishing_activity",
                description=(
                    f"Vessel activity density: {mean_val:.2f} events/km² "
                    f"(baseline: {baseline['mean']:.2f}, "
                    f"change: {pct_change:+.1f}%)"
                ),
                value=round(mean_val, 3),
                unit="events/km2",
                evidence_type=EvidenceType.OBSERVATION,
                supporting_evidence=fishing_obs[:20],
            )

            if abs(pct_change) > 20:
                finding.anomaly_detected = True
                finding.anomaly_severity = "moderate" if abs(pct_change) < 40 else "major"

                direction = "increase" if anomaly > 0 else "decrease"
                hypotheses.append(
                    f"Fishing activity {direction} of {abs(pct_change):.0f}% "
                    "may have contributed to observed ecological changes"
                )

            findings.append(finding)

            # Crowding level classification (LOW, MODERATE, HIGH)
            crowding_level = "LOW"
            if mean_val > 1.2:
                crowding_level = "HIGH"
            elif mean_val > 0.6:
                crowding_level = "MODERATE"

            findings.append(AgentFinding(
                variable="crowding_level",
                description=(
                    f"Fleet crowding level: {crowding_level} ({mean_val:.2f} vessels/km²). "
                    + ("High fleet pressure: gear congestion expected, consider less crowded alternatives." if crowding_level == "HIGH"
                       else "Moderate fleet concentration in operational sector." if crowding_level == "MODERATE"
                       else "Low fleet pressure: open water operations favorable.")
                ),
                value=round(mean_val, 2),
                unit="vessels/km2",
                evidence_type=EvidenceType.DERIVED_METRIC,
            ))

            # Important distinction
            findings.append(AgentFinding(
                variable="vessel_fishing_distinction",
                description=(
                    "Note: Vessel activity density does not confirm fishing activity. "
                    "Vessels may be transiting, anchored, or engaged in non-fishing "
                    "activities. Estimated fishing activity is based on movement "
                    "patterns and should be treated as approximate."
                ),
                evidence_type=EvidenceType.MODEL_INFERENCE,
            ))

            # Mandatory Probabilistic PFZ Disclaimer finding
            findings.append(AgentFinding(
                variable="probabilistic_pfz_advisory",
                description=(
                    "This is a Potential Fishing Zone based on currently available marine conditions. "
                    "Based on SST, chlorophyll and available oceanographic parameters. "
                    "This does not guarantee fish presence or catch."
                ),
                evidence_type=EvidenceType.MODEL_INFERENCE,
            ))

        # Spatial fishing concentration
        if fishing_obs:
            from collections import defaultdict as dd
            lat_concentration = dd(list)
            for obs in fishing_obs:
                lat_bin = round(obs.latitude * 2) / 2
                lat_concentration[lat_bin].append(obs.value)

            if lat_concentration:
                max_lat = max(lat_concentration.items(), key=lambda x: sum(x[1])/len(x[1]))
                findings.append(AgentFinding(
                    variable="fishing_spatial_concentration",
                    description=(
                        f"Highest fishing activity concentration at "
                        f"~{max_lat[0]:.1f}°N (mean: {statistics.mean(max_lat[1]):.2f} events/km²)"
                    ),
                    value=round(statistics.mean(max_lat[1]), 3),
                    unit="events/km2",
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
