"""Tests for Space-Time Route Safety, Vessel Profiles, and Hard Restricted Polygon Avoidance."""

import pytest
from datetime import datetime
from agents.route import calculate_optimal_marine_route, VesselProfile


def test_vessel_profile_thresholds():
    """Verify vessel profiles configure distinct operational wave, wind, and range limits."""
    artisanal = VesselProfile.from_vessel_class("Artisanal")
    assert artisanal.maximum_safe_wave_m == 2.0
    assert artisanal.maximum_safe_wind_ms == 10.0
    assert artisanal.maximum_range_km == 40.0

    motorized = VesselProfile.from_vessel_class("Motorized")
    assert motorized.maximum_safe_wave_m == 2.8
    assert motorized.maximum_safe_wind_ms == 14.0

    trawler = VesselProfile.from_vessel_class("Mechanized Trawler")
    assert trawler.maximum_safe_wave_m == 4.0
    assert trawler.maximum_range_km == 250.0


def test_vessel_range_warning():
    """Verify route warning is issued if destination distance exceeds craft maximum range."""
    # Route ~65 km offshore with artisanal boat (max range 40 km)
    route = calculate_optimal_marine_route(
        start_lat=13.08,
        start_lon=80.27,
        end_lat=13.50,
        end_lon=80.85,
        vessel_class="Artisanal",
    )
    assert route["distance_km"] > 40.0
    warnings_text = " ".join(route["warnings"])
    assert "Vessel Range Warning" in warnings_text


def test_hard_restricted_polygon_avoidance():
    """Verify that routes near restricted zones or MPAs adjust waypoints away from the polygon center."""
    # Karwar Naval base approach channel (~14.78 N, 74.12 E)
    route = calculate_optimal_marine_route(
        start_lat=14.75,
        start_lon=74.05,
        end_lat=14.85,
        end_lon=74.20,
        vessel_class="Motorized",
    )
    assert len(route["waypoints"]) > 0
    warnings_text = " ".join(route["warnings"])
    # Route adjustment notice should be present
    assert "Route adjusted" in warnings_text or "safety buffer" in warnings_text.lower()


def test_time_aware_weather_hazard_evaluation():
    """Verify that waypoints include time-aware ETA and hazard classifications based on vessel limits."""
    route = calculate_optimal_marine_route(
        start_lat=13.08,
        start_lon=80.27,
        end_lat=13.30,
        end_lon=80.60,
        vessel_class="Artisanal",
        departure_time=datetime(2026, 8, 28, 6, 0),
    )

    waypoints = route["waypoints"]
    assert len(waypoints) >= 6
    assert all("eta_hours" in wp for wp in waypoints)
    assert all("wave_height_m" in wp for wp in waypoints)
    assert all("wind_speed_ms" in wp for wp in waypoints)
    assert all("hazard_level" in wp for wp in waypoints)
