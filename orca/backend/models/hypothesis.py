"""ORCA Hypothesis Models."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Hypothesis(BaseModel):
    """A candidate explanation for an observed phenomenon."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    supporting_evidence: list[str] = Field(default_factory=list)  # evidence IDs
    contradicting_evidence: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_breakdown: dict[str, float] = Field(default_factory=dict)
    agent_contributions: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HypothesisResult(BaseModel):
    """Complete hypothesis output."""

    hypotheses: list[Hypothesis]
    top_hypothesis: Optional[Hypothesis] = None
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
