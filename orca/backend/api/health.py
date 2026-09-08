"""ORCA Health API — System health checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter

from config.settings import settings

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """System health check."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "data_mode": settings.DATA_MODE,
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "not_connected",
            "redis": "not_connected",
            "providers": "initialized",
            "offline_safety": "ready",
        },
    }


@router.get("/offline/safety-pack")
async def get_offline_safety_pack() -> dict[str, Any]:
    """Provide verified offline safety pack for caching before departing offshore.
    
    Includes:
    - Sovereign IMBL coordinates & buffer margins
    - Marine Protected Areas (MPAs) & defense exclusion boundaries
    - Active government uniform seasonal bans
    - Emergency distress frequencies & return bearings
    """
    from agents.geofence import IMBL_BOUNDARIES, RESTRICTED_SECURITY_ZONES, MARINE_PROTECTED_AREAS, SEASONAL_FISHING_BANS
    now = datetime.now()

    return {
        "pack_version": "2026.1-offline",
        "generated_at": now.isoformat(),
        "disclaimer": "Offline safety pack: provides local border detection and cached emergency procedures when zero internet is available offshore.",
        "imbl_boundaries": IMBL_BOUNDARIES,
        "restricted_security_zones": RESTRICTED_SECURITY_ZONES,
        "marine_protected_areas": MARINE_PROTECTED_AREAS,
        "seasonal_fishing_bans": SEASONAL_FISHING_BANS,
        "offline_features": [
            "GPS location tracking",
            "4-tier geofence proximity alerts",
            "Cached restricted polygon collision check",
            "Safe return compass vector calculation",
        ],
        "emergency_contacts": {
            "indian_coast_guard_toll_free": "1554",
            "marine_police_helpline": "1093",
            "coastal_radar_vhf_channel": "16",
        },
    }
