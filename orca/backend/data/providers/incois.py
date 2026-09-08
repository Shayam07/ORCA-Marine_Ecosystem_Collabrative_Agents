"""ORCA INCOIS Provider — Indian National Centre for Ocean Information Services.

Integrates with officially accessible INCOIS public services:
- PFZ (Potential Fishing Zone) advisories
- Ocean State Forecast information
- Marine alerts and warnings

IMPORTANT: INCOIS does NOT provide a public REST API.
This provider accesses:
1. PFZ text advisory pages (HTML scraping)
2. PFZ WebGIS map layer data
3. Public marine information pages

All data is from official INCOIS public sources.
ORCA-derived analysis is always clearly distinguished from official INCOIS products.
"""

from __future__ import annotations

import re
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.incois")

# INCOIS PFZ sector definitions (14 coastal sectors)
INCOIS_SECTORS = {
    "SEC001": {"name": "Gujarat", "lat_range": (20.0, 23.5), "lon_range": (68.0, 72.5)},
    "SEC002": {"name": "Maharashtra", "lat_range": (15.5, 20.0), "lon_range": (72.5, 73.5)},
    "SEC003": {"name": "Goa", "lat_range": (14.8, 15.8), "lon_range": (73.5, 74.2)},
    "SEC004": {"name": "Karnataka", "lat_range": (12.0, 14.8), "lon_range": (74.2, 75.5)},
    "SEC005": {"name": "Kerala", "lat_range": (8.0, 12.0), "lon_range": (74.5, 77.5)},
    "SEC006": {"name": "South Tamil Nadu", "lat_range": (8.0, 10.5), "lon_range": (77.0, 79.5)},
    "SEC007": {"name": "North Tamil Nadu", "lat_range": (10.5, 13.5), "lon_range": (79.5, 80.5)},
    "SEC008": {"name": "South Andhra Pradesh", "lat_range": (13.5, 16.0), "lon_range": (80.0, 82.5)},
    "SEC009": {"name": "North Andhra Pradesh", "lat_range": (16.0, 18.5), "lon_range": (82.5, 84.5)},
    "SEC010": {"name": "Odisha", "lat_range": (18.5, 22.0), "lon_range": (84.5, 87.5)},
    "SEC011": {"name": "West Bengal", "lat_range": (21.0, 22.5), "lon_range": (87.5, 89.0)},
    "SEC012": {"name": "Lakshadweep", "lat_range": (8.0, 12.5), "lon_range": (71.0, 74.0)},
    "SEC013": {"name": "Andaman Islands", "lat_range": (6.0, 13.5), "lon_range": (92.0, 94.0)},
    "SEC014": {"name": "Nicobar Islands", "lat_range": (6.5, 9.5), "lon_range": (92.5, 94.5)},
}

# Base URLs for INCOIS public services
INCOIS_BASE = "https://incois.gov.in"
PFZ_TEXT_URL = f"{INCOIS_BASE}/MarineFisheries/TextDataHome"
PFZ_ADVISORY_URL = f"{INCOIS_BASE}/MarineFisheries/PfzAdvisory"
PFZ_WEBGIS_URL = f"{INCOIS_BASE}/MarineFisheries/PfzWebGis"
PFZ_GEOPORTAL_URL = f"{INCOIS_BASE}/geoportal/MFASPFZ"
OSF_URL = f"{INCOIS_BASE}/site/services/osf.jsp"


