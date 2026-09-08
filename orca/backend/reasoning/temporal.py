"""ORCA Temporal Reasoning Engine — Identifies temporal relationships between events."""

from __future__ import annotations

import logging

from models.agent import AgentResult
from models.evidence import TemporalRelationship

logger = logging.getLogger("orca.reasoning.temporal")


class TemporalReasoningEngine:
    """Identifies temporal ordering and relationships between marine events.

    Uses cautious language: preceded, correlated with, consistent with.
    Does NOT automatically claim causation.
    """

    def analyze(
        self, agent_results: list[AgentResult]
    ) -> list[TemporalRelationship]:
        """Analyze temporal relationships across all agent evidence."""

        # Collect timestamped events
        events = []
        for result in agent_results:
            for finding in result.findings:
                if finding.supporting_evidence:
                    earliest = min(
                        (o.timestamp for o in finding.supporting_evidence),
                        default=None,
                    )
                    if earliest:
                        events.append({
                            "description": finding.description[:100],
                            "variable": finding.variable,
                            "timestamp": earliest,
                            "agent": result.agent_type.value,
                            "anomaly": finding.anomaly_detected,
                        })

        if len(events) < 2:
            return []

        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"])

        relationships = []

        # Look for specific patterns
        sst_events = [e for e in events if "temperature" in e["variable"]]
        chla_events = [e for e in events if "chlorophyll" in e["variable"]]
        wind_events = [e for e in events if "wind" in e["variable"]]

        # SST before chlorophyll pattern
        if sst_events and chla_events:
            sst_first = sst_events[0]
            chla_first = chla_events[0]
            delta = (chla_first["timestamp"] - sst_first["timestamp"]).total_seconds() / 3600

            if abs(delta) > 1:
                rel = "preceded" if delta > 0 else "followed"
                relationships.append(TemporalRelationship(
                    event_a="SST anomaly",
                    event_b="Chlorophyll decline",
                    relationship=rel,
                    time_delta_hours=round(abs(delta), 1),
                    description=(
                        f"The SST anomaly {rel} the chlorophyll decline by "
                        f"approximately {abs(delta)/24:.0f} days. This temporal "
                        f"pattern is {'consistent with' if delta > 0 else 'unexpected for'} "
                        "temperature-driven productivity reduction."
                    ),
                ))

        # Wind before SST pattern
        if wind_events and sst_events:
            wind_first = wind_events[0]
            sst_first = sst_events[0]
            delta = (sst_first["timestamp"] - wind_first["timestamp"]).total_seconds() / 3600

            if abs(delta) > 1:
                relationships.append(TemporalRelationship(
                    event_a="Wind change",
                    event_b="SST anomaly",
                    relationship="preceded" if delta > 0 else "followed",
                    time_delta_hours=round(abs(delta), 1),
                    description=(
                        f"Wind conditions changed approximately {abs(delta)/24:.0f} days "
                        f"{'before' if delta > 0 else 'after'} the SST anomaly was detected."
                    ),
                ))

        return relationships
