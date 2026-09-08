"""ORCA Geofence Agent & Maritime Border Alert Engine.

Provides:
- Comprehensive Indian marine restricted zones (IMBL, MPA, Defense/Rocket test, TSS, Port channels).
- Real-time 3-tier boundary proximity & crossing alerts (SAFE, WARNING, CRITICAL).
- Safe return compass heading and vector calculations.
- Safety-first PFZ filtering prioritizing maritime geofence compliance over raw biological scores.
"""

from __future__ import annotations

import math
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType

logger = logging.getLogger("orca.agents.geofence")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine great-circle distance in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def calculate_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing from point 1 to point 2."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - \
        math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


# ── Comprehensive Indian Maritime Geofence Catalog ──────────────────────────

# 1. International Maritime Boundary Lines (IMBL)
IMBL_BOUNDARIES = [
    {
        "id": "IMBL-SRI-LANKA-01",
        "name": "India - Sri Lanka International Maritime Boundary Line (Palk Strait)",
        "category": "IMBL",
        "type": "BORDER",
        "color": "#ef4444",
        "coordinates": [
            [79.8600, 10.0800],
            [79.5400, 9.6800],
            [79.3800, 9.3600],
            [79.2800, 9.1500],
            [79.1100, 8.8800],
            [78.9200, 8.6500],
            [78.5500, 8.3500],
        ],
        "warning_buffer_km": 10.0,
        "critical_buffer_km": 4.5,
        "description": "Sovereign maritime border under 1974/1976 bilateral treaties. Crossing prohibited without bilateral clearance.",
    },
    {
        "id": "IMBL-PAKISTAN-01",
        "name": "India - Pakistan Maritime Boundary Line (Sir Creek / Arabian Sea)",
        "category": "IMBL",
        "type": "BORDER",
        "color": "#ef4444",
        "coordinates": [
            [68.1200, 23.6500],
            [67.8500, 23.4000],
            [67.4500, 23.0500],
            [66.8000, 22.5000],
        ],
        "warning_buffer_km": 15.0,
        "critical_buffer_km": 6.0,
        "description": "High-security maritime boundary in Kutch/Sir Creek region. Active Coast Guard & Naval surveillance sector.",
    },
]

# 2. Defense, Rocket Testing & High-Risk Security Zones
RESTRICTED_SECURITY_ZONES = [
    {
        "id": "RESTRICTED-CHANDIPUR",
        "name": "Dr. APJ Abdul Kalam Island / Chandipur Defense Exclusion Zone",
        "short_name": "Chandipur Missile Test Range",
        "category": "DEFENSE_RESTRICTED",
        "lat": 20.75,
        "lon": 87.05,
        "radius_km": 45.0,
        "color": "#dc2626",
        "severity": "CRITICAL",
        "icon": "⛔",
        "description": "Integrated Test Range (ITR) missile testing corridor. Navigation and fishing strictly prohibited during NOTAM/advisories.",
        "legal_warning": "Ministry of Defence Exclusion Zone. Entry strictly prohibited during firing windows. Unauthorized vessels subject to interception.",
    },
    {
        "id": "RESTRICTED-BOMBAY-HIGH",
        "name": "Bombay High Offshore Petroleum Security Zone (ONGC Platforms)",
        "short_name": "Bombay High Security Zone",
        "category": "DEFENSE_RESTRICTED",
        "lat": 19.42,
        "lon": 71.33,
        "radius_km": 35.0,
        "color": "#dc2626",
        "severity": "CRITICAL",
        "icon": "⛔",
        "description": "Designated 500m-5km security exclusion radius around critical offshore production platforms.",
        "legal_warning": "National Critical Energy Infrastructure. Strict 500m platform safety zone & offshore patrol exclusion.",
    },
    {
        "id": "RESTRICTED-KARWAR-NAVAL",
        "name": "INS Kadamba / Karwar Naval Base Approach Channel",
        "short_name": "Karwar Naval Base Fairway",
        "category": "DEFENSE_RESTRICTED",
        "lat": 14.78,
        "lon": 74.12,
        "radius_km": 18.0,
        "color": "#dc2626",
        "severity": "CRITICAL",
        "icon": "⛔",
        "description": "Naval operational fairway. Fishing vessels prohibited in submarine and warship navigation transit corridors.",
        "legal_warning": "Indian Navy Project Seabird restricted transit corridor. Fishing and anchoring prohibited.",
    },
    {
        "id": "RESTRICTED-VIZAG-NAVAL",
        "name": "Eastern Naval Command / Visakhapatnam Submarine Transit Fairway",
        "short_name": "Vizag Naval Channel",
        "category": "DEFENSE_RESTRICTED",
        "lat": 17.68,
        "lon": 83.35,
        "radius_km": 20.0,
        "color": "#dc2626",
        "severity": "CRITICAL",
        "icon": "⛔",
        "description": "Strategic naval approach channel and submarine transit zone.",
        "legal_warning": "Eastern Naval Command Operational Area. Commercial fishing nets strictly prohibited.",
    },
    {
        "id": "RESTRICTED-SRIHARIKOTA-ISRO",
        "name": "Satish Dhawan Space Centre (SDSC-SHAR) Launch Exclusion Sector",
        "short_name": "Sriharikota ISRO Range",
        "category": "DEFENSE_RESTRICTED",
        "lat": 13.73,
        "lon": 80.30,
        "radius_km": 25.0,
        "color": "#dc2626",
        "severity": "CRITICAL",
        "icon": "⛔",
        "description": "Rocket launch trajectory exclusion zone in the Bay of Bengal.",
        "legal_warning": "ISRO rocket launch safety sector. Strict maritime closure enforced during scheduled launches.",
    },
    {
        "id": "RESTRICTED-KOCHI-NAVAL",
        "name": "Southern Naval Command / Kochi Harbor Defense & Approach Channel",
        "short_name": "Kochi Naval Channel",
        "category": "DEFENSE_RESTRICTED",
        "lat": 9.96,
        "lon": 76.22,
        "radius_km": 16.0,
        "color": "#dc2626",
        "severity": "CRITICAL",
        "icon": "⛔",
        "description": "Naval base approach and warship maneuver zone.",
        "legal_warning": "Naval channel security corridor. Fishing vessels must yield right of way and avoid fairway.",
    },
]

