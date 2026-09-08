"""ORCA Data Service — Unified data access layer for agents.

Agents never access providers directly. They go through DataService.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from data.providers import get_registry
from models.observation import ObservationBatch

logger = logging.getLogger("orca.data_service")


class DataService:
    """Unified data access layer.

    Provides a single interface for agents to request data.
    Handles caching, fallback, and quality control.
    """

    def __init__(self):
        self.registry = get_registry()
        self._cache: dict[str, ObservationBatch] = {}

    def _make_cache_key(
        self, bbox: list[float], start_date: datetime,
        end_date: datetime, variables: list[str], allow_demo: bool = False
    ) -> str:
        bbox_str = ",".join(f"{round(b, 2):.2f}" for b in bbox)
        vars_str = ",".join(sorted(variables))
        s_norm = start_date.strftime("%Y-%m-%d_%H") if hasattr(start_date, "strftime") else str(start_date)[:13]
        e_norm = end_date.strftime("%Y-%m-%d_%H") if hasattr(end_date, "strftime") else str(end_date)[:13]
        return f"{bbox_str}:{s_norm}:{e_norm}:{vars_str}:demo={allow_demo}"

    async def warm_up_cache(self):
        """Warm up provider metadata only — no geographic pre-fetching.
        
        Geographic data should only be fetched when a user query specifies a location.
        This method only verifies providers are initialized and responsive.
        """
        import asyncio
        try:
            async def _check_one(prov):
                try:
                    await asyncio.wait_for(prov.health_check(), timeout=1.5)
                except Exception:
                    pass

            tasks = [_check_one(p) for n, p in self.registry.providers.items() if n != "DEMO"]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("⚡ DataService provider metadata warmed up successfully.")
        except Exception as e:
            logger.warning(f"Provider warm up failed: {e}")

    async def get_observations(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str],
        sources: list[str] | None = None,
        use_cache: bool = True,
        allow_demo: bool = True,
    ) -> ObservationBatch:
        """Fetch observations with 4-tier provider fallback, freshness telemetry, and confidence adjustments."""
        from models.observation import FreshnessStatus, DataSource
        from datetime import timezone

        # Providers (Open-Meteo/ERDDAP/etc.) treat every timestamp as naive UTC
        # and compare against datetime.utcnow().  Map callers pass naive datetimes
        # while the chat flow passes timezone-aware ones; normalize here so a
        # mixed caller never crashes a provider with an offset-naive/aware compare.
        if start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        cache_key = self._make_cache_key(bbox, start_date, end_date, variables, allow_demo)

        if use_cache and cache_key in self._cache:
            cached_batch = self._cache[cache_key]
            # Verify if cached data is still within acceptable freshness
            now = datetime.now(timezone.utc)
            cached_age_h = (now - cached_batch.retrieved_at).total_seconds() / 3600.0
            if cached_age_h < 4.0:
                logger.info(f"Cache hit for {cache_key[:50]}... (age: {cached_age_h:.1f}h)")
                cached_batch.provider_tier = "CACHED"
                return cached_batch

        observations, sources_used = await self.registry.get_data_with_fallback(
            bbox=bbox,
            start_date=start_date,
            end_date=end_date,
            variables=variables,
            preferred_sources=sources,
            allow_demo=allow_demo,
        )

        now = datetime.now(timezone.utc)
        batch_freshness = FreshnessStatus.FRESH
        provider_tier = "PRIMARY"

        if not observations:
            batch_freshness = FreshnessStatus.UNAVAILABLE
            provider_tier = "UNAVAILABLE"
        elif "DEMO" in sources_used and len(sources_used) == 1:
            provider_tier = "SECONDARY"

        # Calculate freshness and apply confidence penalties for stale/delayed data
        max_age_hours = 0.0
        for obs in observations:
            # Set explicit source_name and timestamps
            obs.source_name = obs.source.value if hasattr(obs.source, "value") else str(obs.source)
            obs_time = obs.timestamp if obs.timestamp.tzinfo else obs.timestamp.replace(tzinfo=timezone.utc)
            age_h = max(0.0, (now - obs_time).total_seconds() / 3600.0)
            obs.data_age_hours = round(age_h, 1)
            obs.data_age = f"{age_h:.1f}h"
            obs.observed_at = obs.timestamp
            obs.retrieved_at = now
            
            if age_h <= 6.0:
                obs.freshness_status = FreshnessStatus.FRESH
            elif age_h <= 24.0:
                obs.freshness_status = FreshnessStatus.DELAYED
                obs.confidence = max(0.2, obs.confidence * 0.85)  # 15% reduction for delayed
            else:
                obs.freshness_status = FreshnessStatus.STALE
                obs.confidence = max(0.1, obs.confidence * 0.60)  # 40% reduction for stale

            if age_h > max_age_hours:
                max_age_hours = age_h

        if observations:
            if max_age_hours > 24.0:
                batch_freshness = FreshnessStatus.STALE
            elif max_age_hours > 6.0:
                batch_freshness = FreshnessStatus.DELAYED
            else:
                batch_freshness = FreshnessStatus.FRESH

        batch = ObservationBatch(
            observations=observations,
            source=sources_used[0] if sources_used else DataSource.NONE,
            dataset="mixed",
            bbox=bbox,
            date_range=(start_date, end_date),
            retrieved_at=now,
            record_count=len(observations),
            is_demo="DEMO" in sources_used and len(sources_used) == 1,
            freshness_status=batch_freshness,
            provider_tier=provider_tier,
        )

        if use_cache and observations:
            self._cache[cache_key] = batch

        return batch

    async def get_variable_timeseries(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variable: str,
    ) -> list[dict[str, Any]]:
        """Get a time series for a single variable, averaged over the bbox."""
        batch = await self.get_observations(
            bbox, start_date, end_date, [variable]
        )

        # Group by date and average
        from collections import defaultdict
        daily: dict[str, list[float]] = defaultdict(list)

        for obs in batch.observations:
            if obs.variable == variable:
                day_key = obs.timestamp.strftime("%Y-%m-%d")
                daily[day_key].append(obs.value)

        result = []
        for day_key in sorted(daily.keys()):
            values = daily[day_key]
            result.append({
                "date": day_key,
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "count": len(values),
            })

        return result

    async def get_spatial_summary(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str],
    ) -> dict[str, Any]:
        """Get spatial summary statistics for variables."""
        batch = await self.get_observations(
            bbox, start_date, end_date, variables
        )

        from collections import defaultdict
        import statistics

        summaries: dict[str, dict] = defaultdict(lambda: {
            "values": [], "min_lat": 90, "max_lat": -90,
            "min_lon": 180, "max_lon": -180,
        })

        for obs in batch.observations:
            s = summaries[obs.variable]
            s["values"].append(obs.value)
            s["min_lat"] = min(s["min_lat"], obs.latitude)
            s["max_lat"] = max(s["max_lat"], obs.latitude)
            s["min_lon"] = min(s["min_lon"], obs.longitude)
            s["max_lon"] = max(s["max_lon"], obs.longitude)

        result = {}
        for var_name, s in summaries.items():
            values = s["values"]
            if values:
                result[var_name] = {
                    "mean": statistics.mean(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                    "bbox": [s["min_lon"], s["min_lat"], s["max_lon"], s["max_lat"]],
                }

        return result

    async def get_provider_status(self) -> list[dict[str, Any]]:
        """Get health status of all providers."""
        health_results = await self.registry.health_check_all()
        return [h.model_dump() for h in health_results]

    def clear_cache(self):
        """Clear the observation cache."""
        self._cache.clear()


# Singleton
_data_service: DataService | None = None


def get_data_service() -> DataService:
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service
