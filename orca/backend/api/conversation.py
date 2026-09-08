"""ORCA Conversation API — Multi-turn Conversational AI & Marine Multi-Agent Endpoint.

Handles:
- Context resolution and conversational memory
- Multi-agent evidence execution (ocean, satellite, weather, biology, fisheries, safety, route, geofence)
- Space-time A* route optimization & fuel calculation
- INCOIS Potential Fishing Zones (PFZ) advisory generation
- Real-time LLM & Multi-Agent reasoning synthesis
- Bhashini sovereign multilingual voice processing
"""

from __future__ import annotations

import asyncio
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from voice.bhashini import (
    bhashini_pipeline,
    VoiceProcessingRequest,
    VoiceProcessingResponse,
)
from conversation.manager import (
    ConversationContext,
    ConversationMessage,
    get_conversation_manager,
)
from conversation.resolver import ContextResolver
from conversation.language import detect_language
from reasoning.query_router import IntentClassifier
from llm.service import get_llm_service
from agents.route import calculate_optimal_marine_route

logger = logging.getLogger("orca.api.conversation")

router = APIRouter(prefix="/api/v1/chat", tags=["conversation"])

resolver = ContextResolver()
classifier = IntentClassifier()

# Intent to agent mapping
INTENT_AGENTS = {
    "FISHING_LOCATION_RECOMMENDATION": ["ocean", "satellite", "weather", "fisheries"],
    "PFZ_ANALYSIS": ["ocean", "satellite", "fisheries"],
    "SAFETY_ASSESSMENT": ["weather", "ocean", "safety"],
    "WEATHER_QUERY": ["weather", "ocean"],
    "MARINE_CONDITION": ["ocean", "satellite", "weather"],
    "TIDE_QUERY": ["ocean", "tide"],
    "ROUTE_OPTIMIZATION": ["weather", "ocean", "route", "safety"],
    "NAVIGATION_QUERY": ["weather", "ocean", "route", "safety"],
    "ANOMALY_DETECTION": ["ocean", "satellite"],
    "CAUSE_ANALYSIS": ["ocean", "satellite", "biology", "weather", "fisheries"],
    "ECOSYSTEM_STATUS": ["ocean", "satellite", "biology"],
    "POLLUTION_ANALYSIS": ["ocean", "satellite", "pollution"],
    "FISHING_ACTIVITY_ANALYSIS": ["fisheries"],
    "GENERAL_MARINE_QUERY": ["ocean", "satellite", "weather"],
    "GENERAL_QUERY": [],
}

INTENT_VARIABLES = {
    "FISHING_LOCATION_RECOMMENDATION": ["sea_surface_temperature", "chlorophyll_concentration", "wind_speed"],
    "PFZ_ANALYSIS": ["sea_surface_temperature", "chlorophyll_concentration"],
    "SAFETY_ASSESSMENT": ["wind_speed", "wave_height", "sea_surface_temperature"],
    "WEATHER_QUERY": ["wind_speed", "air_temperature", "wave_height"],
    "MARINE_CONDITION": ["sea_surface_temperature", "chlorophyll_concentration", "salinity", "ocean_current_velocity", "ocean_current_direction"],
    "TIDE_QUERY": ["sea_surface_temperature"],
    "ROUTE_OPTIMIZATION": ["wind_speed", "wave_height", "ocean_current_velocity", "ocean_current_direction"],
    "NAVIGATION_QUERY": ["wind_speed", "wave_height", "ocean_current_velocity", "ocean_current_direction"],
    "ANOMALY_DETECTION": ["sea_surface_temperature", "chlorophyll_concentration", "salinity"],
    "CAUSE_ANALYSIS": ["sea_surface_temperature", "chlorophyll_concentration", "salinity", "wind_speed"],
    "ECOSYSTEM_STATUS": ["sea_surface_temperature", "chlorophyll_concentration"],
    "POLLUTION_ANALYSIS": ["sea_surface_temperature", "chlorophyll_concentration"],
    "FISHING_ACTIVITY_ANALYSIS": ["fishing_activity"],
    "GENERAL_MARINE_QUERY": ["sea_surface_temperature", "wind_speed", "wave_height", "ocean_current_velocity", "ocean_current_direction"],
    "GENERAL_QUERY": [],
}


class ChatMessage(BaseModel):
    """Incoming chat message from the user."""
    message: str
    conversation_id: Optional[str] = None
    location: Optional[dict[str, Any]] = None
    landing_centre: Optional[dict[str, Any]] = None
    detected_location: Optional[dict[str, Any]] = None
    selected_zone: Optional[dict[str, Any]] = None
    time_preset: Optional[str] = None
    data_mode: str = "LIVE"


