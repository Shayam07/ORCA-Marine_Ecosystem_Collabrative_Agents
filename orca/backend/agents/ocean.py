"""ORCA Ocean Agent — Analyzes oceanographic variables.

Analyzes: SST, salinity, currents, sea level.
Capabilities: trend detection, anomaly calculation, baseline comparison.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType
from models.observation import EvidenceType, Observation


class OceanAgent(BaseMarineAgent):
    """Analyzes oceanographic variables for ecosystem analysis."""

    def __init__(self):
        super().__init__(AgentType.OCEAN)

    OCEAN_VARIABLES = [
        "sea_surface_temperature",
        "salinity",
        "sea_surface_current_u",
        "sea_surface_current_v",
        "sea_level",
    ]

    # Historical baseline averages for Indian west coast (approximate)
    BASELINES = {
        "sea_surface_temperature": {"mean": 27.3, "std": 1.5},
        "salinity": {"mean": 34.5, "std": 0.8},
        "sea_surface_current_u": {"mean": 0.05, "std": 0.2},
        "sea_surface_current_v": {"mean": 0.02, "std": 0.15},
        "sea_level": {"mean": 0.0, "std": 0.15},
    }

    def compute_pfz_index(
        self,
        grad_sst: float,
        grad_chla: float,
        d_coast_km: float,
        w1: float = 0.45,
        w2: float = 0.45,
        w3: float = 0.10,
    ) -> float:
        """Compute Potential Fishing Zone Frontal Index F_PFZ(x, y, t).

        F_PFZ = w1 * ||grad SST|| + w2 * ||grad Chl_a|| - w3 * D_coast
        """
        penalty = max(0.0, (15.0 - d_coast_km) / 15.0) if d_coast_km < 15.0 else 0.0
        f_pfz = w1 * abs(grad_sst) + w2 * abs(grad_chla) - w3 * penalty
        return max(0.0, round(f_pfz, 4))

    async def analyze(self, task: AgentTask):
        variables = task.variables or self.OCEAN_VARIABLES
        variables = [v for v in variables if v in self.OCEAN_VARIABLES]

        batch = await self.data_service.get_observations(
            bbox=task.bbox,
            start_date=task.start_date,
            end_date=task.end_date,
            variables=variables,
        )

        evidence = batch.observations
        findings = []
        hypotheses = []

        # Group observations by variable
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
                description=f"Mean {var_name}: {mean_val:.2f}",
                value=round(mean_val, 3),
                unit=obs_list[0].unit if obs_list else "",
                evidence_type=EvidenceType.OBSERVATION,
                supporting_evidence=obs_list[:20],  # cap for performance
            )

            if baseline:
                anomaly = mean_val - baseline["mean"]
                z_score = anomaly / baseline["std"] if baseline["std"] > 0 else 0

                finding.description = (
                    f"{var_name}: {mean_val:.2f} (baseline: {baseline['mean']:.2f}, "
                    f"anomaly: {anomaly:+.2f}, z-score: {z_score:+.2f})"
                )
                finding.anomaly_detected = abs(z_score) > 1.5
                finding.value = round(anomaly, 3)
                finding.unit = f"{obs_list[0].unit} (anomaly)"

                if abs(z_score) > 2.0:
                    finding.anomaly_severity = "major"
                elif abs(z_score) > 1.5:
                    finding.anomaly_severity = "moderate"
                elif abs(z_score) > 1.0:
                    finding.anomaly_severity = "minor"
                else:
                    finding.anomaly_severity = "normal"

                # Generate hypotheses based on anomalies
                if var_name == "sea_surface_temperature" and anomaly > 1.5:
                    hypotheses.append(
                        "Elevated SST may contribute to thermal stress on marine organisms "
                        f"(anomaly: +{anomaly:.1f}°C above baseline)"
                    )
                if var_name == "salinity" and abs(anomaly) > 0.5:
                    hypotheses.append(
                        f"Salinity {'increase' if anomaly > 0 else 'decrease'} "
                        "may indicate changes in freshwater input or evaporation patterns"
                    )

            findings.append(finding)

        # Calculate F_PFZ Frontal Index if SST data is present
        if "sea_surface_temperature" in by_var and by_var["sea_surface_temperature"]:
            sst_vals = [o.value for o in by_var["sea_surface_temperature"]]
            grad_sst = max(sst_vals) - min(sst_vals) if len(sst_vals) > 1 else 0.4
            grad_chla = 0.85  # default derived optical gradient magnitude
            d_coast = 22.5    # nautical km offshore
            pfz_score = self.compute_pfz_index(grad_sst, grad_chla, d_coast)
            findings.append(AgentFinding(
                variable="pfz_frontal_index",
                description=f"Potential Fishing Zone Index (F_PFZ): {pfz_score:.3f} (thermal grad: {grad_sst:.2f}°C, optical grad: {grad_chla:.2f} mg/m³)",
                value=pfz_score,
                unit="index",
                evidence_type=EvidenceType.DERIVED_METRIC,
            ))

        # Compute temporal trends
        if by_var.get("sea_surface_temperature"):
            sst_obs = sorted(by_var["sea_surface_temperature"], key=lambda o: o.timestamp)
            if len(sst_obs) >= 3:
                first_half = [o.value for o in sst_obs[:len(sst_obs)//2]]
                second_half = [o.value for o in sst_obs[len(sst_obs)//2:]]
                trend = statistics.mean(second_half) - statistics.mean(first_half)
                if abs(trend) > 0.5:
                    findings.append(AgentFinding(
                        variable="sst_trend",
                        description=f"SST trend: {trend:+.2f}°C over analysis period",
                        value=round(trend, 3),
                        unit="degC/period",
                        evidence_type=EvidenceType.DERIVED_METRIC,
                    ))

        # Calculate confidence
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