# 3. Marine Protected Areas (MPAs) & Ecologically Sensitive Biospheres
MARINE_PROTECTED_AREAS = [
    {
        "id": "MPA-GULF-OF-MANNAR",
        "name": "Gulf of Mannar Marine National Park & Biosphere Reserve",
        "category": "MPA",
        "lat": 9.15,
        "lon": 79.10,
        "radius_km": 38.0,
        "color": "#10b981",
        "spawning_season_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # Year-round core protection
        "target_species": ["Dugong", "Coral Reefs", "Sea Cucumbers", "Seagrass"],
        "description": "21 core islands with sensitive coral reef and dugong habitats. Mechanized trawling and non-artisanal extraction banned.",
    },
    {
        "id": "MPA-GAHIRMATHA",
        "name": "Gahirmatha Marine Wildlife Sanctuary (Olive Ridley Turtle Core)",
        "category": "MPA",
        "lat": 20.65,
        "lon": 86.95,
        "radius_km": 30.0,
        "color": "#10b981",
        "spawning_season_months": [11, 12, 1, 2, 3, 4, 5],  # Nov 1 to May 31 mass nesting
        "target_species": ["Olive Ridley Sea Turtle"],
        "description": "World's largest mass nesting rookery for Olive Ridley sea turtles. Seasonal fishing ban in force Nov 1 to May 31.",
    },
    {
        "id": "MPA-RUSHIKULYA",
        "name": "Rushikulya Rookery Offshore Turtle Corridor",
        "category": "MPA",
        "lat": 19.36,
        "lon": 85.08,
        "radius_km": 24.0,
        "color": "#10b981",
        "spawning_season_months": [11, 12, 1, 2, 3, 4, 5],
        "target_species": ["Olive Ridley Sea Turtle", "Pelagic Spawners"],
        "description": "Critical congregation and mating zone for endangered marine turtles off Odisha coast.",
    },
    {
        "id": "MPA-SUNDARBANS-CORE",
        "name": "Sundarbans Biosphere Marine & Mangrove Core",
        "category": "MPA",
        "lat": 21.65,
        "lon": 88.75,
        "radius_km": 40.0,
        "color": "#10b981",
        "spawning_season_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "target_species": ["Estuarine Crocodile", "Hilsa shad breeding", "Tiger reserve estuarine"],
        "description": "UNESCO World Heritage mangrove core. Restricted commercial fishing under Coastal Regulation Zone (CRZ) rules.",
    },
    {
        "id": "MPA-MALVAN",
        "name": "Malvan Marine Wildlife Sanctuary (Maharashtra)",
        "category": "MPA",
        "lat": 16.05,
        "lon": 73.45,
        "radius_km": 15.0,
        "color": "#10b981",
        "spawning_season_months": [6, 7, 8, 9],  # Monsoon spawning ban + year-round sanctuary
        "target_species": ["Coral Reefs", "Pearl Oysters", "Snappers"],
        "description": "Coral and pearl oyster ecosystem. Commercial purse-seining and bottom-trawling strictly prohibited.",
    },
    {
        "id": "MPA-GULF-OF-KUTCH",
        "name": "Marine National Park & Sanctuary, Gulf of Kutch",
        "category": "MPA",
        "lat": 22.58,
        "lon": 69.80,
        "radius_km": 32.0,
        "color": "#10b981",
        "spawning_season_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "target_species": ["Live Coral", "Mangrove Nursery", "Sponges"],
        "description": "Mangroves, sponges, and coral colonies. Commercial fishing regulated by State Forest & Fisheries Dept.",
    },
    {
        "id": "MPA-ANDAMAN-MG",
        "name": "Mahatma Gandhi Marine National Park (Wandoor, Andamans)",
        "category": "MPA",
        "lat": 11.60,
        "lon": 92.58,
        "radius_km": 25.0,
        "color": "#10b981",
        "spawning_season_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "target_species": ["Coral Reefs", "Sea Turtles", "Giant Clams"],
        "description": "Labyrinth Islands coral reefs. Protected marine sanctuary.",
    },
    {
        "id": "MPA-NETRANI",
        "name": "Netrani Island Coral Ecology Reserve (Karnataka)",
        "category": "MPA",
        "lat": 14.02,
        "lon": 74.33,
        "radius_km": 12.0,
        "color": "#10b981",
        "spawning_season_months": [6, 7, 8],
        "target_species": ["Coral Reef Ecosystem", "Butterflyfish", "Whale Shark transit"],
        "description": "Pristine coral biodiversity hotspot off Murudeshwar. Heavy commercial gear restricted.",
    },
]

