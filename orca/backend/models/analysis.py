"""ORCA Analysis Models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .agent import AgentResult
from .evidence import EvidenceItem, TemporalRelationship
from .hypothesis import ConfidenceLevel, Hypothesis
from .observation import Observation


class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class AnalysisRequest(BaseModel):
    """User request for analysis."""

    question: str
    geometry: dict[str, Any]  # GeoJSON geometry
    start_date: str  # ISO date
    end_date: str  # ISO date
    variables: Optional[list[str]] = None


class DataSourceInfo(BaseModel):
    """Information about a data source used in analysis."""

    name: str
    status: str  # "LIVE", "CACHED", "DEMO", "UNAVAILABLE"
    records_used: int = 0
    variables_covered: list[str] = Field(default_factory=list)
    message: Optional[str] = None


class AnalysisResult(BaseModel):
    """Complete analysis result."""

    analysis_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: AnalysisStatus = AnalysisStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # User query
    question: str = ""
    geometry: Optional[dict[str, Any]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Results
    summary: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    ecosystem_status: str = "unknown"

    # Observations
    observations: list[Observation] = Field(default_factory=list)

    # Agent results
    agent_results: list[AgentResult] = Field(default_factory=list)
    agents_used: list[str] = Field(default_factory=list)

    # Reasoning
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    temporal_relationships: list[TemporalRelationship] = Field(
        default_factory=list
    )
    spatial_relationships: list[str] = Field(default_factory=list)

    # Data sources
    data_sources: list[DataSourceInfo] = Field(default_factory=list)

    # Uncertainties
    uncertainties: list[str] = Field(default_factory=list)

    # Timing
    processing_time_ms: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
