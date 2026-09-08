from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("orca.location")


class EnvironmentType(str, Enum):
    COASTAL = "COASTAL"
    INLAND = "INLAND"
    ISLAND = "ISLAND"
    MARINE = "MARINE"  # At sea / offshore


class FishingType(str, Enum):
    MARINE = "MARINE"
    FRESHWATER = "FRESHWATER"
    BOTH = "BOTH"
    UNKNOWN = "UNKNOWN"


class WaterbodyType(str, Enum):
    LAKE = "lake"
    RESERVOIR = "reservoir"
    POND = "pond"
    RIVER = "river"
    CHECK_DAM = "check_dam"
    MARINE = "marine"
    UNKNOWN = "unknown"


class Waterbody(BaseModel):
    """A discovered water body near a location."""
    name: str
    type: WaterbodyType
    latitude: float
    longitude: float
    distance_km: float
    fishing_permitted: str = "UNKNOWN"  # YES / NO / UNKNOWN
    permission_notes: str = ""
    fishing_activity: str = "UNKNOWN"  # KNOWN / HISTORICAL / UNKNOWN
    source: str = "geospatial"


class LocationContext(BaseModel):
    """Geographic context for a user's location."""
    location_name: str
    latitude: float
    longitude: float
    bbox: Optional[list[float]] = None  # [west, south, east, north]
    country: str = "India"
    state: Optional[str] = None
    district: Optional[str] = None
    environment: EnvironmentType = EnvironmentType.INLAND
    nearest_coast_km: Optional[float] = None
    nearest_harbor: Optional[dict] = None  # name, lat, lon, distance_km, state
    marine_region: Optional[str] = None
    fishing_type: FishingType = FishingType.UNKNOWN
    applicable_domains: list[str] = Field(default_factory=list)
    inapplicable_domains: list[str] = Field(default_factory=list)
    waterbodies: list[Waterbody] = Field(default_factory=list)
    clarification_needed: Optional[str] = None