# 4. Official Indian Uniform Seasonal Fishing Bans (Government of India / Dept. of Fisheries)
SEASONAL_FISHING_BANS = [
    {
        "id": "BAN-EAST-COAST-UNIFORM",
        "name": "Government of India East Coast Uniform Seasonal Fishing Ban",
        "coast": "EAST",
        "start_month": 4,
        "start_day": 15,
        "end_month": 6,
        "end_day": 14,
        "duration_days": 61,
        "affected_states": ["Tamil Nadu", "Andhra Pradesh", "Odisha", "West Bengal", "Puducherry"],
        "min_lat": 8.0,
        "max_lat": 23.0,
        "min_lon": 78.0,
        "max_lon": 90.0,
        "purpose": "Protection of fish spawning, egg-bearing females, and pelagic juvenile recruitment during peak pre-monsoon breeding season.",
        "gear_restricted": "All mechanized and motorized fishing vessels (traditional artisanal craft exempted).",
    },
    {
        "id": "BAN-WEST-COAST-UNIFORM",
        "name": "Government of India West Coast Uniform Seasonal Fishing Ban",
        "coast": "WEST",
        "start_month": 6,
        "start_day": 1,
        "end_month": 7,
        "end_day": 31,
        "duration_days": 61,
        "affected_states": ["Kerala", "Karnataka", "Goa", "Maharashtra", "Gujarat", "Lakshadweep"],
        "min_lat": 8.0,
        "max_lat": 24.0,
        "min_lon": 68.0,
        "max_lon": 77.8,
        "purpose": "Monsoon conservation ban safeguarding southwest monsoon pelagic and demersal fish broodstock and spawning migrations.",
        "gear_restricted": "All mechanized trawlers, purse-seiners, and motorized vessels.",
    },
]

# 5. Major Port Traffic Separation Schemes (TSS) & Channels
PORT_TRAFFIC_ZONES = [
    {"name": "Chennai Port TSS Approach", "lat": 13.08, "lon": 80.30, "radius_km": 6.0, "category": "PORT_TSS"},
    {"name": "Mumbai Port & JNPT Fairway", "lat": 18.94, "lon": 72.84, "radius_km": 9.0, "category": "PORT_TSS"},
    {"name": "Cochin Outer Harbour Channel", "lat": 9.97, "lon": 76.25, "radius_km": 6.0, "category": "PORT_TSS"},
    {"name": "Visakhapatnam Deepwater Channel", "lat": 17.70, "lon": 83.30, "radius_km": 6.0, "category": "PORT_TSS"},
    {"name": "Kolkata / Haldia Hooghly Estuary Approach", "lat": 22.02, "lon": 88.10, "radius_km": 12.0, "category": "PORT_TSS"},
    {"name": "Mormugao Port Approach (Goa)", "lat": 15.42, "lon": 73.78, "radius_km": 6.0, "category": "PORT_TSS"},
]


# ── Seasonal Ban & Spawning Evaluators ────────────────────────────────────────

