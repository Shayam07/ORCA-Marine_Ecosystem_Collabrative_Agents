"""ORCA Evidence Deduplicator — Prevents false cross-agent agreement.

Two observations from the same underlying dataset must not count as
independent supporting evidence. Cross-agent agreement is only meaningful
when agents provide genuinely independent evidence.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from models.observation import Observation

logger = logging.getLogger("orca.reasoning.deduplication")


class EvidenceDeduplicator:
    """Removes duplicate evidence from overlapping data sources.

    Deduplication key: (dataset, variable, rounded_lat, rounded_lon, date)
    """

    def __init__(self, spatial_tolerance: float = 0.05, temporal_tolerance_hours: int = 6):
        """
        Args:
            spatial_tolerance: Degrees of tolerance for spatial deduplication
            temporal_tolerance_hours: Hours of tolerance for temporal deduplication
        """
        self.spatial_tolerance = spatial_tolerance
        self.temporal_tolerance_hours = temporal_tolerance_hours

    def _make_key(self, obs: Observation) -> tuple:
        """Create a deduplication key for an observation."""
        lat_rounded = round(obs.latitude / self.spatial_tolerance) * self.spatial_tolerance
        lon_rounded = round(obs.longitude / self.spatial_tolerance) * self.spatial_tolerance
        date_key = obs.timestamp.strftime("%Y-%m-%d-%H")
        return (obs.dataset, obs.variable, lat_rounded, lon_rounded, date_key)

    def deduplicate(self, observations: list[Observation]) -> list[Observation]:
        """Remove duplicate observations.

        When two observations have the same key, keep the one with higher quality.
        """
        by_key: dict[tuple, list[Observation]] = defaultdict(list)

        for obs in observations:
            key = self._make_key(obs)
            by_key[key].append(obs)

        deduplicated = []
        duplicates_removed = 0

        for key, obs_list in by_key.items():
            if len(obs_list) == 1:
                deduplicated.append(obs_list[0])
            else:
                # Keep highest quality observation
                best = max(obs_list, key=lambda o: o.quality)
                deduplicated.append(best)
                duplicates_removed += len(obs_list) - 1

        if duplicates_removed > 0:
            logger.info(
                f"Deduplication: removed {duplicates_removed} duplicate observations "
                f"({len(observations)} → {len(deduplicated)})"
            )

        return deduplicated

    def compute_independent_evidence_count(
        self,
        observations: list[Observation],
    ) -> dict[str, int]:
        """Count genuinely independent evidence per variable.

        Returns dict of variable → independent evidence count.
        """
        by_var: dict[str, list[Observation]] = defaultdict(list)
        for obs in observations:
            by_var[obs.variable].append(obs)

        independent_counts = {}
        for var, obs_list in by_var.items():
            deduplicated = self.deduplicate(obs_list)
            independent_counts[var] = len(deduplicated)

        return independent_counts

    def check_cross_agent_agreement(
        self,
        observations_by_agent: dict[str, list[Observation]],
    ) -> list[dict[str, Any]]:
        """Check for genuine cross-agent agreement.

        Only counts as agreement if agents provide observations from
        DIFFERENT datasets.
        """
        agreements = []

        # Group all observations by variable
        var_agents: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

        for agent_name, obs_list in observations_by_agent.items():
            for obs in obs_list:
                var_agents[obs.variable][agent_name].add(obs.dataset)

        for variable, agent_datasets in var_agents.items():
            if len(agent_datasets) < 2:
                continue

            # Check if agents use different datasets
            all_datasets = set()
            agent_list = []
            for agent, datasets in agent_datasets.items():
                all_datasets.update(datasets)
                agent_list.append(agent)

            if len(all_datasets) >= 2:
                # Agents use genuinely different data sources
                agreements.append({
                    "variable": variable,
                    "agents": agent_list,
                    "datasets": sorted(all_datasets),
                    "genuinely_independent": True,
                    "description": (
                        f"Agents {', '.join(agent_list)} independently confirm "
                        f"anomaly in {variable} using different datasets: "
                        f"{', '.join(sorted(all_datasets))}"
                    ),
                })
            else:
                # Agents use the same dataset — NOT independent
                agreements.append({
                    "variable": variable,
                    "agents": agent_list,
                    "datasets": sorted(all_datasets),
                    "genuinely_independent": False,
                    "description": (
                        f"Agents {', '.join(agent_list)} observe {variable} "
                        f"but share the same dataset ({', '.join(all_datasets)}). "
                        f"This is NOT independent confirmation."
                    ),
                })

        return agreements
