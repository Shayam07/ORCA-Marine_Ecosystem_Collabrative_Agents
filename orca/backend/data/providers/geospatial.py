"""ORCA Geospatial Provider — Coastlines, bathymetry, marine boundaries."""

from __future__ import annotations

import logging
from datetime import datetime

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.geospatial")


class GeospatialProvider(MarineDataProvider):
    """Provider for geographic/bathymetric data.

    Sources: Natural Earth, GEBCO, Marine boundaries.
    """

    def __init__(self):
        super().__init__("GEOSPATIAL")
        self._status = ProviderStatus.HEALTHY

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name, status=self._status,
            last_check=datetime.utcnow(),
            message="Demo mode",
            datasets_available=["coastlines", "bathymetry", "eez"],
        )

    async def get_data(self, bbox, start_date, end_date, variables, **kwargs):
        from models.observation import ObservationBatch
        return ObservationBatch(
            observations=[], source="GEOSPATIAL", dataset="geographic",
            record_count=0, bbox=bbox, date_range=(start_date, end_date),
        )
