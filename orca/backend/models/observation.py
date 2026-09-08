"""ORCA Data Models — Observations with provenance."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    OBSERVATION = "OBSERVATION"
    DERIVED_METRIC = "DERIVED_METRIC"
    ML_RESULT = "ML_RESULT"
    LITERATURE = "LITERATURE"
    MODEL_INFERENCE = "MODEL_INFERENCE"


class DataSource(str, Enum):
    NONE = "NONE"
    MOSDAC = "MOSDAC"
    COPERNICUS_MARINE = "COPERNICUS_MARINE"
    NASA = "NASA"
    NOAA = "NOAA"
    ERA5 = "ERA5"
    GLOBAL_FISHING_WATCH = "GLOBAL_FISHING_WATCH"
    LITERATURE = "LITERATURE"
    GEOSPATIAL = "GEOSPATIAL"
    INCOIS = "INCOIS"
    DEMO = "DEMO"


class QualityStatus(str, Enum):
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    FLAGGED = "FLAGGED"
    SUSPECT = "SUSPECT"
    BAD = "BAD"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"          # 🟢 < 6 hours old
    DELAYED = "DELAYED"      # 🟡 6 - 24 hours old
    STALE = "STALE"          # 🔴 > 24 hours old
    UNAVAILABLE = "UNAVAILABLE"  # ⚫ No data or unreachable


class Observation(BaseModel):
    """A single marine observation with full provenance and freshness tracking."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: DataSource
    source_name: Optional[str] = None
    dataset: str
    variable: str
    value: float
    unit: str
    latitude: float
    longitude: float
    timestamp: datetime
    observed_at: Optional[datetime] = None
    forecast_time: Optional[datetime] = None
    data_age: str = "0.0h"
    data_age_hours: float = 0.0
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH
    geometry: Optional[dict[str, Any]] = None  # GeoJSON
    spatial_resolution: Optional[str] = None
    temporal_resolution: Optional[str] = None
    quality: float = Field(default=1.0, ge=0.0, le=1.0)
    quality_status: QualityStatus = QualityStatus.GOOD
    quality_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_demo: bool = False


class ObservationBatch(BaseModel):
    """A batch of observations from a single provider query with provenance & degradation state."""

    observations: list[Observation]
    source: DataSource
    dataset: str
    bbox: Optional[list[float]] = None  # [west, south, east, north]
    date_range: Optional[tuple[datetime, datetime]] = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    record_count: int = 0
    is_demo: bool = False
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH
    provider_tier: str = "PRIMARY"  # PRIMARY | SECONDARY | CACHED | UNAVAILABLE


class ObservationQuery(BaseModel):
    """Query parameters for fetching observations."""

    bbox: list[float] = Field(description="[west, south, east, north]")
    start_date: datetime
    end_date: datetime
    variables: list[str]
    sources: Optional[list[DataSource]] = None
    max_records: int = 10000
