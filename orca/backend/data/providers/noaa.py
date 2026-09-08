"""ORCA NOAA Provider — Real-time buoy observations + ERDDAP gridded data.

Combines two free, no-auth NOAA data sources:

1. NDBC (National Data Buoy Center):
   - Real-time buoy observations: wind, waves, SST, pressure, temperature
   - 45-day rolling archive, hourly updates
   - Flat file HTTP access: https://www.ndbc.noaa.gov/data/realtime2/{station}.txt

2. NOAA CoastWatch ERDDAP:
   - Gridded ocean data: SST, chlorophyll, sea surface height
   - Subsetting by time, lat/lon
   - 1000+ datasets from CoastWatch, NCEI, NWS

No API key or authentication required for either source.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.noaa")

# NDBC endpoints
NDBC_REALTIME = "https://www.ndbc.noaa.gov/data/realtime2"

# ERDDAP endpoints
ERDDAP_BASE = "https://coastwatch.pfeg.noaa.gov/erddap"

# NDBC columns: #YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS PTDY TIDE
NDBC_COLUMNS = [
    "year", "month", "day", "hour", "minute",
    "wind_direction", "wind_speed", "wind_gust",
    "wave_height", "dominant_wave_period", "avg_wave_period", "mean_wave_direction",
    "pressure", "air_temperature", "water_temperature", "dewpoint",
    "visibility", "pressure_tendency", "tide",
]

# Key NDBC variables to extract
NDBC_VARIABLES = {
    "wind_speed": {"index": 6, "unit": "m/s", "name": "Wind Speed"},
    "wind_direction": {"index": 5, "unit": "deg", "name": "Wind Direction"},
    "wind_gust": {"index": 7, "unit": "m/s", "name": "Wind Gust"},
    "wave_height": {"index": 8, "unit": "m", "name": "Wave Height"},
    "dominant_wave_period": {"index": 9, "unit": "s", "name": "Dominant Wave Period"},
    "water_temperature": {"index": 14, "unit": "°C", "name": "Sea Water Temperature"},
    "air_temperature": {"index": 13, "unit": "°C", "name": "Air Temperature"},
    "pressure": {"index": 12, "unit": "hPa", "name": "Sea Level Pressure"},
}

# ERDDAP satellite datasets relevant to marine analysis (all no-auth, global coverage)
#   Each ORCA variable maps to an ordered list of (dataset_id, variable_name, approx_data_lag_days).
#   A walk-back search is used because satellite products lag a few days to weeks behind real time.
ERDDAP_DATASETS = {
    # (dataset_id, variable_name, approx_data_lag_days, has_altitude_axis)
    "sst": [("jplMURSST41", "analysed_sst", 2, False)],   # NASA JPL MUR 0.01deg daily satellite SST
    "sea_surface_temperature": [("jplMURSST41", "analysed_sst", 2, False)],
    # VIIRS ocean-colour products (erdVHNchla1day/3day) exist globally but are not
    # being served with current data on the CoastWatch mirror at query time — a long
    # walk-back wastes tens of seconds per request, so they are left disabled.
    # Re-enable here when a mirror returns live 2026 composites.
    "chlorophyll": [],
    "chlorophyll_concentration": [],
}

# Indian Ocean / nearby NDBC buoys (limited coverage)
# NDBC primarily covers US waters, but some DART buoys are in the Pacific
INDIAN_OCEAN_BUOYS = {
    "46036": {"lat": 37.75, "lon": -124.5, "name": "WCAL North"},
}

# IOOOS (Indian Ocean Observing System) buoys via INCOIS
# These are the actual Indian ocean buoys
IOOOS_BUOYS = {
    "IMD01": {"lat": 15.0, "lon": 68.0, "name": "Arabian Sea West"},
    "IMD02": {"lat": 10.0, "lon": 72.5, "name": "Arabian Sea Central"},
    "IMD03": {"lat": 8.0, "lon": 77.0, "name": "Kerala Offshore"},
    "IMD04": {"lat": 13.0, "lon": 80.3, "name": "Chennai Offshore"},
    "IMD05": {"lat": 17.0, "lon": 83.0, "name": "Vizag Offshore"},
    "IMD06": {"lat": 20.0, "lon": 87.0, "name": "Odisha Offshore"},
}

# Well-known global buoys for fallback
GLOBAL_BUOYS = {
    "41002": {"lat": 32.3, "lon": -75.4, "name": "S Hatteras"},
    "42001": {"lat": 25.9, "lon": -89.7, "name": "Mid Gulf"},
    "46036": {"lat": 37.75, "lon": -124.5, "name": "WCAL North"},
    "51000": {"lat": 23.4, "lon": -153.8, "name": "Papa"},
    "51001": {"lat": 24.4, "lon": -153.0, "name": "Hawaii SW"},
    "51002": {"lat": 17.1, "lon": -157.8, "name": "Hawaii W"},
    "51003": {"lat": 19.2, "lon": -162.3, "name": "Hawaii NW"},
}


class NOAAProvider(MarineDataProvider):
    """Provider combining NDBC buoy data and ERDDAP gridded data.

    No authentication required — both sources are freely accessible.
    """

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__("NOAA")
        self._http_client: httpx.AsyncClient | None = None
        # NOAA NDBC and ERDDAP are free — always available
        self._status = ProviderStatus.HEALTHY
        logger.info("NOAA: NDBC + ERDDAP ready (no auth needed)")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(12.0),
                follow_redirects=True,
                headers={"User-Agent": "ORCA-NOAA/1.0"},
            )
        return self._http_client

    async def health_check(self) -> ProviderHealth:
        """Check NDBC and ERDDAP availability."""
        client = await self._get_client()
        ndbc_ok = False
        erddap_ok = False

        try:
            resp = await client.get(
                f"{NDBC_REALTIME}/41002.txt",
                params={"units": "metric"},
                timeout=8.0,
            )
            ndbc_ok = resp.status_code == 200 and len(resp.text) > 100
        except Exception:
            pass

        try:
            resp = await client.get(
                f"{ERDDAP_BASE}/info/index.csv",
                params={"page": "1", "itemsPerPage": "1"},
                timeout=8.0,
            )
            erddap_ok = resp.status_code == 200
        except Exception:
            pass

        status = (
            ProviderStatus.HEALTHY if (ndbc_ok or erddap_ok)
            else ProviderStatus.DEGRADED if (ndbc_ok or erddap_ok)
            else ProviderStatus.UNAVAILABLE
        )
        self._status = status

        sources = []
        if ndbc_ok:
            sources.append("NDBC")
        if erddap_ok:
            sources.append("ERDDAP")

        return ProviderHealth(
            provider_name=self.name,
            status=status,
            last_check=datetime.utcnow(),
            last_successful_retrieval=self._last_successful_retrieval,
            message=f"Available: {', '.join(sources)}" if sources else "Unavailable",
            datasets_available=list(NDBC_VARIABLES.keys()) + list(ERDDAP_DATASETS.keys()),
        )

    async def _get_ndbc_data(
        self, station_id: str, data_type: str = "txt"
    ) -> str:
        """Fetch NDBC real-time data file."""
        client = await self._get_client()
        url = f"{NDBC_REALTIME}/{station_id}.{data_type}"
        resp = await client.get(url, params={"units": "metric"})
        resp.raise_for_status()
        return resp.text

    def _parse_ndbc_data(
        self, text: str, station_id: str, variables: list[str]
    ) -> list[dict]:
        """Parse NDBC text data into observations."""
        observations = []
        lines = text.strip().split("\n")

        if len(lines) < 3:
            return observations

        data_lines = lines[2:]  # Skip # header and units line

        for line in data_lines[:24]:  # Last 24 hours max
            parts = line.split()
            if len(parts) < 15:
                continue

            try:
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                hour = int(parts[3])
                minute = int(parts[4])

                timestamp = datetime(year, month, day, hour, minute)

                for var in variables:
                    var_info = NDBC_VARIABLES.get(var)
                    if not var_info:
                        continue

                    idx = var_info["index"]
                    if idx >= len(parts):
                        continue

                    val_str = parts[idx]
                    if val_str in ("MM", "m", "999.0", "999.00"):
                        continue  # Missing data

                    value = float(val_str)
                    if value == 999.0 or abs(value) > 1000:
                        continue  # Bad data

                    # Get station location
                    station = GLOBAL_BUOYS.get(station_id, INDIAN_OCEAN_BUOYS.get(station_id, {}))

                    observations.append({
                        "variable": var,
                        "value": value,
                        "unit": var_info["unit"],
                        "latitude": station.get("lat", 0.0),
                        "longitude": station.get("lon", 0.0),
                        "timestamp": timestamp,
                        "station_id": station_id,
                        "station_name": station.get("name", station_id),
                        "source": "NDBC",
                        "dataset": f"NDBC_{station_id}",
                    })
            except (ValueError, IndexError):
                continue

        return observations

    async def _query_erddap(
        self,
        dataset_id: str,
        bbox: list[float],
        timestamp: datetime,
        erddap_var: str,
        orca_var: str,
        has_altitude_axis: bool = False,
    ) -> list[dict]:
        """Query ERDDAP griddap for ONE timestep over the full bbox grid.

        Only the latest satellite pass matters for the map (older passes are deduped
        away anyway), so we request a single time — this keeps responses small even
        at 0.01-degree resolution. Land/NaN cells are dropped in the parser.
        """
        client = await self._get_client()
        t = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        lat_range = f"[({bbox[1]}):({bbox[3]})]"
        lon_range = f"[({bbox[0]}):({bbox[2]})]"
        if has_altitude_axis:
            time_alt = f"[({t})][(0.0)]"
        else:
            time_alt = f"[({t})]"
        url = f"{ERDDAP_BASE}/griddap/{dataset_id}.csv?{erddap_var}{time_alt}{lat_range}{lon_range}"
        try:
            resp = await client.get(url, timeout=14.0)
            resp.raise_for_status()
            return self._parse_erddap_csv(resp.text, dataset_id, {orca_var: erddap_var}, bbox)
        except Exception as e:
            logger.warning(f"NOAA ERDDAP query failed for {dataset_id} @ {t}: {e}")
            return []

    def _parse_erddap_csv(
        self, csv_text: str, dataset_id: str, variables: dict[str, str], bbox: list[float]
    ) -> list[dict]:
        """Parse ERDDAP CSV response into observations."""
        observations = []
        lines = csv_text.strip().split("\n")

        if len(lines) < 3:
            return observations

        # Header line has column names like "time,latitude,longitude,var1,var2"
        headers = [h.strip().strip('"') for h in lines[0].split(",")]

        for line in lines[1:]:
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) < len(headers):
                continue

            try:
                timestamp = datetime.fromisoformat(parts[0].replace("Z", "+00:00"))
                lat = float(parts[1])
                lon = float(parts[2])

                for i, (var_name, erddap_var) in enumerate(variables.items()):
                    col_idx = headers.index(erddap_var) if erddap_var in headers else 3 + i
                    if col_idx < len(parts):
                        val_str = parts[col_idx]
                        if val_str == "" or val_str == "NaN":
                            continue
                        value = float(val_str)
                        if abs(value) > 9999:
                            continue

                        observations.append({
                            "variable": var_name,
                            "value": value,
                            "unit": self._get_unit(var_name),
                            "latitude": lat,
                            "longitude": lon,
                            "timestamp": timestamp,
                            "station_id": "",
                            "station_name": "",
                            "source": "NOAA_ERDDAP",
                            "dataset": dataset_id,
                        })
            except (ValueError, IndexError):
                continue

        return observations

    async def get_data(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        variables: list[str],
        **kwargs,
    ):
        """Retrieve NOAA data for the given query.

        Combines NDBC buoy observations with ERDDAP gridded data.
        """
        from models.observation import ObservationBatch

        observations = []

        if self._status == ProviderStatus.UNAVAILABLE:
            return ObservationBatch(
                observations=[],
                source="NOAA",
                dataset="unavailable",
                record_count=0,
                bbox=bbox,
                date_range=(start_date, end_date),
            )

        # 1. Get NDBC buoy data (recent 45 days only)
        ndbc_variables = [v for v in variables if v in NDBC_VARIABLES]
        if ndbc_variables:
            # Find buoys near the bbox
            nearby_buoys = self._find_nearby_buoys(bbox)

            tasks = []
            for buoy_id in nearby_buoys[:3]:
                tasks.append(self._fetch_ndbc_buoy(buoy_id, ndbc_variables))

            ndbc_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in ndbc_results:
                if isinstance(result, list):
                    observations.extend(result)

        # 2. ERDDAP satellite data — real VIIRS/MUR gridded products, no auth.
        # Only fetch when the bbox is region-scale (a full-India request at 0.01deg
        # would be tens of millions of cells); wider views are served by the
        # Open-Meteo/ERA5 grid provider instead.
        west, south, east, north = bbox[0], bbox[1], bbox[2], bbox[3]
        bbox_area_deg2 = max(0.0, east - west) * max(0.0, north - south)
        now = datetime.utcnow()

        if bbox_area_deg2 <= 16.0:  # ~4deg x 4deg or smaller
            for orca_var in variables:
                candidates = ERDDAP_DATASETS.get(orca_var)
                if not candidates:
                    continue
                for ds_id, erddap_var, lag_days, has_altitude_axis in candidates[:1]:
                    # Satellite products lag real time. Check at most 2 candidate timesteps
                    # with a short timeout to prevent blocking the query pipeline.
                    e_date = end_date.replace(tzinfo=None) if getattr(end_date, "tzinfo", None) is not None else end_date
                    s_date = start_date.replace(tzinfo=None) if getattr(start_date, "tzinfo", None) is not None else start_date
                    for back in range(2):
                        target = min(e_date, now - timedelta(days=lag_days + 2 * back))
                        if target < s_date - timedelta(days=3):
                            break
                        try:
                            result = await asyncio.wait_for(
                                self._query_erddap(ds_id, bbox, target, erddap_var, orca_var, has_altitude_axis),
                                timeout=3.0,
                            )
                        except Exception:
                            result = []
                        if result:
                            for row in result:
                                observations.append(self._create_observation(
                                    dataset=str(row.get("dataset", ds_id)),
                                    variable=row["variable"],
                                    value=row["value"],
                                    unit=row["unit"],
                                    latitude=row["latitude"],
                                    longitude=row["longitude"],
                                    timestamp=row["timestamp"],
                                    quality=0.85,
                                    metadata={"platform": "satellite", "satellite_product": ds_id},
                                ))
                            break

        if observations:
            self._last_successful_retrieval = datetime.utcnow()

        datasets = list(set(
            getattr(o, 'dataset', '') if hasattr(o, 'dataset') else o.get('dataset', '')
            for o in observations
        ))
        dataset_str = ",".join(datasets) if datasets else "none"

        return ObservationBatch(
            observations=observations,
            source="NOAA",
            dataset=dataset_str,
            record_count=len(observations),
            bbox=bbox,
            date_range=(start_date, end_date),
        )

    async def _fetch_ndbc_buoy(self, buoy_id: str, variables: list[str]) -> list[dict]:
        """Fetch and parse NDBC buoy data."""
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{NDBC_REALTIME}/{buoy_id}.txt",
                params={"units": "metric"},
                timeout=8.0,
            )
            resp.raise_for_status()
            raw_obs = self._parse_ndbc_data(resp.text, buoy_id, variables)

            observations = []
            for raw in raw_obs:
                obs = self._create_observation(
                    dataset=raw["dataset"],
                    variable=raw["variable"],
                    value=raw["value"],
                    unit=raw["unit"],
                    latitude=raw["latitude"],
                    longitude=raw["longitude"],
                    timestamp=raw["timestamp"],
                    quality=0.9,  # NDBC quality control
                    metadata={
                        "station_id": raw["station_id"],
                        "station_name": raw["station_name"],
                        "platform": "buoy",
                        "network": "NDBC",
                    },
                )
                observations.append(obs)
            return observations
        except Exception as e:
            logger.warning(f"NOAA NDBC buoy {buoy_id} failed: {e}")
            return []

    def _find_nearby_buoys(self, bbox: list[float]) -> list[str]:
        """Find NDBC buoys within or near the bounding box."""
        # NDBC coverage is primarily US waters + some Pacific
        # Extend bbox by 20 degrees to find nearby buoys
        expanded = [bbox[0] - 20, bbox[1] - 20, bbox[2] + 20, bbox[3] + 20]

        nearby = []
        for buoy_id, info in GLOBAL_BUOYS.items():
            lat, lon = info["lat"], info["lon"]
            if (expanded[1] <= lat <= expanded[3] and expanded[0] <= lon <= expanded[2]):
                nearby.append(buoy_id)

        return nearby

    def _get_unit(self, variable: str) -> str:
        units = {
            "sst": "°C",
            "sea_surface_temperature": "°C",
            "chlorophyll": "mg/m³",
            "chlorophyll_concentration": "mg/m³",
            "salinity": "PSU",
            "sea_level": "m",
            "wind_speed": "m/s",
            "wind_direction": "deg",
            "wave_height": "m",
            "wave_period": "s",
            "wave_direction": "deg",
            "water_temperature": "°C",
            "air_temperature": "°C",
            "pressure": "hPa",
        }
        return units.get(variable, "unknown")
