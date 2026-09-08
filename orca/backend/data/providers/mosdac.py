"""ORCA ISRO/MOSDAC Provider — Real API integration with MOSDAC download API.

MOSDAC (Meteorological & Oceanographic Satellite Data Archival Centre) provides
Indian Earth observation data from ISRO satellites including:
- INSAT-3D/3DR: Atmospheric profiles, SST, OLR
- Oceansat-2/3: Ocean color (chlorophyll, sediment), scatterometer winds
- RISAT: SAR data
- EOS: Earth observation

API endpoints (from official mdapi.py):
- POST /download_api/gettoken    → authenticate, get bearer token
- GET  /apios/datasets.json      → list all available datasets
- POST /download_api/download    → download granule data
- GET  /download_api/check-internet → connectivity check
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.mosdac")

# MOSDAC API base URLs
_BASE = "https://mosdac.gov.in"
TOKEN_URL = f"{_BASE}/download_api/gettoken"
DATASETS_URL = f"{_BASE}/apios/datasets.json"
DOWNLOAD_URL = f"{_BASE}/download_api/download"
CHECK_INTERNET_URL = f"{_BASE}/download_api/check-internet"
REFRESH_URL = f"{_BASE}/download_api/refresh-token"
LOGOUT_URL = f"{_BASE}/download_api/logout"

# MOSDAC datasets relevant to marine/ocean analysis
# These are the actual datasetIds from the MOSDAC catalog
MARINE_DATASETS = {
    # Oceansat-3 (EOS-06) Ocean Color Monitor — chlorophyll, sediment, Kd490
    "O3OCM_L2C_STD": {
        "name": "Oceansat-3 OCM Level 2C",
        "variables": ["chlorophyll", "sediment", "kd490"],
        "description": "Ocean color parameters from OCM-3 on Oceansat-3",
        "resolution_km": 1.0,
    },
    "O2OCM_L2C_STD": {
        "name": "Oceansat-2 OCM Level 2C",
        "variables": ["chlorophyll", "sediment", "kd490"],
        "description": "Ocean color parameters from OCM-2 on Oceansat-2",
        "resolution_km": 4.0,
    },
    "O2OCM_L3G_AQUA": {
        "name": "Oceansat-2 OCM Level 3 Gridded",
        "variables": ["chlorophyll", "sediment"],
        "description": "Gridded ocean color products",
        "resolution_km": 4.0,
    },
    # INSAT-3D/3DR — SST, OLR, atmospheric
    "3RIMG_L2B_SST": {
        "name": "INSAT-3R IMAGER SST",
        "variables": ["sst"],
        "description": "Sea surface temperature from INSAT-3R imager",
        "resolution_km": 4.0,
    },
    "3DIMG_L2B_SST": {
        "name": "INSAT-3D IMAGER SST",
        "variables": ["sst"],
        "description": "Sea surface temperature from INSAT-3D imager",
        "resolution_km": 4.0,
    },
    "3DIMG_L2B_OLR": {
        "name": "INSAT-3D Outgoing Longwave Radiation",
        "variables": ["olr"],
        "description": "Outgoing longwave radiation for atmospheric analysis",
        "resolution_km": 4.0,
    },
    # Scatterometer winds
    "O2SCT_L2B_WIND": {
        "name": "Oceansat-2 Scatterometer Wind",
        "variables": ["wind_speed", "wind_direction"],
        "description": "Ocean surface wind vector from OSCAT",
        "resolution_km": 50.0,
    },
    "O2SCT_L3W_DAILYAWV": {
        "name": "Oceansat-2 Daily Analyzed Wind Vector",
        "variables": ["wind_speed", "wind_direction", "wind_stress"],
        "description": "Daily gridded wind product at 0.5 degree",
        "resolution_km": 55.0,
    },
    # RISAT SAR
    "R2SAR_L2B_STD": {
        "name": "RISAT-1 SAR Level 2B",
        "variables": ["sar_backscatter"],
        "description": "SAR backscatter from RISAT-1",
        "resolution_km": 1.0,
    },
}

# Variable to MOSDAC variable name mapping
VARIABLE_MAP = {
    "sst": ["sst", "sea_surface_temperature"],
    "chlorophyll": ["chlorophyll", "chlor_a", "chla"],
    "sediment": ["sediment", "turbidity", "nflh"],
    "kd490": ["kd490", "diffuse_attenuation"],
    "wind_speed": ["wind_speed", "windspd"],
    "wind_direction": ["wind_direction", "winddir"],
    "wind_stress": ["wind_stress"],
    "olr": ["olr", "outgoing_longwave_radiation"],
    "sar_backscatter": ["sigma0", "backscatter"],
}


class MOSDACProvider(MarineDataProvider):
    """Provider for ISRO MOSDAC Earth observation datasets.

    Authenticates via MOSDAC's download API using username/password,
    searches the dataset catalog, and retrieves ocean observation data.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        super().__init__("MOSDAC")
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_expiry: float = 0
        self._datasets_cache: dict | None = None
        self._http_client: httpx.AsyncClient | None = None

        if username and password:
            self._status = ProviderStatus.HEALTHY
            logger.info("MOSDAC: Credentials configured, provider ready.")
        else:
            self._status = ProviderStatus.UNAVAILABLE
            logger.warning("MOSDAC: No credentials configured. Set MOSDAC_USERNAME and MOSDAC_PASSWORD.")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "ORCA-MOSDAC/1.0",
                    "Accept": "application/json",
                },
            )
        return self._http_client

    async def _authenticate(self) -> str:
        """Get or refresh a MOSDAC API token."""
        if self._token and time.time() < self._token_expiry:
            return self._token

        if not self._username or not self._password:
            raise ValueError("MOSDAC credentials not configured")

        client = await self._get_client()
        try:
            resp = await client.post(
                TOKEN_URL,
                json={"username": self._username, "password": self._password},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("token") or data.get("access_token") or data.get("jwt")
            if not self._token:
                # Some MOSDAC APIs return the token directly as a string
                if isinstance(data, str):
                    self._token = data
                else:
                    raise ValueError(f"No token in response: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            # Tokens typically last 30 minutes
            self._token_expiry = time.time() + 1500
            logger.info("MOSDAC: Authentication successful")
            return self._token
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("MOSDAC: Rate limited, waiting 25s...")
                await asyncio.sleep(25)
                # Retry once
                resp = await client.post(
                    TOKEN_URL,
                    json={"username": self._username, "password": self._password},
                )
                resp.raise_for_status()
                data = resp.json()
                self._token = data.get("token") or data.get("access_token")
                self._token_expiry = time.time() + 1500
                return self._token
            raise

    async def _get_datasets(self) -> list[dict]:
        """Fetch the MOSDAC dataset catalog."""
        if self._datasets_cache is not None:
            return self._datasets_cache

        client = await self._get_client()
        try:
            resp = await client.get(DATASETS_URL)
            resp.raise_for_status()
            data = resp.json()
            self._datasets_cache = data if isinstance(data, list) else []
            logger.info(f"MOSDAC: Loaded {len(self._datasets_cache)} datasets from catalog")
            return self._datasets_cache
        except Exception as e:
            logger.warning(f"MOSDAC: Failed to load dataset catalog: {e}")
            return []

    async def _search_data(
        self,
        dataset_id: str,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        count: int = 50,
    ) -> list[dict]:
        """Search for data granules in a dataset."""
        client = await self._get_client()
        token = await self._authenticate()

        bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

        # MOSDAC download API search uses the /download endpoint with search params
        search_payload = {
            "datasetId": dataset_id,
            "startTime": start_date.strftime("%Y-%m-%d"),
            "endTime": end_date.strftime("%Y-%m-%d"),
            "count": str(min(count, 100)),
            "boundingBox": bbox_str,
            "gId": "",
        }

        headers = {"Authorization": f"Bearer {token}"}

        try:
            # Try the download API search
            resp = await client.post(
                DOWNLOAD_URL,
                json=search_payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get("results", data.get("data", data.get("granules", [])))
            return []
        except httpx.HTTPStatusError as e:
            logger.warning(f"MOSDAC: Search failed for {dataset_id}: {e.response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"MOSDAC: Search error for {dataset_id}: {e}")
            return []

    async def _fetch_granule_data(
        self, granule: dict, variable: str
    ) -> list[dict[str, Any]]:
        """Fetch and parse a single granule's data.

        MOSDAC granules contain metadata (lat, lon, time, value).
        For browse/download products, we extract the metadata directly.
        """
        observations = []

        try:
            # Extract location and time from granule metadata
            lat = granule.get("latitude") or granule.get("lat")
            lon = granule.get("longitude") or granule.get("lon")
            timestamp_str = (
                granule.get("startTime")
                or granule.get("date")
                or granule.get("time")
                or granule.get("startTimeGMT")
            )
            value = granule.get("value") or granule.get("dataValue")

            if lat is not None and lon is not None:
                obs = {
                    "lat": float(lat),
                    "lon": float(lon),
                    "variable": variable,
                    "value": float(value) if value is not None else None,
                    "timestamp": timestamp_str,
                    "dataset": granule.get("datasetId", granule.get("productName", "MOSDAC")),
                    "source": "MOSDAC",
                    "granule_id": granule.get("gId", granule.get("id", "")),
                    "file_size": granule.get("fileSize"),
                    "download_url": granule.get("downloadUrl", granule.get("ftpPath", "")),
                }
                observations.append(obs)

            # Some granules have multiple data points
            data_points = granule.get("dataPoints", granule.get("points", []))
            for dp in data_points:
                if isinstance(dp, dict):
                    observations.append({
                        "lat": float(dp.get("lat", lat or 0)),
                        "lon": float(dp.get("lon", lon or 0)),
                        "variable": variable,
                        "value": float(dp.get("value", 0)),
                        "timestamp": dp.get("time", timestamp_str),
                        "dataset": granule.get("datasetId", "MOSDAC"),
                        "source": "MOSDAC",
                        "granule_id": granule.get("gId", ""),
                    })
        except (ValueError, TypeError) as e:
            logger.debug(f"MOSDAC: Failed to parse granule: {e}")

        return observations

    async def health_check(self) -> ProviderHealth:
        """Check MOSDAC API availability."""
        if self._status == ProviderStatus.UNAVAILABLE:
            return ProviderHealth(
                provider_name=self.name,
                status=ProviderStatus.UNAVAILABLE,
                last_check=datetime.utcnow(),
                message="Credentials not configured",
                datasets_available=list(MARINE_DATASETS.keys()),
            )

        client = await self._get_client()
        try:
            # Check internet connectivity
            resp = await client.get(CHECK_INTERNET_URL, timeout=8.0)
            api_ok = resp.status_code < 500

            # Try to authenticate
            if api_ok:
                try:
                    await self._authenticate()
                    auth_ok = True
                except Exception as e:
                    auth_ok = False
                    logger.warning(f"MOSDAC: Auth failed during health check: {e}")
            else:
                auth_ok = False

            status = ProviderStatus.HEALTHY if (api_ok and auth_ok) else ProviderStatus.DEGRADED
            self._status = status

            return ProviderHealth(
                provider_name=self.name,
                status=status,
                last_check=datetime.utcnow(),
                last_successful_retrieval=self._last_successful_retrieval,
                message="API reachable" if api_ok else "API unreachable",
                datasets_available=list(MARINE_DATASETS.keys()),
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
        """Retrieve MOSDAC data for the given spatial/temporal query.

        Searches relevant MOSDAC datasets and returns observations
        mapped to ORCA's standard variable names.
        """
        from models.observation import ObservationBatch

        observations = []
        matched_datasets = []

        if self._status == ProviderStatus.UNAVAILABLE:
            return ObservationBatch(
                observations=[],
                source="MOSDAC",
                dataset="unavailable",
                record_count=0,
                bbox=bbox,
                date_range=(start_date, end_date),
            )

        # Match requested variables to MOSDAC datasets
        datasets_to_query = []
        for var in variables:
            var_lower = var.lower()
            for ds_id, ds_info in MARINE_DATASETS.items():
                if var_lower in ds_info["variables"] or any(
                    alias in ds_info["variables"]
                    for aliases in [VARIABLE_MAP.get(var_lower, [var_lower])]
                    for alias in aliases
                ):
                    if ds_id not in [d[0] for d in datasets_to_query]:
                        datasets_to_query.append((ds_id, var_lower))

        # If no specific match, query all marine datasets
        if not datasets_to_query:
            datasets_to_query = [
                (ds_id, ds_info["variables"][0])
                for ds_id, ds_info in list(MARINE_DATASETS.items())[:4]
            ]

        # Query datasets in parallel (up to 3 to respect rate limits)
        async def _query_single_dataset(ds_id: str, primary_var: str):
            try:
                granules = await asyncio.wait_for(
                    self._search_data(ds_id, bbox, start_date, end_date, count=30),
                    timeout=2.0,
                )
                if not granules:
                    return ds_id, []

                obs_list = []
                for granule in granules:
                    raw_obs = await self._fetch_granule_data(granule, primary_var)
                    for raw in raw_obs:
                        if raw.get("value") is not None:
                            obs = self._create_observation(
                                dataset=ds_id,
                                variable=primary_var,
                                value=raw["value"],
                                unit=self._get_unit(primary_var),
                                latitude=raw["lat"],
                                longitude=raw["lon"],
                                timestamp=datetime.fromisoformat(
                                    raw["timestamp"].replace("Z", "+00:00")
                                )
                                if raw.get("timestamp")
                                else datetime.now(timezone.utc),
                                quality=0.8,  # ISRO satellite data quality
                                metadata={
                                    "satellite": self._get_satellite(ds_id),
                                    "sensor": self._get_sensor(ds_id),
                                    "granule_id": raw.get("granule_id", ""),
                                    "resolution_km": MARINE_DATASETS.get(ds_id, {}).get(
                                        "resolution_km", 4.0
                                    ),
                                },
                            )
                            obs_list.append(obs)
                return ds_id, obs_list
            except Exception as e:
                logger.warning(f"MOSDAC: Error querying {ds_id}: {e}")
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
            self._last_successful_retrieval = datetime.now(timezone.utc)

        dataset_str = ",".join(matched_datasets) if matched_datasets else "none"

        return ObservationBatch(
            observations=observations,
            source="MOSDAC",
            dataset=dataset_str,
            record_count=len(observations),
            bbox=bbox,
            date_range=(start_date, end_date),
        )

    def _get_unit(self, variable: str) -> str:
        units = {
            "sst": "°C",
            "chlorophyll": "mg/m³",
            "sediment": "mg/m³",
            "kd490": "m⁻¹",
            "wind_speed": "m/s",
            "wind_direction": "°",
            "wind_stress": "N/m²",
            "olr": "W/m²",
            "sar_backscatter": "dB",
        }
        return units.get(variable, "unknown")

    def _get_satellite(self, dataset_id: str) -> str:
        if "3RIMG" in dataset_id or "3DIMG" in dataset_id:
            return "INSAT-3D/3DR"
        if "O2" in dataset_id:
            return "Oceansat-2"
        if "O3" in dataset_id:
            return "Oceansat-3 (EOS-06)"
        if "R2" in dataset_id:
            return "RISAT-1"
        return "ISRO"

    def _get_sensor(self, dataset_id: str) -> str:
        if "IMG" in dataset_id:
            return "Imager"
        if "OCM" in dataset_id:
            return "OCM"
        if "SCT" in dataset_id:
            return "Scatterometer"
        if "SAR" in dataset_id:
            return "SAR"
        return "Unknown"
