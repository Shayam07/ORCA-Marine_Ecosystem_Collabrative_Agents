"""ORCA Coordinator Agent — Concurrent execution with per-agent timeouts."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from .ocean import OceanAgent
from .satellite import SatelliteAgent
from .biology import BiologyAgent
from .weather import WeatherAgent
from .fisheries import FisheriesAgent
from .pollution import PollutionAgent
from .literature import LiteratureAgent
from .safety import MarineSafetyAgent
from .tide import TideAgent
from .route import MarineRouteAgent
from .geofence import GeofenceAgent
from models.agent import AgentResult, AgentStatus, AgentTask, AgentType
from reasoning.query_router import TaskPlan

logger = logging.getLogger("orca.agents.coordinator")

# Per-agent timeout limits (seconds) - Optimized for speed
AGENT_TIMEOUTS: dict[str, float] = {
    "ocean": 2.5,
    "satellite": 2.5,
    "biology": 2.0,
    "weather": 1.5,
    "fisheries": 2.0,
    "pollution": 1.5,
    "literature": 1.5,
    "safety": 1.5,
    "tide": 1.5,
    "route": 1.5,
    "geofence": 1.5,
}


class CoordinatorAgent:
    """Orchestrates 11 specialized agents with concurrent execution and timeouts."""

    def __init__(self):
        self.agents = {
            AgentType.OCEAN: OceanAgent(),
            AgentType.SATELLITE: SatelliteAgent(),
            AgentType.BIOLOGY: BiologyAgent(),
            AgentType.WEATHER: WeatherAgent(),
            AgentType.FISHERIES: FisheriesAgent(),
            AgentType.POLLUTION: PollutionAgent(),
            AgentType.LITERATURE: LiteratureAgent(),
            AgentType.SAFETY: MarineSafetyAgent(),
            AgentType.TIDE: TideAgent(),
            AgentType.ROUTE: MarineRouteAgent(),
            AgentType.GEOFENCE: GeofenceAgent(),
        }

    def _select_agents(self, plan: TaskPlan) -> list[AgentType]:
        """Select agents based on the task plan."""
        selected = []
        name_to_type = {
            "ocean": AgentType.OCEAN,
            "satellite": AgentType.SATELLITE,
            "biology": AgentType.BIOLOGY,
            "weather": AgentType.WEATHER,
            "fisheries": AgentType.FISHERIES,
            "pollution": AgentType.POLLUTION,
            "literature": AgentType.LITERATURE,
            "safety": AgentType.SAFETY,
            "tide": AgentType.TIDE,
            "route": AgentType.ROUTE,
            "geofence": AgentType.GEOFENCE,
        }
        for name in plan.agent_selection.required:
            if name in name_to_type:
                selected.append(name_to_type[name])
        for name in plan.agent_selection.optional:
            if name in name_to_type and name_to_type[name] not in selected:
                selected.append(name_to_type[name])
        return selected

    async def coordinate(
        self,
        question: str,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str] | None = None,
        geometry: dict[str, Any] | None = None,
        plan: TaskPlan | None = None,
    ) -> AgentResult:
        """Run agents concurrently with per-agent timeouts."""
        start_time = time.time()

        if plan:
            required_agents = self._select_agents(plan)
            intent = plan.classification.intent.value
        else:
            required_agents = list(self.agents.keys())
            intent = "UNKNOWN"

        logger.info(
            f"[TIMING] Coordinator dispatching {len(required_agents)} agents: "
            f"{[a.value for a in required_agents]} (intent={intent})"
        )

        # Create tasks
        tasks = []
        for agent_type in required_agents:
            task = AgentTask(
                agent_type=agent_type, question=question, bbox=bbox,
                start_date=start_date, end_date=end_date,
                variables=variables or [],
                context={"geometry": geometry, "intent": intent} if geometry else {"intent": intent},
            )
            tasks.append(task)

        # Run ALL agents concurrently with individual timeouts
        async def run_agent_with_timeout(agent_type, task):
            agent = self.agents[agent_type]
            timeout = AGENT_TIMEOUTS.get(agent_type.value, 8.0)
            return await agent.execute(task, timeout=timeout)

        coros = [run_agent_with_timeout(t.agent_type, t) for t in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Process results
        all_findings = []
        all_evidence = []
        all_hypotheses = []
        agent_results = []
        agents_used = []
        data_sources_used = set()
        total_confidence = 0.0
        valid_count = 0

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Agent raised exception: {result}")
                continue
            agent_results.append(result)
            agents_used.append(result.agent_type.value)
            all_findings.extend(result.findings)
            all_evidence.extend(result.evidence)
            all_hypotheses.extend(result.hypotheses)
            data_sources_used.update(result.data_sources_used)
            if result.status == AgentStatus.SUCCESS:
                total_confidence += result.confidence
                valid_count += 1

        avg_confidence = total_confidence / valid_count if valid_count > 0 else 0.0
        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            f"[TIMING] Coordinator completed: {elapsed_ms:.0f}ms, "
            f"{valid_count}/{len(required_agents)} succeeded, "
            f"{len(all_evidence)} evidence, confidence={avg_confidence:.3f}"
        )

        return AgentResult(
            agent_type=AgentType.COORDINATOR,
            status=AgentStatus.SUCCESS if valid_count > 0 else AgentStatus.FAILED,
            findings=all_findings, evidence=all_evidence, hypotheses=all_hypotheses,
            confidence=round(avg_confidence, 3),
            start_time=datetime.utcnow(), end_time=datetime.utcnow(),
            records_retrieved=len(all_evidence),
            data_sources_used=sorted(data_sources_used),
            metadata={
                "agent_results": [r.model_dump() for r in agent_results],
                "agents_used": agents_used,
                "processing_time_ms": elapsed_ms,
                "agents_succeeded": valid_count,
                "agents_total": len(required_agents),
                "intent": intent,
            },
        )
