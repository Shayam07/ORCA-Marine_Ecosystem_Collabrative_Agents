"""ORCA Agent Models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .observation import EvidenceType, Observation


class AgentType(str, Enum):
    COORDINATOR = "coordinator"
    OCEAN = "ocean"
    SATELLITE = "satellite"
    BIOLOGY = "biology"
    WEATHER = "weather"
    POLLUTION = "pollution"
    FISHERIES = "fisheries"
    LITERATURE = "literature"
    SAFETY = "safety"
    TIDE = "tide"
    ROUTE = "route"
    GEOFENCE = "geofence"


class AgentStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NO_DATA = "NO_DATA"


class AgentTask(BaseModel):
    """Task dispatched to a specialized agent."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: AgentType
    question: str
    bbox: list[float]
    start_date: datetime
    end_date: datetime
    variables: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class AgentFinding(BaseModel):
    """A single finding from an agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    variable: str
    description: str
    value: Optional[float] = None
    unit: Optional[str] = None
    anomaly_detected: bool = False
    anomaly_severity: Optional[str] = None  # normal, minor, moderate, major
    evidence_type: EvidenceType = EvidenceType.OBSERVATION
    supporting_evidence: list[Observation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Complete result from an agent execution."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: AgentType
    status: AgentStatus = AgentStatus.QUEUED
    task_id: str = ""
    findings: list[AgentFinding] = Field(default_factory=list)
    evidence: list[Observation] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    data_sources_used: list[str] = Field(default_factory=list)
    records_retrieved: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