COASTAL_HARBORS = [
    {"name": "Kasimedu Fishing Harbour, Chennai", "lat": 13.1245, "lon": 80.2982, "state": "Tamil Nadu", "district": "Chennai"},
    {"name": "Cuddalore Fishing Harbour", "lat": 11.7185, "lon": 79.7782, "state": "Tamil Nadu", "district": "Cuddalore"},
    {"name": "Nagapattinam Port Harbour", "lat": 10.7656, "lon": 79.8424, "state": "Tamil Nadu", "district": "Nagapattinam"},
    {"name": "Rameswaram Fishing Jetty", "lat": 9.2876, "lon": 79.3129, "state": "Tamil Nadu", "district": "Ramanathapuram"},
    {"name": "Thoothukudi (Tuticorin) Fishing Harbour", "lat": 8.7642, "lon": 78.1348, "state": "Tamil Nadu", "district": "Thoothukudi"},
    {"name": "Kanyakumari / Colachel Jetty", "lat": 8.0883, "lon": 77.5385, "state": "Tamil Nadu", "district": "Kanyakumari"},
    {"name": "Cochin Fisheries Harbour, Kochi", "lat": 9.9392, "lon": 76.2598, "state": "Kerala", "district": "Ernakulam"},
    {"name": "Vizhinjam Sea Port Harbour", "lat": 8.3756, "lon": 76.9942, "state": "Kerala", "district": "Thiruvananthapuram"},
    {"name": "Neendakara Fishing Harbour, Kollam", "lat": 8.9392, "lon": 76.5382, "state": "Kerala", "district": "Kollam"},
    {"name": "Munambam Mini Fishing Harbour", "lat": 10.1856, "lon": 76.1685, "state": "Kerala", "district": "Ernakulam"},
    {"name": "Beypore Port, Kozhikode", "lat": 11.1624, "lon": 75.8042, "state": "Kerala", "district": "Kozhikode"},
    {"name": "Visakhapatnam Fishing Harbour", "lat": 17.6985, "lon": 83.2982, "state": "Andhra Pradesh", "district": "Visakhapatnam"},
    {"name": "Kakinada Fisheries Harbour", "lat": 16.9892, "lon": 82.2475, "state": "Andhra Pradesh", "district": "East Godavari"},
    {"name": "Machilipatnam Fishing Port", "lat": 16.1824, "lon": 81.1645, "state": "Andhra Pradesh", "district": "Krishna"},
    {"name": "Sassoon Dock, Mumbai", "lat": 18.9168, "lon": 72.8242, "state": "Maharashtra", "district": "Mumbai"},
    {"name": "Bhaucha Dhakka, Mumbai", "lat": 18.9568, "lon": 72.8512, "state": "Maharashtra", "district": "Mumbai"},
    {"name": "Mirkarwada Fishing Harbour, Ratnagiri", "lat": 16.9942, "lon": 73.2845, "state": "Maharashtra", "district": "Ratnagiri"},
    {"name": "Veraval Mega Fishing Harbour", "lat": 20.9024, "lon": 70.3685, "state": "Gujarat", "district": "Gir Somnath"},
    {"name": "Porbandar Fishing Harbour", "lat": 21.6425, "lon": 69.6052, "state": "Gujarat", "district": "Porbandar"},
    {"name": "Okha Jetty, Dwarka", "lat": 22.4645, "lon": 69.0724, "state": "Gujarat", "district": "Devbhumi Dwarka"},
    {"name": "Old Port / Mangalore Fisheries Harbour", "lat": 12.8685, "lon": 74.8385, "state": "Karnataka", "district": "Dakshina Kannada"},
    {"name": "Malpe Port & Harbour, Udupi", "lat": 13.3512, "lon": 74.7025, "state": "Karnataka", "district": "Udupi"},
    {"name": "Paradeep Fishing Harbour", "lat": 20.2642, "lon": 86.6852, "state": "Odisha", "district": "Jagatsinghpur"},
    {"name": "Dhamra Fisheries Harbour", "lat": 20.8145, "lon": 86.9642, "state": "Odisha", "district": "Bhadrak"},
    {"name": "Digha Mohana Fishery Harbour", "lat": 21.6245, "lon": 87.5385, "state": "West Bengal", "district": "Purba Medinipur"},
    {"name": "Kakdwip Fisheries Port", "lat": 21.8745, "lon": 88.1895, "state": "West Bengal", "district": "South 24 Parganas"},
    {"name": "Malim / Panaji Fishing Harbour", "lat": 15.5024, "lon": 73.8345, "state": "Goa", "district": "North Goa"},
    {"name": "Junglighat Fishing Harbour, Port Blair", "lat": 11.6645, "lon": 92.7385, "state": "Andaman and Nicobar", "district": "South Andaman"},
]


def find_nearest_coastal_harbor(lat: float, lon: float) -> dict:
    """Find the nearest coastal fishing harbor to any latitude/longitude coordinate."""
    import math
    def _dist(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))

    best = None
    min_d = float("inf")
    for h in COASTAL_HARBORS:
        d = _dist(lat, lon, h["lat"], h["lon"])
        if d < min_d:
            min_d = d
            best = {**h, "distance_km": round(d, 1)}
    return best or {**COASTAL_HARBORS[0], "distance_km": 20.0}


# ── Indian location database with environment classification ──────────────

