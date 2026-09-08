"""ORCA Base Agent — Common interface for all specialized agents."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime

from data.service import DataService, get_data_service
from models.agent import AgentFinding, AgentResult, AgentStatus, AgentTask, AgentType

logger = logging.getLogger("orca.agents")


class BaseMarineAgent(ABC):
    """Abstract base class for all marine ecosystem agents.

    Every agent must:
    1. receive a structured task
    2. request data through DataService
    3. analyze data
    4. produce structured findings
    5. produce evidence
    6. generate candidate hypotheses
    7. calculate local confidence
    8. return AgentResult
    """

    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.data_service: DataService = get_data_service()
        self.logger = logging.getLogger(f"orca.agents.{agent_type.value}")

    async def execute(self, task: AgentTask, timeout: float = 3.0) -> AgentResult:
        """Execute an agent task with timing, timeout, and error handling.
        
        Args:
            task: The agent task to execute
            timeout: Maximum seconds before timeout (default 3s, reduced to prevent
                     external SDK blocking from stalling the orchestrator pipeline)
        """
        result = AgentResult(
            agent_type=self.agent_type,
            task_id=task.task_id,
            status=AgentStatus.RUNNING,
            start_time=datetime.utcnow(),
        )

        start = time.time()

        try:
            # Run with timeout
            findings, evidence, hypotheses, confidence = await asyncio.wait_for(
                self.analyze(task),
                timeout=timeout,
            )
            result.findings = findings
            result.evidence = evidence
            result.hypotheses = hypotheses
            result.confidence = confidence
            result.status = AgentStatus.SUCCESS
            result.records_retrieved = len(evidence)

            if not evidence:
                result.status = AgentStatus.NO_DATA
                result.confidence = 0.0

        except asyncio.TimeoutError:
            elapsed = (time.time() - start) * 1000
            self.logger.warning(
                f"Agent {self.agent_type.value} TIMED OUT after {elapsed:.0f}ms "
                f"(limit: {timeout*1000:.0f}ms)"
            )
            result.status = AgentStatus.FAILED
            result.error = f"Timeout after {timeout}s"
        except Exception as e:
            self.logger.error(f"Agent {self.agent_type.value} failed: {e}", exc_info=True)
            result.status = AgentStatus.FAILED
            result.error = str(e)

        result.end_time = datetime.utcnow()
        result.data_sources_used = list(set(
            obs.source.value for obs in result.evidence
        ))

        elapsed = (time.time() - start) * 1000
        self.logger.info(
            f"[TIMING] {self.agent_type.value}: {result.status.value} "
            f"({elapsed:.0f}ms, {result.records_retrieved} records, "
            f"{len(result.findings)} findings)"
        )

        return result

    @abstractmethod
    async def analyze(
        self, task: AgentTask
    ) -> tuple[
        list[AgentFinding],  # findings
        list,                # evidence (Observations)
        list[str],           # hypotheses
        float,               # confidence
    ]:
        """Core analysis logic. Must be implemented by each agent.

        Returns:
            (findings, evidence, hypotheses, confidence)
        """
        ...

    def _compute_basic_confidence(
        self,
        num_evidence: int,
        avg_quality: float,
        num_findings: int,
    ) -> float:
        """Simple confidence heuristic based on evidence quantity and quality."""
        if num_evidence == 0:
            return 0.0

        evidence_factor = min(1.0, num_evidence / 10.0)  # saturates at 10 records
        quality_factor = avg_quality
        finding_factor = min(1.0, num_findings / 5.0)  # saturates at 5 findings

        return round(
            0.4 * evidence_factor + 0.4 * quality_factor + 0.2 * finding_factor,
            3,
        )