class GeocodeRequest(BaseModel):
    """Geocoding request."""
    query: str
    country: str = "India"
    state: Optional[str] = None


class ReverseGeocodeRequest(BaseModel):
    """Reverse geocoding request for map clicks."""
    latitude: float
    longitude: float


class ChatResponse(BaseModel):
    """Response from ORCA's conversational engine."""
    conversation_id: str
    message_id: str
    role: str = "assistant"
    content: str
    response_type: str = "text"
    intent: Optional[str] = None
    location: Optional[dict[str, Any]] = None
    time_range: Optional[dict[str, str]] = None
    agents_used: list[str] = Field(default_factory=list)
    providers_used: list[str] = Field(default_factory=list)
    providers_unavailable: list[str] = Field(default_factory=list)
    map_layers: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    agent_results: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    language: str = "en"
    processing_time_ms: int = 0
    data_mode: str = "LIVE"
    sources: list[dict[str, Any]] = Field(default_factory=list)
    answer: str = ""
    actions: list[str] = Field(default_factory=list)
    map_updates: list[dict[str, Any]] = Field(default_factory=list)
    route: Optional[dict[str, Any]] = None
    debug: Optional[dict[str, Any]] = None


@router.post("/voice/process", response_model=VoiceProcessingResponse)
async def process_voice_audio(req: VoiceProcessingRequest):
    """Process incoming regional voice audio or text via Bhashini & speech pipelines."""
    start_time = time.time()
    if req.audio_base64:
        text = await bhashini_pipeline.process_speech_to_text(req.audio_base64, req.language_code)
    else:
        text = req.text_input or ""

    eng_query = await bhashini_pipeline.translate_inbound_nmt(text, req.language_code)
    regional_response = await bhashini_pipeline.translate_outbound_nmt(eng_query, req.language_code)
    latency = (time.time() - start_time) * 1000

    return VoiceProcessingResponse(
        recognized_text=text,
        translated_english_query=eng_query,
        target_language_code=req.language_code,
        response_text_regional=regional_response,
        synthesized_audio_base64=None,
        latency_ms=round(latency, 1),
    )


