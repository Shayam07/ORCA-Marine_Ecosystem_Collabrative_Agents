"""ORCA Copernicus Marine Provider — Optimized for performance.

Key optimizations:
- Vectorized data extraction (no nested Python loops)
- In-memory caching
- Per-variable parallel fetching
- Timeout protection
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.copernicus")

# Dataset IDs — use NRT (near-real-time) products for current data
# OPENDAP/CMEMS product catalogue:
#   Analysis Forecast: cmems_mod_glo_phy-analysed-forecast_0.083deg_PT1H-i
#   Multi-year:        cmems_mod_glo_phy_my_0.083deg_P1D-m (up to ~3 months old)
#   BIO Multi-year:    cmems_mod_glo_bgc_my_0.25deg_P1D-m
VARIABLE_MAP = {
    "sea_surface_temperature": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "thetao"),
    "sst": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "thetao"),
    "temperature": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "thetao"),
    "chlorophyll": ("cmems_mod_glo_bgc_my_0.25deg_P1D-m", "chl"),
    "chlorophyll_concentration": ("cmems_mod_glo_bgc_my_0.25deg_P1D-m", "chl"),
    "ocean_color": ("cmems_mod_glo_bgc_my_0.25deg_P1D-m", "chl"),
    "salinity": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "so"),
    "sea_water_salinity": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "so"),
    "currents_u": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "uo"),
    "ocean_currents_u": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "uo"),
    "currents_v": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "vo"),
    "ocean_currents_v": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "vo"),
    "wind_speed": ("cmems_mod_glo_phy_my_0.083deg_P1D-m", "u10"),
    "wave_height": ("cmems_mod_glo_wav_my_0.25deg_P1D-m", "VHM0"),
}

UNITS = {
    "sst": "degC", "sea_surface_temperature": "degC", "temperature": "degC",
    "chlorophyll": "mg/m3", "chlorophyll_concentration": "mg/m3", "ocean_color": "mg/m3",
    "salinity": "PSU", "sea_water_salinity": "PSU",
    "currents_u": "m/s", "currents_v": "m/s",
    "ocean_currents_u": "m/s", "ocean_currents_v": "m/s",
}

# In-memory cache: key → (timestamp, observations)
_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL = 300  # 5 minutes


class CopernicusMarineProvider(MarineDataProvider):
    """Provider for Copernicus Marine Service data — optimized."""

    def __init__(self, username: str | None = None, password: str | None = None):
        super().__init__("COPERNICUS_MARINE")
        self._username = username
        self._password = password
        self._logged_in = False
        if username and password:
            self._status = ProviderStatus.HEALTHY
        else:
            self._status = ProviderStatus.UNAVAILABLE
            logger.info("Copernicus Marine: credentials not configured.")

    async def _ensure_login(self):
        if self._logged_in:
            return True
        if not self._username or not self._password:
            self._status = ProviderStatus.UNAVAILABLE
            return False
        try:
            import copernicusmarine
            res = await asyncio.to_thread(
                copernicusmarine.login,
                username=self._username,
                password=self._password,
                force_overwrite=True,
            )
            self._logged_in = bool(res)
            if self._logged_in:
                self._status = ProviderStatus.HEALTHY
                logger.info("Logged into Copernicus Marine successfully")
                return True
            else:
                self._status = ProviderStatus.DEGRADED
                return False
        except Exception as e:
            logger.warning(f"Copernicus login failed: {e}")
            self._status = ProviderStatus.DEGRADED
            return False

    async def health_check(self) -> ProviderHealth:
        if self._status == ProviderStatus.UNAVAILABLE or not (self._username and self._password):
            return ProviderHealth(provider_name=self.name, status=ProviderStatus.UNAVAILABLE,
                                  last_check=datetime.utcnow(), message="Credentials not configured")
        if self._username and self._password:
            self._status = ProviderStatus.HEALTHY
            return ProviderHealth(provider_name=self.name, status=ProviderStatus.HEALTHY,
                                  last_check=datetime.utcnow(), message="Ready")
        return ProviderHealth(provider_name=self.name, status=self._status,
                              last_check=datetime.utcnow())

    def _make_cache_key(self, bbox, start_date, end_date, variable, product_id, cm_var):
        bbox_str = ",".join(f"{b:.2f}" for b in bbox)
        return f"copernicus:{product_id}:{cm_var}:{bbox_str}:{start_date.date()}:{end_date.date()}"

    async def get_data(self, bbox, start_date, end_date, variables=None, **kwargs):
        from models.observation import ObservationBatch

        if self._status == ProviderStatus.UNAVAILABLE or not (self._username and self._password):
            return ObservationBatch(observations=[], source="COPERNICUS_MARINE",
                                    dataset="unavailable", record_count=0,
                                    bbox=bbox, date_range=(start_date, end_date))

        if not await self._ensure_login():
            return ObservationBatch(observations=[], source="COPERNICUS_MARINE",
                                    dataset="login_failed", record_count=0,
                                    bbox=bbox, date_range=(start_date, end_date))

        used_variables = variables or ["chlorophyll", "sst", "salinity"]

        # Copernicus Multi-Year datasets have ~2-3 month latency.
        # Clamp to 90 days ago to stay within actual dataset availability.
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        max_date = now - timedelta(days=90)
        if end_date > max_date:
            logger.info(f"Copernicus: clamping end_date from {end_date.date()} to {max_date.date()} (multi-year latency)")
            end_date = max_date
        if start_date > end_date:
            start_date = end_date - timedelta(days=7)

        # Fetch variables in parallel
        all_observations = []
        fetch_tasks = []
        task_vars = []

        for var_name in used_variables:
            if var_name not in VARIABLE_MAP:
                continue
            product_id, cm_var = VARIABLE_MAP[var_name]
            cache_key = self._make_cache_key(bbox, start_date, end_date, var_name, product_id, cm_var)

            # Check cache
            if cache_key in _cache:
                ts, cached_obs = _cache[cache_key]
                if time.time() - ts < CACHE_TTL:
                    logger.info(f"Copernicus cache hit: {var_name} ({len(cached_obs)} obs)")
                    all_observations.extend(cached_obs)
                    continue

            fetch_tasks.append(self._fetch_variable(var_name, product_id, cm_var, bbox, start_date, end_date))
            task_vars.append(var_name)

        # Execute fetches in parallel with timeout
        if fetch_tasks:
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*fetch_tasks, return_exceptions=True),
                    timeout=15  # 15 second total timeout for all variables
                )
                for var_name, result in zip(task_vars, results):
                    if isinstance(result, Exception):
                        logger.warning(f"Copernicus: {var_name} failed: {result}")
                    elif result:
                        all_observations.extend(result)
                        # Cache the result
                        cache_key = self._make_cache_key(
                            bbox, start_date, end_date, var_name,
                            VARIABLE_MAP[var_name][0], VARIABLE_MAP[var_name][1]
                        )
                        _cache[cache_key] = (time.time(), result)
            except asyncio.TimeoutError:
                logger.warning("Copernicus: parallel fetch timed out after 15s")

        return ObservationBatch(
            observations=all_observations,
            source="COPERNICUS_MARINE",
            dataset="copernicus_marine",
            record_count=len(all_observations),
            bbox=bbox,
            date_range=(start_date, end_date),
        )

    async def _fetch_variable(self, var_name, product_id, cm_var, bbox, start_date, end_date):
        """Fetch a single variable — runs in executor to avoid blocking."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._fetch_variable_sync,
            var_name, product_id, cm_var, bbox, start_date, end_date,
        )

    def _fetch_variable_sync(self, var_name, product_id, cm_var, bbox, start_date, end_date):
        """Synchronous fetch — runs in thread executor."""
        from models.observation import Observation

        observations = []
        west, south, east, north = bbox
        start_str = start_date.strftime("%Y-%m-%dT00:00:00")
        end_str = end_date.strftime("%Y-%m-%dT23:59:59")

        try:
            import copernicusmarine
            import xarray as xr
            import pandas as pd

            with tempfile.TemporaryDirectory() as tmpdir:
                output_file = Path(tmpdir) / f"{var_name}.nc"

                # Subset data
                copernicusmarine.subset(
                    dataset_id=product_id,
                    variables=[cm_var],
                    minimum_longitude=west,
                    maximum_longitude=east,
                    minimum_latitude=south,
                    maximum_latitude=north,
                    start_datetime=start_str,
                    end_datetime=end_str,
                    output_filename=str(output_file),
                )

                if not output_file.exists():
                    return observations

                time.sleep(0.5)  # Ensure file is closed on Windows

                # Load and extract — VECTORIZED, no nested loops
                ds = xr.load_dataset(str(output_file))

                if cm_var not in ds:
                    return observations

                data = ds[cm_var]

                # Select surface layer
                if 'depth' in data.dims:
                    data = data.isel(depth=0)

                # Vectorized extraction: flatten all dimensions at once
                # Limit to max 7 time steps
                if 'time' in data.dims:
                    data = data.isel(time=slice(0, 7))

                # Drop NaN values and extract as arrays
                valid_mask = ~xr.DataArray.isnull(data).values.flatten()
                flat_values = data.values.flatten()[valid_mask]

                # Get coordinates for valid points
                if 'latitude' in data.dims and 'longitude' in data.dims:
                    lats = data.latitude.values
                    lons = data.longitude.values
                    times = data.time.values if 'time' in data.dims else [None]

                    # Create meshgrid of coordinates
                    import numpy as np
                    lat_grid, lon_grid, time_grid = np.meshgrid(
                        lats, lons, times[:len(data.time)] if 'time' in data.dims else [None],
                        indexing='ij'
                    )

                    flat_lats = lat_grid.flatten()[valid_mask]
                    flat_lons = lon_grid.flatten()[valid_mask]
                    flat_times = time_grid.flatten()[valid_mask]

                    for val, lat, lon, ts in zip(flat_values, flat_lats, flat_lons, flat_times):
                        if not np.isnan(val):
                            timestamp = pd.Timestamp(ts).to_pydatetime() if ts is not None else start_date
                            observations.append(Observation(
                                source="COPERNICUS_MARINE",
                                dataset=product_id,
                                variable=var_name,
                                value=float(val),
                                unit=UNITS.get(var_name, "unknown"),
                                latitude=float(lat),
                                longitude=float(lon),
                                timestamp=timestamp,
                                quality=0.85,
                                metadata={"copernicus_variable": cm_var, "product_id": product_id},
                            ))

                logger.info(f"Copernicus: {var_name} → {len(observations)} observations")

        except Exception as e:
            logger.warning(f"Copernicus fetch {var_name} failed: {e}")

        return observations
