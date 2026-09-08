"""ORCA Evidence Models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from .agent import AgentType
from .observation import EvidenceType, Observation


class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceItem(BaseModel):
    """A piece of evidence used in reasoning."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    dataset: str
    variable: str
    value: Optional[float] = None
    unit: Optional[str] = None
    location: Optional[dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    agent: AgentType
    evidence_type: EvidenceType
    strength: EvidenceStrength = EvidenceStrength.MODERATE
    description: str = ""
    observations: list[Observation] = Field(default_factory=list)


class TemporalRelationship(BaseModel):
    """Describes a temporal relationship between events."""

    event_a: str
    event_b: str
    relationship: str  # "preceded", "coincided", "followed"
    time_delta_hours: Optional[float] = None
    description: str = ""


class FusionResult(BaseModel):
    """Result of the evidence fusion engine."""

    agreements: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    temporal_relationships: list[TemporalRelationship] = Field(
        default_factory=list
    )
    spatial_relationships: list[str] = Field(default_factory=list)
    ranked_evidence: list[EvidenceItem] = Field(default_factory=list)
    evidence_convergence_score: float = 0.0