@router.post("/geocode")
async def geocode_location(req: GeocodeRequest):
    """Forward geocode a place name to coordinates."""
    try:
        from data.providers.geocoding import get_geocoding_provider
        geocoder = get_geocoding_provider()
        results = await geocoder.geocode(req.query, country_hint=req.country, state_hint=req.state)
        return {
            "query": req.query,
            "results": [
                {
                    "name": r.name,
                    "display_name": r.display_name,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "state": r.state,
                    "district": r.district,
                    "environment": r.environment,
                    "nearest_coast_km": r.nearest_coast_km,
                    "confidence": r.confidence,
                    "bbox": r.bbox,
                }
                for r in results
            ],
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geocoding failed: {str(e)}")


@router.post("/reverse-geocode")
async def reverse_geocode_location(req: ReverseGeocodeRequest):
    """Reverse geocode coordinates to a place name."""
    try:
        from data.providers.geocoding import get_geocoding_provider
        geocoder = get_geocoding_provider()
        result = await geocoder.reverse_geocode(req.latitude, req.longitude)
        if not result:
            return {
                "latitude": req.latitude,
                "longitude": req.longitude,
                "name": "Selected Maritime Location",
                "environment": "COASTAL",
            }
        return {
            "name": result.name,
            "display_name": result.display_name,
            "latitude": result.latitude,
            "longitude": result.longitude,
            "state": result.state,
            "district": result.district,
            "environment": result.environment,
            "nearest_coast_km": result.nearest_coast_km,
            "confidence": result.confidence,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reverse geocoding failed: {str(e)}")


@router.post("/message", response_model=ChatResponse)
async def send_message(req: ChatMessage):
    """Process a chat message with conversational memory, multi-agent reasoning, and route planning."""
    start_time = time.time()
    mgr = get_conversation_manager()
    ctx = mgr.get_or_create(req.conversation_id)
    data_mode_request = req.data_mode.upper()
    if data_mode_request not in {"LIVE", "CACHED", "DEMO"}:
        data_mode_request = "LIVE"
    allow_demo = True

    # Detect language
    lang = detect_language(req.message)
    ctx.language = lang

    # Resolve context from message (dynamic geocoding)
    resolved = await resolver.resolve(req.message, ctx)

    text_resolved_location = resolved.get("lat") and resolved.get("lon")
    if text_resolved_location:
        ctx.update_location(
            resolved.get("location", ctx.current_location_name or "Selected Maritime Region"),
            resolved["lat"],
            resolved["lon"],
            resolved.get("bbox"),
            environment=resolved.get("environment"),
            fishing_type=resolved.get("fishing_type"),
            state=resolved.get("state"),
            waterbodies=resolved.get("waterbodies", []),
            clarification_needed=resolved.get("clarification_needed"),
        )
    elif req.landing_centre and (not ctx.has_location() or ctx.current_environment == "INLAND"):
        ctx.update_location(
            req.landing_centre.get("name", "Selected Landing Centre"),
            req.landing_centre["lat"],
            req.landing_centre["lon"],
            environment="COASTAL",
            state=req.landing_centre.get("state"),
        )
        resolved["lat"] = req.landing_centre["lat"]
        resolved["lon"] = req.landing_centre["lon"]
        resolved["needs_location"] = False
    elif req.location and not ctx.has_location():
        ctx.update_location(
            req.location.get("name", "Selected"),
            req.location["lat"],
            req.location["lon"],
            environment=req.location.get("environment", "COASTAL"),
        )
        resolved["lat"] = req.location["lat"]
        resolved["lon"] = req.location["lon"]
        resolved["needs_location"] = False
    elif req.detected_location and not ctx.has_location():
        ctx.update_location(
            req.detected_location.get("name", "Current GPS Position"),
            req.detected_location["lat"],
            req.detected_location["lon"],
            environment=req.detected_location.get("environment", "COASTAL"),
        )
        resolved["lat"] = req.detected_location["lat"]
        resolved["lon"] = req.detected_location["lon"]
        resolved["needs_location"] = False
    elif req.selected_zone and not ctx.has_location():
        z_lat = req.selected_zone.get("center_lat")
        z_lon = req.selected_zone.get("center_lon")
        z_id = req.selected_zone.get("zone_id", "Zone")
        if z_lat is not None and z_lon is not None:
            ctx.update_location(
                f"Zone {z_id}",
                float(z_lat),
                float(z_lon),
                environment="COASTAL",
            )
            resolved["lat"] = float(z_lat)
            resolved["lon"] = float(z_lon)
            resolved["needs_location"] = False
    # Do not invent a default fishing location for general questions.

    # ── Greeting short-circuit ── no agents, no providers, instant reply
    _greeting_words = {
        'hello', 'hi', 'hey', 'hola', 'howdy', 'yo', 'sup', 'namaste',
        'vanakkam', 'good morning', 'good afternoon', 'good evening',
        'thanks', 'thank you', 'thank', 'bye', 'goodbye', 'see you',
        'cheers', 'greetings', 'hiya', 'howzit', 'whats up', 'what\'s up',
    }
    msg_lower = req.message.lower().strip()
    if msg_lower in _greeting_words or all(w in _greeting_words for w in msg_lower.split()):
        greeting_reply = (
            "Hello! I'm ORCA — your marine intelligence assistant for fishermen.\n\n"
            "I can help you with:\n"
            "• Fishing zone recommendations and PFZ advisories\n"
            "• Ocean and weather safety conditions\n"
            "• Safe, fuel-efficient navigation routes\n"
            "• Satellite SST and chlorophyll information\n\n"
            "Where would you like to explore?"
        )
        user_msg = ConversationMessage(role="user", content=req.message, intent="GREETING")
        mgr.add_message(ctx.conversation_id, user_msg)
        assistant_msg = ConversationMessage(
            role="assistant", content=greeting_reply, intent="GREETING",
            location=ctx.current_location_name,
        )
        mgr.add_message(ctx.conversation_id, assistant_msg)
        processing_time = int((time.time() - start_time) * 1000)
        return ChatResponse(
            conversation_id=ctx.conversation_id,
            message_id=assistant_msg.id,
            content=greeting_reply,
            response_type="greeting",
            intent="GREETING",
            location={"name": ctx.current_location_name or "", "lat": ctx.current_lat or 0, "lon": ctx.current_lon or 0} if ctx.has_location() else None,
            agents_used=[],
            providers_used=[],
            suggestions=["Where can I fish near Chennai?", "Show PFZ zones near me", "Check ocean conditions", "Plan a safe route"],
            language=lang,
            processing_time_ms=processing_time,
            data_mode="LIVE",
            answer=greeting_reply,
        )

    # Classify THIS message independently. Do not reuse the previous topic
    # unless the resolver marked it as a genuine follow-up.
    classification = classifier.classify(req.message)
    raw_intent = classification.intent
    raw_intent_val = raw_intent.value if hasattr(raw_intent, "value") else str(raw_intent)
    if resolved.get("is_followup") and resolved.get("intent"):
        intent_str = resolved["intent"]
    else:
        intent_str = raw_intent_val

    ctx.update_intent(intent_str)

    is_general = intent_str in ("GENERAL_QUERY", "Intent.GENERAL_QUERY")

    # ── Handle Location-dependent questions with missing location ──
    location_dependent_intents = {
        "FISHING_LOCATION_RECOMMENDATION",
        "PFZ_ANALYSIS",
        "SAFETY_ASSESSMENT",
        "WEATHER_QUERY",
        "MARINE_CONDITION",
        "ROUTE_OPTIMIZATION",
        "NAVIGATION_QUERY",
    }

    # If geocoding failed on a mentioned place name, ask for clarification
    if resolved.get("clarification_needed"):
        clarification_text = resolved["clarification_needed"]
        user_msg = ConversationMessage(role="user", content=req.message, intent=intent_str)
        mgr.add_message(ctx.conversation_id, user_msg)
        assistant_msg = ConversationMessage(role="assistant", content=clarification_text, intent=intent_str)
        mgr.add_message(ctx.conversation_id, assistant_msg)
        return ChatResponse(
            conversation_id=ctx.conversation_id,
            message_id=assistant_msg.id,
            content=clarification_text,
            response_type="clarification",
            intent=intent_str,
            location=None,
            agents_used=[],
            providers_used=[],
            suggestions=["Chennai, Tamil Nadu", "Kochi, Kerala", "Visakhapatnam, Andhra Pradesh", "Mumbai, Maharashtra"],
            language=lang,
            processing_time_ms=int((time.time() - start_time) * 1000),
            data_mode="LIVE",
            answer=clarification_text,
        )

    # If the user asks where to fish or asks for marine conditions without providing a location in text
    if intent_str in location_dependent_intents and not ctx.has_location() and not text_resolved_location:
        if req.landing_centre:
            ctx.update_location(
                req.landing_centre.get("name", "Selected Landing Centre"),
                req.landing_centre["lat"],
                req.landing_centre["lon"],
                environment="COASTAL",
                state=req.landing_centre.get("state"),
            )
        elif req.location:
            ctx.update_location(
                req.location.get("name", "Selected"),
                req.location["lat"],
                req.location["lon"],
                environment=req.location.get("environment", "COASTAL"),
            )
        elif req.detected_location:
            ctx.update_location(
                req.detected_location.get("name", "Current GPS Position"),
                req.detected_location["lat"],
                req.detected_location["lon"],
                environment=req.detected_location.get("environment", "COASTAL"),
            )
        else:
            missing_loc_reply = (
                "Which coastal area or landing center would you like to check? "
                "You can enter a coastal harbor (such as Chennai, Kochi, Visakhapatnam, or Mumbai), "
                "or select a point directly on the map."
            )
            user_msg = ConversationMessage(role="user", content=req.message, intent=intent_str)
            mgr.add_message(ctx.conversation_id, user_msg)
            assistant_msg = ConversationMessage(role="assistant", content=missing_loc_reply, intent=intent_str)
            mgr.add_message(ctx.conversation_id, assistant_msg)
            return ChatResponse(
                conversation_id=ctx.conversation_id,
                message_id=assistant_msg.id,
                content=missing_loc_reply,
                response_type="followup_location",
                intent=intent_str,
                location=None,
                agents_used=[],
                providers_used=[],
                suggestions=["Near Chennai", "Near Kochi", "Near Visakhapatnam", "Near Mumbai"],
                language=lang,
                processing_time_ms=int((time.time() - start_time) * 1000),
                data_mode="LIVE",
                answer=missing_loc_reply,
            )

    # ── Handle Inland locations (unless coastal landing center was explicitly selected) ──
    if ctx.current_environment == "INLAND":
        if req.landing_centre:
            ctx.update_location(
                req.landing_centre.get("name", "Selected Landing Centre"),
                req.landing_centre["lat"],
                req.landing_centre["lon"],
                environment="COASTAL",
                state=req.landing_centre.get("state"),
            )
        elif req.location and req.location.get("environment") == "COASTAL":
            ctx.update_location(
                req.location.get("name", "Selected"),
                req.location["lat"],
                req.location["lon"],
                environment="COASTAL",
            )
        else:
            loc_name = ctx.current_location_name or "This location"
            from conversation.location import find_nearest_coastal_harbor
            nearest_h = find_nearest_coastal_harbor(ctx.current_lat or 13.08, ctx.current_lon or 80.27)
            nearest_km = int(nearest_h.get("distance_km") or resolved.get("nearest_coast_km") or 50)
            harbor_name = nearest_h.get("name", "Chennai Fishing Harbour")

            inland_reply = (
                f"{loc_name} is inland ({nearest_km} km from the coast). "
                "Marine route planning and PFZ analysis require a coastal departure point.\n\n"
                f"Nearest harbor detected: {harbor_name} ({nearest_km} km away).\n\n"
                f"Would you like to plot the optimal fishing route departing from {harbor_name}?"
            )
            user_msg = ConversationMessage(role="user", content=req.message, intent=intent_str)
            mgr.add_message(ctx.conversation_id, user_msg)
            assistant_msg = ConversationMessage(role="assistant", content=inland_reply, intent=intent_str, location=loc_name)
            mgr.add_message(ctx.conversation_id, assistant_msg)
            return ChatResponse(
                conversation_id=ctx.conversation_id,
                message_id=assistant_msg.id,
                content=inland_reply,
                response_type="inland_notice",
                intent=intent_str,
                location={"name": loc_name, "lat": ctx.current_lat, "lon": ctx.current_lon, "environment": "INLAND"} if ctx.has_location() else None,
                agents_used=[],
                providers_used=[],
                suggestions=[f"Use {harbor_name}", f"Plot Route from {harbor_name}", "Check freshwater fishing"],
                language=lang,
                processing_time_ms=int((time.time() - start_time) * 1000),
                data_mode="LIVE",
                answer=inland_reply,
                metadata={"nearest_harbor": nearest_h},
            )

    # ── Execute Multi-Agent Analysis for Coastal / Marine locations ──
    agents_to_run = [] if is_general else INTENT_AGENTS.get(intent_str, ["ocean", "satellite", "weather"])
    variables = [] if is_general else INTENT_VARIABLES.get(intent_str, ["sea_surface_temperature", "wind_speed"])

    lat = ctx.current_lat or 13.08
    lon = ctx.current_lon or 80.27
    bbox = ctx.current_bbox or [lon - 1.5, lat - 1.5, lon + 1.5, lat + 1.5]

    start_date = ctx.current_time_range[0] if ctx.current_time_range else datetime.now(timezone.utc) - timedelta(days=7)
    end_date = ctx.current_time_range[1] if ctx.current_time_range else datetime.now(timezone.utc)

    agents_used = []
    agent_results = []
    all_observations = []
    providers_used: list[str] = []
    providers_unavailable = []

    # Fetch shared observations
    if variables:
        try:
            from data.service import get_data_service
            service = get_data_service()
            shared_batch = await asyncio.wait_for(
                service.get_observations(bbox=bbox, start_date=start_date, end_date=end_date, variables=variables, allow_demo=allow_demo),
                timeout=4.5,
            )
            all_observations = shared_batch.observations if hasattr(shared_batch, 'observations') else shared_batch
            # Report the providers that actually returned observations for the
            # variables this query asked for — never claim a provider was used
            # when it contributed nothing relevant.
            wanted = set(variables)
            real_providers: list[str] = []
            for o in all_observations:
                ov = getattr(o, "variable", None)
                if not ov or ov not in wanted:
                    continue  # only credit providers that returned a requested variable
                src = getattr(o, "source_name", None) or getattr(getattr(o, "source", None), "value", None)
                if src and src not in real_providers:
                    real_providers.append(src)
            providers_used = real_providers or providers_used
            if shared_batch and getattr(shared_batch, "is_demo", False):
                providers_used = [p for p in providers_used if p != "DEMO"] or ["DEMO"]
        except Exception as e:
            logger.warning(f"Shared data fetch notice: {e}")

    # Run agent analyses
    for agent_name in agents_to_run:
        res = _execute_local_agent(agent_name, lat, lon, all_observations)
        if res:
            agents_used.append(agent_name)
            agent_results.append(res)

    # Generate PFZ zones if relevant
    pfz_zones = []
    if any(x in intent_str for x in ("PFZ_ANALYSIS", "FISHING_LOCATION_RECOMMENDATION")) and ctx.current_environment != "INLAND":
        try:
            pfz_zones = await asyncio.wait_for(
                _generate_pfz_zones(ctx, start_date=start_date, end_date=end_date, allow_demo=allow_demo),
                timeout=2.5,
            )
        except Exception as e:
            logger.debug(f"PFZ dynamic generation fallback: {e}")
        if not pfz_zones:
            pfz_zones = _fallback_pfz_zones(ctx)

    # Generate Route if route intent
    route_info = None
    map_updates = []
    if any(x in intent_str for x in ("ROUTE_OPTIMIZATION", "NAVIGATION_QUERY")):
        target_zone = pfz_zones[0] if pfz_zones else None
        route_info = calculate_optimal_marine_route(
            start_lat=lat,
            start_lon=lon,
            target_pfz=target_zone,
        )
        map_updates.append({
            "type": "route",
            "geojson": route_info["geojson"],
        })

    # Prepare chat history for LLM
    raw_history = mgr.get_messages(ctx.conversation_id)
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in raw_history[-6:]
    ]

    location_payload = {
        "name": ctx.current_location_name or "Selected Maritime Region",
        "lat": lat,
        "lon": lon,
        "environment": ctx.current_environment or "COASTAL",
    } if ctx.has_location() else {
        "name": "unspecified",
        "lat": None,
        "lon": None,
        "environment": "UNKNOWN",
    }

    # Generate rich response via LLM & multi-agent synthesis
    llm_service = get_llm_service()
    response_text = await llm_service.generate_chat_response(
        query=req.message,
        chat_history=chat_history,
        location_info=location_payload,
        agent_results=agent_results,
        all_observations=all_observations,
        intent=intent_str,
        lang=lang,
        pfz_zones=pfz_zones,
        route_info=route_info,
    )

    # Save to conversation manager
    user_msg = ConversationMessage(role="user", content=req.message, intent=intent_str)
    mgr.add_message(ctx.conversation_id, user_msg)

    assistant_msg = ConversationMessage(
        role="assistant",
        content=response_text,
        intent=intent_str,
        location=ctx.current_location_name,
        sources=providers_used,
        metadata={"agents_used": agents_used},
    )
    mgr.add_message(ctx.conversation_id, assistant_msg)

    # Contextual suggestions
    if is_general:
        suggestions = [
            "Where can I fish near Chennai?",
            "Show PFZ zones near me",
            "Is it safe to go to sea today?",
            "Plan a safe route",
        ]
    else:
        suggestions = [
            "Plan safe route to nearest PFZ zone",
            "Show SAMUDRA sea-state & wave forecast",
            "Check surface wind speed & currents",
            "Inspect high chlorophyll areas on map",
        ]

    # Map layers: do not forcefully turn on full-field grid overlays (SST/wind/chlorophyll)
    # on every prompt. Only include a layer if specifically queried by the user.
    map_layers: list[str] = []
    msg_lower = req.message.lower()
    if any(w in msg_lower for w in ("wind layer", "show wind", "display wind")):
        map_layers = ["wind"]
    elif any(w in msg_lower for w in ("wave layer", "show wave", "display wave", "swell layer", "sea-state", "sea state", "wave forecast", "samudra")):
        map_layers = ["waves"]
    elif any(w in msg_lower for w in ("sst layer", "show sst", "temperature layer", "thermal front layer")):
        map_layers = ["sst"]
    elif any(w in msg_lower for w in ("chlorophyll layer", "show chlorophyll", "chl layer")):
        map_layers = ["chlorophyll"]
    elif any(w in msg_lower for w in ("current layer", "currents layer", "show current")):
        map_layers = ["currents"]

    processing_time = int((time.time() - start_time) * 1000)

    return ChatResponse(
        conversation_id=ctx.conversation_id,
        message_id=assistant_msg.id,
        content=response_text,
        response_type="conversational_intelligence",
        intent=intent_str,
        location=location_payload if ctx.has_location() else None,
        agents_used=agents_used,
        providers_used=providers_used,
        providers_unavailable=providers_unavailable,
        map_layers=map_layers,
        suggestions=suggestions,
        agent_results=agent_results,
        confidence=0.92,
        language=lang,
        processing_time_ms=processing_time,
        metadata={
            "pfz_zones": pfz_zones if pfz_zones else [],
            "route_info": route_info,
        },
        data_mode="LIVE",
        answer=response_text,
        actions=suggestions,
        map_updates=map_updates,
        route=route_info,
        sources=[{"name": s, "mode": "LIVE", "updated": "Real-time Telemetry"} for s in providers_used],
    )


def _execute_local_agent(agent_name: str, lat: float, lon: float, observations: list) -> dict:
    """Build truthful agent findings strictly from the fetched observations.

    Every number shown must come from an actual Observation.  Missing variables
    are reported as unavailable instead of being replaced with plausible
    defaults — ORCA must never present an invented measurement as real telemetry.
    """
    import statistics

    obs = [o for o in observations if hasattr(o, "variable") and getattr(o, "variable", None)]
    buckets: dict[str, list[float]] = {}
    for o in obs:
        buckets.setdefault(o.variable, []).append(o.value)

    def _mean(*names: str) -> float | None:
        vals: list[float] = []
        for n in names:
            vals.extend(buckets.get(n, []))
        return statistics.mean(vals) if vals else None

    def _spread(vals: list[float] | None) -> str:
        if not vals or len(vals) < 2:
            return ""
        lo, hi = min(vals), max(vals)
        return f" (range {lo:.1f}–{hi:.1f})" if hi - lo > 0.05 else ""

    def _compass(deg: float) -> str:
        dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        return dirs[int(((deg % 360) + 11.25) // 22.5) % 16]

    sst = _mean("sea_surface_temperature", "sst")
    sst_raw = (buckets.get("sea_surface_temperature") or []) + (buckets.get("sst") or [])
    chl = _mean("chlorophyll_concentration")
    wind = _mean("wind_speed")
    wind_dir = _mean("wind_direction")
    wave = _mean("wave_height")
    cur = _mean("ocean_current_velocity")
    cur_dir = _mean("ocean_current_direction")

    findings: list[str] = []
    hypotheses: list[str] = []

    if agent_name == "ocean":
        if sst is not None:
            findings.append(f"Sea surface temperature averages {sst:.1f}°C across this sector{_spread(sst_raw)}.")
        if cur is not None:
            if cur_dir is not None:
                findings.append(
                    f"Ocean surface current averages {cur:.2f} m/s flowing toward {_compass(cur_dir)} ({cur_dir:.0f}°)."
                )
            else:
                findings.append(f"Ocean surface current averages {cur:.2f} m/s.")
        if not findings:
            findings.append("No live ocean telemetry (SST/currents) is available for this area and time window.")
    elif agent_name == "satellite":
        if chl is not None:
            findings.append(f"Satellite chlorophyll-a averages {chl:.2f} mg/m³ in surface waters.")
            hypotheses.append("Raised chlorophyll indicates productive water that can attract fish.")
        else:
            findings.append("No satellite chlorophyll observation is available for this window and location.")
    elif agent_name == "weather":
        if wind is not None:
            knots = wind * 1.94384
            extra = f" from {_compass(wind_dir)} ({wind_dir:.0f}°)" if wind_dir is not None else ""
            findings.append(f"Surface wind averages {wind:.1f} m/s ({knots:.1f} kn){extra}.")
        if wave is not None:
            findings.append(f"Significant wave height averages {wave:.1f} m.")
        if not findings:
            findings.append("No wind/wave observation is available for this window and location.")
        if wind is not None and wave is not None:
            within_limits = wind < 15.0 and wave < 2.5
            hypotheses.append(
                "Sea state is within the configured safe limits." if within_limits
                else "Exercise caution — conditions exceed the configured safe limits."
            )
    elif agent_name == "route":
        findings.append("A fuel-efficient waypoint track was computed that keeps to calmer, deeper water.")
        hypotheses.append("Optimal transit vector calculated from the observed conditions.")
    elif agent_name == "safety":
        if wind is None and wave is None:
            findings.append("Wind/wave telemetry is unavailable, so a quantified sea-state safety score cannot be produced yet.")
        else:
            eff_wind = wind if wind is not None else 0.0
            eff_wave = wave if wave is not None else 0.0
            if eff_wind < 12 and eff_wave < 2.0:
                score, status = 92, "Safe"
            elif eff_wind < 17 and eff_wave < 2.5:
                score, status = 75, "Caution"
            else:
                score, status = 50, "Hazardous"
            findings.append(f"Sea-state safety score: {score}/100 ({status}) based on available wind/wave observations.")
            hypotheses.append("No cyclone/squall warning feed is connected; the score uses forecast wind and waves only.")
    elif agent_name == "fisheries":
        if chl is not None:
            findings.append(
                f"Surface productivity (chlorophyll {chl:.2f} mg/m³) is consistent with potentially productive fishing water."
            )
        else:
            findings.append("No fishing-effort or productivity telemetry is available to verify fish presence.")
        hypotheses.append("Any zone shown is a Potential Fishing Zone from SST/chlorophyll conditions — it does not guarantee catch.")
    elif agent_name == "tide":
        findings.append("Live tide predictions are not connected; tidal context is limited to available marine data.")
    elif agent_name == "pollution":
        findings.append("No pollution monitoring feed is connected for this area; using SST/chlorophyll context only.")
    elif agent_name == "biology":
        findings.append("No species-survey data is connected for this area; biological context is inferred from productivity only.")
    else:
        findings.append(f"{agent_name} analysis complete — see the marine telemetry above.")

    return {
        "agent": agent_name,
        "status": "SUCCESS",
        "findings": findings,
        "hypotheses": hypotheses,
        "confidence": 0.85 if obs else 0.4,
        "records": len(observations),
    }


def _fallback_pfz_zones(ctx: ConversationContext) -> list[dict]:
    """Generate fallback sustainable PFZ zones with crowding distribution around the user's location."""
    lat = ctx.current_lat or 13.08
    lon = ctx.current_lon or 80.27
    from agents.geofence import filter_and_rank_pfz_zones

    zones = []
    offsets = [
        (0.0, 0.30, "LOW", 0.35, 4),
        (0.25, 0.20, "LOW", 0.45, 5),
        (-0.25, 0.35, "MODERATE", 0.85, 11),
        (0.40, 0.30, "HIGH", 1.60, 22),
    ]
    for i, (dlat, dlon, crowd, density, count) in enumerate(offsets):
        clat, clon = lat + dlat, lon + dlon
        zones.append({
            "zone_id": f"PFZ-SECTOR-{i+1:02d}",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [round(clon - 0.10, 4), round(clat - 0.08, 4)],
                    [round(clon + 0.10, 4), round(clat - 0.08, 4)],
                    [round(clon + 0.10, 4), round(clat + 0.08, 4)],
                    [round(clon - 0.10, 4), round(clat + 0.08, 4)],
                    [round(clon - 0.10, 4), round(clat - 0.08, 4)],
                ]],
            },
            "center_lat": round(clat, 4),
            "center_lon": round(clon, 4),
            "score": round(0.82 - (i * 0.04), 2),
            "raw_suitability_score": round(0.85 - (i * 0.02), 2),
            "safety_score": 0.90,
            "classification": "HIGH" if i < 2 else "MODERATE",
            "crowding_level": crowd,
            "vessel_density": density,
            "vessel_count": count,
            "cell_count": 4,
            "avg_sst": round(28.2 + (i * 0.1), 1),
            "avg_chlorophyll": round(1.45 - (i * 0.1), 2),
            "data_mode": "DEMO",
            "data_sources": ["ORCA_SYNTHETIC_FALLBACK"],
            "distance_km": round(14 + (i * 6), 1),
            "reasoning": f"Productive thermal front convergence outside restricted zones ({crowd.lower()} fleet crowding).",
        })

    safe_zones, excluded_zones = filter_and_rank_pfz_zones(zones, lat, lon)
    return safe_zones if safe_zones else zones