INDIA_LOCATIONS = {
    # ── Coastal cities (marine fishing applicable) ─────────────────────
    "chennai": {
        "lat": 13.0827, "lon": 80.2707,
        "bbox": [79.8, 12.8, 80.5, 13.3],
        "state": "Tamil Nadu", "district": "Chennai",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0.5,
        "waterbodies": [
            {"name": "Chennai Fishing Harbour", "type": "marine", "lat": 13.08, "lon": 80.29, "fishing_permitted": "YES"},
            {"name": "Ennore Creek", "type": "marine", "lat": 13.22, "lon": 80.32, "fishing_permitted": "YES"},
        ],
    },
    "mumbai": {
        "lat": 19.0760, "lon": 72.8777,
        "bbox": [72.5, 18.8, 73.2, 19.3],
        "state": "Maharashtra", "district": "Mumbai",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0.3,
        "waterbodies": [
            {"name": "Mumbai Fishing Harbour", "type": "marine", "lat": 18.95, "lon": 72.84, "fishing_permitted": "YES"},
        ],
    },
    "kochi": {
        "lat": 9.9312, "lon": 76.2673,
        "bbox": [76.0, 9.7, 76.5, 10.2],
        "state": "Kerala", "district": "Ernakulam",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0.5,
        "waterbodies": [
            {"name": "Cochin Fishing Harbour", "type": "marine", "lat": 9.97, "lon": 76.27, "fishing_permitted": "YES"},
            {"name": "Vembanad Lake", "type": "lake", "lat": 9.95, "lon": 76.35, "fishing_permitted": "YES"},
        ],
    },
    "goa": {
        "lat": 15.2993, "lon": 74.1240,
        "bbox": [73.7, 14.9, 74.5, 15.6],
        "state": "Goa", "district": "Goa",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 1.0,
        "waterbodies": [
            {"name": "Mandovi River", "type": "river", "lat": 15.50, "lon": 73.91, "fishing_permitted": "YES"},
            {"name": "Zuari River", "type": "river", "lat": 15.40, "lon": 73.87, "fishing_permitted": "YES"},
        ],
    },
    "visakhapatnam": {
        "lat": 17.6868, "lon": 83.2185,
        "bbox": [82.9, 17.4, 83.5, 18.0],
        "state": "Andhra Pradesh", "district": "Visakhapatnam",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0.5,
    },
    "vizag": {
        "lat": 17.6868, "lon": 83.2185,
        "bbox": [82.9, 17.4, 83.5, 18.0],
        "state": "Andhra Pradesh", "district": "Visakhapatnam",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0.5,
    },
    "tuticorin": {
        "lat": 8.7642, "lon": 78.1348,
        "bbox": [77.9, 8.5, 78.4, 9.0],
        "state": "Tamil Nadu", "district": "Thoothukudi",
        "environment": "COASTAL",
        "marine_region": "Gulf of Mannar",
        "nearest_coast_km": 0.3,
    },
    "thoothukudi": {
        "lat": 8.7642, "lon": 78.1348,
        "bbox": [77.9, 8.5, 78.4, 9.0],
        "state": "Tamil Nadu", "district": "Thoothukudi",
        "environment": "COASTAL",
        "marine_region": "Gulf of Mannar",
        "nearest_coast_km": 0.3,
    },
    "mangalore": {
        "lat": 12.9141, "lon": 74.8560,
        "bbox": [74.6, 12.7, 75.1, 13.1],
        "state": "Karnataka", "district": "Dakshina Kannada",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0.3,
    },
    "puri": {
        "lat": 19.8135, "lon": 85.8312,
        "bbox": [85.5, 19.5, 86.1, 20.1],
        "state": "Odisha", "district": "Puri",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0.5,
    },
    "pondicherry": {
        "lat": 11.9416, "lon": 79.8083,
        "bbox": [79.5, 11.7, 80.1, 12.2],
        "state": "Puducherry", "district": "Puducherry",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0.3,
    },
    "kanyakumari": {
        "lat": 8.0883, "lon": 77.5385,
        "bbox": [77.2, 7.8, 77.9, 8.4],
        "state": "Tamil Nadu", "district": "Kanyakumari",
        "environment": "COASTAL",
        "marine_region": "Indian Ocean",
        "nearest_coast_km": 0.2,
    },
    "rameswaram": {
        "lat": 9.2876, "lon": 79.3129,
        "bbox": [79.0, 9.0, 79.6, 9.5],
        "state": "Tamil Nadu", "district": "Ramanathapuram",
        "environment": "ISLAND",
        "marine_region": "Palk Strait",
        "nearest_coast_km": 0.1,
    },

    # ── Inland cities (freshwater fishing applicable) ──────────────────
    "patna": {
        "lat": 25.5941, "lon": 85.1376,
        "bbox": [84.9, 25.4, 85.4, 25.8],
        "state": "Bihar", "district": "Patna",
        "environment": "INLAND",
        "nearest_coast_km": 450.0,
        "marine_region": None,
        "waterbodies": [
            {"name": "Ganges River", "type": "river", "lat": 25.62, "lon": 85.18, "fishing_permitted": "YES", "fishing_activity": "KNOWN"},
        ],
    },
    "tiruppur": {
        "lat": 11.1085, "lon": 77.3411,
        "bbox": [77.1, 10.9, 77.5, 11.3],
        "state": "Tamil Nadu", "district": "Tiruppur",
        "environment": "INLAND",
        "nearest_coast_km": 150.0,
        "marine_region": None,
        "waterbodies": [
            {"name": "Noyyal River", "type": "river", "lat": 11.11, "lon": 77.35, "fishing_permitted": "UNKNOWN", "fishing_activity": "UNKNOWN"},
            {"name": "Nanjarayan Tank", "type": "lake", "lat": 11.16, "lon": 77.33, "fishing_permitted": "UNKNOWN", "fishing_activity": "HISTORICAL"},
        ],
    },
    "tirupur": {
        "lat": 11.1085, "lon": 77.3411,
        "bbox": [77.1, 10.9, 77.5, 11.3],
        "state": "Tamil Nadu", "district": "Tiruppur",
        "environment": "INLAND",
        "nearest_coast_km": 150.0,
        "marine_region": None,
    },
    "coimbatore": {
        "lat": 11.0168, "lon": 76.9558,
        "bbox": [76.7, 10.8, 77.2, 11.2],
        "state": "Tamil Nadu", "district": "Coimbatore",
        "environment": "INLAND",
        "nearest_coast_km": 120.0,
        "marine_region": None,
        "waterbodies": [
            {"name": "Vedapatti Lake", "type": "lake", "lat": 11.03, "lon": 76.97, "fishing_permitted": "UNKNOWN", "fishing_activity": "HISTORICAL"},
            {"name": "Kumaraswamy Lake", "type": "lake", "lat": 11.00, "lon": 76.93, "fishing_permitted": "UNKNOWN", "fishing_activity": "HISTORICAL"},
            {"name": "Perur Lake", "type": "lake", "lat": 10.98, "lon": 76.88, "fishing_permitted": "UNKNOWN", "fishing_activity": "HISTORICAL"},
            {"name": "Singanallur Lake", "type": "lake", "lat": 11.01, "lon": 77.02, "fishing_permitted": "UNKNOWN", "fishing_activity": "HISTORICAL"},
            {"name": "Valankulam Lake", "type": "lake", "lat": 11.02, "lon": 76.96, "fishing_permitted": "UNKNOWN", "fishing_activity": "UNKNOWN"},
            {"name": "Poondi Lake", "type": "lake", "lat": 10.97, "lon": 76.98, "fishing_permitted": "UNKNOWN", "fishing_activity": "UNKNOWN"},
        ],
    },
    "madurai": {
        "lat": 9.9252, "lon": 78.1198,
        "bbox": [77.8, 9.7, 78.4, 10.2],
        "state": "Tamil Nadu", "district": "Madurai",
        "environment": "INLAND",
        "nearest_coast_km": 90.0,
        "waterbodies": [
            {"name": "Vaigai River", "type": "river", "lat": 9.93, "lon": 78.12, "fishing_permitted": "UNKNOWN", "fishing_activity": "HISTORICAL"},
            {"name": "Periyar Lake", "type": "lake", "lat": 9.85, "lon": 77.15, "fishing_permitted": "UNKNOWN", "fishing_activity": "UNKNOWN"},
        ],
    },
    "bengaluru": {
        "lat": 12.9716, "lon": 77.5946,
        "bbox": [77.3, 12.7, 77.9, 13.2],
        "state": "Karnataka", "district": "Bengaluru Urban",
        "environment": "INLAND",
        "nearest_coast_km": 300.0,
        "waterbodies": [
            {"name": "Ulsoor Lake", "type": "lake", "lat": 12.98, "lon": 77.63, "fishing_permitted": "NO", "fishing_activity": "UNKNOWN"},
            {"name": "Hebbal Lake", "type": "lake", "lat": 13.04, "lon": 77.59, "fishing_permitted": "UNKNOWN", "fishing_activity": "UNKNOWN"},
        ],
    },
    "bangalore": {
        "lat": 12.9716, "lon": 77.5946,
        "bbox": [77.3, 12.7, 77.9, 13.2],
        "state": "Karnataka", "district": "Bengaluru Urban",
        "environment": "INLAND",
        "nearest_coast_km": 300.0,
    },
    "hyderabad": {
        "lat": 17.3850, "lon": 78.4867,
        "bbox": [78.2, 17.1, 78.8, 17.7],
        "state": "Telangana", "district": "Hyderabad",
        "environment": "INLAND",
        "nearest_coast_km": 250.0,
        "waterbodies": [
            {"name": "Hussain Sagar Lake", "type": "lake", "lat": 17.42, "lon": 78.47, "fishing_permitted": "UNKNOWN", "fishing_activity": "UNKNOWN"},
        ],
    },
    "pune": {
        "lat": 18.5204, "lon": 73.8567,
        "bbox": [73.6, 18.3, 74.1, 18.7],
        "state": "Maharashtra", "district": "Pune",
        "environment": "INLAND",
        "nearest_coast_km": 120.0,
    },
    "lucknow": {
        "lat": 26.8467, "lon": 80.9462,
        "bbox": [80.7, 26.6, 81.2, 27.1],
        "state": "Uttar Pradesh", "district": "Lucknow",
        "environment": "INLAND",
        "nearest_coast_km": 800.0,
    },
    "jaipur": {
        "lat": 26.9124, "lon": 75.7873,
        "bbox": [75.5, 26.7, 76.0, 27.1],
        "state": "Rajasthan", "district": "Jaipur",
        "environment": "INLAND",
        "nearest_coast_km": 700.0,
    },
    "kanpur": {
        "lat": 26.4499, "lon": 80.3319,
        "bbox": [80.1, 26.2, 80.6, 26.7],
        "state": "Uttar Pradesh", "district": "Kanpur",
        "environment": "INLAND",
        "nearest_coast_km": 800.0,
    },
    "nagpur": {
        "lat": 21.1458, "lon": 79.0882,
        "bbox": [78.8, 20.9, 79.3, 21.4],
        "state": "Maharashtra", "district": "Nagpur",
        "environment": "INLAND",
        "nearest_coast_km": 600.0,
    },
    "indore": {
        "lat": 22.7196, "lon": 75.8577,
        "bbox": [75.6, 22.5, 76.1, 22.9],
        "state": "Madhya Pradesh", "district": "Indore",
        "environment": "INLAND",
        "nearest_coast_km": 500.0,
    },
    "bhopal": {
        "lat": 23.2599, "lon": 77.4126,
        "bbox": [77.2, 23.0, 77.6, 23.5],
        "state": "Madhya Pradesh", "district": "Bhopal",
        "environment": "INLAND",
        "nearest_coast_km": 600.0,
    },
    "salem": {
        "lat": 11.6643, "lon": 78.1460,
        "bbox": [77.9, 11.4, 78.4, 11.9],
        "state": "Tamil Nadu", "district": "Salem",
        "environment": "INLAND",
        "nearest_coast_km": 160.0,
    },
    "trichy": {
        "lat": 10.7905, "lon": 78.7047,
        "bbox": [78.5, 10.6, 78.9, 11.0],
        "state": "Tamil Nadu", "district": "Tiruchirappalli",
        "environment": "INLAND",
        "nearest_coast_km": 80.0,
    },
    "erode": {
        "lat": 11.3410, "lon": 77.7172,
        "bbox": [77.5, 11.1, 77.9, 11.5],
        "state": "Tamil Nadu", "district": "Erode",
        "environment": "INLAND",
        "nearest_coast_km": 180.0,
    },
    "delhi": {
        "lat": 28.6139, "lon": 77.2090,
        "bbox": [77.0, 28.4, 77.4, 28.9],
        "state": "Delhi", "district": "Delhi",
        "environment": "INLAND",
        "nearest_coast_km": 1000.0,
    },

    # ── States (inland if no coast) ────────────────────────────────────
    "tamil nadu": {
        "lat": 11.1271, "lon": 78.6569,
        "bbox": [76.0, 8.0, 80.5, 13.5],
        "state": "Tamil Nadu",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0,
    },
    "kerala": {
        "lat": 10.8505, "lon": 76.2711,
        "bbox": [72.2, 8.0, 77.5, 12.8],
        "state": "Kerala",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0,
    },
    "karnataka": {
        "lat": 15.3173, "lon": 75.7139,
        "bbox": [74.0, 11.5, 78.5, 18.5],
        "state": "Karnataka",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0,
    },
    "andhra pradesh": {
        "lat": 15.9129, "lon": 79.7400,
        "bbox": [77.0, 12.5, 84.5, 19.5],
        "state": "Andhra Pradesh",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0,
    },
    "odisha": {
        "lat": 20.9517, "lon": 85.0985,
        "bbox": [81.0, 17.5, 87.5, 22.5],
        "state": "Odisha",
        "environment": "COASTAL",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0,
    },
    "maharashtra": {
        "lat": 19.7515, "lon": 75.7139,
        "bbox": [72.5, 15.5, 74.0, 22.0],
        "state": "Maharashtra",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0,
    },
    "gujarat": {
        "lat": 22.2587, "lon": 71.1924,
        "bbox": [68.0, 20.0, 74.5, 24.5],
        "state": "Gujarat",
        "environment": "COASTAL",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0,
    },
    "andaman": {
        "lat": 11.7, "lon": 92.7,
        "bbox": [91.5, 6.5, 94.5, 14.0],
        "state": "Andaman and Nicobar Islands",
        "environment": "ISLAND",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0,
    },
    "lakshadweep": {
        "lat": 10.5, "lon": 72.5,
        "bbox": [71.5, 8.0, 74.0, 12.5],
        "state": "Lakshadweep",
        "environment": "ISLAND",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0,
    },

    # ── Marine regions ─────────────────────────────────────────────────
    "bay of bengal": {
        "lat": 14.0, "lon": 87.5,
        "bbox": [80.0, 5.0, 95.0, 22.0],
        "environment": "MARINE",
        "marine_region": "Bay of Bengal",
        "nearest_coast_km": 0,
    },
    "arabian sea": {
        "lat": 15.0, "lon": 72.0,
        "bbox": [56.0, 5.0, 78.0, 24.0],
        "environment": "MARINE",
        "marine_region": "Arabian Sea",
        "nearest_coast_km": 0,
    },
    "indian ocean": {
        "lat": 0.0, "lon": 80.0,
        "bbox": [30.0, -40.0, 120.0, 25.0],
        "environment": "MARINE",
        "marine_region": "Indian Ocean",
        "nearest_coast_km": 0,
    },
}


