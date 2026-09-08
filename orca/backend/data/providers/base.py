"""ORCA Base Data Provider — Abstract interface for all data sources."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from models.observation import Observation, ObservationBatch

logger = logging.getLogger("orca.providers")


class ProviderStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class ProviderHealth(BaseModel):
    """Health status of a data provider."""

    provider_name: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    last_check: Optional[datetime] = None
    last_successful_retrieval: Optional[datetime] = None
    message: Optional[str] = None
    datasets_available: list[str] = Field(default_factory=list)


class MarineDataProvider(ABC):
    """Abstract base class for all marine data providers.

    Every provider must implement this interface so agents never need
    to know provider-specific implementation details.
    """

    def __init__(self, name: str):
        self.name = name
        self._status = ProviderStatus.UNKNOWN
        self._last_successful_retrieval: Optional[datetime] = None

    @property
    def status(self) -> ProviderStatus:
        return self._status

    async def health_check(self) -> ProviderHealth:
        """Check provider health and availability."""
        return ProviderHealth(
            provider_name=self.name,
            status=self._status,
            last_check=datetime.utcnow(),
            last_successful_retrieval=self._last_successful_retrieval,
        )

    @abstractmethod
    async def get_data(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str],
        **kwargs,
    ) -> ObservationBatch:
        """Retrieve data for a given spatial/temporal query.

        Args:
            bbox: [west, south, east, north]
            start_date: Start of time range
            end_date: End of time range
            variables: List of variable names to retrieve

        Returns:
            ObservationBatch with normalized observations
        """
        ...

    async def get_metadata(self, dataset: str) -> dict[str, Any]:
        """Get metadata for a specific dataset."""
        return {"dataset": dataset, "provider": self.name}

    def _create_observation(
        self,
        *,
        dataset: str,
        variable: str,
        value: float,
        unit: str,
        latitude: float,
        longitude: float,
        timestamp: datetime,
        quality: float = 1.0,
        metadata: dict[str, Any] | None = None,
        is_demo: bool = False,
    ) -> Observation:
        """Helper to create a well-formed Observation."""
        from models.observation import DataSource

        source_map = {
            "MOSDAC": DataSource.MOSDAC,
            "COPERNICUS_MARINE": DataSource.COPERNICUS_MARINE,
            "NASA": DataSource.NASA,
            "NOAA": DataSource.NOAA,
            "ERA5": DataSource.ERA5,
            "GLOBAL_FISHING_WATCH": DataSource.GLOBAL_FISHING_WATCH,
            "LITERATURE": DataSource.LITERATURE,
            "GEOSPATIAL": DataSource.GEOSPATIAL,
            "INCOIS": DataSource.INCOIS,
            "DEMO": DataSource.DEMO,
        }
        source = source_map.get(self.name, DataSource.DEMO)

        return Observation(
            source=source,
            dataset=dataset,
            variable=variable,
            value=value,
            unit=unit,
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp,
            quality=quality,
            metadata=metadata or {},
            is_demo=is_demo,
        )
