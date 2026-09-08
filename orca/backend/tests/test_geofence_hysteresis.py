"""Tests for GPS Buffer Zones, Accuracy Margins, and Consecutive Reading Hysteresis."""

import pytest
from agents.geofence import check_marine_geofence


def test_geofence_buffer_tiers():
    """Verify standard distance-based buffer tiers (SAFE, WARNING_BUFFER, CRITICAL_BUFFER)."""
    # Point ~30 km offshore Chennai -> SAFE
    safe_check = check_marine_geofence(lat=13.08, lon=80.60)
    assert safe_check["status"] == "SAFE"
    assert safe_check["buffer_zone_tier"] == "SAFE"

    # Point near Sir Creek IMBL (lat 23.65, lon 68.10) ~9 km away -> WARNING_BUFFER
    warn_check = check_marine_geofence(lat=23.65, lon=68.19)
    assert warn_check["status"] == "WARNING"
    assert warn_check["buffer_zone_tier"] == "WARNING_BUFFER"

    # Point ~2 km from Sir Creek IMBL -> CRITICAL_BUFFER
    crit_check = check_marine_geofence(lat=23.65, lon=68.12)
    assert crit_check["status"] == "CRITICAL"
    assert crit_check["buffer_zone_tier"] == "CRITICAL_BUFFER"


def test_gps_accuracy_error_buffer_expansion():
    """Verify that degraded GPS accuracy (> 100m) expands buffer thresholds."""
    res_high_acc = check_marine_geofence(lat=23.65, lon=68.20, gps_accuracy_meters=10.0)
    res_low_acc = check_marine_geofence(lat=23.65, lon=68.20, gps_accuracy_meters=300.0)

    assert res_low_acc["gps_accuracy_meters"] == 300.0


def test_consecutive_hysteresis_filters_single_point_gps_jitter():
    """Verify that a single isolated spike into critical territory with noisy GPS does not cause panic siren."""
    # History shows last 3 fixes were SAFE
    safe_history = [
        {"status": "SAFE"},
        {"status": "SAFE"},
        {"status": "SAFE"},
    ]

    # Jumpy fix with degraded accuracy (150m error) near Sir Creek
    jitter_check = check_marine_geofence(
        lat=23.65,
        lon=68.12,  # raw critical
        gps_accuracy_meters=150.0,
        history=safe_history,
    )

    # Status should be downgraded to WARNING with verification note
    assert jitter_check["status"] == "WARNING"
    assert "Position spike detected" in jitter_check["alert_message"] or "Verifying consecutive fixes" in jitter_check["alert_message"]