def resolve_location(name: str) -> LocationContext | None:
    """Resolve a location name to a full LocationContext.
    
    Tries hardcoded Indian locations first, then returns None
    to signal that dynamic geocoding should be used.
    """
    name_lower = name.lower().strip()

    # Remove common prefixes
    for prefix in ["near ", "at ", "in ", "around ", "off ", "close to ", "from ", "to "]:
        if name_lower.startswith(prefix):
            name_lower = name_lower[len(prefix):]

    # Check exact matches only — NEVER use substring matching
    # Because "patna" is a substring of "visakhapatnam" which would be wrong
    for loc_name, info in INDIA_LOCATIONS.items():
        if name_lower == loc_name:
            return _build_context(loc_name.title(), info)

    # NOT found in hardcoded list — return None to trigger dynamic geocoding
    return None


async def resolve_location_dynamic(name: str) -> LocationContext | None:
    """Resolve a location using real geocoding (Nominatim).
    
    First tries the hardcoded list, then falls back to OpenStreetMap
    geocoding. NEVER silently substitutes a different city.
    """
    # Try hardcoded list first (fast)
    static_result = resolve_location(name)
    if static_result:
        return static_result

    # Dynamic geocoding via Nominatim
    try:
        from data.providers.geocoding import get_geocoding_provider
        
        geocoder = get_geocoding_provider()
        results = await geocoder.geocode(name, country_hint="India")
        
        if not results:
            logger.info(f"Dynamic geocoding failed for '{name}' — no results")
            return None
        
        # Use the best result
        best = results[0]
        
        # Only accept results with reasonable confidence
        if best.confidence < 0.3:
            logger.info(f"Dynamic geocoding low confidence for '{name}': {best.confidence}")
            return None
        
        # Build LocationContext from geocoded result
        return _build_context_from_geocoded(best)
        
    except Exception as e:
        logger.warning(f"Dynamic geocoding error for '{name}': {e}")
        return None


