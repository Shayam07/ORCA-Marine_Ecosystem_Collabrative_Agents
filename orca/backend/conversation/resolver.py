"""ORCA Context Resolver — Interprets follow-up messages using conversation context.

Handles:
- "Near Chennai" → updates location while keeping intent
- "What about tomorrow?" → updates time while keeping intent + location
- "Is it safe?" → switches to safety intent while keeping location + time
- "What about here?" → updates location from map click
"""

from __future__ import annotations

import re
import logging
from datetime import datetime, timezone, timedelta

from .manager import ConversationContext
from .location import resolve_location, resolve_location_dynamic

logger = logging.getLogger("orca.resolver")


class ContextResolver:
    """Resolves ambiguous or follow-up messages using conversation context."""

    async def resolve(self, message: str, context: ConversationContext) -> dict:
        """Analyze a message in context and return resolved parameters.

        Returns dict with:
          - intent: resolved intent
          - location: location name (if updated)
          - lat/lon/bbox: coordinates
          - time_range: resolved time
          - is_followup: whether this is a follow-up
          - needs_location: whether location is needed
          - clarification_needed: if a location was mentioned but couldn't be resolved
          - location_source: CHAT / MAP_CLICK / MAP_SEARCH
        """
        msg = message.strip().lower()
        prev_location = context.current_location_name
        result = {
            "intent": None,
            "location": None,
            "lat": None,
            "lon": None,
            "bbox": None,
            "region": None,
            "time_range": None,
            "time_preset": None,
            "is_followup": False,
            "needs_location": not context.has_location(),
            "needs_time": not context.has_time(),
            "location_source": "CHAT",
            "location_changed": False,
        }

        # ── Step 1: Extract location with 3-state result ──────────────
        # Returns: RESOLVED / MENTIONED_NOT_RESOLVED / NOT_MENTIONED
        location_result = await self._extract_location_3state(msg)
        loc_state = location_result["state"]

        if loc_state == "RESOLVED":
            # Location was mentioned AND successfully geocoded
            loc = location_result["location"]
            result["location"] = loc["name"]
            result["lat"] = loc["lat"]
            result["lon"] = loc["lon"]
            result["bbox"] = loc["bbox"]
            result["region"] = loc.get("region")
            result["environment"] = loc.get("environment")
            result["fishing_type"] = loc.get("fishing_type")
            result["state"] = loc.get("state")
            result["nearest_coast_km"] = loc.get("nearest_coast_km")
            result["clarification_needed"] = loc.get("clarification_needed")
            result["waterbodies"] = loc.get("waterbodies", [])
            result["applicable_domains"] = loc.get("applicable_domains", [])
            result["inapplicable_domains"] = loc.get("inapplicable_domains", [])
            result["needs_location"] = False
            # Detect location change
            if prev_location and prev_location != loc["name"]:
                result["location_changed"] = True
                logger.info(f"LOCATION CHANGE: {prev_location} -> {loc['name']}")

        elif loc_state == "MENTIONED_NOT_RESOLVED":
            # User typed a place name but geocoding failed
            # DO NOT inherit previous location — ask for clarification
            query = location_result.get("query", message.strip())
            result["clarification_needed"] = (
                f"I couldn't precisely locate '{query}'. "
                f"Could you provide the state or country? "
                f"For example: '{query}, Tamil Nadu' or you can select it on the map."
            )
            result["needs_location"] = False  # We know they want a location
            # Do NOT set result["location"] — this prevents inheriting old location
            logger.info(f"LOCATION UNRESOLVED: '{query}' — asking user for clarification")

        else:
            # NOT_MENTIONED — no location in the message
            # If the conversation already has a location, inherit it for seamless context
            if context.has_location():
                result["is_followup"] = True
                result["location"] = context.current_location_name
                result["lat"] = context.current_lat
                result["lon"] = context.current_lon
                result["bbox"] = context.current_bbox
                result["region"] = context.current_region
                result["environment"] = context.current_environment
                result["needs_location"] = False
            else:
                result["needs_location"] = True

        # 3. Try to extract time
        time_info = self._extract_time(msg)
        if time_info:
            result["time_range"] = time_info["range"]
            result["time_preset"] = time_info["preset"]
            result["needs_time"] = False
        elif context.has_time() and self._is_time_reference(msg):
            # User said "tomorrow" or "what about..." → update time
            result["time_range"] = context.current_time_range
            result["time_preset"] = context.time_preset
            result["needs_time"] = False

        # 4. Try to extract intent
        intent = self._extract_intent(msg)
        if intent:
            result["intent"] = intent
        elif context.current_intent and (self._is_context_only_query(msg) or self._is_time_only_query(msg)):
            # Inherit intent only for genuine short follow-ups
            result["intent"] = context.current_intent

        # 4b. Check for PFZ zone / sector references (e.g. PFZ-SECTOR-04)
        zone_id = self._extract_zone_id(message)
        if zone_id:
            result["zone_id"] = zone_id
            if not result.get("intent") or result.get("intent") == "GENERAL_QUERY":
                result["intent"] = "PFZ_ANALYSIS"

        # 5. Determine if we need to ask for missing info
        if not result["needs_location"] and not result["needs_time"]:
            result["is_followup"] = True

        logger.info(f"Resolved: intent={result['intent']}, location={result['location']}, "
                     f"time={result['time_preset']}, followup={result['is_followup']}")

        return result

    def _extract_place_name(self, msg: str) -> str | None:
        """Extract a place name from a natural language message.
        
        Handles:
        - "Where can I fish in Tiruppur?" → "Tiruppur"
        - "Show PFZ near Chennai" → "Chennai"
        - "What about Mumbai?" → "Mumbai"
        - "fishing near Kanyakumari" → "Kanyakumari"
        - "Patna" → "Patna" (standalone place name)
        - "Tirupur" → "Tirupur" (standalone with common misspelling)
        - "Where can I fish?" → None (no place specified)
        - "Is it safe?" → None (no place specified)
        """
        msg_clean = msg.strip()
        msg_lower = msg_clean.lower()

        # Comprehensive filler list — words that can never be standalone place names
        filler = {
            # Questions / Interrogatives
            'where', 'can', 'the', 'a', 'an', 'to', 'of', 'and', 'or', 'but',
            'i', 'me', 'my', 'you', 'your', 'it', 'its', 'we', 'they', 'he', 'she',
            'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'do', 'does', 'did', 'have', 'has', 'had',
            'go', 'going', 'went', 'come', 'coming',
            'show', 'see', 'find', 'check', 'look', 'tell', 'give', 'get', 'use',
            'switch', 'change', 'set', 'pick', 'select', 'plan', 'plot',
            'can', 'could', 'would', 'should', 'might', 'may',
            # Adjectives / descriptors / superlatives
            'nearest', 'nearby', 'near', 'close', 'closest', 'optimal', 'optimum',
            'potential', 'suitable', 'favorable', 'prime', 'best', 'worst', 'better',
            'good', 'bad', 'high', 'low', 'deep', 'shallow', 'rich', 'fertile',
            'safe', 'safety', 'danger', 'dangerous', 'risky', 'risk',
            'rough', 'calm', 'clear', 'warm', 'cold', 'hot', 'cool', 'mild', 'strong', 'weak',
            # Marine & meteorological domain nouns
            'pfz', 'sst', 'chlorophyll', 'chl', 'temperature', 'conditions', 'forecast', 'forecasts',
            'fish', 'fishing', 'zone', 'zones', 'area', 'areas', 'spot', 'spots', 'sector', 'sectors',
            'water', 'sea', 'ocean', 'marine', 'coastal', 'offshore', 'inland', 'pelagic', 'demersal',
            'boat', 'vessel', 'craft', 'harbour', 'harbor', 'port', 'dock', 'jetty', 'landing', 'centre', 'center',
            'weather', 'wind', 'winds', 'wave', 'waves', 'swell', 'current', 'currents', 'tide', 'tides', 'rain', 'storm',
            'border', 'boundary', 'imbl', 'geofence', 'restricted', 'alert', 'alerts', 'hazard', 'hazards',
            'route', 'routes', 'navigation', 'bearing', 'heading', 'distance', 'speed', 'eta', 'fuel',
            'tomorrow', 'today', 'yesterday', 'tonight', 'morning', 'evening', 'now', 'currently',
            # Prepositions / connectors
            'in', 'at', 'around', 'off', 'from', 'about', 'with', 'for', 'this', 'that',
            'what', 'how', 'which', 'when', 'why',
            # Follow-up conversational tokens
            'yes', 'no', 'ok', 'sure', 'thanks', 'thank', 'please', 'plz',
            'hey', 'hi', 'hello', 'help', 'more', 'else', 'other',
            'back', 'again', 'also', 'info', 'really', 'very',
            'any', 'here', 'there', 'then', 'place', 'location',
            'howdy', 'yo', 'sup', 'namaste', 'vanakkam',
            # Technical, sensor, satellite, and ocean advisory terms
            'samudra', 'incois', 'mosdac', 'ascat', 'modis', 'viirs', 'avhrr', 'navic',
            'state', 'seastate', 'sea-state', 'contour', 'contours', 'vector', 'vectors',
            'layer', 'layers', 'raster', 'imagery', 'satellite', 'telemetry',
            'bulletin', 'bulletins', 'advisory', 'advisories', 'observation', 'observations',
            'ground', 'grounds', 'fleet', 'density', 'salinity', 'velocity', 'depth',
            'sounding', 'crowd', 'crowding', 'pressure', 'level', 'levels',
            'score', 'scores', 'rank', 'ranks', 'suitability', 'recommendation', 'recommendations',
            'analysis', 'data', 'mode', 'live', 'demo', 'simulated', 'status', 'pfzsector',
        }
        # Temporal/qualifier tails that must never become part of a place name
        # (e.g. "near Chennai right now" -> "Chennai", not "Chennai Right").
        tail_stops = {
            'right', 'now', 'currently', 'today', 'tomorrow', 'tonight',
            'yesterday', 'just', 'soon', 'yet', 'please', 'around', 'coast',
        }
        
        # 1. First check prepositional matches: "in <place>", "near <place>", "around <place>", etc.
        location_patterns = [
            r'\b(?:in|near|at|around|off|close to|from|to)\s+([a-zA-Z0-9\s_-]+?)(?:\?|\.|!|$)',
            r'\b(?:what about|how about)\s+([a-zA-Z0-9\s_-]+?)(?:\?|\.|!|$)',
        ]
        
        # Clause boundaries — when a capture after "near/in/at …" runs on to the
        # rest of the sentence ("near Chennai with low vessel crowding and no
        # seasonal ban restrictions"), the place name must stop at the first
        # clause word, or geocoding fails on "Chennai Crowding Seasonal Ban…".
        clause_boundaries = {
            'with', 'and', 'or', 'but', 'no', 'not', 'without', 'avoiding',
            'avoid', 'excluding', 'exclude', 'during', 'before', 'after', 'plus',
            'then', 'while', 'when', 'where', 'which', 'because', 'please', 'also',
            'due', 'is', 'are', 'has', 'have', 'too', 'for', 'on', 'by', 'to', 'at',
            'in', 'near', 'around', 'off', 'from', 'with', 'including', 'low',
            'high', 'moderate', 'safe', 'restricted', 'seasonal', 'current', 'today',
            'tomorrow', 'right', 'now', 'winds', 'wind', 'waves', 'wave', 'weather',
        }

        def _is_non_location_term(cand: str) -> bool:
            """Return True if candidate is a zone/system reference rather than a geographic place."""
            c = cand.lower().strip()
            if re.search(r'\b(zone|sector|pfz|cell|grid|samudra|forecast|seastate|sea state)\b', c):
                return True
            return False

        def _cut_at_clause(words: list[str]) -> list[str]:
            """Return words up to (not including) the first clause boundary word."""
            out: list[str] = []
            for w in words:
                if w in clause_boundaries:
                    break
                out.append(w)
            return out

        def _clean(raw_words: list[str]) -> str | None:
            """Cut at clause boundaries, drop filler/tail words, keep a non-empty tail."""
            words = _cut_at_clause(raw_words)
            cand_words = [w for w in words if w not in filler and len(w) > 1 and not w.isdigit()]
            while cand_words and cand_words[-1].lower() in tail_stops:
                cand_words.pop()
            if not cand_words:
                return None
            cand = ' '.join(cand_words).title()
            if _is_non_location_term(cand):
                return None
            return cand

        for pattern in location_patterns:
            match = re.search(pattern, msg_lower, re.IGNORECASE)
            if match:
                raw_candidate = match.group(1).strip()
                # Split with whitespace and hyphens
                raw_words = re.sub(r'[^a-zA-Z0-9\s]', ' ', raw_candidate).split()
                cleaned = _clean(raw_words)
                if cleaned:
                    return cleaned
        
        # 2. Standalone place name check: e.g. "Patna", "Chennai", "Tiruppur", "Kochi", "Dhanbad"
        # Only treat as a standalone place name if the message is NOT a query/command sentence.
        query_lead_tokens = {
            'what', 'where', 'how', 'when', 'why', 'who', 'which',
            'is', 'are', 'was', 'were', 'can', 'could', 'should', 'would', 'will',
            'do', 'does', 'did', 'have', 'has', 'had',
            'show', 'see', 'find', 'check', 'look', 'tell', 'give', 'get', 'use',
            'plan', 'plot', 'calculate', 'explain', 'analyze', 'display', 'inspect',
            'switch', 'change', 'set', 'pick', 'select', 'navigate', 'recommend',
        }
        first_few_words = [w for w in re.sub(r'[^a-zA-Z\s]', ' ', msg_lower).split()[:3]]
        has_query_structure = (
            '?' in msg or
            any(w in query_lead_tokens for w in first_few_words)
        )
        if has_query_structure:
            # Questions and action commands must specify location via preposition (e.g. "near Chennai")
            return None

        words = re.sub(r'[^a-zA-Z\s]', ' ', msg_lower).split()
        significant = [w for w in words if w not in filler and len(w) > 1]
        
        # Only treat as location if there is a clear place name and it's not a generic query sentence
        if significant and len(significant) <= 4:
            cleaned = _clean(significant)
            if cleaned:
                return cleaned
        
        return None

    def _extract_zone_id(self, msg: str) -> str | None:
        """Extract PFZ zone/sector ID if referenced in message."""
        match = re.search(r'\b(PFZ-SECTOR-\d+|EXCLUDED-\d+|ZONE-\d+|ZONE-[A-Z0-9-]+)\b', msg, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        num_match = re.search(r'\b(?:zone|sector)\s*#?\s*0*(\d+)\b', msg, re.IGNORECASE)
        if num_match:
            num = int(num_match.group(1))
            return f"PFZ-SECTOR-{num:02d}"
        return None

    async def _extract_location_3state(self, msg: str) -> dict:
        """Extract location with explicit 3-state result.
        
        Returns:
            {"state": "RESOLVED", "location": {...}}
            {"state": "MENTIONED_NOT_RESOLVED", "query": "..."}
            {"state": "NOT_MENTIONED"}
        
        This distinction is critical:
        - NOT_MENTIONED: "What about tomorrow?" → inherit context
        - MENTIONED_NOT_RESOLVED: "Patna" (geocoding failed) → ask user
        - RESOLVED: "Chennai" → use it
        NEVER silently substitute a different city.
        """
        place_name = self._extract_place_name(msg)
        if not place_name:
            return {"state": "NOT_MENTIONED"}
        
        # Try geocoding with the extracted place name
        ctx = await resolve_location_dynamic(place_name)
        if ctx:
            return {
                "state": "RESOLVED",
                "location": {
                    "name": ctx.location_name,
                    "lat": ctx.latitude,
                    "lon": ctx.longitude,
                    "bbox": ctx.bbox or [ctx.longitude - 2, ctx.latitude - 2, ctx.longitude + 2, ctx.latitude + 2],
                    "region": ctx.marine_region,
                    "environment": ctx.environment.value,
                    "fishing_type": ctx.fishing_type.value,
                    "state": ctx.state,
                    "nearest_coast_km": ctx.nearest_coast_km,
                    "clarification_needed": ctx.clarification_needed,
                    "waterbodies": [w.model_dump() for w in ctx.waterbodies],
                    "applicable_domains": ctx.applicable_domains,
                    "inapplicable_domains": ctx.inapplicable_domains,
                },
            }
        
        # Location was mentioned but geocoding failed
        logger.info(f"Location '{place_name}' was mentioned but could not be geocoded")
        return {"state": "MENTIONED_NOT_RESOLVED", "query": place_name}

    def _extract_location(self, msg: str) -> dict | None:
        """Synchronous fallback — tries hardcoded list only."""
        place_name = self._extract_place_name(msg)
        if not place_name:
            return None
        ctx = resolve_location(place_name)
        if ctx:
            return {
                "name": ctx.location_name,
                "lat": ctx.latitude,
                "lon": ctx.longitude,
                "bbox": ctx.bbox or [ctx.longitude - 2, ctx.latitude - 2, ctx.longitude + 2, ctx.latitude + 2],
                "region": ctx.marine_region,
                "environment": ctx.environment.value,
                "fishing_type": ctx.fishing_type.value,
                "state": ctx.state,
                "nearest_coast_km": ctx.nearest_coast_km,
                "clarification_needed": ctx.clarification_needed,
                "waterbodies": [w.model_dump() for w in ctx.waterbodies],
                "applicable_domains": ctx.applicable_domains,
                "inapplicable_domains": ctx.inapplicable_domains,
            }
        return None

    def _extract_time(self, msg: str) -> dict | None:
        """Extract time reference from a message."""
        msg_lower = msg.lower()

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if any(w in msg_lower for w in ["today", "right now", "currently", "now"]):
            return {"range": (now, now + timedelta(hours=24)), "preset": "today"}
        elif any(w in msg_lower for w in ["tomorrow", "tom"]):
            tomorrow = today_start + timedelta(days=1)
            return {"range": (tomorrow, tomorrow + timedelta(hours=24)), "preset": "tomorrow"}
        elif any(w in msg_lower for w in ["day after tomorrow"]):
            dat = today_start + timedelta(days=2)
            return {"range": (dat, dat + timedelta(hours=24)), "preset": "day_after_tomorrow"}
        elif any(w in msg_lower for w in ["this week", "next 7 days", "upcoming week"]):
            return {"range": (today_start, today_start + timedelta(days=7)), "preset": "this_week"}
        elif any(w in msg_lower for w in ["this month", "next 30 days"]):
            return {"range": (today_start, today_start + timedelta(days=30)), "preset": "this_month"}
        elif any(w in msg_lower for w in ["yesterday"]):
            yesterday = today_start - timedelta(days=1)
            return {"range": (yesterday, yesterday + timedelta(hours=24)), "preset": "yesterday"}
        elif any(w in msg_lower for w in ["last week"]):
            return {"range": (today_start - timedelta(days=7), today_start), "preset": "last_week"}
        elif any(w in msg_lower for w in ["morning"]):
            tomorrow = today_start + timedelta(days=1)
            return {"range": (tomorrow.replace(hour=5), tomorrow.replace(hour=12)), "preset": "tomorrow_morning"}
        elif any(w in msg_lower for w in ["evening"]):
            tomorrow = today_start + timedelta(days=1)
            return {"range": (tomorrow.replace(hour=15), tomorrow.replace(hour=21)), "preset": "tomorrow_evening"}

        return None

    def _extract_intent(self, msg: str) -> str | None:
        """Extract intent from a message."""
        msg_lower = msg.lower()

        # Safety queries
        if any(w in msg_lower for w in ["safe", "safety", "danger", "hazard", "risk", "warning"]):
            return "SAFETY_ASSESSMENT"

        # Weather & Sea-State queries
        if any(w in msg_lower for w in ["weather", "wind", "rain", "storm", "cyclone", "lightning", "sea-state", "sea state", "wave", "waves", "swell", "samudra", "forecast"]):
            return "WEATHER_QUERY"

        # Tide queries
        if any(w in msg_lower for w in ["tide", "tidal", "high tide", "low tide"]):
            return "TIDE_QUERY"

        # PFZ queries
        if any(w in msg_lower for w in ["pfz", "potential fishing zone", "fishing zone", "fishing area", "zone pfz", "pfz-sector"]):
            return "PFZ_ANALYSIS"

        # Route queries
        if any(w in msg_lower for w in ["route", "path", "navigation", "safest way"]):
            return "ROUTE_OPTIMIZATION"

        # Fishing queries
        if any(w in msg_lower for w in ["fish", "fishing", "catch", "where to"]):
            return "FISHING_LOCATION_RECOMMENDATION"

        # SST queries
        if any(w in msg_lower for w in ["sst", "temperature", "sea surface"]):
            return "MARINE_CONDITION"

        # Chlorophyll queries
        if any(w in msg_lower for w in ["chlorophyll", "productivity", "phytoplankton"]):
            return "MARINE_CONDITION"

        return None

    def _is_context_only_query(self, msg: str) -> bool:
        """Check if the query is a pure follow-up with no new location info.
        
        IMPORTANT: If a place name is extracted from the message, this is NOT
        context-only — the user is specifying a new location.
        """
        # If we extracted a place name, the user is specifying a location — NOT context-only
        place_name = self._extract_place_name(msg)
        if place_name:
            return False
        
        followup_patterns = [
            r"^what about\b",
            r"^how about\b",
            r"^and (the |for |near )?",
            r"^same (for|place|location)",
            r"^tell me more",
            r"^what else",
            r"^any other",
            r"^again\??$",
            r"^more\??$",
            r"^yes\??$",
            r"^ok\??$",
            r"^sure\??$",
        ]
        for pattern in followup_patterns:
            if re.match(pattern, msg, re.IGNORECASE):
                return True
        return False

    def _is_time_only_query(self, msg: str) -> bool:
        """Check if the message only references time (no location).
        
        Examples: "What about tomorrow?", "Tomorrow", "Next week"
        These should inherit the previous location.
        """
        # Must contain a time reference
        if not self._is_time_reference(msg):
            return False
        # Must NOT contain a location
        place_name = self._extract_place_name(msg)
        if place_name:
            return False
        return True

    def _is_location_query(self, msg: str) -> bool:
        """Check if the message is asking for a new location."""
        location_triggers = ["where", "which area", "which region", "which location", "near"]
        if any(t in msg.lower() for t in location_triggers):
            return True
        # Also detect standalone place names
        place_name = self._extract_place_name(msg)
        if place_name:
            return True
        return False

    def _is_time_reference(self, msg: str) -> bool:
        """Check if the message contains a time reference."""
        time_words = ["tomorrow", "today", "yesterday", "morning", "evening",
                      "tonight", "next week", "this week", "next month"]
        return any(w in msg.lower() for w in time_words)
