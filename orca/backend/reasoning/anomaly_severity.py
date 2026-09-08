"""ORCA Anomaly Severity Engine — Variable-specific anomaly classification.

Uses standardized anomalies, variable-specific thresholds, and
documented methodology instead of averaging unrelated percentages.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any, Optional
from pydantic import BaseModel, Field

from models.observation import Observation

logger = logging.getLogger("orca.reasoning.anomaly_severity")


class VariableAnomaly(BaseModel):
    """Anomaly assessment for a single variable."""
    variable: str
    display_name: str
    current_value: float
    baseline_value: float
    unit: str
    raw_anomaly: float
    standardized_anomaly: float  # z-score
    severity: str  # "normal", "minor", "moderate", "major", "extreme"
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    data_points: int = 0
    methodology: str = ""


class AnomalyAssessment(BaseModel):
    """Complete anomaly assessment for a region."""
    variables: list[VariableAnomaly] = Field(default_factory=list)
    overall_severity: str = "normal"
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    num_anomalies: int = 0
    data_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    methodology: str = (
        "Each variable is compared against a historical baseline. "
        "Severity is determined by standardized anomaly (z-score) with "
        "variable-specific thresholds."
    )


# ── Variable-specific baselines and thresholds ──────────────────────

VARIABLE_CONFIGS: dict[str, dict[str, Any]] = {
    "sea_surface_temperature": {
        "display_name": "Sea Surface Temperature",
        "unit": "°C",
        "baseline_mean": 27.3,
        "baseline_std": 1.5,
        # Severity thresholds (z-score)
        "thresholds": {
            "minor": 1.0,
            "moderate": 1.5,
            "major": 2.0,
            "extreme": 3.0,
        },
    },
    "chlorophyll_concentration": {
        "display_name": "Chlorophyll Concentration",
        "unit": "mg/m³",
        "baseline_mean": 1.5,
        "baseline_std": 0.8,
        "thresholds": {
            "minor": 1.0,
            "moderate": 1.5,
            "major": 2.0,
            "extreme": 3.0,
        },
    },
    "salinity": {
        "display_name": "Salinity",
        "unit": "PSU",
        "baseline_mean": 34.5,
        "baseline_std": 0.8,
        "thresholds": {
            "minor": 1.0,
            "moderate": 1.5,
            "major": 2.0,
            "extreme": 3.0,
        },
    },
    "wind_speed": {
        "display_name": "Wind Speed",
        "unit": "m/s",
        "baseline_mean": 7.0,
        "baseline_std": 3.0,
        "thresholds": {
            "minor": 1.0,
            "moderate": 1.5,
            "major": 2.0,
            "extreme": 3.0,
        },
    },
    "sea_surface_current_u": {
        "display_name": "Ocean Current (U)",
        "unit": "m/s",
        "baseline_mean": 0.05,
        "baseline_std": 0.2,
        "thresholds": {
            "minor": 1.0,
            "moderate": 1.5,
            "major": 2.0,
            "extreme": 3.0,
        },
    },
}


class AnomalySeverityEngine:
    """Calculates anomaly severity using variable-specific methodology."""

    def assess_variable(
        self,
        variable: str,
        observations: list[Observation],
    ) -> Optional[VariableAnomaly]:
        """Assess anomaly severity for a single variable."""
        config = VARIABLE_CONFIGS.get(variable)
        if not config:
            return None

        values = [o.value for o in observations if o.variable == variable]
        if not values:
            return None

        current_mean = statistics.mean(values)
        baseline_mean = config["baseline_mean"]
        baseline_std = config["baseline_std"]

        # Raw anomaly
        raw_anomaly = current_mean - baseline_mean

        # Standardized anomaly (z-score)
        if baseline_std > 0:
            standardized = raw_anomaly / baseline_std
        else:
            standardized = 0.0

        # Determine severity using variable-specific thresholds
        abs_z = abs(standardized)
        thresholds = config["thresholds"]

        if abs_z >= thresholds["extreme"]:
            severity = "extreme"
        elif abs_z >= thresholds["major"]:
            severity = "major"
        elif abs_z >= thresholds["moderate"]:
            severity = "moderate"
        elif abs_z >= thresholds["minor"]:
            severity = "minor"
        else:
            severity = "normal"

        # Percentage change
        pct_change = (raw_anomaly / baseline_mean * 100) if baseline_mean != 0 else 0

        # Direction
        direction = "increased" if raw_anomaly > 0 else "decreased"

        description = (
            f"{config['display_name']}: {current_mean:.2f} {config['unit']} "
            f"(baseline: {baseline_mean:.2f} {config['unit']}, "
            f"{direction} by {abs(pct_change):.1f}%, "
            f"z-score: {standardized:+.2f})"
        )

        # Confidence based on data quantity and quality
        data_confidence = min(1.0, len(values) / 10.0)
        quality_values = [o.quality for o in observations if o.variable == variable]
        quality_confidence = statistics.mean(quality_values) if quality_values else 0.5

        confidence = 0.5 * data_confidence + 0.5 * quality_confidence

        methodology = (
            f"Compared {len(values)} observations against baseline "
            f"(μ={baseline_mean}, σ={baseline_std}). "
            f"Standardized anomaly z={standardized:.2f} classified as {severity} "
            f"using threshold ≥{thresholds[severity]}."
        )

        return VariableAnomaly(
            variable=variable,
            display_name=config["display_name"],
            current_value=round(current_mean, 3),
            baseline_value=baseline_mean,
            unit=config["unit"],
            raw_anomaly=round(raw_anomaly, 3),
            standardized_anomaly=round(standardized, 3),
            severity=severity,
            description=description,
            confidence=round(confidence, 3),
            data_points=len(values),
            methodology=methodology,
        )

    def assess(
        self,
        observations: list[Observation],
        variables: list[str] | None = None,
    ) -> AnomalyAssessment:
        """Assess anomaly severity for all variables."""
        if variables is None:
            variables = list(set(o.variable for o in observations))

        variable_anomalies = []
        for var in variables:
            anomaly = self.assess_variable(var, observations)
            if anomaly:
                variable_anomalies.append(anomaly)

        # Overall severity: worst variable severity
        severity_order = {"normal": 0, "minor": 1, "moderate": 2, "major": 3, "extreme": 4}
        if variable_anomalies:
            worst = max(variable_anomalies, key=lambda a: severity_order.get(a.severity, 0))
            overall_severity = worst.severity
        else:
            overall_severity = "normal"

        # Overall score: mean of absolute z-scores, capped at 1.0
        if variable_anomalies:
            z_scores = [abs(a.standardized_anomaly) for a in variable_anomalies]
            overall_score = min(1.0, statistics.mean(z_scores) / 3.0)
        else:
            overall_score = 0.0

        num_anomalies = sum(1 for a in variable_anomalies if a.severity != "normal")

        # Data quality
        all_qualities = [o.quality for o in observations]
        data_quality = statistics.mean(all_qualities) if all_qualities else 0.0

        return AnomalyAssessment(
            variables=variable_anomalies,
            overall_severity=overall_severity,
            overall_score=round(overall_score, 3),
            num_anomalies=num_anomalies,
            data_quality=round(data_quality, 3),
        )
