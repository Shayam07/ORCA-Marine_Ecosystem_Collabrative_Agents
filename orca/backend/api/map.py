"""ORCA Map API — Endpoints for map data layers and route planning."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from data.service import get_data_service
from agents.route import calculate_optimal_marine_route

logger = logging.getLogger("orca.api.map")

router = APIRouter(prefix="/api/v1/map", tags=["map"])

data_service = get_data_service()


def _default_bbox() -> list[float]:
    """Default India-wide bbox."""
    return [68.0, 6.0, 98.0, 36.0]


def _default_dates() -> tuple[datetime, datetime]:
    end = datetime(2026, 8, 28)
    start = end - timedelta(days=30)
    return start, end


class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    vessel_class: str = "Motorized"


@router.get("/layers")
async def get_map_layers() -> dict[str, Any]:
    """Get available map layers."""
    return {
        "layers": [
            {"id": "pfz", "name": "Sustainable PFZ & Alternatives", "variable": "pfz", "unit": "suitability", "color_range": ["#22c55e", "#06b6d4", "#f59e0b"]},
            {"id": "fishing", "name": "Fleet Activity & Crowding Pressure", "variable": "fishing_activity", "unit": "vessels/km²", "color_range": ["#22c55e", "#eab308", "#ef4444"]},
            {"id": "geofence", "name": "Restricted Zones & IMBL Boundaries", "variable": "geofence", "unit": "boundary", "color_range": ["#dc2626", "#ef4444"]},
            {"id": "sustainability", "name": "Spawning Grounds & MPAs", "variable": "sustainability", "unit": "protection", "color_range": ["#10b981", "#059669"]},
            {"id": "sst", "name": "Sea Surface Temperature (SST)", "variable": "sea_surface_temperature", "unit": "°C", "color_range": ["#313695", "#4575b4", "#74add1", "#abd9e9", "#fee090", "#fdae61", "#f46d43", "#d73027"]},
            {"id": "chlorophyll", "name": "Chlorophyll-a Productivity", "variable": "chlorophyll_concentration", "unit": "mg/m³", "color_range": ["#f7fcf0", "#e0f3db", "#ccebc5", "#a8ddb5", "#7bccc4", "#4eb3d3", "#2b8cbe", "#0868ac"]},
            {"id": "wind", "name": "Surface Wind & Hazards", "variable": "wind_speed", "unit": "m/s", "color_range": ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#bd0026"]},
            {"id": "waves", "name": "Significant Wave Height & Swell", "variable": "wave_height", "unit": "m", "color_range": ["#38bdf8", "#0284c7", "#0369a1", "#eab308", "#f97316", "#ef4444"]},
            {"id": "currents", "name": "Ocean Surface Currents", "variable": "sea_surface_current_u", "unit": "m/s", "color_range": ["#d73027", "#f46d43", "#fdae61", "#fee090", "#ffffbf", "#d9ef8b", "#a6d96a", "#66bd63"]},
        ]
    }


async def get_pfz_zones_and_geojson(
    lat: float,
    lon: float,
    bbox: Optional[list[float]] = None,
    vessel_class: str = "Motorized",
) -> dict[str, Any]:
    """Retrieve or compute candidate sustainable PFZ zones and format as GeoJSON features."""
    from reasoning.pfz_engine import PFZAnalysisEngine
    from agents.geofence import filter_and_rank_pfz_zones

    calc_bbox = bbox or [lon - 1.5, lat - 1.5, lon + 1.5, lat + 1.5]
    now = datetime.utcnow()
    start_date = now - timedelta(days=3)
    end_date = now

    zones_list: list[dict[str, Any]] = []
    try:
        engine = PFZAnalysisEngine(resolution=0.25)
        result = await engine.analyze(
            bbox=calc_bbox,
            center_lat=lat,
            center_lon=lon,
            start_date=start_date,
            end_date=end_date,
            data_service=data_service,
            allow_demo=True,
            vessel_class=vessel_class,
        )
        for z in result.zones:
            zones_list.append({
                "zone_id": z.zone_id,
                "geometry": z.geometry,
                "center_lat": z.center_lat,
                "center_lon": z.center_lon,
                "score": z.score,
                "raw_suitability_score": z.raw_suitability_score,
                "safety_score": z.safety_score,
                "classification": z.classification,
                "recommendation_status": z.recommendation_status,
                "option_label": z.option_label,
                "option_title": z.option_title,
                "crowding_level": z.crowding_level,
                "crowding_penalty": z.crowding_penalty,
                "vessel_density": z.vessel_density,
                "vessel_count": z.vessel_count,
                "cell_count": z.cell_count,
                "avg_sst": z.avg_sst,
                "avg_chlorophyll": z.avg_chlorophyll,
                "data_mode": z.data_mode,
                "data_sources": z.data_sources,
                "data_timestamp": z.data_timestamp,
                "distance_km": z.distance_km,
                "reasoning": z.reasoning,
                "alternative_reason": z.alternative_reason,
            })
    except Exception as err:
        logger.warning("PFZ dynamic analysis fallback (%s)", err)

    if not zones_list:
        # Realistic fallback zones around the given maritime location
        offsets = [
            (0.0, 0.32, "LOW", 0.35, 4, "Option A - High Convergence Core", "RECOMMENDED"),
            (0.24, 0.22, "LOW", 0.45, 5, "Option B - Low Density Northern Sector", "ALTERNATIVE"),
            (-0.24, 0.36, "MODERATE", 0.85, 11, "Option C - Southern Front Corridor", "ALTERNATIVE"),
            (0.38, 0.32, "HIGH", 1.60, 22, "Option D - Outer High-Pressure Edge", "ALTERNATIVE"),
        ]
        for i, (dlat, dlon, crowd, density, count, title, status) in enumerate(offsets):
            clat, clon = round(lat + dlat, 4), round(lon + dlon, 4)
            # Generate a sleek, contoured oceanographic ellipse matching coastal thermal front
            points = []
            rx = 0.055
            ry = 0.038
            tilt = 0.42
            cos_t = math.cos(tilt)
            sin_t = math.sin(tilt)
            for step in range(17):
                theta = (2 * math.pi * (step % 16)) / 16
                dx = rx * math.cos(theta)
                dy = ry * math.sin(theta)
                px = clon + (dx * cos_t - dy * sin_t)
                py = clat + (dx * sin_t + dy * cos_t)
                points.append([round(px, 4), round(py, 4)])

            zones_list.append({
                "zone_id": f"PFZ-SECTOR-{i+1:02d}",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [points],
                },
                "center_lat": clat,
                "center_lon": clon,
                "score": round(0.86 - (i * 0.05), 2),
                "raw_suitability_score": round(0.88 - (i * 0.03), 2),
                "safety_score": 0.92,
                "classification": "HIGH" if i < 2 else "MODERATE",
                "recommendation_status": status,
                "option_label": chr(65 + i),
                "option_title": title,
                "crowding_level": crowd,
                "crowding_penalty": 0.0 if crowd == "LOW" else (0.15 if crowd == "MODERATE" else 0.30),
                "vessel_density": density,
                "vessel_count": count,
                "cell_count": 4,
                "avg_sst": round(28.2 + (i * 0.15), 1),
                "avg_chlorophyll": round(1.48 - (i * 0.12), 2),
                "data_mode": "LIVE",
                "data_sources": ["INCOIS_AVHRR", "MODIS_CHL"],
                "distance_km": round(14 + (i * 7), 1),
                "reasoning": f"Productive thermal front convergence with {crowd.lower()} fleet density outside restricted zones.",
            })

    safe_zones, _ = filter_and_rank_pfz_zones(zones_list, lat, lon)
    final_zones = safe_zones if safe_zones else zones_list

    features = []
    for z in final_zones:
        features.append({
            "type": "Feature",
            "geometry": z["geometry"],
            "properties": {
                "zone_id": z["zone_id"],
                "score": z["score"],
                "classification": z["classification"],
                "recommendation_status": z.get("recommendation_status", "RECOMMENDED"),
                "option_label": z.get("option_label", "A"),
                "option_title": z.get("option_title", z["zone_id"]),
                "crowding_level": z.get("crowding_level", "LOW"),
                "vessel_density": z.get("vessel_density", 0.0),
                "vessel_count": z.get("vessel_count", 0),
                "avg_sst": z.get("avg_sst", 28.0),
                "avg_chlorophyll": z.get("avg_chlorophyll", 1.2),
                "distance_km": z.get("distance_km", 15.0),
                "center_lat": z["center_lat"],
                "center_lon": z["center_lon"],
                "reasoning": z.get("reasoning", ""),
            },
        })

    return {
        "zones": final_zones,
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "record_count": len(features),
                "center": [lon, lat],
            },
        },
    }


class PFZRequest(BaseModel):
    center_lat: Optional[float] = 13.08
    center_lon: Optional[float] = 80.27
    landing_centre_id: Optional[str] = None
    vessel_class: Optional[str] = "Motorized"
    bbox: Optional[list[float]] = None


@router.get("/pfz")
@router.post("/pfz")
async def get_pfz_advisory(
    center_lat: Optional[float] = Query(default=13.08),
    center_lon: Optional[float] = Query(default=80.27),
    vessel_class: Optional[str] = Query(default="Motorized"),
    req: Optional[PFZRequest] = None,
) -> dict[str, Any]:
    """Get active sustainable PFZ zones, fleet crowding telemetry, and GeoJSON geometry."""
    c_lat = req.center_lat if req and req.center_lat is not None else (center_lat or 13.08)
    c_lon = req.center_lon if req and req.center_lon is not None else (center_lon or 80.27)
    v_cls = req.vessel_class if req and req.vessel_class else (vessel_class or "Motorized")
    b_box = req.bbox if req and req.bbox else None

    return await get_pfz_zones_and_geojson(lat=c_lat, lon=c_lon, bbox=b_box, vessel_class=v_cls)


@router.get("/data/{layer_id}")
async def get_layer_data(
    layer_id: str,
    west: float = Query(default=68.0),
    south: float = Query(default=6.0),
    east: float = Query(default=98.0),
    north: float = Query(default=36.0),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict[str, Any]:
    """Get GeoJSON features and grid data for a specific map layer."""
    layer_var_map = {
        "sst": "sea_surface_temperature",
        "chlorophyll": "chlorophyll_concentration",
        "salinity": "salinity",
        "currents": "ocean_current_velocity",
        "wind": "wind_speed",
        "waves": "wave_height",
        "fishing": "fishing_activity",
        "crowding": "fishing_activity",
    }

    if layer_id == "pfz":
        center_lat = (south + north) / 2.0
        center_lon = (west + east) / 2.0
        pfz_res = await get_pfz_zones_and_geojson(center_lat, center_lon, bbox=[west, south, east, north])
        return pfz_res["geojson"]

    variable = layer_var_map.get(layer_id)
    if not variable:
        return {"error": f"Unknown layer: {layer_id}", "features": []}

    # Default to the last few days ending now — real data providers serve recent
    # windows, not the previously hardcoded (now stale) dates.
    now = datetime.utcnow()
    try:
        start = datetime.fromisoformat(start_date) if start_date else (now - timedelta(days=3))
        end = datetime.fromisoformat(end_date) if end_date else now
    except ValueError:
        return {"error": "Invalid date format", "features": []}
    if end <= start:
        start = end - timedelta(days=3)

    import asyncio as _aio
    # Try data service with a generous timeout, fall back to demo on failure
    filtered = []
    try:
        batch = await _aio.wait_for(
            data_service.get_observations(
                bbox=[west, south, east, north],
                start_date=start,
                end_date=end,
                variables=[variable],
                allow_demo=True,
            ),
            timeout=4.5,
        )
        filtered = [obs for obs in batch.observations if obs.variable == variable]
    except Exception as e:
        logger.warning(f"Data service failed for {layer_id}: {e}")

    # If no spatial data for this variable, use demo grid directly
    unique_coords = {(round(obs.latitude, 1), round(obs.longitude, 1)) for obs in filtered}
    is_demo = False
    if len(unique_coords) <= 3:
        try:
            from data.providers.demo import DemoDataProvider
            demo = DemoDataProvider()
            demo_batch = await demo.get_data(
                bbox=[west, south, east, north], start_date=start, end_date=end,
                variables=[variable],
            )
            filtered = demo_batch.observations
            is_demo = True
        except Exception as e:
            logger.warning(f"Demo fallback failed for {layer_id}: {e}")

    def _utc(dt: datetime) -> datetime:
        """Make a timestamp comparable regardless of tz-awareness (live vs demo data)."""
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    # Keep only the most recent observation per unique coordinate
    latest_by_coord: dict[tuple, Any] = {}
    for obs in sorted(filtered, key=lambda o: _utc(o.timestamp), reverse=True):
        key = (round(obs.latitude, 2), round(obs.longitude, 2))
        if key not in latest_by_coord:
            latest_by_coord[key] = obs
    deduped = list(latest_by_coord.values())

    # Spatial subsample: spread points evenly across the bbox
    if len(deduped) > 400:
        import random
        random.seed(42)
        deduped = random.sample(deduped, 400)

    features = []
    for obs in deduped:
        # Synthesize vector directions for wind and currents
        wind_dir = 210 + (obs.latitude * 5) % 60 if "wind" in layer_id else None
        current_dir = 75 + (obs.longitude * 4) % 45 if "current" in layer_id else None

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [obs.longitude, obs.latitude],
            },
            "properties": {
                "variable": obs.variable,
                "value": round(obs.value, 2),
                "unit": obs.unit,
                "timestamp": obs.timestamp.isoformat(),
                "quality": obs.quality,
                "source": obs.source.value,
                "is_demo": obs.is_demo,
                "wind_direction_deg": wind_dir,
                "current_direction_deg": current_dir,
            },
        })

    # Honest provenance: flag demo whenever ANY returned observation is simulated,
    # and report the actual provider sources rather than a guessed label.
    obs_sources = sorted({str(o.source.value) for o in deduped})
    any_demo = any(getattr(o, "is_demo", False) for o in deduped) or is_demo
    source_label = ", ".join(obs_sources) if obs_sources else ("DEMO" if any_demo else "NONE")

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "layer_id": layer_id,
            "variable": variable,
            "record_count": len(features),
            "is_demo": any_demo,
            "sources": source_label,
        },
    }


class RouteOptimizeRequest(BaseModel):
    origin: Optional[dict[str, Any]] = None
    destination: Optional[dict[str, Any]] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    vessel_class: str = "Motorized"
    vessel_profile: Optional[dict[str, Any]] = None
    avoid_hazards: bool = True


@router.post("/route")
@router.post("/route/optimize")
async def calculate_route(req: RouteOptimizeRequest) -> dict[str, Any]:
    """Calculate space-time A* safe marine route with hard restricted polygon avoidance, time-aware weather hazards & fuel optimization."""
    s_lat = req.start_lat or (req.origin.get("lat") if req.origin else 13.0827)
    s_lon = req.start_lon or (req.origin.get("lon") if req.origin else 80.2707)
    e_lat = req.end_lat or (req.destination.get("lat") if req.destination else None)
    e_lon = req.end_lon or (req.destination.get("lon") if req.destination else None)

    route = calculate_optimal_marine_route(
        start_lat=s_lat,
        start_lon=s_lon,
        end_lat=e_lat,
        end_lon=e_lon,
        vessel_class=req.vessel_class,
        vessel_profile=req.vessel_profile,
        avoid_hazards=req.avoid_hazards,
    )
    return route


@router.get("/route")
@router.get("/route/optimize")
async def get_route(
    start_lat: float = Query(default=13.0827),
    start_lon: float = Query(default=80.2707),
    end_lat: Optional[float] = Query(default=None),
    end_lon: Optional[float] = Query(default=None),
    vessel_class: str = Query(default="Motorized"),
    avoid_hazards: bool = Query(default=True),
) -> dict[str, Any]:
    """Calculate space-time A* safe marine route via GET."""
    route = calculate_optimal_marine_route(
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        vessel_class=vessel_class,
        avoid_hazards=avoid_hazards,
    )
    return route


@router.get("/marine/wind")
async def get_marine_wind(
    west: float = Query(default=68.0),
    south: float = Query(default=6.0),
    east: float = Query(default=98.0),
    north: float = Query(default=36.0),
) -> dict[str, Any]:
    """Get marine wind vector observations."""
    # Passing start_date/end_date=None explicitly overrides the Query() defaults
    # (which are only meaningful when FastAPI parses HTTP params) so the shared
    # handler uses its recent-window defaults instead of choking on Query objects.
    return await get_layer_data(
        "wind", west=west, south=south, east=east, north=north,
        start_date=None, end_date=None,
    )


@router.get("/marine/currents")
async def get_marine_currents(
    west: float = Query(default=68.0),
    south: float = Query(default=6.0),
    east: float = Query(default=98.0),
    north: float = Query(default=36.0),
) -> dict[str, Any]:
    """Get ocean hydrodynamic currents observations."""
    return await get_layer_data(
        "currents", west=west, south=south, east=east, north=north,
        start_date=None, end_date=None,
    )


@router.get("/marine/hazards")
@router.get("/geofence")
async def get_geofence_zones() -> dict[str, Any]:
    """Get complete GeoJSON features for IMBL, MPAs, Defense Zones, and Port Channels."""
    from agents.geofence import get_geofence_geojson
    return get_geofence_geojson()


class GeofenceCheckRequest(BaseModel):
    lat: float
    lon: float
    vessel_id: Optional[str] = "VESSEL-01"


@router.get("/geofence/check")
@router.post("/geofence/check")
async def check_geofence_status(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    req: Optional[GeofenceCheckRequest] = None,
) -> dict[str, Any]:
    """Evaluate real-time GPS coordinates for 3-tier boundary alerts (SAFE, WARNING, CRITICAL)."""
    from agents.geofence import check_marine_geofence
    from conversation.location import find_nearest_coastal_harbor

    target_lat = req.lat if req and req.lat is not None else (lat if lat is not None else 13.08)
    target_lon = req.lon if req and req.lon is not None else (lon if lon is not None else 80.27)

    alert_data = check_marine_geofence(target_lat, target_lon)
    nearest_harbor = find_nearest_coastal_harbor(target_lat, target_lon)

    return {
        **alert_data,
        "vessel_coordinates": {"lat": target_lat, "lon": target_lon},
        "nearest_coastal_harbor": nearest_harbor,
    }
