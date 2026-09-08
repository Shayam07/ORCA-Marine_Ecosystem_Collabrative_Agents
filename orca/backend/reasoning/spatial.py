"""ORCA Spatial Reasoning Engine — Compares regions and identifies spatial patterns."""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict

from models.agent import AgentResult

logger = logging.getLogger("orca.reasoning.spatial")


class SpatialReasoningEngine:
    """Compares selected region with neighboring and historical regions.

    Uses PostGIS for geographic operations in production.
    For MVP, uses in-memory spatial analysis.
    """

    def analyze(
        self,
        agent_results: list[AgentResult],
        bbox: list[float],
    ) -> list[str]:
        """Analyze spatial relationships in the evidence."""

        # Collect all observations with locations
        all_obs = []
        for result in agent_results:
            all_obs.extend(result.evidence)

        if not all_obs:
            return []

        relationships = []

        # Group by variable and spatial bins
        by_var = defaultdict(list)
        for obs in all_obs:
            by_var[obs.variable].append(obs)

        # Analyze spatial patterns
        for var_name, obs_list in by_var.items():
            if len(obs_list) < 5:
                continue

            # Create spatial bins
            lat_bins = defaultdict(list)
            for obs in obs_list:
                lat_bin = round(obs.latitude * 2) / 2  # 0.5 degree
                lat_bins[lat_bin].append(obs.value)

            if len(lat_bins) >= 2:
                bin_means = {k: statistics.mean(v) for k, v in lat_bins.items()}
                overall_mean = statistics.mean(list(bin_means.values()))

                if overall_mean != 0:
                    spatial_cv = statistics.stdev(bin_means.values()) / abs(overall_mean)

                    if spatial_cv > 0.2:
                        max_bin = max(bin_means.items(), key=lambda x: x[1])
                        min_bin = min(bin_means.items(), key=lambda x: x[1])
                        relationships.append(
                            f"Notable spatial gradient in {var_name}: "
                            f"higher values at {max_bin[0]:.1f}°N "
                            f"({max_bin[1]:.2f}) vs {min_bin[0]:.1f}°N "
                            f"({min_bin[1]:.2f})"
                        )

        # Check if anomaly is local or widespread
        anomaly_vars = set()
        for result in agent_results:
            for finding in result.findings:
                if finding.anomaly_detected:
                    anomaly_vars.add(finding.variable)

        if anomaly_vars:
            # Count observations inside vs outside bbox center
            center_lat = (bbox[1] + bbox[3]) / 2
            center_lon = (bbox[0] + bbox[2]) / 2

            inner, outer = 0, 0
            for obs in all_obs:
                if obs.variable in anomaly_vars:
                    dist = ((obs.latitude - center_lat) ** 2 + (obs.longitude - center_lon) ** 2) ** 0.5
                    if dist < 1.0:
                        inner += 1
                    else:
                        outer += 1

            if inner > 0 and outer > 0:
                ratio = inner / (inner + outer)
                if ratio > 0.7:
                    relationships.append(
                        "Anomaly appears concentrated in the selected region"
                    )
                elif ratio < 0.3:
                    relationships.append(
                        "Anomaly appears to extend beyond the selected region"
                    )
                else:
                    relationships.append(
                        "Anomaly is distributed across the selected and surrounding regions"
                    )

        return relationships
