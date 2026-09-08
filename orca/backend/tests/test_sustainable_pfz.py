"""Unit tests for Sustainable PFZ Decision Layer, Crowding Protection, and Ecological Bans."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from main import app
from reasoning.pfz_engine import PFZAnalysisEngine, PFZCell
from agents.geofence import (
    filter_and_rank_pfz_zones,
    is_seasonal_ban_active,
    check_spawning_and_ecological_sensitivity,
    check_marine_geofence,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_seasonal_fishing_ban_detection():
    """Verify that official Indian seasonal fishing bans are detected accurately by date and location."""
    # East Coast Ban is April 15 - June 14
    east_coast_lat, east_coast_lon = 13.08, 80.27
    date_during_ban = datetime(2026, 5, 10)
    date_outside_ban = datetime(2026, 8, 20)

    ban_active = is_seasonal_ban_active(east_coast_lat, east_coast_lon, date_during_ban)
    assert ban_active["is_active"] is True
    assert "East Coast" in ban_active["ban_name"]

    ban_inactive = is_seasonal_ban_active(east_coast_lat, east_coast_lon, date_outside_ban)
    assert ban_inactive["is_active"] is False


def test_spawning_and_mpa_protection_detection():
    """Verify that Marine Protected Areas and spawning sanctuaries are detected."""
    # Gahirmatha Olive Ridley Turtle Sanctuary
    gahirmatha_lat, gahirmatha_lon = 20.65, 86.95
    spawning_season_date = datetime(2026, 1, 15)

    eco_check = check_spawning_and_ecological_sensitivity(gahirmatha_lat, gahirmatha_lon, spawning_season_date)
    assert eco_check["is_protected"] is True
    assert eco_check["is_spawning_season"] is True
    assert "Gahirmatha" in eco_check["name"]


def test_strict_exclusion_of_restricted_and_spawning_zones():
    """Verify that restricted areas and active spawning zones are strictly excluded from PFZ recommendations."""
    candidate_zones = [
        {
            "zone_id": "ZONE-PERMITTED",
            "center_lat": 13.20,
            "center_lon": 80.40,
            "score": 0.85,
            "raw_suitability_score": 0.85,
            "crowding_level": "LOW",
            "vessel_density": 0.3,
            "vessel_count": 3,
        },
        {
            "zone_id": "ZONE-IMBL-BORDER",
            "center_lat": 9.15,
            "center_lon": 79.28,  # Near Palk Strait IMBL
            "score": 0.95,  # High raw score
            "raw_suitability_score": 0.95,
            "crowding_level": "LOW",
        },
        {
            "zone_id": "ZONE-GAHIRMATHA-SPAWNING",
            "center_lat": 20.65,
            "center_lon": 86.95,  # Inside Olive Ridley Core
            "score": 0.92,
            "raw_suitability_score": 0.92,
            "crowding_level": "LOW",
        },
    ]

    safe_zones, excluded_zones = filter_and_rank_pfz_zones(
        candidate_zones,
        origin_lat=13.08,
        origin_lon=80.27,
        check_date=datetime(2026, 1, 15),
    )

    safe_ids = [z["zone_id"] for z in safe_zones]
    excluded_ids = [z["zone_id"] for z in excluded_zones]

    assert "ZONE-PERMITTED" in safe_ids
    assert "ZONE-IMBL-BORDER" in excluded_ids
    assert "ZONE-GAHIRMATHA-SPAWNING" in excluded_ids

    # Verify exclusion reasons are present
    excluded_reasons = [z.get("exclusion_reason") for z in excluded_zones]
    assert all(r is not None and len(r) > 0 for r in excluded_reasons)


def test_crowding_penalty_prioritizes_low_pressure_alternative():
    """Verify that high fleet crowding incurs a penalty and prioritizes a low-pressure alternative zone."""
    candidate_zones = [
        {
            "zone_id": "ZONE-HIGH-CROWD",
            "center_lat": 13.15,
            "center_lon": 80.35,
            "score": 0.88,
            "raw_suitability_score": 0.88,
            "crowding_level": "HIGH",
            "vessel_density": 2.2,
            "vessel_count": 28,
            "distance_km": 15.0,
        },
        {
            "zone_id": "ZONE-LOW-CROWD",
            "center_lat": 13.25,
            "center_lon": 80.45,
            "score": 0.80,  # Slightly lower raw suitability
            "raw_suitability_score": 0.80,
            "crowding_level": "LOW",
            "vessel_density": 0.3,
            "vessel_count": 4,
            "distance_km": 20.0,
        },
    ]

    safe_zones, _ = filter_and_rank_pfz_zones(
        candidate_zones,
        origin_lat=13.08,
        origin_lon=80.27,
        check_date=datetime(2026, 8, 20),
    )

    assert len(safe_zones) == 2
    # The low-crowding zone should rank #1 due to crowding penalty on the congested zone
    top_zone = safe_zones[0]
    assert top_zone["zone_id"] == "ZONE-LOW-CROWD"
    assert top_zone["recommendation_status"] == "RECOMMENDED"
    assert top_zone["option_label"] == "OPTION A"

    second_zone = safe_zones[1]
    assert second_zone["zone_id"] == "ZONE-HIGH-CROWD"
    assert second_zone["recommendation_status"] == "ALTERNATIVE"
    assert second_zone["option_label"] == "OPTION B"


def test_pfz_engine_sustainable_analysis():
    """Test full PFZAnalysisEngine pipeline with simulated data."""
    import asyncio
    engine = PFZAnalysisEngine(resolution=0.25)
    bbox = [80.0, 12.5, 81.0, 13.5]

    result = asyncio.run(engine.analyze(
        bbox=bbox,
        center_lat=13.08,
        center_lon=80.27,
        start_date=datetime(2026, 8, 20),
        end_date=datetime(2026, 8, 22),
        data_service=None,
        allow_demo=True,
    ))

    assert len(result.zones) > 0
    top = result.zones[0]
    assert top.recommendation_status == "RECOMMENDED"
    assert top.option_label == "OPTION A"
    assert top.crowding_level in ("LOW", "MODERATE", "HIGH")
    assert top.vessel_density >= 0.0
    assert len(top.suggested_grid_cells) > 0


def test_chat_api_returns_sustainable_pfz_metadata(client):
    """Verify chat API returns sustainable PFZ options and clear trade-off explanations."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "Where can I fish near Chennai?",
        "conversation_id": "test_conv_sustainable",
        "data_mode": "LIVE"
    })
    assert resp.status_code == 200
    data = resp.json()
    pfz_zones = data["metadata"].get("pfz_zones", [])
    assert len(pfz_zones) > 0

    first_zone = pfz_zones[0]
    assert "crowding_level" in first_zone
    assert "recommendation_status" in first_zone
    assert "option_label" in first_zone

    content = data["content"]
    # Ensure AI does NOT say "high chlorophyll therefore fish here"
    assert "therefore you should fish here" not in content.lower()
    # Ensure AI mentions safe/sustainable/crowding advice
    assert "sustainable" in content.lower() or "offshore" in content.lower() or "option" in content.lower()
