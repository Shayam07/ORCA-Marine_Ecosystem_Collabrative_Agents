"""Regression tests for ContextResolver place-name extraction.

Covers the clause-cut fix: a capture after "near/in/at …" must stop at the first
clause word so "… near Chennai with low vessel crowding and no seasonal ban
restrictions." resolves to Chennai instead of a bogus multi-word place name.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conversation.resolver import ContextResolver


def _place(msg: str):
    return ContextResolver()._extract_place_name(msg.lower())


def test_dock_suggestion_stops_at_clause():
    """The ORCA Tools PFZ suggestion must resolve to Chennai, not a garbage phrase."""
    msg = "Show me safe, sustainable PFZ zones near Chennai with low vessel crowding and no seasonal ban restrictions."
    assert _place(msg) == "Chennai"


def test_simple_prepositional_locations():
    assert _place("where can i fish near Chennai") == "Chennai"
    assert _place("fishing near Kanyakumari") == "Kanyakumari"
    assert _place("plan a route from Chennai") == "Chennai"
    assert _place("is it safe off Kochi") == "Kochi"
    assert _place("what about Mumbai") == "Mumbai"
    assert _place("Show me SST and chlorophyll near Visakhapatnam") == "Visakhapatnam"


def test_temporal_tail_never_joins_place():
    assert _place("currents near Chennai right now") == "Chennai"
    assert _place("tell me about the sea near Chennai tomorrow") == "Chennai"


def test_standalone_place_name():
    assert _place("Patna") == "Patna"


def test_no_location_returns_none():
    for msg in ("where can i fish", "is it safe", "show pfz near me", "hello"):
        assert _place(msg) is None