def _build_context_from_geocoded(geo) -> LocationContext:
    """Build a LocationContext from a GeocodedLocation."""
    env = EnvironmentType(geo.environment)
    fishing_type = FishingType.MARINE if env in (
        EnvironmentType.COASTAL, EnvironmentType.MARINE, EnvironmentType.ISLAND
    ) else FishingType.FRESHWATER

    applicable = ["weather", "ocean", "satellite", "fisheries"]
    inapplicable = []

    if env == EnvironmentType.INLAND:
        inapplicable.extend(["pfz_marine", "tide", "marine_advisory"])
        applicable = ["weather", "freshwater_fishing", "geospatial"]

    bbox = geo.bbox or [
        geo.longitude - 2, geo.latitude - 2,
        geo.longitude + 2, geo.latitude + 2,
    ]

    nearest_h = find_nearest_coastal_harbor(geo.latitude, geo.longitude)

    return LocationContext(
        location_name=geo.name,
        latitude=geo.latitude,
        longitude=geo.longitude,
        bbox=bbox,
        country=geo.country,
        state=geo.state,
        district=geo.district or geo.city,
        environment=env,
        nearest_coast_km=geo.nearest_coast_km or nearest_h.get("distance_km"),
        nearest_harbor=nearest_h,
        marine_region=geo.marine_region,
        fishing_type=fishing_type,
        applicable_domains=applicable,
        inapplicable_domains=inapplicable,
        waterbodies=[],
        clarification_needed=None,
    )