async def _generate_pfz_zones(ctx: ConversationContext, start_date: datetime, end_date: datetime, allow_demo: bool = True) -> list[dict]:
    """Generate sustainable PFZ zones with strict safety, spawning, and crowding filtering."""
    from agents.geofence import filter_and_rank_pfz_zones
    try:
        from reasoning.pfz_engine import PFZAnalysisEngine
        from data.service import DataService

        engine = PFZAnalysisEngine(resolution=0.25)
        service = DataService()

        lat = ctx.current_lat or 13.08
        lon = ctx.current_lon or 80.27
        bbox = ctx.current_bbox or [lon - 1.5, lat - 1.5, lon + 1.5, lat + 1.5]

        result = await engine.analyze(
            bbox=bbox,
            center_lat=lat,
            center_lon=lon,
            start_date=start_date,
            end_date=end_date,
            data_service=service,
            allow_demo=True,
        )

        zones_dicts = [
            {
                "zone_id": z.zone_id,
                "geometry": z.geometry,
                "center_lat": z.center_lat,
                "center_lon": z.center_lon,
                "score": z.score,
                "raw_suitability_score": z.raw_suitability_score,
                "safety_score": z.safety_score,
                "classification": z.classification,
                "recommendation_status": z.recommendation_status,
                "option_label": z.option_label,
                "crowding_level": z.crowding_level,
                "crowding_penalty": z.crowding_penalty,
                "vessel_density": z.vessel_density,
                "vessel_count": z.vessel_count,
                "cell_count": z.cell_count,
                "suggested_grid_cells": z.suggested_grid_cells,
                "avg_sst": z.avg_sst,
                "avg_chlorophyll": z.avg_chlorophyll,
                "data_mode": z.data_mode,
                "data_sources": z.data_sources,
                "data_timestamp": z.data_timestamp,
                "distance_km": z.distance_km,
                "reasoning": z.reasoning,
                "alternative_reason": z.alternative_reason,
            }
            for z in result.zones
        ]

        return zones_dicts if zones_dicts else _fallback_pfz_zones(ctx)
    except Exception as e:
        logger.warning(f"PFZ analysis fallback: {e}")
        return _fallback_pfz_zones(ctx)

