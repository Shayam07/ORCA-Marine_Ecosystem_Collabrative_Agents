"""Unit tests for ORCA conversational behavior, context memory, and location handling."""

import pytest
from fastapi.testclient import TestClient
from main import app
from conversation.manager import get_conversation_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_missing_location_asks_followup(client):
    """When user asks 'Where can I fish?' without a location, ORCA asks for one."""
    conv_id = "test_conv_missing_loc"
    
    resp = client.post("/api/v1/chat/message", json={
        "message": "Where can I fish?",
        "conversation_id": conv_id,
        "data_mode": "LIVE"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] == "followup_location"
    assert "Which location would you like me to check" in data["content"] or "coastal" in data["content"].lower()
    assert data["location"] is None


def test_coastal_query_provides_recommendation_and_coordinates(client):
    """When user specifies a coastal city, ORCA resolves location and provides PFZ data."""
    conv_id = "test_conv_coastal"
    
    resp = client.post("/api/v1/chat/message", json={
        "message": "Where can I fish near Chennai?",
        "conversation_id": conv_id,
        "data_mode": "LIVE"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["location"] is not None
    assert "chennai" in data["location"]["name"].lower()
    assert data["location"]["environment"] == "COASTAL"
    assert len(data["metadata"].get("pfz_zones", [])) > 0
    assert not data["content"].startswith("PFZ Analysis:")
    assert not data["content"].startswith("Environmental Suitability:")


def test_context_retention_and_location_overwrite(client):
    """Test multi-turn flow: Chennai -> 'What about tomorrow?' -> 'Patna' -> 'Kochi'."""
    conv_id = "test_conv_multiturn"
    
    # Turn 1: Chennai
    r1 = client.post("/api/v1/chat/message", json={
        "message": "Where can I fish near Chennai?",
        "conversation_id": conv_id,
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert "chennai" in d1["location"]["name"].lower()
    
    # Turn 2: What about tomorrow? (Should inherit Chennai)
    r2 = client.post("/api/v1/chat/message", json={
        "message": "What about tomorrow?",
        "conversation_id": conv_id,
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["location"] is not None
    assert "chennai" in d2["location"]["name"].lower()
    assert d2["response_type"] != "followup_location"
    
    # Turn 3: Patna (Inland location must overwrite Chennai immediately)
    r3 = client.post("/api/v1/chat/message", json={
        "message": "Patna",
        "conversation_id": conv_id,
    })
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["response_type"] == "inland_notice"
    assert "patna" in d3["location"]["name"].lower()
    assert d3["location"]["environment"] == "INLAND"
    assert "inland" in d3["content"].lower()
    assert "chennai" not in d3["content"].lower()
    
    # Turn 4: Kochi (Coastal location must overwrite Patna)
    r4 = client.post("/api/v1/chat/message", json={
        "message": "Kochi",
        "conversation_id": conv_id,
    })
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["location"] is not None
    assert "kochi" in d4["location"]["name"].lower()
    assert d4["location"]["environment"] == "COASTAL"
    assert "patna" not in d4["content"].lower()
    
    # Turn 5: Is it safe? (Should inherit Kochi)
    r5 = client.post("/api/v1/chat/message", json={
        "message": "Is it safe?",
        "conversation_id": conv_id,
    })
    assert r5.status_code == 200
    d5 = r5.json()
    assert d5["location"] is not None
    assert "kochi" in d5["location"]["name"].lower()


def test_resolver_does_not_mistake_system_or_zones_for_place_names():
    """Unit test: resolver must never extract 'Samudra Seastate' or 'Pfzsector' as locations."""
    from conversation.resolver import ContextResolver
    res = ContextResolver()

    assert res._extract_place_name("Show SAMUDRA sea-state & wave forecast") is None
    assert res._extract_place_name("What are the fishing conditions in zone PFZ-SECTOR-04?") is None
    assert res._extract_place_name("Plan safe route to nearest PFZ zone") is None
    assert res._extract_place_name("Is it safe?") is None
    assert res._extract_place_name("Where can I fish near Chennai?") == "Chennai"
    assert res._extract_place_name("What about Mumbai?") == "Mumbai"
    assert res._extract_place_name("Patna") == "Patna"
    assert res._extract_place_name("Kochi") == "Kochi"
    assert res._extract_zone_id("What are the fishing conditions in zone PFZ-SECTOR-04?") == "PFZ-SECTOR-04"


def test_samudra_seastate_query_succeeds(client):
    """'Show SAMUDRA sea-state & wave forecast' uses active coastal location and activates waves layer."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "Show SAMUDRA sea-state & wave forecast",
        "landing_centre": {"name": "Kasimedu", "lat": 13.12, "lon": 80.30, "state": "Tamil Nadu"},
        "data_mode": "LIVE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] != "clarification"
    assert "couldn't precisely locate" not in data["content"].lower()
    assert "samudra seastate" not in data["content"].lower()
    assert "waves" in data.get("map_layers", [])


def test_pfz_sector_query_succeeds(client):
    """'What are the fishing conditions in zone PFZ-SECTOR-04?' answers without geocoding failure."""
    resp = client.post("/api/v1/chat/message", json={
        "message": "What are the fishing conditions in zone PFZ-SECTOR-04?",
        "landing_centre": {"name": "Kasimedu", "lat": 13.12, "lon": 80.30, "state": "Tamil Nadu"},
        "data_mode": "LIVE",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["response_type"] != "clarification"
    assert "couldn't precisely locate" not in data["content"].lower()
    assert "pfzsector" not in data["content"].lower()
    assert data["intent"] == "PFZ_ANALYSIS"
