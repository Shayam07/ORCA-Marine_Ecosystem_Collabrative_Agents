"""ORCA Weather Provider — Open-Meteo marine weather API.

Uses Open-Meteo's free marine forecast API for:
- Wind speed/direction
- Wave height/period
- Air temperature
- Pressure
- Sea surface temperature (from marine API)

No API key required.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.weather")

# Open-Meteo endpoints
OPENMETEO_MARINE = "https://marine-api.open-meteo.com/v1/marine"
OPENMETEO_WEATHER = "https://api.open-meteo.com/v1/forecast"


class WeatherProvider(MarineDataProvider):
    """Provider for weather and marine forecast data via Open-Meteo.

    Free, no authentication required. Global coverage.
    """

    def __init__(self):
        super().__init__("ERA5")
        self._status = ProviderStatus.HEALTHY
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(12.0),
                follow_redirects=True,
                headers={"User-Agent": "ORCA-Weather/1.0"},
            )
        return self._http_client

    async def health_check(self) -> ProviderHealth:
        """Check Open-Meteo availability."""
        try:
            client = await self._get_client()
            resp = await client.get(
                OPENMETEO_WEATHER,
                params={"latitude": 13.08, "longitude": 80.27, "current_weather": "true"},
                timeout=8.0,
            )
            if resp.status_code == 200:
                self._status = ProviderStatus.HEALTHY
                return ProviderHealth(
                    provider_name=self.name,
                    status=ProviderStatus.HEALTHY,
                    last_check=datetime.utcnow(),
                    message="Open-Meteo API available",
                    datasets_available=["marine_forecast", "weather_forecast"],
                )
            else:
                self._status = ProviderStatus.DEGRADED
                return ProviderHealth(
                    provider_name=self.name,
                    status=ProviderStatus.DEGRADED,
                    last_check=datetime.utcnow(),
                    message=f"Open-Meteo returned {resp.status_code}",
                )
        except Exception as e:
            self._status = ProviderStatus.UNAVAILABLE
            return ProviderHealth(
                provider_name=self.name,
                status=ProviderStatus.UNAVAILABLE,
                last_check=datetime.utcnow(),
                message=f"Open-Meteo unreachable: {e}",
            )

    async def get_data(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str],
        **kwargs,
    ):
        """Retrieve live marine data from Open-Meteo over a spatial ocean grid.

        Open-Meteo is point-based, so a single center-point query only yields one
        coordinate — which the map layer treats as "no spatial data". Instead we
        sample a grid of ocean points across the bounding box and request them all
        in one batched multi-coordinate call (real ERA5-based waves/wind/SST/currents).
        """
        from models.observation import Observation, ObservationBatch
        from .demo import DemoDataProvider

        if self._status == ProviderStatus.UNAVAILABLE:
            return ObservationBatch(
                observations=[], source="ERA5", dataset="unavailable",
                record_count=0, bbox=bbox, date_range=(start_date, end_date),
            )

        variables = [v for v in variables if v]
        observations: list[Observation] = []

        # Keep the date window inside Open-Meteo's reach (forecast archive + ~7d forecast).
        now = datetime.utcnow()
        s_date = start_date.replace(tzinfo=None) if getattr(start_date, "tzinfo", None) is not None else start_date
        e_date = end_date.replace(tzinfo=None) if getattr(end_date, "tzinfo", None) is not None else end_date
        start = max(s_date, now - timedelta(days=6))
        end = min(e_date, now + timedelta(days=7))
        if end <= start:
            end = start + timedelta(days=1)
        start_s, end_s = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

        try:
            client = await self._get_client()

            # ── Build an ocean-only grid across the bbox ────────────────────────
            # Walk the FULL grid (no early-exit cap): an early `len(points) < 90`
            # stop lets the row-major scan exhaust the budget on the southernmost
            # rows first, so a large bbox (e.g. all of India) ends up with every
            # point crammed into the bottom strip. Sample every candidate, then
            # down-sample evenly over the whole area to the request budget.
            west, south, east, north = bbox[0], bbox[1], bbox[2], bbox[3]
            span = max(east - west, north - south)
            step = round(min(max(span / 10.0, 0.1), 2.5), 2)
            lat_step = min(step, 1.0) if (north - south) > 6 else step
            lon_step = min(step, 1.0) if (east - west) > 6 else step

            candidates: list[tuple[float, float]] = []
            lat = south
            while lat <= north:
                lon = west
                while lon <= east:
                    try:
                        if DemoDataProvider._is_ocean(round(lat, 3), round(lon, 3)):
                            candidates.append((round(lat, 2), round(lon, 2)))
                    except Exception:
                        candidates.append((round(lat, 2), round(lon, 2)))
                    lon = round(lon + lon_step, 3)
                lat = round(lat + lat_step, 3)

            # Even spatial down-sample (index-proportional) so the whole bbox is
            # represented, not just the corner the row-major scan reached first.
            budget = 90
            points: list[tuple[float, float]] = []
            if len(candidates) <= budget:
                points = candidates
            else:
                n = len(candidates)
                points = [candidates[round(i * (n - 1) / (budget - 1))] for i in range(budget)]
            if not points:
                return ObservationBatch(
                    observations=[], source="ERA5", dataset="none",
                    record_count=0, bbox=bbox, date_range=(start_date, end_date),
                )

            lat_list = ",".join(str(p[0]) for p in points)
            lon_list = ",".join(str(p[1]) for p in points)

            requested = set(variables)
            want_marine = bool(requested & {
                "sea_surface_temperature", "ocean_current_velocity",
                "ocean_current_direction", "wave_height", "wave_period", "wave_direction",
            })
            want_atmos = bool(requested & {"wind_speed", "wind_direction"})

            results: dict[str, httpx.Response] = {}
            tasks: list[tuple[str, asyncio.Task]] = []

            async def _get(params: dict) -> httpx.Response:
                return await client.get(OPENMETEO_MARINE if params.get("_marine") else OPENMETEO_WEATHER, params={k: v for k, v in params.items() if k != "_marine"})

            if want_marine:
                tasks.append(("marine", asyncio.create_task(_get({
                    "_marine": True,
                    "latitude": lat_list, "longitude": lon_list,
                    "start_date": start_s, "end_date": end_s,
                    "hourly": "sea_surface_temperature,ocean_current_velocity,ocean_current_direction",
                    "daily": "wave_height_max,wave_period_max,wave_direction_dominant",
                    "timezone": "UTC", "cell_selection": "sea",
                }))))
            if want_atmos:
                tasks.append(("atmos", asyncio.create_task(_get({
                    "latitude": lat_list, "longitude": lon_list,
                    "start_date": start_s, "end_date": end_s,
                    "daily": "wind_speed_10m_max,wind_direction_10m_dominant",
                    "wind_speed_unit": "ms",  # Open-Meteo defaults to km/h
                    "timezone": "UTC",
                }))))

            for name, task in tasks:
                try:
                    resp = await asyncio.wait_for(task, timeout=12.0)
                    if resp is not None and resp.status_code == 200:
                        results[name] = resp
                except Exception:
                    logger.warning(f"Open-Meteo {name} request failed")

            def _last(values: list) -> tuple[int, object]:
                """Index + value of the last non-null entry."""
                for i in range(len(values) - 1, -1, -1):
                    if values[i] is not None:
                        return i, values[i]
                return -1, None

            grid_quality = 0.85 if len(points) > 5 else 0.7

            for resp in results.values():
                payload = resp.json()
                entries = payload if isinstance(payload, list) else [payload]

                for pt in entries:
                    if not isinstance(pt, dict) or "latitude" not in pt:
                        continue
                    plat = pt["latitude"]
                    plon = pt["longitude"]

                    # Waves (daily): last available day
                    daily = pt.get("daily", {}) or {}
                    dtimes = daily.get("time", [])
                    for var, unit in [("wave_height", "m"), ("wave_period", "s"), ("wave_direction", "°")]:
                        key = {"wave_height": "wave_height_max", "wave_period": "wave_period_max", "wave_direction": "wave_direction_dominant"}[var]
                        if var not in requested:
                            continue
                        idx, val = _last(daily.get(key, []))
                        if idx >= 0 and 0 <= idx < len(dtimes):
                            observations.append(Observation(
                                source="ERA5", dataset="OpenMeteo_Marine", variable=var,
                                value=float(val), unit=unit, latitude=plat, longitude=plon,
                                timestamp=datetime.fromisoformat(dtimes[idx]), quality=grid_quality,
                                spatial_resolution=f"{step:.2f}°",
                            ))

                    # SST / currents (hourly): last available hour
                    hourly = pt.get("hourly", {}) or {}
                    htimes = hourly.get("time", [])
                    for var, unit, key in [
                        ("sea_surface_temperature", "°C", "sea_surface_temperature"),
                        ("ocean_current_velocity", "m/s", "ocean_current_velocity"),
                        ("ocean_current_direction", "°", "ocean_current_direction"),
                    ]:
                        if var not in requested:
                            continue
                        idx, val = _last(hourly.get(key, []))
                        if idx >= 0 and 0 <= idx < len(htimes):
                            observations.append(Observation(
                                source="ERA5", dataset="OpenMeteo_Marine", variable=var,
                                value=float(val), unit=unit, latitude=plat, longitude=plon,
                                timestamp=datetime.fromisoformat(htimes[idx]), quality=grid_quality,
                                spatial_resolution=f"{step:.2f}°",
                            ))

                    # Wind (daily max): from the weather API response
                    if "wind_speed" in requested:
                        for var, unit, key in [("wind_speed", "m/s", "wind_speed_10m_max"), ("wind_direction", "°", "wind_direction_10m_dominant")]:
                            if var not in requested:
                                continue
                            idx, val = _last(daily.get(key, []))
                            if idx >= 0 and 0 <= idx < len(dtimes):
                                observations.append(Observation(
                                    source="ERA5", dataset="OpenMeteo_Weather", variable=var,
                                    value=float(val), unit=unit, latitude=plat, longitude=plon,
                                    timestamp=datetime.fromisoformat(dtimes[idx]), quality=grid_quality,
                                    spatial_resolution=f"{step:.2f}°",
                                ))

            if observations:
                self._last_successful_retrieval = datetime.utcnow()
                logger.info(f"Open-Meteo grid: {len(points)} ocean points, {len(observations)} observations")

        except Exception as e:
            logger.warning(f"Weather provider error: {e}")

        return ObservationBatch(
            observations=observations,
            source="ERA5",
            dataset="OpenMeteo",
            record_count=len(observations),
            bbox=bbox,
            date_range=(start_date, end_date),
        )
