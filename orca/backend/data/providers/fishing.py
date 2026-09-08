"""ORCA Fishing Activity Provider — Real Global Fishing Watch integration.

Uses the GFW 4Wings API for fishing effort data and Events API for vessel events.
Requires FISHING_API_KEY environment variable.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.fishing")

# GFW API base URL
GFW_API_BASE = "https://gateway.api.globalfishingwatch.org"


class FishingActivityProvider(MarineDataProvider):
    """Provider for vessel/fishing activity data from Global Fishing Watch.

    Clearly distinguishes vessel presence from estimated fishing activity.
    Uses the 4Wings API for fishing effort maps and Events API for events.
    """

    def __init__(self, api_key: str | None = None):
        super().__init__("GLOBAL_FISHING_WATCH")
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None
        if api_key:
            self._status = ProviderStatus.HEALTHY
        else:
            self._status = ProviderStatus.UNAVAILABLE
            logger.warning("Fishing: FISHING_API_KEY not configured.")

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=GFW_API_BASE,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                },
                timeout=10.0,
                follow_redirects=True,
            )
        return self._client

    async def health_check(self) -> ProviderHealth:
        if self._status == ProviderStatus.UNAVAILABLE:
            return ProviderHealth(
                provider_name=self.name,
                status=ProviderStatus.UNAVAILABLE,
                last_check=datetime.utcnow(),
                message="FISHING_API_KEY not configured",
            )
        try:
            # Simple health check - try to access the stats endpoint
            client = self._get_client()
            params = {
                "datasets[0]": "public-global-fishing-effort:latest",
                "fields": "ACTIVITY-HOURS",
                "date-range": "2024-01-01,2024-01-31",
            }
            resp = await client.get("/v3/4wings/stats/", params=params, timeout=10.0, follow_redirects=True)
            # 200 or 301 (redirect) both mean the API is reachable
            if resp.status_code in (200, 301, 302):
                self._status = ProviderStatus.HEALTHY
                return ProviderHealth(
                    provider_name=self.name,
                    status=ProviderStatus.HEALTHY,
                    last_check=datetime.utcnow(),
                    message="Connected to Global Fishing Watch API",
                )
            else:
                self._status = ProviderStatus.DEGRADED
                return ProviderHealth(
                    provider_name=self.name,
                    status=ProviderStatus.DEGRADED,
                    last_check=datetime.utcnow(),
                    message=f"API returned status {resp.status_code}",
                )
        except Exception as e:
            self._status = ProviderStatus.DEGRADED
            logger.warning(f"GFW health check failed: {e}")
            return ProviderHealth(
                provider_name=self.name,
                status=ProviderStatus.DEGRADED,
                last_check=datetime.utcnow(),
                message=f"Connection error: {str(e)[:100]}",
            )

    async def get_data(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str] | None = None,
        **kwargs,
    ):
        """Get fishing activity data for a bounding box and time range.

        Uses GFW 4Wings report API with custom polygon to get fishing effort.
        """
        from models.observation import Observation, ObservationBatch

        if self._status == ProviderStatus.UNAVAILABLE:
            logger.warning("Fishing provider unavailable, returning empty")
            return ObservationBatch(
                observations=[],
                source="GLOBAL_FISHING_WATCH",
                dataset="unavailable",
                record_count=0,
                bbox=bbox,
                date_range=(start_date, end_date),
            )

        observations = []

        try:
            client = self._get_client()

            # Format dates for GFW API (YYYY-MM-DD)
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            # Create polygon from bbox [west, south, east, north]
            west, south, east, north = bbox
            polygon = {
                "type": "Polygon",
                "coordinates": [[
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],  # Close the polygon
                ]],
            }

            # Use 4Wings report API for fishing effort by area
            params = {
                "spatial-resolution": "LOW",
                "temporal-resolution": "ENTIRE",
                "group-by": "FLAG",
                "datasets[0]": "public-global-fishing-effort:latest",
                "date-range": f"{start_str},{end_str}",
                "format": "JSON",
            }

            body = {"geojson": polygon}

            resp = await client.post(
                "/v3/4wings/report",
                params=params,
                json=body,
            )

            if resp.status_code == 200:
                data = resp.json()
                # Parse the report response
                entries = data.get("entries", [])
                total_hours = 0
                total_vessels = 0
                by_flag = {}

                for entry_group in entries:
                    # Each entry group contains data by dataset
                    for dataset_key, dataset_entries in entry_group.items():
                        if not dataset_entries:
                            continue
                        for entry in dataset_entries:
                            hours = entry.get("hours", 0)
                            flag = entry.get("flag", "UNK")
                            vessel_ids = entry.get("vesselIDs", 0)

                            total_hours += hours
                            total_vessels = max(total_vessels, vessel_ids)

                            if flag not in by_flag:
                                by_flag[flag] = {"hours": 0, "vessels": 0}
                            by_flag[flag]["hours"] += hours
                            by_flag[flag]["vessels"] = max(
                                by_flag[flag]["vessels"], vessel_ids
                            )

                # Create fishing effort observation
                if total_hours > 0:
                    obs = Observation(
                        source="GLOBAL_FISHING_WATCH",
                        dataset="public-global-fishing-effort:latest",
                        variable="fishing_effort_hours",
                        value=total_hours,
                        unit="hours",
                        latitude=(south + north) / 2,
                        longitude=(west + east) / 2,
                        timestamp=start_date,
                        spatial_resolution="bbox",
                        temporal_resolution="period",
                        quality=0.85,
                        metadata={
                            "total_vessels": total_vessels,
                            "by_flag": by_flag,
                            "bbox": bbox,
                            "api_endpoint": "4wings/report",
                        },
                    )
                    observations.append(obs)

                # Create vessel presence observation
                if total_vessels > 0:
                    obs_vessel = Observation(
                        source="GLOBAL_FISHING_WATCH",
                        dataset="public-global-fishing-effort:latest",
                        variable="vessel_presence",
                        value=total_vessels,
                        unit="vessels",
                        latitude=(south + north) / 2,
                        longitude=(west + east) / 2,
                        timestamp=start_date,
                        spatial_resolution="bbox",
                        temporal_resolution="period",
                        quality=0.85,
                        metadata={
                            "by_flag": by_flag,
                            "bbox": bbox,
                        },
                    )
                    observations.append(obs_vessel)

            elif resp.status_code == 401:
                logger.error("GFW API authentication failed - check API key")
                self._status = ProviderStatus.DEGRADED
            else:
                logger.warning(f"GFW API returned status {resp.status_code}: {resp.text[:200]}")

        except httpx.TimeoutException:
            logger.error("GFW API request timed out")
        except httpx.RequestError as e:
            logger.error(f"GFW API request error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in fishing provider: {e}", exc_info=True)

        return ObservationBatch(
            observations=observations,
            source="GLOBAL_FISHING_WATCH",
            dataset="public-global-fishing-effort:latest",
            record_count=len(observations),
            bbox=bbox,
            date_range=(start_date, end_date),
            metadata={
                "api_version": "v3",
                "status": self._status.value,
            },
        )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
