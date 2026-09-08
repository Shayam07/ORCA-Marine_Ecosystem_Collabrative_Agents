"""ORCA Geocoding Provider — Dynamic location resolution using OpenStreetMap Nominatim.

Provides forward geocoding (place name → coordinates) and reverse geocoding
(coordinates → place name). Never guesses or silently substitutes locations.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Optional

import aiohttp
from pydantic import BaseModel

logger = logging.getLogger("orca.geocoding")


class GeocodedLocation(BaseModel):
    """Result of a geocoding lookup."""
    name: str
    display_name: str
    latitude: float
    longitude: float
    country: str = "India"
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    confidence: float = 0.0
    source: str = "nominatim"
    bbox: Optional[list[float]] = None  # [west, south, east, north]

    # Environment classification
    environment: str = "INLAND"  # COASTAL, INLAND, ISLAND, MARINE
    nearest_coast_km: Optional[float] = None
    marine_region: Optional[str] = None


# ── Indian coastal approximation (simplified coastline points) ──────────
# Used to estimate nearest coast distance
INDIAN_COAST_POINTS = [
    # Tamil Nadu coast
    (13.08, 80.27), (12.99, 80.25), (12.50, 80.15), (11.62, 79.80),
    (10.79, 79.84), (9.97, 76.27), (8.76, 78.13), (8.09, 77.54),
    # Kerala coast
    (10.00, 76.22), (9.50, 76.30), (8.90, 76.55), (8.50, 76.90),
    # Karnataka coast
    (12.87, 74.88), (13.65, 74.68), (14.52, 74.40),
    # Goa coast
    (15.40, 73.88), (15.50, 73.91),
    # Maharashtra coast
    (16.00, 73.50), (17.00, 73.00), (18.00, 72.85), (19.08, 72.88),
    (19.80, 72.82),
    # Gujarat coast
    (20.50, 72.80), (21.00, 72.20), (22.00, 70.00), (23.00, 68.50),
    # Odisha coast
    (19.81, 85.83), (20.50, 87.00), (21.50, 87.50),
    # West Bengal coast
    (21.60, 87.50), (22.00, 88.00),
    # Andhra coast
    (17.69, 83.22), (16.50, 81.80), (15.50, 80.40),
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km using Haversine formula."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_nearest_coast(lat: float, lon: float) -> float:
    """Estimate distance to nearest Indian coast in km."""
    min_dist = float("inf")
    for coast_lat, coast_lon in INDIAN_COAST_POINTS:
        d = _haversine_km(lat, lon, coast_lat, coast_lon)
        if d < min_dist:
            min_dist = d
    return round(min_dist, 1)


def classify_environment(lat: float, lon: float, nearest_coast_km: float) -> str:
    """Classify a location as COASTAL, INLAND, ISLAND, or MARINE."""
    if nearest_coast_km < 5.0:
        return "COASTAL"
    elif nearest_coast_km < 25.0:
        return "COASTAL"  # Still marine-relevant
    else:
        return "INLAND"


class GeocodingProvider:
    """Real geocoding using OpenStreetMap Nominatim.
    
    Features:
    - Forward geocoding: place name → coordinates
    - Reverse geocoding: coordinates → place name
    - Environment classification based on coastal proximity
    - India-focused with country bias
    - Handles Tamil, Hindi, and other Indian language names
    """

    NOMINATIM_URL = "https://nominatim.openstreetmap.org"
    
    # Common Indian location aliases
    ALIASES = {
        "tirupur": "Tiruppur, Tamil Nadu, India",
        "tiruppur": "Tiruppur, Tamil Nadu, India",
        "tiruchi": "Tiruchirappalli, Tamil Nadu, India",
        "trichy": "Tiruchirappalli, Tamil Nadu, India",
        "trichy": "Tiruchirappalli, Tamil Nadu, India",
        "madurai": "Madurai, Tamil Nadu, India",
        "salem": "Salem, Tamil Nadu, India",
        "erode": "Erode, Tamil Nadu, India",
        "thanjavur": "Thanjavur, Tamil Nadu, India",
        "tanjore": "Thanjavur, Tamil Nadu, India",
        "pondy": "Pondicherry, India",
        "puducherry": "Pondicherry, India",
        "vizag": "Visakhapatnam, Andhra Pradesh, India",
        "vishakhapatnam": "Visakhapatnam, Andhra Pradesh, India",
        "cochyn": "Kochi, Kerala, India",
        "calicut": "Kozhikode, Kerala, India",
        "kozhikode": "Kozhikode, Kerala, India",
        "trivandrum": "Thiruvananthapuram, Kerala, India",
        "thiruvananthapuram": "Thiruvananthapuram, Kerala, India",
        "belgaum": "Belagavi, Karnataka, India",
        "belagavi": "Belagavi, Karnataka, India",
        "bangalore": "Bengaluru, Karnataka, India",
        "bengaluru": "Bengaluru, Karnataka, India",
        "bombay": "Mumbai, Maharashtra, India",
        "calcutta": "Kolkata, West Bengal, India",
        "madras": "Chennai, Tamil Nadu, India",
    }

    # Indian state/region keywords for bias
    INDIA_KEYWORDS = [
        "india", "tamil nadu", "kerala", "karnataka", "andhra pradesh",
        "telangana", "maharashtra", "gujarat", "odisha", "west bengal",
        "goa", "rajasthan", "madhya pradesh", "uttar pradesh",
    ]

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: dict[str, GeocodedLocation] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "ORCA-MarineIntelligence/1.0 (research)"},
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def geocode(
        self,
        place_name: str,
        country_hint: str = "India",
        state_hint: Optional[str] = None,
        limit: int = 5,
    ) -> list[GeocodedLocation]:
        """Forward geocode a place name to coordinates.
        
        Args:
            place_name: The location name to geocode
            country_hint: Country to bias results toward
            state_hint: State/region to bias results toward
            limit: Maximum number of results
            
        Returns:
            List of GeocodedLocation results sorted by confidence
        """
        query = place_name.strip()
        if not query:
            return []

        # Check cache
        cache_key = query.lower()
        if cache_key in self._cache:
            logger.info(f"Geocoding cache hit: {query}")
            return [self._cache[cache_key]]

        # Check aliases
        alias_key = query.lower().replace(",", "").strip()
        if alias_key in self.ALIASES:
            query = self.ALIASES[alias_key]
            logger.info(f"Geocoding alias resolved: {place_name} → {query}")

        # Build search query with India bias
        search_query = query
        if country_hint and country_hint.lower() not in query.lower():
            search_query = f"{query}, {country_hint}"

        try:
            session = await self._get_session()
            params = {
                "q": search_query,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
                "extratags": 1,
                "namedetails": 1,
            }

            # Add country bias
            if country_hint:
                params["countrycodes"] = "in"  # India ISO code

            async with session.get(f"{self.NOMINATIM_URL}/search", params=params) as resp:
                if resp.status != 200:
                    logger.warning(f"Nominatim returned status {resp.status}")
                    return []

                data = await resp.json()

                if not data:
                    logger.info(f"No geocoding results for: {query}")
                    return []

                results = []
                for i, item in enumerate(data):
                    lat = float(item.get("lat", 0))
                    lon = float(item.get("lon", 0))

                    if lat == 0 and lon == 0:
                        continue

                    # Extract address components
                    addr = item.get("address", {})
                    display_name = item.get("display_name", query)
                    namedetails = item.get("namedetails", {})

                    # Get best name
                    name = namedetails.get("name", query)
                    if not name or name == "":
                        # Try to extract from display_name
                        name = display_name.split(",")[0] if display_name else query

                    # Calculate confidence
                    confidence = self._calculate_confidence(
                        query, name, addr, i, item.get("importance", 0)
                    )

                    # Get bounding box
                    bbox_raw = item.get("boundingbox", [])
                    bbox = None
                    if len(bbox_raw) == 4:
                        # Nominatim returns [south, north, west, east]
                        try:
                            bbox = [
                                float(bbox_raw[2]),  # west
                                float(bbox_raw[0]),  # south
                                float(bbox_raw[3]),  # east
                                float(bbox_raw[1]),  # north
                            ]
                        except (ValueError, IndexError):
                            bbox = None

                    # Estimate coastal proximity
                    nearest_coast = estimate_nearest_coast(lat, lon)
                    environment = classify_environment(lat, lon, nearest_coast)

                    # Determine marine region
                    marine_region = None
                    if environment in ("COASTAL", "MARINE"):
                        if 75.0 <= lon <= 80.0 and lat <= 12.0:
                            marine_region = "Lakshadweep Sea"
                        elif 78.0 <= lon <= 82.0 and 8.0 <= lat <= 14.0:
                            marine_region = "Gulf of Mannar"
                        elif lon > 80.0:
                            marine_region = "Bay of Bengal"
                        else:
                            marine_region = "Arabian Sea"

                    result = GeocodedLocation(
                        name=name,
                        display_name=display_name,
                        latitude=lat,
                        longitude=lon,
                        country=addr.get("country", country_hint),
                        state=addr.get("state") or addr.get("state_district"),
                        district=addr.get("county") or addr.get("district"),
                        city=addr.get("city") or addr.get("town") or addr.get("village"),
                        confidence=confidence,
                        bbox=bbox,
                        environment=environment,
                        nearest_coast_km=nearest_coast,
                        marine_region=marine_region,
                    )
                    results.append(result)

                # Sort by confidence
                results.sort(key=lambda r: r.confidence, reverse=True)

                # Cache the best result
                if results:
                    self._cache[cache_key] = results[0]

                logger.info(f"Geocoded '{place_name}' → {len(results)} results, best: "
                           f"{results[0].name} ({results[0].latitude:.4f}, {results[0].longitude:.4f}) "
                           f"env={results[0].environment}" if results else f"No results for '{place_name}'")

                return results

        except asyncio.TimeoutError:
            logger.warning(f"Geocoding timeout for: {query}")
            return []
        except Exception as e:
            logger.warning(f"Geocoding error for '{query}': {e}")
            return []

    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> Optional[GeocodedLocation]:
        """Reverse geocode coordinates to a place name.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            GeocodedLocation or None
        """
        cache_key = f"rev_{latitude:.4f},{longitude:.4f}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            session = await self._get_session()
            params = {
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "addressdetails": 1,
                "extratags": 1,
                "namedetails": 1,
            }

            async with session.get(f"{self.NOMINATIM_URL}/reverse", params=params) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                if not data or "error" in data:
                    return None

                addr = data.get("address", {})
                namedetails = data.get("namedetails", {})
                name = namedetails.get("name", "")
                display_name = data.get("display_name", "")

                if not name:
                    name = display_name.split(",")[0] if display_name else "Unknown"

                # Get bounding box
                bbox_raw = data.get("boundingbox", [])
                bbox = None
                if len(bbox_raw) == 4:
                    try:
                        bbox = [
                            float(bbox_raw[2]), float(bbox_raw[0]),
                            float(bbox_raw[3]), float(bbox_raw[1]),
                        ]
                    except (ValueError, IndexError):
                        bbox = None

                nearest_coast = estimate_nearest_coast(latitude, longitude)
                environment = classify_environment(latitude, longitude, nearest_coast)

                result = GeocodedLocation(
                    name=name,
                    display_name=display_name,
                    latitude=latitude,
                    longitude=longitude,
                    country=addr.get("country", "India"),
                    state=addr.get("state"),
                    district=addr.get("county") or addr.get("district"),
                    city=addr.get("city") or addr.get("town") or addr.get("village"),
                    confidence=0.9,
                    bbox=bbox,
                    environment=environment,
                    nearest_coast_km=nearest_coast,
                )

                self._cache[cache_key] = result
                return result

        except Exception as e:
            logger.warning(f"Reverse geocoding error: {e}")
            return None

    def _calculate_confidence(
        self,
        query: str,
        result_name: str,
        address: dict,
        rank: int,
        importance: float,
    ) -> float:
        """Calculate confidence score for a geocoding result."""
        score = 0.5  # Base score

        # Exact name match bonus
        query_lower = query.lower().split(",")[0].strip()
        name_lower = result_name.lower()
        if query_lower == name_lower:
            score += 0.3
        elif query_lower in name_lower or name_lower in query_lower:
            score += 0.15

        # Rank bonus (first result is usually best)
        score += max(0, 0.15 - rank * 0.03)

        # Importance bonus
        score += min(importance * 0.1, 0.1)

        # India bonus
        if address.get("country", "").lower() == "india":
            score += 0.05

        # State match bonus
        state = address.get("state", "").lower()
        if state and any(s in state for s in ["tamil", "kerala", "karnataka", "andhra"]):
            score += 0.02

        return min(score, 1.0)

    def __del__(self):
        """Cleanup session on garbage collection."""
        if self._session and not self._session.closed:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
            except Exception:
                pass


# Singleton
_geocoding_provider: Optional[GeocodingProvider] = None


def get_geocoding_provider() -> GeocodingProvider:
    global _geocoding_provider
    if _geocoding_provider is None:
        _geocoding_provider = GeocodingProvider()
    return _geocoding_provider
