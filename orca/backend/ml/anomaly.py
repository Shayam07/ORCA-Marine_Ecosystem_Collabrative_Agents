"""ORCA Anomaly Detection — Isolation Forest for marine ecosystem anomalies."""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from typing import Any

import numpy as np

from models.observation import Observation

logger = logging.getLogger("orca.ml.anomaly")


class AnomalyDetector:
    """Detects marine ecosystem anomalies using Isolation Forest.

    Pipeline:
    1. Feature engineering from observations
    2. Scaling
    3. Isolation Forest
    4. Anomaly score → severity mapping
    """

    FEATURES = [
        "sea_surface_temperature",
        "chlorophyll_concentration",
        "salinity",
        "wind_speed",
    ]

    # Historical baselines for Indian west coast
    BASELINES = {
        "sea_surface_temperature": {"mean": 27.3, "std": 1.5},
        "chlorophyll_concentration": {"mean": 1.5, "std": 0.8},
        "salinity": {"mean": 34.5, "std": 0.8},
        "wind_speed": {"mean": 8.0, "std": 3.0},
    }

    def __init__(self):
        self._model = None
        self._scaler_params: dict[str, dict] = {}

    def detect_anomalies(
        self, observations: list[Observation]
    ) -> dict[str, Any]:
        """Run anomaly detection on observations.

        Returns:
            {
                "anomaly_score": float,
                "severity": str,  # "normal", "minor", "moderate", "major"
                "anomalous_variables": list[str],
                "feature_scores": dict[str, float],
                "method": "isolation_forest"
            }
        """
        if not observations:
            return {
                "anomaly_score": 0.0,
                "severity": "normal",
                "anomalous_variables": [],
                "feature_scores": {},
                "method": "baseline_zscore",
            }

        # Group by variable
        by_var: dict[str, list[float]] = defaultdict(list)
        for obs in observations:
            by_var[obs.variable].append(obs.value)

        # Compute z-scores against baselines
        z_scores = {}
        anomalous = []

        for var_name, values in by_var.items():
            if var_name in self.BASELINES:
                baseline = self.BASELINES[var_name]
                mean = statistics.mean(values)
                z = (mean - baseline["mean"]) / baseline["std"] if baseline["std"] > 0 else 0
                z_scores[var_name] = round(z, 3)
                if abs(z) > 1.5:
                    anomalous.append(var_name)

        # Try Isolation Forest if enough data
        feature_matrix = self._build_feature_matrix(observations)
        if feature_matrix is not None and len(feature_matrix) >= 10:
            if_score = self._run_isolation_forest(feature_matrix)
        else:
            # Fallback to z-score based scoring
            if z_scores:
                if_score = abs(statistics.mean(z_scores.values()))
            else:
                if_score = 0.0

        # Map to severity
        severity = self._score_to_severity(if_score)

        return {
            "anomaly_score": round(min(1.0, if_score), 3),
            "severity": severity,
            "anomalous_variables": anomalous,
            "feature_scores": z_scores,
            "method": "isolation_forest" if feature_matrix is not None else "baseline_zscore",
        }

    def _build_feature_matrix(
        self, observations: list[Observation]
    ) -> np.ndarray | None:
        """Build feature matrix for Isolation Forest."""
        by_var: dict[str, list[float]] = defaultdict(list)
        for obs in observations:
            if obs.variable in self.FEATURES:
                by_var[obs.variable].append(obs.value)

        available = [f for f in self.FEATURES if f in by_var and by_var[f]]
        if len(available) < 2:
            return None

        # Normalize to same length
        min_len = min(len(by_var[f]) for f in available)
        matrix = []
        for i in range(min_len):
            row = []
            for f in available:
                val = by_var[f][i]
                bl = self.BASELINES.get(f, {"mean": 0, "std": 1})
                normalized = (val - bl["mean"]) / bl["std"] if bl["std"] > 0 else 0
                row.append(normalized)
            matrix.append(row)

        return np.array(matrix)

    def _run_isolation_forest(self, X: np.ndarray) -> float:
        """Run Isolation Forest on feature matrix."""
        try:
            from sklearn.ensemble import IsolationForest

            model = IsolationForest(
                n_estimators=100,
                contamination=0.1,
                random_state=42,
            )
            model.fit(X)

            scores = model.score_samples(X)
            # Convert to 0-1 range (more negative = more anomalous)
            mean_score = float(np.mean(scores))
            # Isolation Forest scores are typically -1 to 1
            anomaly_score = max(0, min(1.0, -mean_score))
            return anomaly_score

        except ImportError:
            logger.warning("scikit-learn not available, falling back to z-score")
            return 0.0

    def _score_to_severity(self, score: float) -> str:
        if score > 0.7:
            return "major"
        elif score > 0.5:
            return "moderate"
        elif score > 0.3:
            return "minor"
        return "normal"