def _build_context(name: str, info: dict) -> LocationContext:
    """Build a LocationContext from location database info."""
    env = EnvironmentType(info.get("environment", "INLAND"))
    fishing_type = FishingType.MARINE if env in (EnvironmentType.COASTAL, EnvironmentType.MARINE, EnvironmentType.ISLAND) else FishingType.FRESHWATER

    applicable = ["weather", "ocean", "satellite", "fisheries"]
    inapplicable = []

    if env == EnvironmentType.INLAND:
        # Marine PFZ not applicable for inland
        inapplicable.extend(["pfz_marine", "tide", "marine_advisory"])
        applicable = ["weather", "freshwater_fishing", "geospatial"]

    waterbodies = []
    for wb in info.get("waterbodies", []):
        waterbodies.append(Waterbody(
            name=wb["name"],
            type=WaterbodyType(wb["type"]),
            latitude=wb["lat"],
            longitude=wb["lon"],
            distance_km=0,  # Will be calculated
            fishing_permitted=wb.get("fishing_permitted", "UNKNOWN"),
            fishing_activity=wb.get("fishing_activity", "UNKNOWN"),
        ))

    nearest_h = find_nearest_coastal_harbor(info["lat"], info["lon"])

    return LocationContext(
        location_name=name,
        latitude=info["lat"],
        longitude=info["lon"],
        bbox=info.get("bbox"),
        state=info.get("state"),
        district=info.get("district"),
        environment=env,
        nearest_coast_km=info.get("nearest_coast_km") or nearest_h.get("distance_km"),
        nearest_harbor=nearest_h,
        marine_region=info.get("marine_region"),
        fishing_type=fishing_type,
        applicable_domains=applicable,
        inapplicable_domains=inapplicable,
        waterbodies=waterbodies,
        clarification_needed=None,
    )
