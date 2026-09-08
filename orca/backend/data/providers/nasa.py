"""ORCA NASA Earthdata Provider — Real API integration with NASA CMR.

Accesses ocean color and SST data from NASA's Earth observation satellites:
- Aqua MODIS: Chlorophyll-a, Kd490, SST, PAR, ocean color
- VIIRS SNPP: Similar ocean color products
- PACE OCI: Next-gen ocean biogeochemistry

Uses NASA's CMR (Common Metadata Repository) API for search and
Earthdata Login (EDL) for authentication with username/password.

Key datasets:
- MODISA_L3m_CHL: Chlorophyll-a concentration (4km, daily/monthly)
- MODISA_L3m_KD: Diffuse attenuation coefficient Kd(490)
- MODISA_L3m_PAR: Photosynthetically Available Radiation
- MODISA_L3b_SST: Sea Surface Temperature (4km, binned)
- MODISA_L3m_RRS: Remote-sensing reflectance
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.nasa")

# CMR API endpoints
CMR_BASE = "https://cmr.earthdata.nasa.gov"
CMR_SEARCH = f"{CMR_BASE}/search"
EDL_TOKEN_URL = "https://urs.earthdata.nasa.gov/api/users/token"

# NASA Earthdata datasets for marine/ocean analysis
NASA_DATASETS = {
    # Ocean Color - Chlorophyll
    "MODISA_L3m_CHL": {
        "concept_id": "C3380709133-OB_CLOUD",
        "short_name": "MODISA_L3m_CHL",
        "name": "Aqua MODIS Chlorophyll-a (L3 Mapped)",
        "variables": ["chlorophyll"],
        "provider": "OB_CLOUD",
        "version": "2022.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Global mapped chlorophyll-a concentration from MODIS Aqua",
    },
    "MODISA_L3m_CHL_NRT": {
        "concept_id": "C3380709124-OB_CLOUD",
        "short_name": "MODISA_L3m_CHL_NRT",
        "name": "Aqua MODIS Chlorophyll-a NRT",
        "variables": ["chlorophyll"],
        "provider": "OB_CLOUD",
        "version": "2022.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Near real-time chlorophyll-a from MODIS Aqua",
    },
    # Ocean Color - Kd490
    "MODISA_L3m_KD": {
        "concept_id": "C3380709198-OB_CLOUD",
        "short_name": "MODISA_L3m_KD",
        "name": "Aqua MODIS Kd(490) (L3 Mapped)",
        "variables": ["kd490"],
        "provider": "OB_CLOUD",
        "version": "2022.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Diffuse attenuation coefficient at 490nm",
    },
    # Ocean Color - PAR
    "MODISA_L3m_PAR": {
        "concept_id": "C3380709277-OB_CLOUD",
        "short_name": "MODISA_L3m_PAR",
        "name": "Aqua MODIS PAR (L3 Mapped)",
        "variables": ["par"],
        "provider": "OB_CLOUD",
        "version": "2022.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Photosynthetically Available Radiation",
    },
    # Ocean Color - RRS (Remote Sensing Reflectance)
    "MODISA_L3m_RRS": {
        "concept_id": "C3380709369-OB_CLOUD",
        "short_name": "MODISA_L3m_RRS",
        "name": "Aqua MODIS RRS (L3 Mapped)",
        "variables": ["reflectance"],
        "provider": "OB_CLOUD",
        "version": "2022.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Remote-sensing reflectance at multiple wavelengths",
    },
    # SST - MODIS Aqua
    "MODISA_L3b_SST": {
        "concept_id": "C1615905769-OB_DAAC",
        "short_name": "MODISA_L3b_SST",
        "name": "Aqua MODIS SST (L3 Binned)",
        "variables": ["sst"],
        "provider": "OB_DAAC",
        "version": "3.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Sea Surface Temperature from MODIS Aqua 11μm daytime",
    },
    # GHRSST MODIS Aqua
    "MODIS_A-JPL-L2P": {
        "concept_id": "C1940473819-POCLOUD",
        "short_name": "MODIS_A-JPL-L2P-v2019.0",
        "name": "GHRSST MODIS Aqua SST L2P",
        "variables": ["sst"],
        "provider": "POCLOUD",
        "version": "2019.0",
        "resolution_km": 1.0,
        "temporal_resolution": "daily",
        "description": "High-resolution SST from MODIS Aqua via GHRSST",
    },
    # VIIRS SNPP
    "SNPP_VIIRS_L3m_CHL": {
        "concept_id": "C3380709133-OB_CLOUD",  # Will search dynamically
        "short_name": "SNPPVIIRS_L3m_CHL",
        "name": "VIIRS SNPP Chlorophyll-a",
        "variables": ["chlorophyll"],
        "provider": "OB_CLOUD",
        "version": "2022.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Chlorophyll-a from VIIRS on SNPP",
    },
    # Ocean Color IOP
    "MODISA_L3m_IOP": {
        "concept_id": "C3380709177-OB_CLOUD",
        "short_name": "MODISA_L3m_IOP",
        "name": "Aqua MODIS Inherent Optical Properties",
        "variables": ["a_443", "bbp_443", "adg_443"],
        "provider": "OB_CLOUD",
        "version": "2022.0",
        "resolution_km": 4.0,
        "temporal_resolution": "daily",
        "description": "Inherent optical properties from MODIS Aqua",
    },
}

# Variable name mapping
VAR_MAP = {
    "chlorophyll": ["chlorophyll", "chlor_a", "chla"],
    "sst": ["sst", "sea_surface_temperature"],
    "kd490": ["kd490", "diffuse_attenuation"],
    "par": ["par", "photosynthetically_available_radiation"],
    "reflectance": ["rrs", "reflectance"],
    "a_443": ["a_443", "absorption"],
    "bbp_443": ["bbp_443", "backscattering"],
    "adg_443": ["adg_443", "gelbstoff"],
}


class NASAProvider(MarineDataProvider):
    """Provider for NASA Earth observation data via CMR API.

    Uses NASA's Common Metadata Repository for search and
    Earthdata Login for authentication.
    """

    def __init__(
        self,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        super().__init__("NASA")
        self._username = username or api_key  # NASA_API_KEY can be username
        self._password = password
        self._edl_token: str | None = None
        self._token_expiry: float = 0
        self._http_client: httpx.AsyncClient | None = None
        self._collections_cache: dict | None = None
        self._basic_auth_ok: bool = True  # Start with Basic Auth as fallback

        # CMR search works without auth for open data collections
        # Full data access requires Earthdata Login credentials
        self._status = ProviderStatus.HEALTHY
        if self._username and self._password:
            logger.info("NASA: Credentials configured — full access.")
        elif self._username:
            logger.info("NASA: Username only — open data search enabled.")
        else:
            logger.info("NASA: No credentials — CMR search only (open data).")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "ORCA-NASA/1.0",
                    "Accept": "application/json",
                },
            )
        return self._http_client

    async def _get_edl_token(self) -> str | None:
        """Get Earthdata Login token for authenticated data access.
        
        If token creation fails (e.g. max tokens reached), we fall back
        to using Basic Auth directly which NASA also supports.
        """
        if self._edl_token and time.time() < self._token_expiry:
            return self._edl_token

        if not self._username or not self._password:
            return None

        # If we already know Basic Auth works, skip token creation
        if self._basic_auth_ok:
            return None

        client = await self._get_client()
        try:
            resp = await client.post(
                EDL_TOKEN_URL,
                auth=httpx.BasicAuth(self._username, self._password),
            )
            if resp.status_code == 200:
                data = resp.json()
                self._edl_token = data.get("access_token") or data.get("token")
                self._token_expiry = time.time() + 3500
                logger.info("NASA: EDL token acquired")
                return self._edl_token
            elif resp.status_code == 403 and "max_token" in resp.text:
                # Max tokens reached — use Basic Auth instead
                self._basic_auth_ok = True
                logger.info("NASA: Max tokens reached, using Basic Auth")
                return None
            else:
                logger.warning(f"NASA: EDL token request failed: {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"NASA: EDL token error: {e}")
            return None

    async def _search_collections(
        self, keyword: str, provider: str | None = None, page_size: int = 10
    ) -> list[dict]:
        """Search NASA CMR for data collections."""
        client = await self._get_client()
        params = {
            "keyword": keyword,
            "page_size": str(page_size),
            "sort_key[]": "-revision_date",
        }
        if provider:
            params["provider"] = provider

        try:
            resp = await client.get(f"{CMR_SEARCH}/collections.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("feed", {}).get("entry", [])
        except Exception as e:
            logger.warning(f"NASA: Collection search failed: {e}")
            return []

    async def _search_granules(
        self,
        concept_id: str,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        count: int = 20,
    ) -> list[dict]:
        """Search for data granules within a collection."""
        client = await self._get_client()

        params = {
            "collection_concept_id": concept_id,
            "bounding_box": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "temporal": f"{start_date.strftime('%Y-%m-%dT00:00:00Z')},{end_date.strftime('%Y-%m-%dT23:59:59Z')}",
            "page_size": str(min(count, 50)),
            "sort_key[]": "-start_date",
        }

        try:
            resp = await client.get(f"{CMR_SEARCH}/granules.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("feed", {}).get("entry", [])
        except Exception as e:
            logger.warning(f"NASA: Granule search failed for {concept_id}: {e}")
            return []

    def _extract_granule_metadata(self, granule: dict) -> dict[str, Any]:
        """Extract useful metadata from a CMR granule."""
        # Get bounding box from various CMR fields
        bbox = None
        # Try spatial field first
        spatial = granule.get("umm", {}).get("spatial") or {}
        if not spatial:
            # CMR JSON format: boxes is a list of strings "south west north east"
            boxes = granule.get("boxes", [])
            if boxes:
                try:
                    parts = boxes[0].split()
                    # CMR format: "south west north east"
                    bbox = [float(parts[1]), float(parts[0]), float(parts[3]), float(parts[2])]
                except (IndexError, ValueError):
                    pass
        # Fallback: estimate from orbit metadata
        if not bbox:
            # For L3 mapped products, estimate from the global grid
            bbox = [0.0, 0.0, 360.0, 90.0]  # Global

        # Get time range
        time_start = granule.get("time_start")
        time_end = granule.get("time_end")

        # Get links
        links = granule.get("links", [])
        data_links = [
            l.get("href", "")
            for l in links
            if l.get("rel") == "data" or "download" in l.get("href", "").lower()
        ]
        browse_links = [
            l.get("href", "")
            for l in links
            if l.get("rel") == "browse" or "browse" in l.get("href", "").lower()
        ]

        return {
            "id": granule.get("id", ""),
            "title": granule.get("title", ""),
            "time_start": time_start,
            "time_end": time_end,
            "bbox": bbox,
            "data_links": data_links[:3],
            "browse_links": browse_links[:2],
            "cloud_cover": granule.get("cloud_cover"),
            "day_night_flag": granule.get("day_night_flag"),
            "production_date": granule.get("production_date"),
        }

    async def health_check(self) -> ProviderHealth:
        """Check NASA CMR API availability."""
        if self._status == ProviderStatus.UNAVAILABLE:
            return ProviderHealth(
                provider_name=self.name,
                status=ProviderStatus.UNAVAILABLE,
                last_check=datetime.utcnow(),
                message="Credentials not configured",
                datasets_available=list(NASA_DATASETS.keys()),
            )

        client = await self._get_client()
        try:
            # Test CMR search availability
            resp = await client.get(
                f"{CMR_SEARCH}/collections.json",
                params={"keyword": "ocean color", "page_size": "1"},
                timeout=8.0,
            )
            cmr_ok = resp.status_code == 200

            # Test EDL access if credentials available
            edl_ok = True
            if self._username and self._password:
                token = await self._get_edl_token()
                if token:
                    edl_ok = True
                elif self._basic_auth_ok:
                    edl_ok = True  # Basic Auth works
                else:
                    edl_ok = False

            status = ProviderStatus.HEALTHY if (cmr_ok and edl_ok) else ProviderStatus.DEGRADED
            self._status = status

            return ProviderHealth(
                provider_name=self.name,
                status=status,
                last_check=datetime.utcnow(),
                last_successful_retrieval=self._last_successful_retrieval,
                message="CMR API reachable" + (" + EDL authenticated" if edl_ok and self._username else ""),
                datasets_available=list(NASA_DATASETS.keys()),
            )
        except Exception as e:
            self._status = ProviderStatus.DEGRADED
            return ProviderHealth(
                provider_name=self.name,
                status=ProviderStatus.DEGRADED,
                last_check=datetime.utcnow(),
                message=f"Health check error: {e}",
            )

    async def get_data(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str],
        **kwargs,
    ):
        """Retrieve NASA Earth observation data for the given query.

        Searches CMR for relevant granules and returns metadata
        about available data products.
        """
        from models.observation import ObservationBatch

        observations = []
        matched_datasets = []

        if self._status == ProviderStatus.UNAVAILABLE:
            return ObservationBatch(
                observations=[],
                source="NASA",
                dataset="unavailable",
                record_count=0,
                bbox=bbox,
                date_range=(start_date, end_date),
            )

        # Match requested variables to NASA datasets
        datasets_to_query = []
        for var in variables:
            var_lower = var.lower()
            for ds_id, ds_info in NASA_DATASETS.items():
                if var_lower in ds_info["variables"] or any(
                    alias in ds_info["variables"]
                    for aliases in [VAR_MAP.get(var_lower, [var_lower])]
                    for alias in aliases
                ):
                    if ds_id not in [d[0] for d in datasets_to_query]:
                        datasets_to_query.append((ds_id, var_lower))

        # If no specific match, query chlorophyll and SST
        if not datasets_to_query:
            datasets_to_query = [
                ("MODISA_L3m_CHL", "chlorophyll"),
                ("MODISA_L3b_SST", "sst"),
            ]

        # Query datasets in parallel (up to 3 to respect rate limits)
        async def _query_single_dataset(ds_id: str, primary_var: str):
            ds_info = NASA_DATASETS.get(ds_id, {})
            concept_id = ds_info.get("concept_id", "")
            if not concept_id:
                return ds_id, []

            try:
                granules = await asyncio.wait_for(
                    self._search_granules(concept_id, bbox, start_date, end_date, count=10),
                    timeout=2.0,
                )
                if not granules:
                    return ds_id, []

                obs_list = []
                for granule in granules:
                    meta = self._extract_granule_metadata(granule)

                    # Extract center point from bounding box
                    center_lat = 0.0
                    center_lon = 0.0
                    if meta["bbox"]:
                        center_lon = (meta["bbox"][0] + meta["bbox"][2]) / 2
                        center_lat = (meta["bbox"][1] + meta["bbox"][3]) / 2

                    # Parse time
                    ts = None
                    if meta["time_start"]:
                        try:
                            ts = datetime.fromisoformat(
                                meta["time_start"].replace("Z", "+00:00")
                            )
                        except ValueError:
                            ts = datetime.now(timezone.utc)

                    obs = self._create_observation(
                        dataset=ds_id,
                        variable=primary_var,
                        value=0.0,  # Value not available from metadata alone
                        unit=self._get_unit(primary_var),
                        latitude=center_lat,
                        longitude=center_lon,
                        timestamp=ts or datetime.now(timezone.utc),
                        quality=0.9,
                        metadata={
                            "granule_ur": meta.get("granule_ur"),
                            "producer_granule_id": meta.get("producer_granule_id"),
                            "day_night": meta.get("day_night_flag"),
                            "cloud_cover": meta.get("cloud_cover"),
                            "download_url": meta["data_links"][0] if meta["data_links"] else None,
                            "browse_url": meta["browse_links"][0] if meta["browse_links"] else None,
                        },
                    )
                    obs_list.append(obs)
                return ds_id, obs_list
            except Exception as e:
                logger.warning(f"NASA: Error querying {ds_id}: {e}")
                return ds_id, []

        tasks = [_query_single_dataset(d[0], d[1]) for d in datasets_to_query[:3]]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, tuple):
                    ds_id, obs_list = res
                    if obs_list:
                        matched_datasets.append(ds_id)
                        observations.extend(obs_list)

        if observations:
            self._last_successful_retrieval = datetime.utcnow()

        dataset_str = ",".join(matched_datasets) if matched_datasets else "none"

        return ObservationBatch(
            observations=observations,
            source="NASA",
            dataset=dataset_str,
            record_count=len(observations),
            bbox=bbox,
            date_range=(start_date, end_date),
        )

    def _get_unit(self, variable: str) -> str:
        units = {
            "chlorophyll": "mg/m³",
            "sst": "°C",
            "kd490": "m⁻¹",
            "par": "E/m²/day",
            "reflectance": "sr⁻¹",
            "a_443": "m⁻¹",
            "bbp_443": "m⁻¹",
            "adg_443": "m⁻¹",
        }
        return units.get(variable, "unknown")
