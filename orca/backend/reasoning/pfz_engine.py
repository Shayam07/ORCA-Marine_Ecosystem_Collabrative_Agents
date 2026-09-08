"""ORCA PFZ Analysis Engine — Identifies candidate fishing zones.

Generates a marine search grid, retrieves environmental data,
calculates suitability scores, clusters suitable cells, and
produces geographic polygons for display on the map.

IMPORTANT: These are ORCA-derived candidate zones, NOT official PFZ advisories.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("orca.pfz")

# ── Configuration ────────────────────────────────────────────────────────

# Default grid resolution (degrees)
DEFAULT_GRID_RESOLUTION = 0.25  # ~25 km cells

# Scoring thresholds
HIGH_SUITABILITY = 0.78
MODERATE_SUITABILITY = 0.58
LOW_SUITABILITY = 0.38

# Scoring weights for raw biological suitability
SCORING_WEIGHTS = {
    "chlorophyll": 0.30,    # Primary productivity indicator
    "sst": 0.25,            # Temperature suitability
    "sst_gradient": 0.20,   # Ocean fronts (productivity hotspots)
    "wind": 0.15,           # Weather safety factor
    "fishing_activity": 0.10,  # Baseline fishing index
}

# SST optimal range for Indian waters (°C)
SST_OPTIMAL_MIN = 24.0
SST_OPTIMAL_MAX = 30.0
SST_IDEAL = 27.0

# Chlorophyll thresholds (mg/m³)
CHL_LOW = 0.3
CHL_MODERATE = 1.0
CHL_HIGH = 2.0
CHL_VERY_HIGH = 5.0


class PFZCell(BaseModel):
    """A single marine grid cell with environmental, safety, and crowding data."""
    cell_id: str
    lat: float
    lon: float
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    # Environmental data
    sst: Optional[float] = None
    chlorophyll: Optional[float] = None
    sst_gradient: Optional[float] = None
    wind_speed: Optional[float] = None
    wave_height: Optional[float] = None
    fishing_activity: Optional[float] = None
    # Crowding & Fleet Pressure
    vessel_density: float = 0.0  # vessels / km2
    vessel_count: int = 0
    crowding_level: str = "LOW"  # LOW (🟢), MODERATE (🟡), HIGH (🔴)
    crowding_penalty: float = 0.0
    # Legal, Ecological, & Safety Exclusion
    is_restricted_area: bool = False
    is_spawning_protected: bool = False
    is_seasonal_ban_active: bool = False
    is_critical_hazard: bool = False
    protection_details: Optional[str] = None
    hazard_details: Optional[str] = None
    # Data quality & mode
    data_quality: float = 0.0
    data_mode: str = "NO_DATA"  # LIVE, CACHED, DEMO, NO_DATA
    data_sources: list[str] = Field(default_factory=list)
    data_timestamp: Optional[str] = None
    # Scoring components
    sst_score: float = 0.0
    chl_score: float = 0.0
    gradient_score: float = 0.0
    wind_score: float = 0.0
    raw_suitability_score: float = 0.0
    safety_score: float = 0.0
    data_confidence: float = 0.8
    spawning_risk_penalty: float = 0.0
    environmental_risk_penalty: float = 0.0
    restricted_area_penalty: float = 0.0
    final_sustainable_score: float = 0.0
    total_score: float = 0.0


class PFZZone(BaseModel):
    """A clustered group of suitable cells forming a sustainable fishing zone."""
    zone_id: str
    geometry: dict[str, Any]  # GeoJSON Polygon
    center_lat: float
    center_lon: float
    score: float  # Final sustainable recommendation score
    raw_suitability_score: float = 0.75
    safety_score: float = 0.85
    data_confidence: float = 0.85
    classification: str  # HIGH, MODERATE, LOW
    recommendation_status: str = "RECOMMENDED"  # RECOMMENDED, ALTERNATIVE, EXCLUDED_RESTRICTED, EXCLUDED_ECOLOGICAL, EXCLUDED_UNSAFE
    option_label: str = "OPTION A"  # OPTION A, OPTION B, OPTION C
    option_title: Optional[str] = None  # e.g. "Option A — Best Overall"
    crowding_level: str = "LOW"  # LOW, MODERATE, HIGH
    crowding_penalty: float = 0.0
    vessel_density: float = 0.3
    vessel_count: int = 3
    cell_count: int = 1
    suggested_grid_cells: list[dict[str, Any]] = Field(default_factory=list)
    avg_sst: Optional[float] = None
    avg_chlorophyll: Optional[float] = None
    data_mode: str = "NO_DATA"
    data_sources: list[str] = Field(default_factory=list)
    data_timestamp: Optional[str] = None
    distance_km: Optional[float] = None
    reasoning: str = ""
    alternative_reason: str = ""
    exclusion_reason: Optional[str] = None


class PFZResult(BaseModel):
    """Complete Sustainable PFZ analysis result with alternatives and exclusions."""
    zones: list[PFZZone]
    top_recommendation: Optional[PFZZone] = None
    alternatives: list[PFZZone] = Field(default_factory=list)
    excluded_zones: list[PFZZone] = Field(default_factory=list)
    total_cells: int
    suitable_cells: int
    data_mode: str
    data_sources: list[str]
    disclaimer: str
    data_availability: dict[str, bool]  # Which variables were available


class PFZAnalysisEngine:
    """Analyzes marine areas to identify sustainable, safe, and responsible candidate fishing zones."""

    def __init__(self, resolution: float = DEFAULT_GRID_RESOLUTION):
        self.resolution = resolution

    async def analyze(
        self,
        bbox: list[float],
        center_lat: float,
        center_lon: float,
        start_date: datetime,
        end_date: datetime,
        data_service=None,
        allow_demo: bool = False,
        vessel_profile: Optional[dict[str, Any]] = None,
        vessel_class: Optional[str] = None,
    ) -> PFZResult:
        """Run sustainable PFZ analysis pipeline.

        Decision Hierarchy:
          1. Legal / Border Restrictions -> EXCLUDE
          2. Ecological / Spawning Protection -> EXCLUDE
          3. Marine Safety (Wind, Wave) -> STRICT SAFETY OVERRIDE (EXCLUDE IF UNSAFE)
          4. Crowding / Fleet Pressure -> PENALIZE & PREFER ALTERNATIVE
          5. Biological Suitability -> RANK PERMITTED ZONES
        """
        from agents.route import VesselProfile
        if vessel_profile:
            v_prof = VesselProfile(
                boat_type=vessel_profile.get("boat_type", "Motorized"),
                boat_size_m=vessel_profile.get("boat_size_m", 9.5),
                fuel_capacity_l=vessel_profile.get("fuel_capacity_l", 120.0),
                maximum_range_km=vessel_profile.get("maximum_range_km", 90.0),
                maximum_safe_wave_m=vessel_profile.get("maximum_safe_wave_m", 2.8),
                maximum_safe_wind_ms=vessel_profile.get("maximum_safe_wind_ms", 14.0),
            )
        else:
            v_prof = VesselProfile.from_vessel_class(vessel_class or "Artisanal")

        logger.info(f"Sustainable PFZ analysis: bbox={bbox}, center=({center_lat:.2f}, {center_lon:.2f}), vessel={v_prof.boat_type}")

        # 1. Generate marine search grid
        cells = self._generate_grid(bbox)
        logger.info(f"Generated {len(cells)} grid cells")

        # 2. Retrieve environmental data for each cell
        if data_service:
            cells = await self._retrieve_data(cells, bbox, start_date, end_date, data_service, allow_demo)
        else:
            logger.warning("No data service available for PFZ analysis")
            if allow_demo:
                cells = self._simulate_data(cells)

        # 3. Apply Legal, Spawning, & Seasonal Protection Checks
        cells = self._apply_protection_and_crowding_telemetry(cells, start_date)

        # 4. Calculate Multi-Factor Sustainable Scores with strict vessel safety limits
        cells = self._score_cells(cells, v_prof)

        # 5. Identify permitted suitable cells (strictly exclude restricted, active spawning, and severe hazards)
        permitted_suitable = [
            c for c in cells
            if c.total_score >= LOW_SUITABILITY
            and not c.is_restricted_area
            and not c.is_seasonal_ban_active
            and not (c.is_spawning_protected and c.spawning_risk_penalty >= 0.5)
            and not c.is_critical_hazard
        ]
        
        excluded_cells = [
            c for c in cells
            if c.is_restricted_area
            or c.is_seasonal_ban_active
            or (c.is_spawning_protected and c.spawning_risk_penalty >= 0.5)
            or c.is_critical_hazard
        ]

        logger.info(f"Permitted suitable cells: {len(permitted_suitable)}/{len(cells)} (Excluded: {len(excluded_cells)})")

        # 6. Cluster neighboring permitted cells into zones
        candidate_zones = self._cluster_cells(permitted_suitable, center_lat, center_lon)

        # 7. Generate zone polygons and grid dispersal cells
        candidate_zones = self._generate_polygons(candidate_zones)

        # 8. Filter and rank zones using sustainable decision hierarchy
        from agents.geofence import filter_and_rank_pfz_zones
        raw_zone_dicts = [
            {
                "zone_id": z.zone_id,
                "geometry": z.geometry,
                "center_lat": z.center_lat,
                "center_lon": z.center_lon,
                "score": z.score,
                "raw_suitability_score": z.raw_suitability_score,
                "safety_score": z.safety_score,
                "data_confidence": z.data_confidence,
                "classification": z.classification,
                "cell_count": z.cell_count,
                "avg_sst": z.avg_sst,
                "avg_chlorophyll": z.avg_chlorophyll,
                "data_mode": z.data_mode,
                "data_sources": z.data_sources,
                "data_timestamp": z.data_timestamp,
                "distance_km": z.distance_km,
                "reasoning": z.reasoning,
                "vessel_density": z.vessel_density,
                "vessel_count": z.vessel_count,
                "crowding_level": z.crowding_level,
                "suggested_grid_cells": z.suggested_grid_cells,
            }
            for z in candidate_zones
        ]

        safe_ranked_dicts, excluded_zone_dicts = filter_and_rank_pfz_zones(
            raw_zone_dicts, center_lat, center_lon, check_date=start_date
        )

        # Re-wrap into PFZZone instances
        ranked_zones = []
        for i, zd in enumerate(safe_ranked_dicts):
            z_obj = PFZZone(
                zone_id=f"PFZ-SECTOR-{i+1:02d}",
                geometry=zd.get("geometry", {}),
                center_lat=zd.get("center_lat", center_lat),
                center_lon=zd.get("center_lon", center_lon),
                score=zd.get("score", zd.get("final_sustainable_score", 0.75)),
                raw_suitability_score=zd.get("raw_suitability_score", 0.75),
                safety_score=zd.get("safety_score", 0.85),
                data_confidence=zd.get("data_confidence", 0.85),
                classification=zd.get("classification", "HIGH"),
                recommendation_status=zd.get("recommendation_status", "RECOMMENDED" if i == 0 else "ALTERNATIVE"),
                option_label=zd.get("option_label", f"OPTION {chr(65+i)}"),
                option_title=zd.get("option_title"),
                crowding_level=zd.get("crowding_level", "LOW"),
                crowding_penalty=zd.get("crowding_penalty", 0.0),
                vessel_density=zd.get("vessel_density", 0.3),
                vessel_count=zd.get("vessel_count", 3),
                cell_count=zd.get("cell_count", 1),
                suggested_grid_cells=zd.get("suggested_grid_cells", []),
                avg_sst=zd.get("avg_sst"),
                avg_chlorophyll=zd.get("avg_chlorophyll"),
                data_mode=zd.get("data_mode", "LIVE"),
                data_sources=zd.get("data_sources", ["INCOIS", "MOSDAC"]),
                data_timestamp=zd.get("data_timestamp"),
                distance_km=zd.get("distance_km"),
                reasoning=zd.get("reasoning", ""),
                alternative_reason=zd.get("alternative_reason", ""),
            )
            ranked_zones.append(z_obj)

        excluded_zones_list = [
            PFZZone(
                zone_id=f"EXCLUDED-{i+1:02d}",
                geometry=zd.get("geometry", {}),
                center_lat=zd.get("center_lat", center_lat),
                center_lon=zd.get("center_lon", center_lon),
                score=zd.get("score", 0.1),
                classification="LOW",
                recommendation_status=zd.get("recommendation_status", "EXCLUDED_RESTRICTED"),
                option_label="EXCLUDED",
                crowding_level=zd.get("crowding_level", "LOW"),
                exclusion_reason=zd.get("exclusion_reason"),
                reasoning=zd.get("reasoning", ""),
            )
            for i, zd in enumerate(excluded_zone_dicts)
        ]

        # Top recommendation and alternatives
        top_rec = ranked_zones[0] if ranked_zones else None
        alts = ranked_zones[1:4] if len(ranked_zones) > 1 else []

        # Determine data mode
        data_mode = self._determine_data_mode(cells)
        data_sources = list(set(s for c in cells for s in c.data_sources))
        data_availability = {
            "chlorophyll": any(c.chlorophyll is not None for c in cells),
            "sst": any(c.sst is not None for c in cells),
            "sst_gradient": any(c.sst_gradient is not None for c in cells),
            "wind": any(c.wind_speed is not None for c in cells),
            "fishing_activity": any(c.fishing_activity is not None for c in cells),
            "vessel_density": any(c.vessel_density > 0 for c in cells),
        }

        return PFZResult(
            zones=ranked_zones,
            top_recommendation=top_rec,
            alternatives=alts,
            excluded_zones=excluded_zones_list,
            total_cells=len(cells),
            suitable_cells=len(permitted_suitable),
            data_mode=data_mode,
            data_sources=data_sources,
            disclaimer=self._get_disclaimer(data_mode),
            data_availability=data_availability,
        )

    def _generate_grid(self, bbox: list[float]) -> list[PFZCell]:
        """Generate a regular grid of marine cells within the bbox."""
        west, south, east, north = bbox
        cells = []
        cell_idx = 0

        lat = south
        while lat < north:
            lon = west
            while lon < east:
                cell = PFZCell(
                    cell_id=f"cell_{cell_idx:04d}",
                    lat=round(lat + self.resolution / 2, 4),
                    lon=round(lon + self.resolution / 2, 4),
                    lat_min=round(lat, 4),
                    lat_max=round(lat + self.resolution, 4),
                    lon_min=round(lon, 4),
                    lon_max=round(lon + self.resolution, 4),
                )
                cells.append(cell)
                cell_idx += 1
                lon += self.resolution
            lat += self.resolution

        return cells

    async def _retrieve_data(
        self,
        cells: list[PFZCell],
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        data_service,
        allow_demo: bool = False,
    ) -> list[PFZCell]:
        """Retrieve environmental and vessel activity data for grid cells."""
        try:
            batch = await data_service.get_observations(
                bbox=bbox,
                start_date=start_date,
                end_date=end_date,
                variables=[
                    "sea_surface_temperature", "chlorophyll_concentration",
                    "wind_speed", "fishing_activity", "wave_height", 
                    "ocean_current_velocity"
                ],
                allow_demo=allow_demo,
            )
            observations = batch.observations if hasattr(batch, 'observations') else []

            if not observations:
                logger.warning("No observations returned for PFZ analysis")
                return self._simulate_data(cells) if allow_demo else cells

            logger.info(f"PFZ: Retrieved {len(observations)} observations from providers")

            for obs in observations:
                for cell in cells:
                    if (cell.lat_min <= obs.latitude <= cell.lat_max and
                            cell.lon_min <= obs.longitude <= cell.lon_max):
                        if obs.variable in ("sea_surface_temperature", "sst"):
                            cell.sst = obs.value
                            cell.data_sources.append(obs.source.value if hasattr(obs.source, 'value') else str(obs.source))
                            cell.data_timestamp = obs.timestamp.isoformat()
                        elif obs.variable in ("chlorophyll_concentration", "chlorophyll"):
                            cell.chlorophyll = obs.value
                            cell.data_sources.append(obs.source.value if hasattr(obs.source, 'value') else str(obs.source))
                        elif "wind" in obs.variable:
                            cell.wind_speed = obs.value
                            cell.data_sources.append(obs.source.value if hasattr(obs.source, 'value') else str(obs.source))
                        elif "fishing" in obs.variable:
                            cell.fishing_activity = obs.value
                            # Derive vessel density estimation
                            cell.vessel_density = round(obs.value * 1.5, 2)
                            cell.vessel_count = int(obs.value * 18)
                        elif "wave" in obs.variable:
                            cell.wave_height = obs.value
                            if cell.wind_speed is None:
                                cell.wind_speed = obs.value * 2
                            cell.data_sources.append(obs.source.value if hasattr(obs.source, 'value') else str(obs.source))
                        cell.data_quality = max(cell.data_quality, obs.quality)

            cells = self._calculate_sst_gradients(cells)
            return cells

        except Exception as e:
            logger.warning(f"Data retrieval failed: {e}")
            return self._simulate_data(cells) if allow_demo else cells

    def _simulate_data(self, cells: list[PFZCell]) -> list[PFZCell]:
        """Generate realistic simulated oceanographic and vessel activity data (DEMO mode)."""
        import random
        random.seed(42)

        for cell in cells:
            base_sst = 28.2 - abs(cell.lat - 13.0) * 0.25
            cell.sst = round(base_sst + random.uniform(-1.0, 1.0), 2)

            coast_dist = max(0.1, abs(cell.lon - 80.2))
            base_chl = 2.2 * math.exp(-coast_dist * 2.5)
            cell.chlorophyll = round(max(0.2, base_chl + random.uniform(-0.3, 0.4)), 3)

            cell.wind_speed = round(random.uniform(4.0, 11.5), 1)
            cell.wave_height = round(0.8 + cell.wind_speed * 0.12, 1)

            # Realistic simulated vessel activity with crowding variation
            rand_pressure = random.random()
            if rand_pressure > 0.70:
                # High pressure hotspot near harbour
                cell.fishing_activity = round(random.uniform(0.75, 1.2), 2)
                cell.vessel_density = round(random.uniform(1.4, 2.5), 2)
                cell.vessel_count = random.randint(18, 35)
                cell.crowding_level = "HIGH"
            elif rand_pressure > 0.35:
                cell.fishing_activity = round(random.uniform(0.40, 0.70), 2)
                cell.vessel_density = round(random.uniform(0.7, 1.3), 2)
                cell.vessel_count = random.randint(8, 17)
                cell.crowding_level = "MODERATE"
            else:
                cell.fishing_activity = round(random.uniform(0.1, 0.35), 2)
                cell.vessel_density = round(random.uniform(0.1, 0.6), 2)
                cell.vessel_count = random.randint(1, 7)
                cell.crowding_level = "LOW"

            cell.data_mode = "DEMO"
            cell.data_sources = ["INCOIS_SIMULATED", "MOSDAC_SIMULATED"]

        return cells

    def _apply_protection_and_crowding_telemetry(self, cells: list[PFZCell], check_date: datetime) -> list[PFZCell]:
        """Evaluate legal boundaries, official seasonal bans, and spawning grounds."""
        from agents.geofence import check_marine_geofence, check_spawning_and_ecological_sensitivity

        for cell in cells:
            # 1. Maritime Border & Defense Check
            geofence = check_marine_geofence(cell.lat, cell.lon)
            if geofence["status"] == "CRITICAL" or geofence["min_border_distance_km"] < 8.0:
                cell.is_restricted_area = True
                cell.protection_details = geofence["alert_message"]
                cell.restricted_area_penalty = 1.0

            # 2. Spawning & Seasonal Ban Check
            eco = check_spawning_and_ecological_sensitivity(cell.lat, cell.lon, check_date)
            if eco.get("ban_active"):
                cell.is_seasonal_ban_active = True
                cell.protection_details = eco["ban_details"]["description"]
                cell.spawning_risk_penalty = 1.0

            if eco.get("is_protected") and eco.get("is_spawning_season"):
                cell.is_spawning_protected = True
                cell.protection_details = f"Spawning Core: {eco['name']}"
                cell.spawning_risk_penalty = 0.8

            # 3. Crowding Penalty
            if cell.crowding_level == "HIGH" or cell.vessel_density > 1.2:
                cell.crowding_penalty = 0.25
            elif cell.crowding_level == "MODERATE" or cell.vessel_density > 0.6:
                cell.crowding_penalty = 0.10
            else:
                cell.crowding_penalty = 0.0

        return cells

    def _calculate_sst_gradients(self, cells: list[PFZCell]) -> list[PFZCell]:
        """Calculate SST gradients (fronts) between adjacent cells."""
        cell_map = {(c.lat, c.lon): c for c in cells}

        for cell in cells:
            neighbors_sst = []
            for dlat in [-self.resolution, 0, self.resolution]:
                for dlon in [-self.resolution, 0, self.resolution]:
                    if dlat == 0 and dlon == 0:
                        continue
                    neighbor = cell_map.get((round(cell.lat + dlat, 4), round(cell.lon + dlon, 4)))
                    if neighbor and neighbor.sst is not None and cell.sst is not None:
                        neighbors_sst.append(neighbor.sst)

            if neighbors_sst and cell.sst is not None:
                avg_neighbor = sum(neighbors_sst) / len(neighbors_sst)
                cell.sst_gradient = round(abs(cell.sst - avg_neighbor), 3)

        return cells

    def _score_cells(self, cells: list[PFZCell], v_prof: Any = None) -> list[PFZCell]:
        """Calculate multi-factor Sustainable PFZ scores for each cell.

        Conceptual Formula:
          FINAL PFZ SCORE =
            FISH SUITABILITY SCORE (SST + Chlorophyll + Gradients)
            + SAFETY SCORE (Wind + Wave clearance)
            + DATA CONFIDENCE
            - CROWDING PENALTY
            - HIGH FISHING PRESSURE PENALTY
            - SPAWNING / ECOLOGICAL RISK PENALTY
            - ENVIRONMENTAL RISK PENALTY
            - RESTRICTED AREA PENALTY
        """
        max_safe_wave = getattr(v_prof, "maximum_safe_wave_m", 2.0) if v_prof else 2.0
        max_safe_wind = getattr(v_prof, "maximum_safe_wind_ms", 10.0) if v_prof else 10.0
        boat_type = getattr(v_prof, "boat_type", "Artisanal") if v_prof else "Artisanal"

        for cell in cells:
            # Critical Safety Override: Sea conditions exceeding vessel limit immediately disqualify cell (Flaw 10 & 13)
            is_critical_wave = cell.wave_height is not None and cell.wave_height > max_safe_wave
            is_critical_wind = cell.wind_speed is not None and cell.wind_speed > max_safe_wind
            if is_critical_wave or is_critical_wind:
                cell.is_critical_hazard = True
                cell.hazard_details = (
                    f"Operational limit exceeded for {boat_type}: "
                    + (f"wave {cell.wave_height}m > {max_safe_wave}m limit; " if is_critical_wave else "")
                    + (f"wind {cell.wind_speed} m/s > {max_safe_wind} m/s limit;" if is_critical_wind else "")
                )
                cell.safety_score = 0.0
                cell.environmental_risk_penalty = 1.0
                cell.final_sustainable_score = 0.0
                cell.total_score = 0.0
                continue

            # SST Score
            if cell.sst is not None:
                if SST_OPTIMAL_MIN <= cell.sst <= SST_OPTIMAL_MAX:
                    deviation = abs(cell.sst - SST_IDEAL) / (SST_OPTIMAL_MAX - SST_OPTIMAL_MIN)
                    cell.sst_score = round(1.0 - deviation * 0.5, 3)
                else:
                    cell.sst_score = 0.1
            else:
                cell.sst_score = 0.0

            # Chlorophyll Score
            if cell.chlorophyll is not None:
                if cell.chlorophyll >= CHL_HIGH:
                    cell.chl_score = 0.90
                elif cell.chlorophyll >= CHL_MODERATE:
                    cell.chl_score = 0.70 + (cell.chlorophyll - CHL_MODERATE) / (CHL_HIGH - CHL_MODERATE) * 0.20
                elif cell.chlorophyll >= CHL_LOW:
                    cell.chl_score = 0.40 + (cell.chlorophyll - CHL_LOW) / (CHL_MODERATE - CHL_LOW) * 0.30
                else:
                    cell.chl_score = 0.20
            else:
                cell.chl_score = 0.0

            # SST Gradient Score
            if cell.sst_gradient is not None:
                if cell.sst_gradient > 2.0:
                    cell.gradient_score = 0.95
                elif cell.sst_gradient > 1.0:
                    cell.gradient_score = 0.75
                elif cell.sst_gradient > 0.5:
                    cell.gradient_score = 0.50
                else:
                    cell.gradient_score = 0.30
            else:
                cell.gradient_score = 0.0

            # Weather / Safety Score
            if cell.wind_speed is not None:
                if cell.wind_speed < (max_safe_wind * 0.5):
                    cell.wind_score = 0.95
                    cell.safety_score = 0.95
                elif cell.wind_speed < (max_safe_wind * 0.8):
                    cell.wind_score = 0.80
                    cell.safety_score = 0.85
                elif cell.wind_speed <= max_safe_wind:
                    cell.wind_score = 0.45
                    cell.safety_score = 0.50
                else:
                    cell.wind_score = 0.10
                    cell.safety_score = 0.15
            else:
                cell.wind_score = 0.50
                cell.safety_score = 0.70

            # Environmental risk penalty
            if cell.wind_speed and cell.wind_speed >= (max_safe_wind * 0.85):
                cell.environmental_risk_penalty = 0.30
            elif cell.wave_height and cell.wave_height >= (max_safe_wave * 0.85):
                cell.environmental_risk_penalty = 0.25

            # Biological Suitability component (45%)
            suit_sum = (cell.chl_score * 0.40) + (cell.sst_score * 0.35) + (cell.gradient_score * 0.25)
            cell.raw_suitability_score = round(suit_sum, 3)

            # Data Freshness & Confidence (Flaw 2)
            if cell.data_mode == "NO_DATA":
                conf = 0.30
            elif cell.data_mode == "STALE":
                conf = 0.40  # Stale data penalty
            elif cell.data_mode == "DELAYED":
                conf = 0.65
            else:
                conf = 0.85
            cell.data_confidence = conf

            # Composite Sustainable Formula:
            # S_suitability (45%) + S_safety (25%) + S_conf (15%) - P_crowd - P_spawning - P_env - P_restricted
            sustainable_score = (
                (cell.raw_suitability_score * 0.45) +
                (cell.safety_score * 0.25) +
                (cell.data_confidence * 0.15) +
                0.15
                - cell.crowding_penalty
                - (cell.spawning_risk_penalty * 0.35)
                - cell.environmental_risk_penalty
                - (cell.restricted_area_penalty * 1.0)
            )

            cell.final_sustainable_score = max(0.0, round(sustainable_score, 3))
            cell.total_score = cell.final_sustainable_score

        return cells

    def _cluster_cells(self, suitable_cells: list[PFZCell], center_lat: float, center_lon: float) -> list[PFZZone]:
        """Cluster neighboring suitable cells into sustainable zones using connected components."""
        if not suitable_cells:
            return []

        cell_map = {(round(c.lat, 4), round(c.lon, 4)): c for c in suitable_cells}
        visited = set()
        clusters = []

        for cell in suitable_cells:
            key = (round(cell.lat, 4), round(cell.lon, 4))
            if key in visited:
                continue

            cluster = []
            queue = [cell]
            while queue:
                current = queue.pop(0)
                ckey = (round(current.lat, 4), round(current.lon, 4))
                if ckey in visited:
                    continue
                visited.add(ckey)
                cluster.append(current)

                for dlat in [-self.resolution, self.resolution]:
                    neighbor = cell_map.get((round(current.lat + dlat, 4), round(current.lon, 4)))
                    if neighbor and (round(neighbor.lat, 4), round(neighbor.lon, 4)) not in visited:
                        queue.append(neighbor)
                for dlon in [-self.resolution, self.resolution]:
                    neighbor = cell_map.get((round(current.lat, 4), round(current.lon + dlon, 4)))
                    if neighbor and (round(neighbor.lat, 4), round(neighbor.lon, 4)) not in visited:
                        queue.append(neighbor)

            if cluster:
                avg_score = sum(c.final_sustainable_score for c in cluster) / len(cluster)
                avg_suitability = sum(c.raw_suitability_score for c in cluster) / len(cluster)
                avg_safety = sum(c.safety_score for c in cluster) / len(cluster)
                avg_lat = sum(c.lat for c in cluster) / len(cluster)
                avg_lon = sum(c.lon for c in cluster) / len(cluster)
                avg_vessel_density = sum(c.vessel_density for c in cluster) / len(cluster)
                total_vessels = sum(c.vessel_count for c in cluster)

                crowding_level = (
                    "HIGH" if avg_vessel_density > 1.2 or total_vessels > 18 else
                    "MODERATE" if avg_vessel_density > 0.6 or total_vessels > 8 else
                    "LOW"
                )

                classification = (
                    "HIGH" if avg_score >= HIGH_SUITABILITY else
                    "MODERATE" if avg_score >= MODERATE_SUITABILITY else
                    "LOW"
                )

                distance = self._haversine_km(center_lat, center_lon, avg_lat, avg_lon)

                # Grid Dispersal: list sub-cell waypoints to prevent pinning all users to single coordinate
                dispersed_grid_cells = [
                    {
                        "cell_id": c.cell_id,
                        "center_lat": c.lat,
                        "center_lon": c.lon,
                        "vessel_density": c.vessel_density,
                        "crowding_level": c.crowding_level,
                    }
                    for c in cluster
                ]

                reasoning = self._generate_zone_reasoning(cluster, crowding_level, avg_vessel_density)

                zone = PFZZone(
                    zone_id="",
                    geometry={},
                    center_lat=round(avg_lat, 4),
                    center_lon=round(avg_lon, 4),
                    score=round(avg_score, 3),
                    raw_suitability_score=round(avg_suitability, 3),
                    safety_score=round(avg_safety, 3),
                    classification=classification,
                    cell_count=len(cluster),
                    suggested_grid_cells=dispersed_grid_cells,
                    vessel_density=round(avg_vessel_density, 2),
                    vessel_count=total_vessels,
                    crowding_level=crowding_level,
                    avg_sst=round(sum(c.sst for c in cluster if c.sst) / max(1, sum(1 for c in cluster if c.sst)), 2),
                    avg_chlorophyll=round(sum(c.chlorophyll for c in cluster if c.chlorophyll) / max(1, sum(1 for c in cluster if c.chlorophyll)), 3),
                    data_mode=self._determine_cluster_data_mode(cluster),
                    data_sources=list(set(s for c in cluster for s in c.data_sources)),
                    data_timestamp=max((c.data_timestamp for c in cluster if c.data_timestamp), default=None),
                    distance_km=round(distance, 1),
                    reasoning=reasoning,
                )
                clusters.append(zone)

        return clusters

    def _generate_polygons(self, zones: list[PFZZone]) -> list[PFZZone]:
        """Generate GeoJSON polygons for each zone."""
        for zone in zones:
            lat_min = zone.center_lat - self.resolution
            lat_max = zone.center_lat + self.resolution
            lon_min = zone.center_lon - self.resolution
            lon_max = zone.center_lon + self.resolution

            zone.geometry = {
                "type": "Polygon",
                "coordinates": [[
                    [round(lon_min, 4), round(lat_min, 4)],
                    [round(lon_max, 4), round(lat_min, 4)],
                    [round(lon_max, 4), round(lat_max, 4)],
                    [round(lon_min, 4), round(lat_max, 4)],
                    [round(lon_min, 4), round(lat_min, 4)],
                ]]
            }

        return zones

    def _generate_zone_reasoning(self, cluster: list[PFZCell], crowding_level: str, vessel_density: float) -> str:
        """Generate comprehensive reasoning covering productivity, safety, and crowding status."""
        reasons = []

        avg_sst = sum(c.sst for c in cluster if c.sst) / max(1, sum(1 for c in cluster if c.sst))
        avg_chl = sum(c.chlorophyll for c in cluster if c.chlorophyll) / max(1, sum(1 for c in cluster if c.chlorophyll))

        if avg_sst >= SST_OPTIMAL_MIN and avg_sst <= SST_OPTIMAL_MAX:
            reasons.append(f"favourable SST ({avg_sst:.1f}°C)")

        if avg_chl >= CHL_HIGH:
            reasons.append(f"high biological productivity (Chl-a: {avg_chl:.2f} mg/m³)")
        elif avg_chl >= CHL_MODERATE:
            reasons.append(f"moderate productivity (Chl-a: {avg_chl:.2f} mg/m³)")

        gradients = [c.sst_gradient for c in cluster if c.sst_gradient and c.sst_gradient > 0.5]
        if gradients:
            reasons.append("thermal front aggregation")

        winds = [c.wind_speed for c in cluster if c.wind_speed]
        if winds and max(winds) < 11:
            reasons.append("safe sea weather")

        # Crowding telemetry
        if crowding_level == "LOW":
            reasons.append(f"🟢 low vessel pressure ({vessel_density:.2f} vessels/km²)")
        elif crowding_level == "MODERATE":
            reasons.append(f"🟡 moderate fleet activity ({vessel_density:.2f} vessels/km²)")
        else:
            reasons.append(f"🔴 high fleet congestion ({vessel_density:.2f} vessels/km²)")

        return "; ".join(reasons) if reasons else "Sustainable marine observation sector"

    def _determine_data_mode(self, cells: list[PFZCell]) -> str:
        modes = set(c.data_mode for c in cells)
        if "LIVE" in modes:
            return "LIVE"
        elif "CACHED" in modes:
            return "CACHED"
        return "DEMO" if "DEMO" in modes else "NO_DATA"

    def _determine_cluster_data_mode(self, cluster: list[PFZCell]) -> str:
        modes = set(c.data_mode for c in cluster)
        if "LIVE" in modes:
            return "LIVE"
        elif "CACHED" in modes:
            return "CACHED"
        return "DEMO" if "DEMO" in modes else "NO_DATA"

    def _get_disclaimer(self, data_mode: str) -> str:
        base_disclaimer = (
            "This is a Potential Fishing Zone based on currently available marine conditions. "
            "Based on SST, chlorophyll and available oceanographic parameters. "
            "This does not guarantee fish presence or catch. Always verify sea state and local safety advisories before departure."
        )
        if data_mode == "DEMO":
            return (
                "⚠️ DEMO / SIMULATED DATA: " + base_disclaimer +
                " These candidate zones are for demonstration purposes only and should not be used for actual navigation."
            )
        if data_mode == "NO_DATA":
            return "No current environmental observations were available, so no fishing zone recommendation was produced."
        return base_disclaimer

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

