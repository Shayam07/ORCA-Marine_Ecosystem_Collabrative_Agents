"""ORCA Evidence Fusion Engine — Combines and ranks evidence from all agents.

Detects agreements, contradictions, and relationships.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from models.agent import AgentResult, AgentStatus
from models.evidence import (
    EvidenceItem,
    EvidenceStrength,
    FusionResult,
    TemporalRelationship,
)
from models.observation import EvidenceType

logger = logging.getLogger("orca.reasoning.fusion")


class EvidenceFusionEngine:
    """Combines evidence from multiple agents into a unified picture."""

    def fuse(self, agent_results: list[AgentResult]) -> FusionResult:
        """Fuse evidence from all agent results."""

        all_evidence = self._collect_evidence(agent_results)
        agreements = self._detect_agreements(all_evidence)
        contradictions = self._detect_contradictions(all_evidence)
        temporal = self._detect_temporal_relationships(all_evidence)
        spatial = self._detect_spatial_relationships(all_evidence)
        ranked = self._rank_evidence(all_evidence)

        convergence = self._compute_convergence_score(
            agreements, contradictions, ranked
        )

        result = FusionResult(
            agreements=agreements,
            contradictions=contradictions,
            temporal_relationships=temporal,
            spatial_relationships=spatial,
            ranked_evidence=ranked,
            evidence_convergence_score=convergence,
        )

        logger.info(
            f"Evidence fusion: {len(ranked)} evidence items, "
            f"{len(agreements)} agreements, {len(contradictions)} contradictions, "
            f"convergence: {convergence:.3f}"
        )

        return result

    def _collect_evidence(self, agent_results: list[AgentResult]) -> list[EvidenceItem]:
        """Convert agent findings and observations into EvidenceItems."""
        evidence_items = []

        for result in agent_results:
            if result.status not in (AgentStatus.SUCCESS, AgentStatus.NO_DATA):
                continue

            for finding in result.findings:
                item = EvidenceItem(
                    source=result.data_sources_used[0] if result.data_sources_used else "unknown",
                    dataset=finding.metadata.get("dataset", "mixed"),
                    variable=finding.variable,
                    value=finding.value,
                    unit=finding.unit,
                    agent=result.agent_type,
                    evidence_type=finding.evidence_type,
                    description=finding.description,
                    strength=self._assess_strength(finding),
                )
                evidence_items.append(item)

            # Add raw observations as evidence
            for obs in result.evidence[:10]:  # cap per agent
                item = EvidenceItem(
                    source=obs.source.value,
                    dataset=obs.dataset,
                    variable=obs.variable,
                    value=obs.value,
                    unit=obs.unit,
                    location={"lat": obs.latitude, "lon": obs.longitude},
                    timestamp=obs.timestamp,
                    quality=obs.quality,
                    agent=result.agent_type,
                    evidence_type=EvidenceType.OBSERVATION,
                    observations=[obs],
                )
                evidence_items.append(item)

        return evidence_items

    def _assess_strength(self, finding) -> EvidenceStrength:
        """Assess the strength of a finding."""
        if finding.anomaly_severity == "major":
            return EvidenceStrength.STRONG
        elif finding.anomaly_severity == "moderate":
            return EvidenceStrength.MODERATE
        elif finding.anomaly_severity == "minor":
            return EvidenceStrength.WEAK
        return EvidenceStrength.MODERATE

    def _detect_agreements(self, evidence: list[EvidenceItem]) -> list[str]:
        """Detect where multiple agents agree on the same phenomenon."""
        agreements = []

        # Group by variable
        by_var = defaultdict(list)
        for item in evidence:
            if item.variable:
                by_var[item.variable].append(item)

        for var_name, items in by_var.items():
            agents = set(item.agent for item in items)
            if len(agents) >= 2:
                anomalies = [i for i in items if i.strength in (
                    EvidenceStrength.STRONG, EvidenceStrength.MODERATE
                )]
                if anomalies:
                    agent_names = [a.value for a in agents]
                    agreements.append(
                        f"Multiple agents ({', '.join(agent_names)}) "
                        f"identify anomaly in {var_name}"
                    )

        # Check for cross-variable agreement
        anomaly_vars = set()
        for item in evidence:
            if item.strength in (EvidenceStrength.STRONG, EvidenceStrength.MODERATE):
                anomaly_vars.add(item.variable)

        if "sea_surface_temperature" in anomaly_vars and "chlorophyll_concentration" in anomaly_vars:
            agreements.append(
                "SST anomaly and chlorophyll decline co-occur, "
                "consistent with temperature-driven productivity reduction"
            )

        return agreements

    def _detect_contradictions(self, evidence: list[EvidenceItem]) -> list[str]:
        """Detect where agents or overlapping multi-source datasets disagree."""
        contradictions = []

        # 1. Check for opposing anomaly directions between agents
        by_var = defaultdict(list)
        for item in evidence:
            if item.variable and item.value is not None:
                by_var[item.variable].append(item)

        for var_name, items in by_var.items():
            if len(items) >= 2:
                values = [i.value for i in items if i.value is not None]
                if values and len(set(1 if v > 0 else -1 for v in values)) > 1:
                    agents = [i.agent.value for i in items if i.agent]
                    contradictions.append(
                        f"Mixed signals for {var_name} from {', '.join(set(agents))}"
                    )

                # 2. Inter-dataset numerical divergence check between distinct data sources
                source_values: dict[str, list[float]] = defaultdict(list)
                for item in items:
                    src = getattr(item, 'source', None) or 'unknown'
                    if item.value is not None and src != 'unknown':
                        source_values[src].append(item.value)

                if len(source_values) >= 2:
                    means = {src: sum(vals)/len(vals) for src, vals in source_values.items()}
                    src_list = list(means.keys())
                    for idx_a in range(len(src_list)):
                        for idx_b in range(idx_a + 1, len(src_list)):
                            s_a, s_b = src_list[idx_a], src_list[idx_b]
                            diff = abs(means[s_a] - means[s_b])
                            
                            # Specific thresholding per variable
                            thresh = 1.8 if 'temp' in var_name else (3.5 if 'wind' in var_name else 0.8)
                            if diff > thresh:
                                contradictions.append(
                                    f"⚠️ Dataset disagreement: {s_a} and {s_b} report diverging {var_name} "
                                    f"(Δ = {diff:.1f}). Uncertainty elevated."
                                )

        return contradictions

    def _detect_temporal_relationships(
        self, evidence: list[EvidenceItem]
    ) -> list[TemporalRelationship]:
        """Detect temporal ordering of events."""
        relationships = []

        # Find evidence with timestamps
        timestamped = [e for e in evidence if e.timestamp and e.value is not None]
        timestamped.sort(key=lambda e: e.timestamp)

        # Look for SST changes preceding chlorophyll changes
        sst_events = [e for e in timestamped if "temperature" in e.variable]
        chla_events = [e for e in timestamped if "chlorophyll" in e.variable]

        if sst_events and chla_events:
            sst_first = sst_events[0].timestamp
            chla_first = chla_events[0].timestamp

            if sst_first < chla_first:
                delta_hours = (chla_first - sst_first).total_seconds() / 3600
                relationships.append(TemporalRelationship(
                    event_a="SST anomaly detected",
                    event_b="Chlorophyll decline detected",
                    relationship="preceded",
                    time_delta_hours=round(delta_hours, 1),
                    description=(
                        f"SST anomaly preceded chlorophyll decline by "
                        f"approximately {delta_hours/24:.0f} days"
                    ),
                ))
            elif chla_first < sst_first:
                delta_hours = (sst_first - chla_first).total_seconds() / 3600
                relationships.append(TemporalRelationship(
                    event_a="Chlorophyll decline detected",
                    event_b="SST anomaly detected",
                    relationship="preceded",
                    time_delta_hours=round(delta_hours, 1),
                    description=(
                        f"Chlorophyll decline preceded SST anomaly by "
                        f"approximately {delta_hours/24:.0f} days"
                    ),
                ))

        return relationships

    def _detect_spatial_relationships(self, evidence: list[EvidenceItem]) -> list[str]:
        """Detect spatial patterns in the evidence."""
        relationships = []

        locations = set()
        for item in evidence:
            if item.location:
                locations.add(
                    (round(item.location.get("lat", 0), 1),
                     round(item.location.get("lon", 0), 1))
                )

        if len(locations) > 5:
            lats = [l[0] for l in locations]
            lons = [l[1] for l in locations]
            relationships.append(
                f"Evidence spans a region from {min(lats):.1f}° to {max(lats):.1f}°N, "
                f"{min(lons):.1f}° to {max(lons):.1f}°E"
            )

        return relationships

    def _rank_evidence(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        """Rank evidence by strength and quality."""

        def score(item: EvidenceItem) -> float:
            strength_score = {
                EvidenceStrength.STRONG: 1.0,
                EvidenceStrength.MODERATE: 0.6,
                EvidenceStrength.WEAK: 0.3,
                EvidenceStrength.INSUFFICIENT: 0.1,
            }.get(item.strength, 0.5)

            type_score = {
                EvidenceType.OBSERVATION: 1.0,
                EvidenceType.DERIVED_METRIC: 0.9,
                EvidenceType.LITERATURE: 0.8,
                EvidenceType.ML_RESULT: 0.7,
                EvidenceType.MODEL_INFERENCE: 0.5,
            }.get(item.evidence_type, 0.5)

            return 0.5 * strength_score + 0.3 * type_score + 0.2 * item.quality

        return sorted(evidence, key=score, reverse=True)

    def _compute_convergence_score(
        self,
        agreements: list[str],
        contradictions: list[str],
        ranked: list[EvidenceItem],
    ) -> float:
        """Compute how well evidence converges on a unified picture."""
        if not ranked:
            return 0.0

        agree_factor = min(1.0, len(agreements) / 3.0)
        contra_factor = max(0.0, 1.0 - len(contradictions) * 0.3)
        strength_factor = sum(
            1.0 if e.strength == EvidenceStrength.STRONG else
            0.6 if e.strength == EvidenceStrength.MODERATE else 0.3
            for e in ranked[:5]
        ) / min(5, len(ranked))

        return round(0.3 * agree_factor + 0.3 * contra_factor + 0.4 * strength_factor, 3)
