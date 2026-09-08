"""ORCA Data Providers — Registry and initialization."""

from __future__ import annotations

import logging
from datetime import datetime

from config.settings import settings

from .base import MarineDataProvider, ProviderHealth, ProviderStatus
from .demo import DemoDataProvider

logger = logging.getLogger("orca.providers")


class ProviderRegistry:
    """Central registry for all data providers.

    Manages provider initialization, health checks, and data fallback.
    Implements the priority system: live providers → cached real observations → no data.
    Demo observations are opt-in only.
    """

    def __init__(self):
        self._providers: dict[str, MarineDataProvider] = {}
        self._demo_provider = DemoDataProvider()
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all providers based on configuration."""
        # Always register demo
        self._providers["DEMO"] = self._demo_provider

        # Real providers (stubs until configured)
        try:
            from .copernicus import CopernicusMarineProvider
            self._providers["COPERNICUS_MARINE"] = CopernicusMarineProvider(
                username=settings.COPERNICUS_USERNAME,
                password=settings.COPERNICUS_PASSWORD,
            )
        except Exception as e:
            logger.warning(f"Failed to init Copernicus: {e}")

        try:
            from .mosdac import MOSDACProvider
            self._providers["MOSDAC"] = MOSDACProvider(
                base_url=settings.MOSDAC_BASE_URL,
                api_key=settings.MOSDAC_API_KEY,
                username=settings.MOSDAC_USERNAME,
                password=settings.MOSDAC_PASSWORD,
            )
        except Exception as e:
            logger.warning(f"Failed to init MOSDAC: {e}")

        try:
            from .nasa import NASAProvider
            self._providers["NASA"] = NASAProvider(
                api_key=settings.NASA_API_KEY,
                username=settings.NASA_USERNAME,
                password=settings.NASA_PASSWORD,
            )
        except Exception as e:
            logger.warning(f"Failed to init NASA: {e}")

        try:
            from .noaa import NOAAProvider
            self._providers["NOAA"] = NOAAProvider()
        except Exception as e:
            logger.warning(f"Failed to init NOAA: {e}")

        try:
            from .weather import WeatherProvider
            self._providers["ERA5"] = WeatherProvider()
        except Exception as e:
            logger.warning(f"Failed to init Weather: {e}")

        try:
            from .fishing import FishingActivityProvider
            self._providers["GLOBAL_FISHING_WATCH"] = FishingActivityProvider(
                api_key=settings.FISHING_API_KEY,
            )
        except Exception as e:
            logger.warning(f"Failed to init Fishing: {e}")

        try:
            from .literature import LiteratureProvider
            self._providers["LITERATURE"] = LiteratureProvider()
        except Exception as e:
            logger.warning(f"Failed to init Literature: {e}")

        try:
            from .geospatial import GeospatialProvider
            self._providers["GEOSPATIAL"] = GeospatialProvider()
        except Exception as e:
            logger.warning(f"Failed to init Geospatial: {e}")

        try:
            from .incois import INCOISProvider
            self._providers["INCOIS"] = INCOISProvider()
        except Exception as e:
            logger.warning(f"Failed to init INCOIS: {e}")

        logger.info(f"Initialized {len(self._providers)} providers: {list(self._providers.keys())}")

    @property
    def providers(self) -> dict[str, MarineDataProvider]:
        return self._providers

    def get_provider(self, name: str) -> MarineDataProvider | None:
        return self._providers.get(name)

    def get_demo_provider(self) -> DemoDataProvider:
        return self._demo_provider

    async def get_data_with_fallback(
        self,
        bbox: list[float],
        start_date,
        end_date,
        variables: list[str],
        preferred_sources: list[str] | None = None,
        allow_demo: bool = False,
    ) -> tuple[list, list[str]]:
        """Try providers in priority order. Demo is used only when explicitly enabled.

        Returns (observations, sources_used).
        """
        from models.observation import Observation

        all_observations: list[Observation] = []
        sources_used: list[str] = []

        if preferred_sources:
            source_order = preferred_sources + [
                s for s in self._providers if s not in preferred_sources and s != "DEMO"
            ]
        else:
            # Prioritize fast, high-availability providers (ERA5/Open-Meteo) first
            preferred_defaults = ["ERA5", "NOAA", "INCOIS", "GLOBAL_FISHING_WATCH", "COPERNICUS_MARINE", "MOSDAC", "NASA"]
            source_order = [s for s in preferred_defaults if s in self._providers]
            for s in self._providers:
                if s not in source_order and s not in ("DEMO", "LITERATURE", "GEOSPATIAL"):
                    source_order.append(s)

        import asyncio

        # Tightly bounded provider timeouts (seconds) to prevent stalling the backend
        PROVIDER_TIMEOUTS = {
            "ERA5": 4.0,
            "NOAA": 4.0,
            "GLOBAL_FISHING_WATCH": 3.0,
            "INCOIS": 3.0,
            "COPERNICUS_MARINE": 2.5,
            "MOSDAC": 2.0,
            "NASA": 2.0,
            "LITERATURE": 1.5,
            "GEOSPATIAL": 1.5,
        }
        DEFAULT_TIMEOUT = 3.0

        async def _try_provider(source_name: str):
            if source_name == "DEMO":
                return source_name, []
            provider = self._providers.get(source_name)
            if not provider or provider.status == ProviderStatus.UNAVAILABLE:
                return source_name, []
            timeout = PROVIDER_TIMEOUTS.get(source_name, DEFAULT_TIMEOUT)
            try:
                batch = await asyncio.wait_for(
                    provider.get_data(bbox, start_date, end_date, variables),
                    timeout=timeout
                )
                if batch.observations:
                    return source_name, batch.observations
            except asyncio.TimeoutError:
                logger.warning(f"Provider {source_name} timed out (>{timeout}s)")
            except Exception as e:
                logger.warning(f"Provider {source_name} failed: {e}")
            return source_name, []

        # Run all providers concurrently
        tasks = [_try_provider(s) for s in source_order if s != "DEMO"]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    continue
                source_name, observations = result
                if observations:
                    all_observations.extend(observations)
                    sources_used.append(source_name)

        # Never silently fabricate a production answer. Demo is an intentional mode.
        if not all_observations and allow_demo:
            logger.info("No live data available; explicit DEMO mode enabled")
            batch = await self._demo_provider.get_data(
                bbox, start_date, end_date, variables
            )
            all_observations = batch.observations
            sources_used.append("DEMO")

        return all_observations, sources_used

    async def health_check_all(self) -> list[ProviderHealth]:
        """Check health of all providers."""
        results = []
        for name, provider in self._providers.items():
            try:
                health = await provider.health_check()
                results.append(health)
            except Exception as e:
                results.append(ProviderHealth(
                    provider_name=name,
                    status=ProviderStatus.UNAVAILABLE,
                    last_check=datetime.utcnow(),
                    message=f"Health check failed: {e}",
                ))
        return results


# Singleton
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
