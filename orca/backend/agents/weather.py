"""ORCA Weather Agent — Analyzes atmospheric/weather variables."""

from __future__ import annotations

import statistics
from collections import defaultdict

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType
from models.observation import EvidenceType, Observation


class WeatherAgent(BaseMarineAgent):
    """Analyzes weather and atmospheric conditions."""

    def __init__(self):
        super().__init__(AgentType.WEATHER)

    WEATHER_VARIABLES = [
        "wind_speed",
        "wind_direction",
    ]

    BASELINES = {
        "wind_speed": {"mean": 8.0, "std": 3.0},
        "wind_direction": {"mean": 225.0, "std": 60.0},
    }

    async def analyze(self, task: AgentTask):
        variables = task.variables or self.WEATHER_VARIABLES
        variables = [v for v in variables if v in self.WEATHER_VARIABLES]

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
            if var_name == "wind_direction":
                continue  # handle separately
            values = [o.value for o in obs_list]
            if not values:
                continue

            mean_val = statistics.mean(values)
            baseline = self.BASELINES.get(var_name)

            finding = AgentFinding(
                variable=var_name,
                description=f"Mean {var_name}: {mean_val:.2f}",
                value=round(mean_val, 3),
                unit=obs_list[0].unit,
                evidence_type=EvidenceType.OBSERVATION,
                supporting_evidence=obs_list[:20],
            )

            if baseline:
                anomaly = mean_val - baseline["mean"]
                pct_change = (anomaly / baseline["mean"]) * 100

                finding.description = (
                    f"{var_name}: {mean_val:.2f} "
                    f"(baseline: {baseline['mean']:.2f}, "
                    f"anomaly: {pct_change:+.1f}%)"
                )

                if var_name == "wind_speed" and anomaly < -2.0:
                    finding.anomaly_detected = True
                    finding.anomaly_severity = "moderate" if abs(pct_change) > 20 else "minor"
                    hypotheses.append(
                        f"Reduced wind speed ({pct_change:+.0f}%) may decrease "
                        "ocean mixing and nutrient upwelling"
                    )
                elif var_name == "wind_speed" and anomaly > 3.0:
                    finding.anomaly_detected = True
                    finding.anomaly_severity = "moderate"
                    hypotheses.append(
                        "Elevated wind speeds may increase mixing and affect sea surface conditions"
                    )

            findings.append(finding)

        # Wind analysis
        wind_obs = by_var.get("wind_speed", [])
        if wind_obs:
            wind_vals = [o.value for o in wind_obs]
            mean_wind = statistics.mean(wind_vals)
            baseline_wind = self.BASELINES["wind_speed"]["mean"]

            if mean_wind < baseline_wind * 0.75:
                findings.append(AgentFinding(
                    variable="wind_mixing_impact",
                    description=(
                        f"Reduced wind ({mean_wind:.1f} m/s vs {baseline_wind:.1f} m/s baseline) "
                        "may reduce vertical mixing in the water column"
                    ),
                    value=round(mean_wind - baseline_wind, 2),
                    unit="m/s anomaly",
                    evidence_type=EvidenceType.MODEL_INFERENCE,
                ))

        # Dominant wind direction
        dir_obs = by_var.get("wind_direction", [])
        if dir_obs:
            # Circular mean
            import math
            sin_sum = sum(math.sin(math.radians(o.value)) for o in dir_obs)
            cos_sum = sum(math.cos(math.radians(o.value)) for o in dir_obs)
            dominant_dir = math.degrees(math.atan2(sin_sum, cos_sum)) % 360

            dir_names = {
                (337.5, 360): "N", (0, 22.5): "N", (22.5, 67.5): "NE",
                (67.5, 112.5): "E", (112.5, 157.5): "SE",
                (157.5, 202.5): "S", (202.5, 247.5): "SW",
                (247.5, 292.5): "W", (292.5, 337.5): "NW",
            }
            dir_label = "Unknown"
            for (lo, hi), label in dir_names.items():
                if lo <= dominant_dir <= hi:
                    dir_label = label
                    break

            findings.append(AgentFinding(
                variable="dominant_wind_direction",
                description=f"Dominant wind direction: {dir_label} ({dominant_dir:.0f}°)",
                value=round(dominant_dir, 1),
                unit="degrees",
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
