"""ORCA Fishing Suitability Engine — Scores candidate fishing locations.

This is NOT a claim that fish are present. It is an environmental
suitability estimate based on oceanographic and weather conditions.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from typing import Any
from pydantic import BaseModel, Field

from models.observation import Observation

logger = logging.getLogger("orca.reasoning.suitability")


class CandidateLocation(BaseModel):
    """A candidate fishing location with suitability score."""
    latitude: float
    longitude: float
    label: str = ""
    suitability_score: float = Field(ge=0.0, le=1.0)
    factors: dict[str, float] = Field(default_factory=dict)
    factor_descriptions: list[str] = Field(default_factory=list)
    data_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    data_sources: list[str] = Field(default_factory=list)
    data_freshness: str = "unknown"


class SuitabilityResult(BaseModel):
    """Result of fishing suitability analysis."""
    candidates: list[CandidateLocation] = Field(default_factory=list)
    top_recommendations: list[CandidateLocation] = Field(default_factory=list)
    overall_data_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "This is an environmental suitability estimate and does not guarantee "
        "fish presence. Actual fishing success depends on many factors not "
        "captured by satellite and oceanographic data."
    )


class FishingSuitabilityEngine:
    """Calculates fishing suitability scores for candidate regions.

    Factors considered:
    - SST (species-appropriate temperature range)
    - Chlorophyll / productivity proxy
    - Ocean fronts (temperature gradients)
    - Weather conditions
    - Historical fishing activity (if available)
    """

    # Optimal SST ranges for common Indian Ocean species (°C)
    SST_OPTIMAL = (24.0, 30.0)
    SST_IDEAL = (26.0, 29.0)

    # Chlorophyll ranges indicating productivity (mg/m³)
    CHL_LOW = 0.5
    CHL_OPTIMAL = (1.0, 5.0)
    CHL_HIGH = 10.0

    def generate_candidates(
        self,
        bbox: list[float],
        grid_size: int = 3,
    ) -> list[dict[str, Any]]:
        """Generate candidate locations within a bounding box.

        Creates a grid of candidate points within the bbox.
        """
        west, south, east, north = bbox
        lat_step = (north - south) / grid_size
        lon_step = (east - west) / grid_size

        candidates = []
        for i in range(grid_size):
            for j in range(grid_size):
                lat = south + i * lat_step + lat_step / 2
                lon = west + j * lon_step + lon_step / 2
                candidates.append({
                    "latitude": lat,
                    "longitude": lon,
                    "label": f"Area {chr(65 + i)}{j + 1}",
                    "bbox": [
                        lon - lon_step / 2,
                        lat - lat_step / 2,
                        lon + lon_step / 2,
                        lat + lat_step / 2,
                    ],
                })

        return candidates

    def score_location(
        self,
        candidate: dict[str, Any],
        observations: list[Observation],
    ) -> CandidateLocation:
        """Score a single candidate location based on observations.

        Returns a CandidateLocation with suitability score and factors.
        """
        factors = {}
        descriptions = []
        sources = set()

        # Filter observations near this candidate
        lat, lon = candidate["latitude"], candidate["longitude"]
        nearby = [
            obs for obs in observations
            if abs(obs.latitude - lat) < 1.0 and abs(obs.longitude - lon) < 1.0
        ]

        if not nearby:
            return CandidateLocation(
                latitude=lat,
                longitude=lon,
                label=candidate.get("label", ""),
                suitability_score=0.3,
                factors={"data_availability": 0.0},
                factor_descriptions=["Insufficient data for this location"],
                data_quality=0.0,
                uncertainties=["No observations available for this location"],
            )

        # Group by variable
        by_var: dict[str, list[Observation]] = defaultdict(list)
        for obs in nearby:
            by_var[obs.variable].append(obs)
            sources.add(obs.source.value if hasattr(obs.source, 'value') else str(obs.source))

        # ── SST Factor ──────────────────────────────────────────
        sst_obs = by_var.get("sea_surface_temperature", [])
        if sst_obs:
            sst_values = [o.value for o in sst_obs]
            sst_mean = statistics.mean(sst_values)

            if self.SST_IDEAL[0] <= sst_mean <= self.SST_IDEAL[1]:
                factors["sst"] = 1.0
                descriptions.append(f"SST {sst_mean:.1f}°C — ideal range")
            elif self.SST_OPTIMAL[0] <= sst_mean <= self.SST_OPTIMAL[1]:
                factors["sst"] = 0.7
                descriptions.append(f"SST {sst_mean:.1f}°C — acceptable range")
            elif sst_mean < self.SST_OPTIMAL[0]:
                factors["sst"] = max(0.1, 0.5 * (sst_mean / self.SST_OPTIMAL[0]))
                descriptions.append(f"SST {sst_mean:.1f}°C — below optimal")
            else:
                factors["sst"] = max(0.1, 0.5 * (self.SST_OPTIMAL[1] / sst_mean))
                descriptions.append(f"SST {sst_mean:.1f}°C — above optimal")

            # Check for fronts (high variability = potential front)
            if len(sst_values) > 2:
                sst_std = statistics.stdev(sst_values)
                if sst_std > 0.5:
                    factors["fronts"] = min(1.0, sst_std / 2.0)
                    descriptions.append(f"SST variability ({sst_std:.2f}°C) suggests ocean fronts")
        else:
            factors["sst"] = 0.5  # Neutral if no data
            descriptions.append("SST data not available")

        # ── Chlorophyll / Productivity Factor ────────────────────
        chl_obs = by_var.get("chlorophyll_concentration", [])
        if chl_obs:
            chl_values = [o.value for o in chl_obs]
            chl_mean = statistics.mean(chl_values)

            if self.CHL_OPTIMAL[0] <= chl_mean <= self.CHL_OPTIMAL[1]:
                factors["productivity"] = 1.0
                descriptions.append(f"Chlorophyll {chl_mean:.2f} mg/m³ — good productivity")
            elif chl_mean > self.CHL_HIGH:
                factors["productivity"] = 0.6
                descriptions.append(f"Chlorophyll {chl_mean:.2f} mg/m³ — very high (possible bloom)")
            elif chl_mean > self.CHL_LOW:
                factors["productivity"] = 0.7
                descriptions.append(f"Chlorophyll {chl_mean:.2f} mg/m³ — moderate productivity")
            else:
                factors["productivity"] = 0.3
                descriptions.append(f"Chlorophyll {chl_mean:.2f} mg/m³ — low productivity")
        else:
            factors["productivity"] = 0.5
            descriptions.append("Chlorophyll data not available")

        # ── Wind / Weather Factor ────────────────────────────────
        wind_obs = by_var.get("wind_speed", [])
        if wind_obs:
            wind_values = [o.value for o in wind_obs]
            wind_mean = statistics.mean(wind_values)

            if wind_mean < 5.0:
                factors["weather"] = 1.0
                descriptions.append(f"Wind {wind_mean:.1f} m/s — calm conditions")
            elif wind_mean < 8.0:
                factors["weather"] = 0.8
                descriptions.append(f"Wind {wind_mean:.1f} m/s — moderate")
            elif wind_mean < 12.0:
                factors["weather"] = 0.5
                descriptions.append(f"Wind {wind_mean:.1f} m/s — breezy")
            else:
                factors["weather"] = 0.2
                descriptions.append(f"Wind {wind_mean:.1f} m/s — strong winds")
        else:
            factors["weather"] = 0.5
            descriptions.append("Wind data not available")

        # ── Fishing Activity Factor ──────────────────────────────
        fish_obs = by_var.get("fishing_activity", [])
        if fish_obs:
            fish_values = [o.value for o in fish_obs]
            fish_mean = statistics.mean(fish_values)

            if fish_mean > 0:
                # Some fishing activity = others fish here = potential
                factors["fishing_activity"] = min(1.0, 0.5 + fish_mean * 0.1)
                descriptions.append(f"Fishing activity detected ({fish_mean:.1f})")
            else:
                factors["fishing_activity"] = 0.5
                descriptions.append("No recent fishing activity detected")
        else:
            factors["fishing_activity"] = 0.5
            descriptions.append("Fishing activity data not available")

        # ── Salinity Factor (minor) ─────────────────────────────
        sal_obs = by_var.get("salinity", [])
        if sal_obs:
            sal_mean = statistics.mean([o.value for o in sal_obs])
            if 33.0 <= sal_mean <= 36.0:
                factors["salinity"] = 0.9
            else:
                factors["salinity"] = 0.6
            descriptions.append(f"Salinity {sal_mean:.1f} PSU")
        else:
            factors["salinity"] = 0.5

        # ── Calculate overall score ──────────────────────────────
        weights = {
            "sst": 0.25,
            "productivity": 0.25,
            "weather": 0.20,
            "fishing_activity": 0.15,
            "salinity": 0.05,
            "fronts": 0.10,
            "data_availability": 0.0,
        }

        weighted_sum = 0.0
        weight_total = 0.0
        for factor, value in factors.items():
            w = weights.get(factor, 0.05)
            if factor != "data_availability":
                weighted_sum += w * value
                weight_total += w

        score = weighted_sum / weight_total if weight_total > 0 else 0.3

        # Data quality assessment
        quality_scores = [o.quality for o in nearby]
        data_quality = statistics.mean(quality_scores) if quality_scores else 0.0

        # Data freshness
        if nearby:
            latest = max(o.timestamp for o in nearby)
            freshness = f"Latest: {latest.strftime('%Y-%m-%d')}"
        else:
            freshness = "Unknown"

        return CandidateLocation(
            latitude=lat,
            longitude=lon,
            label=candidate.get("label", ""),
            suitability_score=round(score, 3),
            factors=factors,
            factor_descriptions=descriptions,
            data_quality=round(data_quality, 3),
            data_sources=sorted(sources),
            data_freshness=freshness,
        )

    def analyze(
        self,
        bbox: list[float],
        observations: list[Observation],
        grid_size: int = 3,
    ) -> SuitabilityResult:
        """Full fishing suitability analysis for a region.

        1. Generate candidate locations
        2. Score each candidate
        3. Rank by suitability
        4. Return recommendations
        """
        candidates = self.generate_candidates(bbox, grid_size)

        scored = []
        all_sources = set()
        for cand in candidates:
            location = self.score_location(cand, observations)
            scored.append(location)
            all_sources.update(location.data_sources)

        # Sort by suitability
        scored.sort(key=lambda x: x.suitability_score, reverse=True)

        # Top 3 recommendations
        top = scored[:3]

        # Overall data quality
        qualities = [c.data_quality for c in scored if c.data_quality > 0]
        overall_quality = statistics.mean(qualities) if qualities else 0.0

        # Uncertainties
        uncertainties = []
        if overall_quality < 0.5:
            uncertainties.append("Data quality is limited for some areas")
        if not any(c.factors.get("fishing_activity", 0) > 0.5 for c in scored):
            uncertainties.append("No recent fishing activity data available")
        if not any(c.factors.get("sst", 0) > 0.7 for c in scored):
            uncertainties.append("SST conditions may not be optimal")

        return SuitabilityResult(
            candidates=scored,
            top_recommendations=top,
            overall_data_quality=round(overall_quality, 3),
            data_sources_used=sorted(all_sources),
            uncertainties=uncertainties,
        )