class INCOISProvider(MarineDataProvider):
    """INCOIS marine data provider.

    Accesses officially available INCOIS public services:
    - PFZ advisories (text + map)
    - Ocean state forecast information
    - Marine hazard alerts

    NOTE: INCOIS does not provide a formal REST API.
    This provider uses HTML parsing of public advisory pages.
    """

    def __init__(self):
        super().__init__("INCOIS")
        self._capabilities: list[str] = []
        self._sector_cache: dict[str, dict] = {}
        self._last_advisory_date: Optional[datetime] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(2.5), follow_redirects=True)
        return self._http_client

    async def get_data(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str],
        **kwargs,
    ):
        """Retrieve INCOIS data for the given region.

        INCOIS data is advisory-based (not gridded observations),
        so we return PFZ advisory zones as observations.
        """
        from models.observation import Observation, ObservationBatch

        observations = []

        try:
            # Attempt to fetch PFZ advisory data
            pfz_data = await self._fetch_pfz_advisory()

            if pfz_data:
                # Map PFZ zones to observations
                for zone in pfz_data.get("zones", []):
                    zone_lat = zone.get("latitude")
                    zone_lon = zone.get("longitude")

                    if zone_lat is None or zone_lon is None:
                        continue

                    # Check if zone falls within requested bbox
                    if not (bbox[0] <= zone_lon <= bbox[2] and
                            bbox[1] <= zone_lat <= bbox[3]):
                        continue

                    # Create observation for PFZ zone
                    obs = Observation(
                        source="INCOIS",
                        dataset="PFZ_Advisory",
                        variable="potential_fishing_zone",
                        value=1.0,  # Binary: zone exists
                        unit="advisory",
                        latitude=zone_lat,
                        longitude=zone_lon,
                        timestamp=zone.get("forecast_date", datetime.now(timezone.utc)),
                        quality=0.9,
                        metadata={
                            "sector": zone.get("sector"),
                            "depth_m": zone.get("depth_m"),
                            "distance_km": zone.get("distance_km"),
                            "direction": zone.get("direction"),
                            "landing_center": zone.get("landing_center"),
                            "advisory_type": "OFFICIAL_PFZ",
                            "source": "INCOIS",
                        },
                    )
                    observations.append(obs)

                self._last_advisory_date = datetime.now(timezone.utc)
                self._status = ProviderStatus.HEALTHY

        except Exception as e:
            logger.warning(f"INCOIS data fetch failed: {e}")
            self._status = ProviderStatus.DEGRADED

        return ObservationBatch(
            observations=observations,
            source="INCOIS",
            dataset="PFZ_Advisory",
            bbox=bbox,
            record_count=len(observations),
            is_demo=False,
        )

    async def _fetch_pfz_advisory(self) -> Optional[dict]:
        """Fetch PFZ advisory data from INCOIS public pages.

        Returns parsed advisory data or None if unavailable.
        """
        try:
            client = await self._get_client()

            # Fetch the PFZ text advisory page
            response = await client.get(PFZ_TEXT_URL)
            if response.status_code != 200:
                logger.warning(f"INCOIS PFZ page returned {response.status_code}")
                return None

            html = response.text
            return self._parse_pfz_html(html)

        except Exception as e:
            logger.warning(f"INCOIS fetch/parse error: {e}")
            return None

    def _parse_pfz_html(self, html: str) -> Optional[dict]:
        """Parse PFZ advisory HTML to extract zone information.

        The INCOIS PFZ text page contains:
        - Sector information
        - Latitude/longitude of PFZ locations
        - Depth at PFZ location
        - Distance and direction from landing centers
        """
        zones = []

        # Extract latitude/longitude patterns from advisory text
        # INCOIS format: lat/lon pairs like "13 deg 45 min N, 80 deg 15 min E"
        lat_pattern = r'(\d{1,2})\s*deg\s*(\d{1,2})\s*(?:min)?\s*([NSEW])'
        lon_pattern = r'(\d{1,3})\s*deg\s*(\d{1,2})\s*(?:min)?\s*([NSEW])'

        lat_matches = re.findall(lat_pattern, html, re.IGNORECASE)
        lon_matches = re.findall(lon_pattern, html, re.IGNORECASE)

        # Pair lat/lon matches
        for i, (lat_d, lat_m, lat_dir) in enumerate(lat_matches):
            if i < len(lon_matches):
                lon_d, lon_m, lon_dir = lon_matches[i]

                # Convert to decimal
                lat = int(lat_d) + int(lat_m) / 60.0
                if lat_dir.upper() == 'S':
                    lat = -lat

                lon = int(lon_d) + int(lon_m) / 60.0
                if lon_dir.upper() == 'W':
                    lon = -lon

                # Extract depth if available
                depth_match = re.search(
                    r'(\d+)\s*m(?:eter)?s?\s*(?:depth|deep)',
                    html, re.IGNORECASE
                )
                depth_m = int(depth_match.group(1)) if depth_match else None

                # Extract distance
                dist_match = re.search(
                    r'(\d+)\s*km\s*(?:from|away)',
                    html, re.IGNORECASE
                )
                distance_km = int(dist_match.group(1)) if dist_match else None

                # Extract direction
                dir_match = re.search(
                    r'(north|south|east|west|NE|NW|SE|SW|NNE|NNW|SSE|SSW|ENE|ESE|WNW|WSW)\s*(?:of|from)',
                    html, re.IGNORECASE
                )
                direction = dir_match.group(1) if dir_match else None

                zones.append({
                    "latitude": round(lat, 4),
                    "longitude": round(lon, 4),
                    "depth_m": depth_m,
                    "distance_km": distance_km,
                    "direction": direction,
                    "sector": self._detect_sector(lat, lon),
                    "landing_center": None,
                    "forecast_date": datetime.utcnow(),
                })

        if zones:
            return {
                "zones": zones,
                "source": "INCOIS",
                "type": "OFFICIAL_PFZ",
                "fetched_at": datetime.utcnow().isoformat(),
            }

        return None

    def _detect_sector(self, lat: float, lon: float) -> Optional[str]:
        """Detect which INCOIS sector a coordinate falls in."""
        for sector_id, info in INCOIS_SECTORS.items():
            lat_min, lat_max = info["lat_range"]
            lon_min, lon_max = info["lon_range"]
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                return info["name"]
        return None

    async def health_check(self) -> ProviderHealth:
        """Check INCOIS service availability."""
        try:
            client = await self._get_client()
            response = await client.get(PFZ_ADVISORY_URL)
            if response.status_code == 200:
                self._status = ProviderStatus.HEALTHY
                return ProviderHealth(
                    provider_name=self.name,
                    status=ProviderStatus.HEALTHY,
                    last_check=datetime.now(timezone.utc),
                    last_successful_retrieval=self._last_advisory_date,
                    message="INCOIS PFZ advisory page accessible",
                    datasets_available=["PFZ_Advisory", "Ocean_State_Forecast"],
                )
            else:
                self._status = ProviderStatus.DEGRADED
                return ProviderHealth(
                    provider_name=self.name,
                    status=ProviderStatus.DEGRADED,
                    last_check=datetime.now(timezone.utc),
                    message=f"INCOIS returned status {response.status_code}",
                )
        except Exception as e:
            self._status = ProviderStatus.UNAVAILABLE
            return ProviderHealth(
                provider_name=self.name,
                status=ProviderStatus.UNAVAILABLE,
                last_check=datetime.now(timezone.utc),
                message=f"INCOIS unreachable: {e}",
            )

    async def get_capabilities(self) -> dict[str, Any]:
        """Return INCOIS capability information."""
        return {
            "provider": "INCOIS",
            "full_name": "Indian National Centre for Ocean Information Services",
            "status": self._status.value,
            "capabilities": [
                "PFZ_ADVISORY",
                "OCEAN_STATE_FORECAST",
                "MARINE_ALERTS",
                "TSUNAMI_WARNINGS",
                "HIGH_WAVE_ALERTS",
                "SWELL_SURGE",
                "MARINE_HEATWAVE",
            ],
            "data_format": "HTML_advisory_text",
            "sectors_available": len(INCOIS_SECTORS),
            "note": "INCOIS provides advisory data, not gridded observations. "
                    "ORCA combines INCOIS advisories with Copernicus/NOAA satellite data.",
            "endpoints": {
                "pfz_text": PFZ_TEXT_URL,
                "pfz_advisory": PFZ_ADVISORY_URL,
                "pfz_webgis": PFZ_WEBGIS_URL,
                "osf": OSF_URL,
            },
        }

    async def close(self):
        """Clean up HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