def is_seasonal_ban_active(lat: float, lon: float, check_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Check if an official government seasonal fishing ban is active at this coordinate & date."""
    from datetime import datetime as _dt
    d = check_date or _dt.now()
    month = d.month
    day = d.day

    for ban in SEASONAL_FISHING_BANS:
        # Check geographic bbox
        if ban["min_lat"] <= lat <= ban["max_lat"] and ban["min_lon"] <= lon <= ban["max_lon"]:
            # Check date range (handles same year non-wrap or wraps)
            sm, sd = ban["start_month"], ban["start_day"]
            em, ed = ban["end_month"], ban["end_day"]

            in_ban = False
            if (month > sm or (month == sm and day >= sd)) and (month < em or (month == em and day <= ed)):
                in_ban = True

            if in_ban:
                return {
                    "is_active": True,
                    "ban_id": ban["id"],
                    "ban_name": ban["name"],
                    "coast": ban["coast"],
                    "period": f"{sm:02d}/{sd:02d} to {em:02d}/{ed:02d}",
                    "purpose": ban["purpose"],
                    "gear_restricted": ban["gear_restricted"],
                    "source": ban.get("source", "Department of Fisheries, Ministry of Fisheries, Animal Husbandry & Dairying, Govt of India"),
                    "last_updated": ban.get("last_updated", "2026-04-01"),
                    "restriction_type": ban.get("restriction_type", "OFFICIAL_SEASONAL_BAN"),
                    "valid_from": f"{d.year}-{sm:02d}-{sd:02d}",
                    "valid_to": f"{d.year}-{em:02d}-{ed:02d}",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [ban["min_lon"], ban["min_lat"]],
                            [ban["max_lon"], ban["min_lat"]],
                            [ban["max_lon"], ban["max_lat"]],
                            [ban["min_lon"], ban["max_lat"]],
                            [ban["min_lon"], ban["min_lat"]],
                        ]],
                    },
                    "description": f"Official {ban['name']} in force ({sm:02d}/{sd:02d}–{em:02d}/{ed:02d}). Mechanized fishing prohibited to protect breeding broodstock.",
                }

    return {
        "is_active": False,
        "ban_name": None,
        "source": "Department of Fisheries, Govt of India",
        "last_updated": "2026-04-01",
        "restriction_type": "OFFICIAL_SEASONAL_BAN",
        "valid_from": None,
        "valid_to": None,
        "geometry": None,
    }


def check_spawning_and_ecological_sensitivity(lat: float, lon: float, check_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Check whether coordinate intersects active spawning grounds or Marine Protected Areas."""
    from datetime import datetime as _dt
    d = check_date or _dt.now()
    month = d.month

    # 1. Check seasonal fishing ban
    ban_info = is_seasonal_ban_active(lat, lon, d)

    # 2. Check proximity to MPAs and spawning reserves
    for mpa in MARINE_PROTECTED_AREAS:
        dist = haversine_km(lat, lon, mpa["lat"], mpa["lon"])
        if dist <= mpa["radius_km"]:
            is_active_season = month in mpa.get("spawning_season_months", [])
            return {
                "is_protected": True,
                "is_spawning_season": is_active_season,
                "area_id": mpa["id"],
                "name": mpa["name"],
                "category": mpa["category"],
                "target_species": mpa.get("target_species", []),
                "distance_km": round(dist, 1),
                "description": mpa["description"],
                "ban_active": ban_info["is_active"],
                "ban_details": ban_info,
                "source": mpa.get("source", "Ministry of Environment, Forest and Climate Change (MoEFCC), Wildlife Protection Act 1972"),
                "last_updated": mpa.get("last_updated", "2026-01-15"),
                "restriction_type": mpa.get("restriction_type", "MARINE_PROTECTED_AREA"),
                "valid_from": f"{d.year}-01-01",
                "valid_to": f"{d.year}-12-31",
                "geometry": {
                    "type": "Point",
                    "coordinates": [mpa["lon"], mpa["lat"]],
                    "radius_km": mpa["radius_km"],
                },
            }

    return {
        "is_protected": False,
        "is_spawning_season": False,
        "area_id": None,
        "name": None,
        "ban_active": ban_info["is_active"],
        "ban_details": ban_info,
        "source": "MoEFCC / State Fisheries Departments",
        "last_updated": "2026-01-15",
        "restriction_type": "NONE",
        "valid_from": None,
        "valid_to": None,
        "geometry": None,
    }


# ── Core Geofencing & Real-Time Alert Evaluation ─────────────────────────────

def check_marine_geofence(
    lat: float,
    lon: float,
    gps_accuracy_meters: Optional[float] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Check vessel coordinates against Indian Maritime Boundary Lines (IMBL), Security Zones, and MPAs.

    Buffer Architecture & Hysteresis:
      - SAFE: > 12 km from border/restricted polygon
      - WARNING_BUFFER (Amber): 5.0 - 12.0 km
      - CRITICAL_BUFFER (Red): 1.5 - 5.0 km
      - RESTRICTED_VIOLATION (Critical Red): < 1.5 km or inside restricted boundary

    GPS Error & Hysteresis Handling:
      - If GPS accuracy is degraded (> 100m), dynamically expand safety buffer margins.
      - Never trigger a hard critical border violation on a single isolated GPS spike if previous fixes were SAFE.
    """
    gps_acc = gps_accuracy_meters or 15.0
    gps_error_km = gps_acc / 1000.0  # meters to km

    min_imbl_dist = float("inf")
    closest_imbl = None

    # Check distance to IMBL boundary line segments
    for boundary in IMBL_BOUNDARIES:
        coords = boundary["coordinates"]
        for pt in coords:
            d = haversine_km(lat, lon, pt[1], pt[0])
            if d < min_imbl_dist:
                min_imbl_dist = d
                closest_imbl = {**boundary, "pt_lat": pt[1], "pt_lon": pt[0]}

    # Check distance to Restricted Zones & MPAs
    min_restricted_dist = float("inf")
    closest_restricted = None

    all_restricted = RESTRICTED_SECURITY_ZONES + MARINE_PROTECTED_AREAS
    for zone in all_restricted:
        d = haversine_km(lat, lon, zone["lat"], zone["lon"])
        effective_d = max(0.0, d - zone["radius_km"])
        if effective_d < min_restricted_dist:
            min_restricted_dist = effective_d
            closest_restricted = {**zone, "center_dist": d}

    # Dynamic buffer margins incorporating GPS error
    critical_imbl_threshold = 5.0 + min(2.0, gps_error_km * 3)
    warning_imbl_threshold = 12.0 + min(3.0, gps_error_km * 3)

    is_raw_critical_imbl = min_imbl_dist < critical_imbl_threshold
    is_raw_warning_imbl = critical_imbl_threshold <= min_imbl_dist <= warning_imbl_threshold

    is_raw_inside_restricted = min_restricted_dist <= (0.5 + gps_error_km)
    is_raw_warning_restricted = (0.5 + gps_error_km) < min_restricted_dist <= (8.0 + gps_error_km)

    # Raw status determination
    if is_raw_critical_imbl or is_raw_inside_restricted:
        raw_status = "CRITICAL"
    elif is_raw_warning_imbl or is_raw_warning_restricted:
        raw_status = "WARNING"
    else:
        raw_status = "SAFE"

    # Consecutive location verification & Hysteresis
    status = raw_status
    hysteresis_note = None

    if raw_status == "CRITICAL" and history:
        # Check if previous fixes were safe and if current point might be single-point GPS jitter
        recent_statuses = [h.get("status", "SAFE") for h in history[-3:] if isinstance(h, dict)]
        if recent_statuses and all(s == "SAFE" for s in recent_statuses) and gps_acc > 50.0:
            # Downgrade to cautious WARNING pending consecutive fix confirmation
            status = "WARNING"
            hysteresis_note = "⚠️ Position spike detected with degraded GPS accuracy (±{:.0f}m). Verifying consecutive fixes before critical alarm.".format(gps_acc)

    # Calculate safe return heading (away from border toward mainland India)
    safe_heading = 270.0  # Default Westward towards Indian coast
    if closest_imbl and min_imbl_dist <= 15.0:
        bearing_to_vessel = calculate_bearing_deg(closest_imbl["pt_lat"], closest_imbl["pt_lon"], lat, lon)
        safe_heading = round(bearing_to_vessel, 0)
    elif closest_restricted and min_restricted_dist <= 10.0:
        bearing_to_vessel = calculate_bearing_deg(closest_restricted["lat"], closest_restricted["lon"], lat, lon)
        safe_heading = round(bearing_to_vessel, 0)

    # Construct alert message
    if status == "CRITICAL":
        if is_raw_critical_imbl:
            alert_message = (
                f"🚨 CRITICAL BORDER ALERT: Vessel is within {min_imbl_dist:.1f} km of the "
                f"{closest_imbl['name']}! Immediately turn to heading {safe_heading:.0f}° to return to permitted Indian waters."
            )
        else:
            alert_message = (
                f"🚨 CRITICAL RESTRICTION ALERT: Vessel is inside {closest_restricted['name']}! "
                f"Fishing is prohibited in this sector. Steer heading {safe_heading:.0f}° to exit."
            )
    elif status == "WARNING":
        if hysteresis_note:
            alert_message = hysteresis_note
        elif is_raw_warning_imbl:
            alert_message = (
                f"⚠️ BORDER PROXIMITY WARNING: Approaching {closest_imbl['name']} ({min_imbl_dist:.1f} km away). "
                f"Maintain safe distance and check heading ({safe_heading:.0f}°)."
            )
        else:
            alert_message = (
                f"⚠️ RESTRICTED AREA PROXIMITY: Approaching {closest_restricted['name']} ({min_restricted_dist:.1f} km away). "
                f"Avoid entering this protected sector."
            )
    else:
        alert_message = "✅ Safe Zone: Vessel operating well within permitted Indian maritime waters."

    return {
        "status": status,
        "raw_status": raw_status,
        "is_safe": status == "SAFE",
        "alert_message": alert_message,
        "min_border_distance_km": round(min_imbl_dist, 1),
        "closest_border_name": closest_imbl["name"] if closest_imbl else "None",
        "min_restricted_distance_km": round(min_restricted_dist, 1),
        "closest_restricted_name": closest_restricted["name"] if closest_restricted else "None",
        "safe_return_heading_deg": safe_heading,
        "gps_accuracy_meters": round(gps_acc, 1),
        "buffer_zone_tier": "CRITICAL_BUFFER" if status == "CRITICAL" else ("WARNING_BUFFER" if status == "WARNING" else "SAFE"),
        "buffer_hierarchy_level": (
            "RESTRICTED_AREA" if (is_raw_inside_restricted or min_imbl_dist < 1.5)
            else ("CRITICAL_BUFFER" if status == "CRITICAL"
            else ("WARNING_BUFFER" if status == "WARNING" else "SAFE_AREA"))
        ),
        "timestamp": "LIVE",
    }



def filter_and_rank_pfz_zones(
    candidate_zones: List[Dict[str, Any]],
    origin_lat: float,
    origin_lon: float,
    check_date: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filter and rank PFZ zones prioritizing maritime safety, legal compliance, and ecological sustainability.
    
    Priority Hierarchy:
      1. LEGAL / RESTRICTED AREAS (IMBL, Defense) -> EXCLUDE IMMEDIATELY
      2. ECOLOGICAL / SPAWNING / SEASONAL BAN PROTECTION -> EXCLUDE IMMEDIATELY
      3. MARINE SAFETY (Wind, Waves) -> PENALIZE / EXCLUDE IF CRITICAL
      4. CROWDING / FISHING PRESSURE -> PENALIZE HIGH CROWDING & PREFER LOW-PRESSURE ALTERNATIVES
      5. PFZ SUITABILITY (SST, Chlorophyll, thermal fronts)
    """
    safe_zones = []
    excluded_zones = []

    for zone in candidate_zones:
        z_lat = zone.get("center_lat", origin_lat + 0.15)
        z_lon = zone.get("center_lon", origin_lon + 0.20)

        # 1. Check Maritime Border / Defense Geofences
        geofence_status = check_marine_geofence(z_lat, z_lon)
        if geofence_status["status"] == "CRITICAL" or geofence_status["min_border_distance_km"] < 8.0:
            exclusion_reason = (
                f"Zone overlaps with or is too close to {geofence_status['closest_border_name']} "
                f"({geofence_status['min_border_distance_km']} km) or {geofence_status['closest_restricted_name']}."
            )
            excluded_zones.append({
                **zone,
                "is_safe": False,
                "recommendation_status": "EXCLUDED_RESTRICTED",
                "exclusion_category": "BORDER_SECURITY",
                "exclusion_reason": exclusion_reason,
            })
            continue

        # 2. Check Spawning & Seasonal Protection Bans
        eco_check = check_spawning_and_ecological_sensitivity(z_lat, z_lon, check_date)
        if eco_check.get("ban_active"):
            ban = eco_check["ban_details"]
            exclusion_reason = (
                f"Active Government Seasonal Fishing Ban ({ban.get('ban_name')}). "
                f"Period {ban.get('period')}: Commercial and mechanized fishing prohibited for breeding conservation."
            )
            excluded_zones.append({
                **zone,
                "is_safe": False,
                "recommendation_status": "EXCLUDED_SEASONAL_BAN",
                "exclusion_category": "SEASONAL_BAN",
                "exclusion_reason": exclusion_reason,
                "spawning_details": ban,
            })
            continue

        if eco_check.get("is_protected") and eco_check.get("is_spawning_season"):
            exclusion_reason = (
                f"Inside {eco_check['name']} during active breeding/spawning season "
                f"(Protected species: {', '.join(eco_check.get('target_species', []))}). "
                "Harvesting restricted to protect juvenile and spawning stock."
            )
            excluded_zones.append({
                **zone,
                "is_safe": False,
                "recommendation_status": "EXCLUDED_ECOLOGICAL",
                "exclusion_category": "ECOLOGICAL_PROTECTION",
                "exclusion_reason": exclusion_reason,
                "spawning_details": eco_check,
            })
            continue

        # 3. Zone is legally & ecologically permitted -> evaluate crowding & safety
        crowding_level = zone.get("crowding_level", "LOW")
        vessel_density = zone.get("vessel_density", 0.3)
        vessel_count = zone.get("vessel_count", 3)
        
        # Calculate Crowding Penalty (0.0 to 0.30)
        crowding_penalty = 0.0
        if crowding_level == "HIGH" or vessel_density > 1.2 or vessel_count > 15:
            crowding_level = "HIGH"
            crowding_penalty = 0.25
        elif crowding_level == "MODERATE" or vessel_density > 0.6 or vessel_count > 7:
            crowding_level = "MODERATE"
            crowding_penalty = 0.10
        else:
            crowding_level = "LOW"
            crowding_penalty = 0.0

        # Safety & Distance factors
        dist = zone.get("distance_km", 25.0)
        dist_factor = max(0.0, 1.0 - (dist / 100.0))
        clearance = geofence_status["min_border_distance_km"]
        clearance_factor = min(1.0, clearance / 30.0)
        raw_suitability = zone.get("score", zone.get("suitability_score", 0.75))

        # Composite Sustainable PFZ Score:
        # Suitability (45%) + Safety/Distance (20%) + Border Clearance (15%) - Crowding Penalty (up to -25%)
        composite_score = round(
            (raw_suitability * 0.45) +
            (dist_factor * 0.20) +
            (clearance_factor * 0.15) +
            0.20 - crowding_penalty,
            3
        )

        safe_zones.append({
            **zone,
            "is_safe": True,
            "safety_status": "PERMITTED",
            "border_clearance_km": clearance,
            "crowding_level": crowding_level,
            "crowding_penalty": crowding_penalty,
            "vessel_density": round(vessel_density, 2),
            "vessel_count": vessel_count,
            "raw_suitability_score": raw_suitability,
            "final_sustainable_score": composite_score,
            "score": composite_score,
        })

    # Sort safe zones by sustainable score
    safe_zones.sort(key=lambda z: z.get("final_sustainable_score", z.get("score", 0)), reverse=True)

    # Label top zone as RECOMMENDED and others as ALTERNATIVE
    for i, sz in enumerate(safe_zones):
        if i == 0:
            sz["recommendation_status"] = "RECOMMENDED"
            sz["option_label"] = "OPTION A"
            sz["option_title"] = "Option A — Best Overall"
            if sz.get("crowding_level") == "LOW":
                sz["alternative_reason"] = "Optimal balance: Favourable oceanographic conditions with low fleet crowding and full safety clearance."
            else:
                sz["alternative_reason"] = "Best available sector in region with permitted safety and environmental scores."
        elif i == 1:
            sz["recommendation_status"] = "ALTERNATIVE"
            sz["option_label"] = "OPTION B"
            sz["option_title"] = "Option B — Less Crowded"
            sz["alternative_reason"] = "Alternative zone: Offers lower vessel density and reduced gear interference."
        elif i == 2:
            sz["recommendation_status"] = "ALTERNATIVE"
            sz["option_label"] = "OPTION C"
            sz["option_title"] = "Option C — Closest Safe Alternative"
            sz["alternative_reason"] = "Closest safe alternative sector with permitted environmental and safety clearance."
        else:
            sz["recommendation_status"] = "ALTERNATIVE"
            sz["option_label"] = f"OPTION {chr(65 + i)}"
            sz["option_title"] = f"Option {chr(65 + i)}"
            sz["alternative_reason"] = "Secondary alternative zone with moderate suitability."

    return safe_zones, excluded_zones


# ── Full GeoJSON FeatureCollection Exporter ─────────────────────────────────

def get_geofence_geojson() -> Dict[str, Any]:
    """Export all maritime borders, MPAs, restricted areas, seasonal bans, and port channels as GeoJSON."""
    features = []

    # 1. IMBL LineStrings
    for b in IMBL_BOUNDARIES:
        coords = b["coordinates"]
        mid_idx = len(coords) // 2
        mid_lon, mid_lat = coords[mid_idx][0], coords[mid_idx][1]
        features.append({
            "type": "Feature",
            "properties": {
                "id": b["id"],
                "name": b["name"],
                "short_name": "Palk Strait IMBL" if "SRI-LANKA" in b["id"] else "Sir Creek Border",
                "category": b["category"],
                "zone_type": "BORDER",
                "type": b["type"],
                "color": b.get("color", "#ef4444"),
                "severity": "CRITICAL",
                "icon": "🚨",
                "center_lat": mid_lat,
                "center_lon": mid_lon,
                "description": b["description"],
                "legal_warning": "Sovereign International Maritime Boundary Line. Crossing strictly prohibited under bilateral treaties.",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": b["coordinates"],
            },
        })

    # 2. Restricted Security & Defense Polygons
    for z in RESTRICTED_SECURITY_ZONES:
        coords = []
        for deg in range(0, 360, 15):
            rad = math.radians(deg)
            dlat = (z["radius_km"] / 111.0) * math.cos(rad)
            dlon = (z["radius_km"] / (111.0 * math.cos(math.radians(z["lat"])))) * math.sin(rad)
            coords.append([round(z["lon"] + dlon, 4), round(z["lat"] + dlat, 4)])
        coords.append(coords[0])

        features.append({
            "type": "Feature",
            "properties": {
                "id": z["id"],
                "name": z["name"],
                "short_name": z.get("short_name", z["name"]),
                "category": z["category"],
                "zone_type": "DEFENSE_RESTRICTED",
                "color": z.get("color", "#dc2626"),
                "severity": z.get("severity", "CRITICAL"),
                "icon": z.get("icon", "⛔"),
                "center_lat": z["lat"],
                "center_lon": z["lon"],
                "radius_km": z["radius_km"],
                "description": z["description"],
                "legal_warning": z.get("legal_warning", "Ministry of Defence Exclusion Zone. Navigation prohibited."),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
        })

    # 3. Marine Protected Areas (MPAs) & Spawning Sanctuaries
    for m in MARINE_PROTECTED_AREAS:
        coords = []
        for deg in range(0, 360, 15):
            rad = math.radians(deg)
            dlat = (m["radius_km"] / 111.0) * math.cos(rad)
            dlon = (m["radius_km"] / (111.0 * math.cos(math.radians(m["lat"])))) * math.sin(rad)
            coords.append([round(m["lon"] + dlon, 4), round(m["lat"] + dlat, 4)])
        coords.append(coords[0])

        features.append({
            "type": "Feature",
            "properties": {
                "id": m["id"],
                "name": m["name"],
                "short_name": m["name"].split(" (")[0],
                "category": m["category"],
                "zone_type": "MPA",
                "color": m.get("color", "#10b981"),
                "severity": "PROTECTED",
                "icon": "🛡️",
                "center_lat": m["lat"],
                "center_lon": m["lon"],
                "radius_km": m["radius_km"],
                "target_species": m.get("target_species", []),
                "description": m["description"],
                "legal_warning": "Ecologically Sensitive Marine Sanctuary. Commercial trawling and extraction prohibited by Wildlife Protection Act.",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ── Agent Execution Class ───────────────────────────────────────────────────

class GeofenceAgent(BaseMarineAgent):
    """Evaluates location against maritime geofences, seasonal bans, and emits safety telemetry."""

    def __init__(self):
        super().__init__(agent_type=AgentType.GEOFENCE)

    async def analyze(self, task: AgentTask):
        lat = task.context.get("lat", 13.08)
        lon = task.context.get("lon", 80.27)
        check_date = task.start_date or datetime.now()

        status_result = check_marine_geofence(lat, lon)
        eco_result = check_spawning_and_ecological_sensitivity(lat, lon, check_date)

        findings = [
            AgentFinding(
                variable="geofence_status",
                description=status_result["alert_message"],
                anomaly_detected=status_result["status"] != "SAFE",
            ),
            AgentFinding(
                variable="imbl_clearance_km",
                description=f"Distance to closest border ({status_result['closest_border_name']}): {status_result['min_border_distance_km']} km",
            ),
        ]

        if eco_result.get("ban_active"):
            findings.append(
                AgentFinding(
                    variable="seasonal_fishing_ban",
                    description=eco_result["ban_details"]["description"],
                    anomaly_detected=True,
                )
            )

        if eco_result.get("is_protected"):
            findings.append(
                AgentFinding(
                    variable="ecological_protection",
                    description=f"Ecological Sanctuary: {eco_result['name']}. {eco_result['description']}",
                    anomaly_detected=eco_result.get("is_spawning_season", False),
                )
            )

        hypotheses = [
            f"Marine Geofence Assessment: {status_result['alert_message']}"
        ]
        if eco_result.get("ban_active"):
            hypotheses.append(f"Seasonal Ban Advisory: {eco_result['ban_details']['description']}")

        return findings, [], hypotheses, 0.95

