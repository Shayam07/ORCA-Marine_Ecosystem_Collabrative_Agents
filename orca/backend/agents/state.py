"""ORCA Shared State Schema — MarineAgentState for LangGraph Multi-Agent Orchestrator."""

from __future__ import annotations

import operator
from typing import Any, Dict, List, Optional
from typing_extensions import Annotated, TypedDict


class MarineAgentState(TypedDict):
    """Centralized state schema passing execution context across
    specialized agents within the LangGraph orchestrator.
    """
    # Conversation and User Session Context
    session_id: str
    user_id: str
    preferred_language: str
    raw_user_input: str
    english_translated_input: str

    # Contextual Spatial-Temporal Metadata
    user_location: Dict[str, float]       # {"latitude": float, "longitude": float}
    target_time_window: Dict[str, str]    # {"start_time": ISOStr, "end_time": ISOStr}
    vessel_class: str                     # Artisanal, Motorized, Mechanized

    # Intent and Routing Control
    intent: str                           # PFZ_QUERY, SAFETY_CHECK, ROUTE_PLAN, EXPLAINABILITY
    extracted_entities: Dict[str, Any]
    next_agent_node: str

    # Ingested and Computed Payload Data
    oceanographic_rasters: Dict[str, Any] # SST, Chlorophyll, SWH, Current Vectors
    pfz_clusters: List[Dict[str, Any]]    # Target coordinates with frontal gradients
    active_hazards: List[Dict[str, Any]]  # Waves, swells, lightning, cyclone tracks
    geofence_breaches: List[str]          # IMBL, MPA, or restricted boundary warnings
    computed_trajectory: Dict[str, Any]   # GeoJSON LineString with path costs

    # Output Generation & Observability
    reasoning_traces: Annotated[List[str], operator.add]
    final_text_response: str
    synthesized_audio_payload: Optional[str]
    deckgl_layer_specs: List[Dict[str, Any]] # Visual layer configs for frontend
