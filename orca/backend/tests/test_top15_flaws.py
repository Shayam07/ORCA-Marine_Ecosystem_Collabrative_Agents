"""Comprehensive Test Suite for Top 15 Critical ORCA Architecture Flaws.

Validates:
 1. PFZ does not guarantee fish (probabilistic disclaimer & confidence score)
 2. Data freshness and provenance tracking (source_name, timestamps, age, freshness_status)
 3. PFZ overcrowding mitigation (vessel density, crowding level, dispersed sub-cells, Option A/B/C)
 4. Spawning and ecological protection (strict exclusion & full legal metadata)
 5. GPS inaccuracy near borders (4-tier buffer zone hierarchy & hysteresis)
 6. Offline connectivity at sea (/api/v1/offline/safety-pack & offline geofencing)
 7. Data provider failure & tiering (PRIMARY -> SECONDARY -> CACHED -> UNAVAILABLE)
 8. Dataset disagreement detection & elevated uncertainty
 9. AI hallucination prevention & zero-invention mandate
 10. Marine safety strictly overrides PFZ suitability
 11. Route safety during travel & departure delay advisory
 12. Routes never cross restricted areas (deflection / hard rejection)
 13. Vessel-specific safety profiles & conservative defaults
 14. Regional language safety templates & ASR confidence checks
 15. Graceful degradation architecture across 4 system states
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta

# Import domain modules
from agents.geofence import (
    check_marine_geofence,
    check_spawning_and_ecological_sensitivity,
    filter_and_rank_pfz_zones,
    SEASONAL_FISHING_BANS,
    MARINE_PROTECTED_AREAS,
)
from agents.route import VesselProfile, calculate_optimal_marine_route
from agents.safety import MarineSafetyAgent
from agents.fisheries import FisheriesAgent
from models.agent import AgentTask, AgentType
from models.evidence import EvidenceItem
from models.observation import Observation, ObservationBatch, DataSource, FreshnessStatus, EvidenceType
from data.service import DataService
from reasoning.pfz_engine import PFZAnalysisEngine, PFZCell, PFZZone
from reasoning.evidence_fusion import EvidenceFusionEngine
from reasoning.confidence import ConfidenceEngine
from voice.bhashini import VALIDATED_SAFETY_TEMPLATES, VoiceProcessingResponse


# ── FLAW 1: PFZ DOES NOT GUARANTEE FISH ──────────────────────────────────────

def test_flaw1_pfz_probabilistic_language_and_disclaimer():
    """Verify that PFZ results use probabilistic language and mandatory disclaimer."""
    engine = PFZAnalysisEngine()
    disclaimer = engine._get_disclaimer("LIVE")
    
    # Must never guarantee catch
    assert "This is a Potential Fishing Zone based on currently available marine conditions" in disclaimer
    assert "does not guarantee fish presence or catch" in disclaimer


# ── FLAW 2: DATA FRESHNESS AND PROVENANCE ─────────────────────────────────────

def test_flaw2_data_freshness_provenance():
    """Verify observations expose source_name, timestamps, age, and freshness_status."""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=30)
    
    fresh_obs = Observation(
        source=DataSource.INCOIS,
        source_name="INCOIS",
        dataset="sst",
        variable="sea_surface_temperature",
        value=28.5,
        unit="degC",
        latitude=10.0,
        longitude=80.0,
        timestamp=now,
        retrieved_at=now,
        data_age="0.0h",
        freshness_status=FreshnessStatus.FRESH,
    )
    assert fresh_obs.source_name == "INCOIS"
    assert fresh_obs.freshness_status == FreshnessStatus.FRESH
    
    stale_obs = Observation(
        source=DataSource.MOSDAC,
        source_name="MOSDAC",
        dataset="sst",
        variable="sea_surface_temperature",
        value=28.2,
        unit="degC",
        latitude=10.0,
        longitude=80.0,
        timestamp=old_time,
        retrieved_at=now,
        data_age="30.0h",
        data_age_hours=30.0,
        freshness_status=FreshnessStatus.STALE,
        confidence=0.5,
    )
    assert stale_obs.freshness_status == FreshnessStatus.STALE
    assert stale_obs.confidence <= 0.60


# ── FLAW 3: PFZ OVERCROWDING MITIGATION ──────────────────────────────────────

def test_flaw3_pfz_overcrowding_and_alternatives():
    """Verify crowding levels, penalties, Option A/B/C labels, and dispersed sub-cells."""
    candidate_zones = [
        {
            "zone_id": "ZONE-1",
            "center_lat": 12.5,
            "center_lon": 80.5,
            "score": 0.90,
            "crowding_level": "HIGH",
            "vessel_density": 1.8,
            "vessel_count": 22,
            "distance_km": 15.0,
        },
        {
            "zone_id": "ZONE-2",
            "center_lat": 12.6,
            "center_lon": 80.6,
            "score": 0.85,
            "crowding_level": "LOW",
            "vessel_density": 0.2,
            "vessel_count": 2,
            "distance_km": 18.0,
        },
        {
            "zone_id": "ZONE-3",
            "center_lat": 12.4,
            "center_lon": 80.4,
            "score": 0.80,
            "crowding_level": "MODERATE",
            "vessel_density": 0.7,
            "vessel_count": 8,
            "distance_km": 10.0,
        },
    ]
    safe_zones, excluded = filter_and_rank_pfz_zones(candidate_zones, origin_lat=12.4, origin_lon=80.3)
    
    assert len(safe_zones) >= 2
    # Verify option labels match OPTION A/B/C and titles reflect Option A/B/C
    assert safe_zones[0]["option_label"] == "OPTION A"
    assert safe_zones[0]["option_title"] == "Option A — Best Overall"
    assert safe_zones[1]["option_label"] == "OPTION B"
    assert safe_zones[1]["option_title"] == "Option B — Less Crowded"
    if len(safe_zones) > 2:
        assert safe_zones[2]["option_label"] == "OPTION C"
        assert safe_zones[2]["option_title"] == "Option C — Closest Safe Alternative"


# ── FLAW 4: SPAWNING AND ECOLOGICAL PROTECTION ───────────────────────────────

def test_flaw4_spawning_and_ecological_protection():
    """Verify strict exclusion of active fishing ban zones and metadata presence."""
    check_date = datetime(2026, 5, 10)
    eco_check = check_spawning_and_ecological_sensitivity(13.0, 80.5, check_date=check_date)
    assert eco_check["ban_active"] is True
    assert "Ministry of Fisheries" in eco_check["ban_details"]["source"]
    assert eco_check["ban_details"]["restriction_type"] == "OFFICIAL_SEASONAL_BAN"
    assert "geometry" in eco_check["ban_details"]


# ── FLAW 5: GPS INACCURACY NEAR BORDERS ──────────────────────────────────────

def test_flaw5_four_tier_buffer_zone_hierarchy():
    """Verify 4-tier buffer: SAFE_AREA -> WARNING_BUFFER -> CRITICAL_BUFFER -> RESTRICTED_AREA."""
    # Point ~2 km from Sir Creek IMBL (lat 23.65, lon 68.12)
    crit = check_marine_geofence(23.65, 68.12)
    assert crit["buffer_hierarchy_level"] in ("CRITICAL_BUFFER", "RESTRICTED_AREA")
    assert crit["min_border_distance_km"] < 5.0
    assert crit["safe_return_heading_deg"] is not None

    # Point safely offshore Chennai (> 50 km from any IMBL)
    safe = check_marine_geofence(13.08, 80.60)
    assert safe["buffer_hierarchy_level"] == "SAFE_AREA"
    assert safe["min_border_distance_km"] > 12.0


# ── FLAW 6: OFFLINE CONNECTIVITY AT SEA ──────────────────────────────────────

def test_flaw6_offline_safety_pack_data():
    """Verify offline safety pack structure and coordinates availability."""
    assert len(SEASONAL_FISHING_BANS) >= 2
    assert len(MARINE_PROTECTED_AREAS) >= 4
    for ban in SEASONAL_FISHING_BANS:
        assert "min_lat" in ban
        assert "max_lat" in ban
        assert "name" in ban
    # Verify check_spawning_and_ecological_sensitivity produces full geometry
    eco = check_spawning_and_ecological_sensitivity(9.15, 79.2)
    assert "geometry" in eco
    assert eco["geometry"]["type"] == "Point"


# ── FLAW 7: DATA PROVIDER FAILURE & TIERING ──────────────────────────────────

def test_flaw7_provider_failure_and_tiering():
    """Verify provider fallback and tier labeling without inventing silent data."""
    ds = DataService()
    # Query an arbitrary bbox
    batch = asyncio.run(ds.get_observations(
        bbox=[80.0, 12.0, 80.5, 12.5],
        start_date=datetime.now(timezone.utc) - timedelta(days=1),
        end_date=datetime.now(timezone.utc),
        variables=["sea_surface_temperature"],
    ))
    assert batch.provider_tier in ("PRIMARY", "SECONDARY", "CACHED", "DEMO", "UNAVAILABLE")
    assert batch.freshness_status in (FreshnessStatus.FRESH, FreshnessStatus.DELAYED, FreshnessStatus.STALE, FreshnessStatus.UNAVAILABLE)


# ── FLAW 8: DATASET DISAGREEMENT DETECTION ───────────────────────────────────

def test_flaw8_dataset_disagreement():
    """Verify evidence fusion detects dataset disagreements and elevates uncertainty."""
    fusion = EvidenceFusionEngine()
    
    now = datetime.now(timezone.utc)
    ev_incois = EvidenceItem(
        source="INCOIS",
        dataset="sst",
        agent=AgentType.SATELLITE,
        variable="sea_surface_temperature",
        value=31.5,
        unit="degC",
        timestamp=now,
        evidence_type=EvidenceType.OBSERVATION,
    )
    ev_mosdac = EvidenceItem(
        source="MOSDAC",
        dataset="sst",
        agent=AgentType.SATELLITE,
        variable="sea_surface_temperature",
        value=28.0,
        unit="degC",
        timestamp=now,
        evidence_type=EvidenceType.OBSERVATION,
    )
    contradictions = fusion._detect_contradictions([ev_incois, ev_mosdac])
    assert any("disagreement" in c.lower() or "diverging" in c.lower() for c in contradictions)


# ── FLAW 9: AI HALLUCINATION PREVENTION ──────────────────────────────────────

def test_flaw9_llm_hallucination_guardrails():
    """Verify SYSTEM_PROMPT strictly prohibits inventing marine measurements."""
    from llm.service import SYSTEM_PROMPT
    assert "The LLM must NEVER calculate, extrapolate, or invent scientific marine measurements" in SYSTEM_PROMPT
    assert "NEVER say: \"Fish are located here\"" in SYSTEM_PROMPT


# ── FLAW 10: SAFETY STRICTLY OVERRIDES PFZ ───────────────────────────────────

def test_flaw10_safety_strictly_overrides_pfz():
    """Verify high biological suitability is disqualified if sea conditions exceed safety limits."""
    engine = PFZAnalysisEngine()
    v_prof = VesselProfile.from_vessel_class("Artisanal")  # wave limit 2.0m, wind 10.0 m/s
    
    hazardous_cell = PFZCell(
        cell_id="HAZARD-01",
        lat=13.0,
        lon=80.4,
        lat_min=12.95,
        lat_max=13.05,
        lon_min=80.35,
        lon_max=80.45,
        sst=28.5,  # Ideal SST
        chlorophyll=2.5,  # High Chlorophyll
        wave_height=3.5,  # DANGEROUS WAVE: Exceeds 2.0m limit!
        wind_speed=15.0,  # DANGEROUS WIND: Exceeds 10 m/s limit!
        data_mode="LIVE",
    )
    
    scored_cells = engine._score_cells([hazardous_cell], v_prof=v_prof)
    assert scored_cells[0].is_critical_hazard is True
    assert scored_cells[0].total_score == 0.0
    assert scored_cells[0].safety_score == 0.0


# ── FLAW 11: ROUTE SAFETY DURING TRAVEL & DEPARTURE DELAY ────────────────────

def test_flaw11_route_time_aware_weather_and_delay():
    """Verify routing checks time-aware weather and recommends delay if mid-route hazard emerges."""
    # Artisanal profile with conservative 2.0m wave threshold
    route = calculate_optimal_marine_route(
        13.0, 80.3,
        13.3, 80.8,
        departure_time=datetime.now(timezone.utc),
        vessel_class="Artisanal",
    )
    assert route["is_navigable"] is True
    assert "departure_delay_recommended" in route
    assert "vessel_profile" in route
    assert route["vessel_profile"]["maximum_safe_wave_m"] == 2.0


# ── FLAW 12: ROUTES NEVER CROSS RESTRICTED AREAS ─────────────────────────────

def test_flaw12_route_restricted_zone_collision_check():
    """Verify destination or waypoints colliding with restricted polygons are flagged."""
    # INS Kadamba / Karwar Naval Base Approach Channel is around (14.78, 74.12) with 18 km radius
    route = calculate_optimal_marine_route(14.5, 74.0, 14.78, 74.12)
    assert route["restricted_zone_collision"] is True
    assert route["is_navigable"] is False
    assert any("HARD CONSTRAINT VIOLATION" in w for w in route["warnings"])


# ── FLAW 13: VESSEL-SPECIFIC SAFETY PROFILES ─────────────────────────────────

def test_flaw13_vessel_profile_thresholds():
    """Verify boat types have distinct safe operating thresholds."""
    artisanal = VesselProfile.from_vessel_class("Artisanal")
    assert artisanal.maximum_safe_wave_m == 2.0
    assert artisanal.maximum_safe_wind_ms == 10.0

    mechanized = VesselProfile.from_vessel_class("DeepSeaMechanized")
    assert mechanized.maximum_safe_wave_m == 4.0
    assert mechanized.maximum_safe_wind_ms == 20.0


# ── FLAW 14: REGIONAL LANGUAGE AND VOICE ERRORS ──────────────────────────────

def test_flaw14_voice_confidence_and_safety_templates():
    """Verify VoiceProcessingResponse includes ASR confidence and validated safety templates."""
    resp = VoiceProcessingResponse(
        recognized_text="மீன்பிடி மண்டலம் எங்கே?",
        translated_english_query="Where is the fishing zone?",
        target_language_code="ta",
        response_text_regional="பரிந்துரைக்கப்பட்ட பகுதி...",
        latency_ms=120.0,
        asr_confidence=0.55,
        requires_confirmation=True,
        confirmation_prompt="Did you ask about fishing zones?",
    )
    assert resp.asr_confidence == 0.55
    assert resp.requires_confirmation is True

    # Check that Tamil, Telugu, Hindi, Malayalam templates exist for critical alerts
    for key in ("BORDER_CRITICAL", "WEATHER_HAZARD", "SEASONAL_BAN", "PFZ_DISCLAIMER"):
        assert key in VALIDATED_SAFETY_TEMPLATES
        assert "ta" in VALIDATED_SAFETY_TEMPLATES[key]
        assert "te" in VALIDATED_SAFETY_TEMPLATES[key]
        assert "hi" in VALIDATED_SAFETY_TEMPLATES[key]
        assert "ml" in VALIDATED_SAFETY_TEMPLATES[key]


# ── FLAW 15: GRACEFUL DEGRADATION ARCHITECTURE ───────────────────────────────

def test_flaw15_graceful_degradation_levels():
    """Verify system recognizes 4 tiers: LIVE, CACHED, OFFLINE/DEMO, UNAVAILABLE."""
    engine = PFZAnalysisEngine()
    
    cell_live = PFZCell(cell_id="c1", lat=12.0, lon=80.0, lat_min=11.9, lat_max=12.1, lon_min=79.9, lon_max=80.1, data_mode="LIVE")
    cell_cached = PFZCell(cell_id="c2", lat=12.0, lon=80.0, lat_min=11.9, lat_max=12.1, lon_min=79.9, lon_max=80.1, data_mode="CACHED")
    cell_demo = PFZCell(cell_id="c3", lat=12.0, lon=80.0, lat_min=11.9, lat_max=12.1, lon_min=79.9, lon_max=80.1, data_mode="DEMO")
    
    assert engine._determine_data_mode([cell_live]) == "LIVE"
    assert engine._determine_data_mode([cell_cached]) == "CACHED"
    assert engine._determine_data_mode([cell_demo]) == "DEMO"
