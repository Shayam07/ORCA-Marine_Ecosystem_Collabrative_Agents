"""ORCA Sources API — Data source status and information."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from data.providers import get_registry

logger = logging.getLogger("orca.api.sources")

router = APIRouter(prefix="/api/v1", tags=["sources"])


@router.get("/sources")
async def get_sources() -> dict[str, Any]:
    """Get information about all data sources."""
    registry = get_registry()
    sources = []

    source_info = {
        "MOSDAC": {
            "name": "ISRO / MOSDAC",
            "description": "Indian Space Research Organisation Earth observation data",
            "variables": ["SST", "chlorophyll", "ocean color"],
        },
        "COPERNICUS_MARINE": {
            "name": "Copernicus Marine",
            "description": "European marine environment monitoring service",
            "variables": ["SST", "salinity", "currents", "sea level", "biogeochemistry"],
        },
        "NASA": {
            "name": "NASA Earthdata",
            "description": "NASA satellite and ocean data",
            "variables": ["SST", "chlorophyll", "ocean color", "atmospheric"],
        },
        "NOAA": {
            "name": "NOAA",
            "description": "National Oceanic and Atmospheric Administration",
            "variables": ["SST", "ocean observations", "environmental anomalies"],
        },
        "ERA5": {
            "name": "ERA5 / Weather",
            "description": "ECMWF atmospheric reanalysis",
            "variables": ["wind", "rainfall", "pressure", "temperature"],
        },
        "GLOBAL_FISHING_WATCH": {
            "name": "Global Fishing Watch",
            "description": "Vessel activity and fishing monitoring",
            "variables": ["vessel presence", "fishing activity", "vessel density"],
        },
        "LITERATURE": {
            "name": "Scientific Literature",
            "description": "Crossref, Semantic Scholar, NASA ADS",
            "variables": ["scientific papers", "research findings"],
        },
        "GEOSPATIAL": {
            "name": "Geographic Data",
            "description": "Coastlines, bathymetry, marine boundaries",
            "variables": ["coastlines", "bathymetry", "EEZ boundaries"],
        },
        "INCOIS": {
            "name": "INCOIS",
            "description": "Indian National Centre for Ocean Information Services - official PFZ advisories, ocean state forecasts, marine alerts",
            "variables": ["PFZ advisory", "ocean state forecast", "marine alerts", "high wave warnings", "swell surge"],
        },
        "DEMO": {
            "name": "Demo / Synthetic Data",
            "description": "Realistic synthetic data for demonstration",
            "variables": ["all variables"],
        },
    }

    for name, provider in registry.providers.items():
        info = source_info.get(name, {"name": name, "description": "", "variables": []})
        tier = "DEMO" if name == "DEMO" else ("PRIMARY" if provider.status.value == "HEALTHY" else "SECONDARY")
        sources.append({
            "id": name,
            "name": info["name"],
            "description": info["description"],
            "status": provider.status.value,
            "variables": info["variables"],
            "provider_tier": tier,
            "freshness_status": "FRESH" if provider.status.value == "HEALTHY" else "UNAVAILABLE",
        })

    return {"sources": sources}


@router.get("/sources/status")
async def get_source_status() -> dict[str, Any]:
    """Get health status of all data sources with freshness telemetry."""
    registry = get_registry()
    health = await registry.health_check_all()
    health_dicts = []
    for h in health:
        d = h.model_dump()
        d["provider_tier"] = "DEMO" if h.provider_name == "DEMO" else ("PRIMARY" if h.status.value == "HEALTHY" else "UNAVAILABLE")
        d["freshness_status"] = "FRESH" if h.status.value == "HEALTHY" else ("UNAVAILABLE" if h.status.value == "UNAVAILABLE" else "DELAYED")
        health_dicts.append(d)
    return {
        "providers": health_dicts
    }


# Also mount on /api/v1/agents for agent status
@router.get("/agents/status")
async def get_agent_status() -> dict[str, Any]:
    """Get status of all agents."""
    return {
        "agents": [
            {"name": "coordinator", "type": "coordinator", "status": "ready"},
            {"name": "ocean", "type": "ocean", "status": "ready"},
            {"name": "satellite", "type": "satellite", "status": "ready"},
            {"name": "biology", "type": "biology", "status": "ready"},
            {"name": "weather", "type": "weather", "status": "ready"},
            {"name": "fisheries", "type": "fisheries", "status": "ready"},
            {"name": "pollution", "type": "pollution", "status": "ready"},
            {"name": "literature", "type": "literature", "status": "ready"},
        ]
    }
