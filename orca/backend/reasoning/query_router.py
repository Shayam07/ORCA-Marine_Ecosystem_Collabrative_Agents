"""ORCA Query Router — Intent classification and task planning.

Every user query is classified into an explicit intent, and only the
relevant agents/data are selected for that intent.
"""

from __future__ import annotations

import logging
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger("orca.router")


class Intent(str, Enum):
    """Supported query intents."""
    FISHING_LOCATION_RECOMMENDATION = "FISHING_LOCATION_RECOMMENDATION"
    PFZ_ANALYSIS = "PFZ_ANALYSIS"
    SAFETY_ASSESSMENT = "SAFETY_ASSESSMENT"
    WEATHER_QUERY = "WEATHER_QUERY"
    TIDE_QUERY = "TIDE_QUERY"
    ROUTE_OPTIMIZATION = "ROUTE_OPTIMIZATION"
    ECOSYSTEM_STATUS = "ECOSYSTEM_STATUS"
    ANOMALY_DETECTION = "ANOMALY_DETECTION"
    CAUSE_ANALYSIS = "CAUSE_ANALYSIS"
    REGION_COMPARISON = "REGION_COMPARISON"
    TEMPORAL_ANALYSIS = "TEMPORAL_ANALYSIS"
    MARINE_CONDITION = "MARINE_CONDITION"
    SATELLITE_ANALYSIS = "SATELLITE_ANALYSIS"
    FISHING_ACTIVITY_ANALYSIS = "FISHING_ACTIVITY_ANALYSIS"
    POLLUTION_ANALYSIS = "POLLUTION_ANALYSIS"
    GENERAL_MARINE_QUERY = "GENERAL_MARINE_QUERY"
    GENERAL_QUERY = "GENERAL_QUERY"


class PipelineType(str, Enum):
    """Different analysis pipelines."""
    FISHING_RECOMMENDATION = "FISHING_RECOMMENDATION"
    ANOMALY = "ANOMALY"
    CAUSE = "CAUSE"
    SIMPLE_DATA = "SIMPLE_DATA"
    GENERAL = "GENERAL"


class QueryClassification(BaseModel):
    """Result of intent classification."""
    intent: Intent
    pipeline: PipelineType
    confidence: float = Field(ge=0.0, le=1.0)
    location_required: bool = True
    time_required: bool = True
    recommendation_required: bool = False
    variables_of_interest: list[str] = Field(default_factory=list)
    reasoning: str = ""


class AgentSelection(BaseModel):
    """Selected agents for a query."""
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)


class TaskPlan(BaseModel):
    """Complete plan for executing a query."""
    classification: QueryClassification
    agent_selection: AgentSelection
    data_variables: list[str] = Field(default_factory=list)
    pipeline_steps: list[str] = Field(default_factory=list)


# ── Keyword patterns for intent classification ──────────────────────────

FISHING_KEYWORDS = [
    "fish", "fishing", "catch", "trawl", "net", "boat", "vessel",
    "where to fish", "go fishing", "fishing ground", "fishing area",
    "fishing spot", "best place", "fishing location", "fishing zone",
    "suitability", "suitable", "good for fishing",
]

ANOMALY_KEYWORDS = [
    "anomal", "unusual", "abnormal", "unprecedented", "strange",
    "different from normal", "outside normal", "exceptional",
    "is this region", "experiencing", "unusual condition",
]

CAUSE_KEYWORDS = [
    "why", "cause", "reason", "explain", "led to", "resulted in",
    "what caused", "what is causing", "what led to", "how did",
    "why did", "why has", "why is", "why are",
]

COMPARISON_KEYWORDS = [
    "compare", "comparison", "versus", "vs", "difference",
    "compared to", "relative to", "against", "last month",
    "historical", "baseline", "normal",
]

TEMPORAL_KEYWORDS = [
    "trend", "over time", "temporal", "change over", "historical",
    "time series", "past", "previous", "last week", "last month",
    "over the years", "seasonal",
]

POLLUTION_KEYWORDS = [
    "pollut", "contamin", "waste", "discharge", "oil spill",
    "microplastic", "sewage", "industrial", "runoff", "turbidity",
    "sediment", "water quality",
]

SATELLITE_KEYWORDS = [
    "satellite", "remote sensing", "ocean color", "chlorophyll",
    "ndvi", "image", "observation from space",
]

PFZ_KEYWORDS = [
    "pfz", "potential fishing zone", "fishing zone", "fishing area",
    "show pfz", "where are the fishing zones", "official pfz",
    "incois pfz", "advisory", "fishing advisory",
]

SAFETY_KEYWORDS = [
    "safe", "safety", "danger", "hazard", "warning", "alert",
    "cyclone", "storm", "high wave", "rough sea", "storm surge",
    "tsunami", "swell", "marine warning", "is it safe",
    "can i go", "should i go", "risk",
]

WEATHER_KEYWORDS = [
    "weather", "wind", "rain", "forecast", "temperature today",
    "wave height", "sea state", "marine weather",
]

TIDE_KEYWORDS = [
    "tide", "tidal", "high tide", "low tide", "tide time",
]

ROUTE_KEYWORDS = [
    "route", "navigation", "course", "heading", "waypoint",
    "safest route", "best route", "how to get there",
]

SIMPLE_DATA_KEYWORDS = [
    "what is the sst", "what is the temperature", "current sst",
    "current temperature", "what is salinity", "what is the salinity",
    "current conditions", "right now", "current value",
    "what is the wind", "current wind",
]

MARINE_CONDITION_KEYWORDS = [
    "sea state", "wave height", "weather at sea",
    "marine weather", "safe to sail",
    "current conditions", "sea condition", "ocean condition",
    # Currents: a bare "currents"/"current speed" question is a marine-condition
    # query. Kept as explicit compound terms so plain English words such as
    # "currently" or "current map" are not misread as ocean-current intents.
    "currents", "ocean current", "sea current", "surface current",
    "tidal current", "current speed", "current direction",
    "how fast is the current", "current flow",
]

MARINE_DOMAIN_TERMS = [
    "ocean", "sea", "marine", "coast", "coastal", "harbour", "harbor", "port",
    "fish", "fishing", "pfz", "sst", "chlorophyll", "tide", "tidal", "wave",
    "swell", "incois", "samudra", "mosdac", "vessel", "boat", "trawl",
    "bay of bengal", "arabian sea", "upwelling", "salinity", "tsunami",
    "cyclone", "squall", "imbl", "pelagic", "mackerel", "sardine", "tuna",
    "navigation route", "waypoint", "fishing zone",
]


class IntentClassifier:
    """Classifies user queries into intents using keyword/pattern matching.
    
    This is intentionally rule-based so it is deterministic and auditable.
    An LLM-based classifier could be added as an optional enhancement.
    """

    def _is_marine_domain(self, text: str) -> bool:
        return any(term in text for term in MARINE_DOMAIN_TERMS)

    def classify(self, question: str) -> QueryClassification:
        q = question.lower().strip()
        marine = self._is_marine_domain(q)

        # Check each intent category
        scores: dict[Intent, float] = {}

        # FISHING_LOCATION_RECOMMENDATION
        fishing_score = self._keyword_score(q, FISHING_KEYWORDS)
        if fishing_score > 0 and (marine or any(w in q for w in ("fish", "fishing", "catch", "trawl", "pfz"))):
            scores[Intent.FISHING_LOCATION_RECOMMENDATION] = fishing_score

        # ANOMALY_DETECTION
        anomaly_score = self._keyword_score(q, ANOMALY_KEYWORDS)
        if anomaly_score > 0 and marine:
            scores[Intent.ANOMALY_DETECTION] = anomaly_score

        # CAUSE_ANALYSIS — only for marine questions ("why"/"explain" is too broad otherwise)
        cause_score = self._keyword_score(q, CAUSE_KEYWORDS)
        if cause_score > 0 and marine:
            scores[Intent.CAUSE_ANALYSIS] = cause_score

        # REGION_COMPARISON
        comparison_score = self._keyword_score(q, COMPARISON_KEYWORDS)
        if comparison_score > 0 and marine:
            scores[Intent.REGION_COMPARISON] = comparison_score

        # TEMPORAL_ANALYSIS
        temporal_score = self._keyword_score(q, TEMPORAL_KEYWORDS)
        if temporal_score > 0 and marine:
            scores[Intent.TEMPORAL_ANALYSIS] = temporal_score

        # POLLUTION_ANALYSIS
        pollution_score = self._keyword_score(q, POLLUTION_KEYWORDS)
        if pollution_score > 0 and marine:
            scores[Intent.POLLUTION_ANALYSIS] = pollution_score

        # SATELLITE_ANALYSIS
        satellite_score = self._keyword_score(q, SATELLITE_KEYWORDS)
        if satellite_score > 0 and marine:
            scores[Intent.SATELLITE_ANALYSIS] = satellite_score

        # SIMPLE_DATA (what is SST, etc.)
        simple_score = self._keyword_score(q, SIMPLE_DATA_KEYWORDS)
        if simple_score > 0 and marine:
            scores[Intent.MARINE_CONDITION] = simple_score

        # MARINE_CONDITION
        marine_score = self._keyword_score(q, MARINE_CONDITION_KEYWORDS)
        if marine_score > 0:
            scores[Intent.MARINE_CONDITION] = max(
                scores.get(Intent.MARINE_CONDITION, 0), marine_score
            )

        # PFZ Analysis
        pfz_score = self._keyword_score(q, PFZ_KEYWORDS)
        if pfz_score > 0:
            scores[Intent.PFZ_ANALYSIS] = pfz_score + 2.0  # Boost: very specific intent

        # Safety Assessment — "safe" alone is not enough
        safety_score = self._keyword_score(q, SAFETY_KEYWORDS)
        if safety_score > 0 and marine:
            scores[Intent.SAFETY_ASSESSMENT] = safety_score + 1.5

        # Weather Query
        weather_score = self._keyword_score(q, WEATHER_KEYWORDS)
        if weather_score > 0 and (marine or "weather" in q or "forecast" in q or "rain" in q):
            scores[Intent.WEATHER_QUERY] = weather_score

        # Tide Query
        tide_score = self._keyword_score(q, TIDE_KEYWORDS)
        if tide_score > 0:
            scores[Intent.TIDE_QUERY] = tide_score + 2.0  # Very specific

        # Route Optimization
        route_score = self._keyword_score(q, ROUTE_KEYWORDS)
        if route_score > 0:
            scores[Intent.ROUTE_OPTIMIZATION] = route_score + 1.0

        # Fishing activity analysis (distinct from location recommendation)
        if Intent.FISHING_LOCATION_RECOMMENDATION not in scores:
            fishing_activity_kw = ["fishing activity", "fishing effort", "vessel activity",
                                    "how much fishing", "fishing pressure"]
            fa_score = self._keyword_score(q, fishing_activity_kw)
            if fa_score > 0:
                scores[Intent.FISHING_ACTIVITY_ANALYSIS] = fa_score

        # Determine winning intent
        if not scores:
            if marine:
                return QueryClassification(
                    intent=Intent.GENERAL_MARINE_QUERY,
                    pipeline=PipelineType.GENERAL,
                    confidence=0.5,
                    location_required=True,
                    reasoning="Marine topic without a specific pipeline",
                )
            return QueryClassification(
                intent=Intent.GENERAL_QUERY,
                pipeline=PipelineType.GENERAL,
                confidence=0.9,
                location_required=False,
                time_required=False,
                reasoning="General question — route to LLM, do not reuse previous marine intent",
            )

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Map intent to pipeline
        pipeline = self._intent_to_pipeline(best_intent)

        # Extract variables of interest
        variables = self._extract_variables(q, best_intent)

        classification = QueryClassification(
            intent=best_intent,
            pipeline=pipeline,
            confidence=min(1.0, best_score),
            location_required=True,
            time_required=True,
            recommendation_required=(best_intent == Intent.FISHING_LOCATION_RECOMMENDATION),
            variables_of_interest=variables,
            reasoning=f"Matched intent {best_intent.value} with score {best_score:.2f}",
        )

        logger.info(f"Intent classified: {best_intent.value} (score={best_score:.2f}, pipeline={pipeline.value})")
        return classification

    def _keyword_score(self, text: str, keywords: list[str]) -> float:
        """Score text against keyword list."""
        score = 0.0
        for kw in keywords:
            if kw in text:
                # Longer keyword matches are more specific
                weight = 1.0 + (len(kw.split()) - 1) * 0.5
                score += weight
        return score

    def _intent_to_pipeline(self, intent: Intent) -> PipelineType:
        """Map intent to analysis pipeline."""
        mapping = {
            Intent.FISHING_LOCATION_RECOMMENDATION: PipelineType.FISHING_RECOMMENDATION,
            Intent.FISHING_ACTIVITY_ANALYSIS: PipelineType.FISHING_RECOMMENDATION,
            Intent.PFZ_ANALYSIS: PipelineType.FISHING_RECOMMENDATION,
            Intent.SAFETY_ASSESSMENT: PipelineType.SIMPLE_DATA,
            Intent.WEATHER_QUERY: PipelineType.SIMPLE_DATA,
            Intent.TIDE_QUERY: PipelineType.SIMPLE_DATA,
            Intent.ROUTE_OPTIMIZATION: PipelineType.GENERAL,
            Intent.ANOMALY_DETECTION: PipelineType.ANOMALY,
            Intent.ECOSYSTEM_STATUS: PipelineType.ANOMALY,
            Intent.CAUSE_ANALYSIS: PipelineType.CAUSE,
            Intent.REGION_COMPARISON: PipelineType.CAUSE,
            Intent.TEMPORAL_ANALYSIS: PipelineType.CAUSE,
            Intent.MARINE_CONDITION: PipelineType.SIMPLE_DATA,
            Intent.SATELLITE_ANALYSIS: PipelineType.SIMPLE_DATA,
            Intent.POLLUTION_ANALYSIS: PipelineType.CAUSE,
            Intent.GENERAL_MARINE_QUERY: PipelineType.GENERAL,
            Intent.GENERAL_QUERY: PipelineType.GENERAL,
        }
        return mapping.get(intent, PipelineType.GENERAL)

    def _extract_variables(self, question: str, intent: Intent) -> list[str]:
        """Extract variables of interest from the question."""
        q = question.lower()
        variables = []

        var_keywords = {
            "sst": "sea_surface_temperature",
            "temperature": "sea_surface_temperature",
            "sea surface temperature": "sea_surface_temperature",
            "chlorophyll": "chlorophyll_concentration",
            "chl": "chlorophyll_concentration",
            "productivity": "chlorophyll_concentration",
            "salinity": "salinity",
            "current": "sea_surface_current_u",
            "wind": "wind_speed",
            "wave": "wave_height",
            "fishing": "fishing_activity",
            "fishing activity": "fishing_activity",
            "fishing effort": "fishing_activity",
        }

        for keyword, variable in var_keywords.items():
            if keyword in q and variable not in variables:
                variables.append(variable)

        # Add default variables based on intent
        if intent == Intent.FISHING_LOCATION_RECOMMENDATION:
            defaults = ["sea_surface_temperature", "chlorophyll_concentration", "wind_speed"]
            for v in defaults:
                if v not in variables:
                    variables.append(v)
        elif intent == Intent.ANOMALY_DETECTION:
            defaults = ["sea_surface_temperature", "chlorophyll_concentration", "salinity"]
            for v in defaults:
                if v not in variables:
                    variables.append(v)
        elif intent == Intent.CAUSE_ANALYSIS:
            defaults = ["sea_surface_temperature", "chlorophyll_concentration"]
            for v in defaults:
                if v not in variables:
                    variables.append(v)

        return variables


class TaskPlanner:
    """Selects agents and plans pipeline steps based on intent."""

    # ── Agent selection matrix ──────────────────────────────────────

    AGENT_MATRIX: dict[Intent, AgentSelection] = {
        Intent.FISHING_LOCATION_RECOMMENDATION: AgentSelection(
            required=["fisheries", "ocean", "satellite", "weather"],
            optional=["biology"],
            excluded=["literature", "pollution"],
        ),
        Intent.PFZ_ANALYSIS: AgentSelection(
            required=["ocean", "satellite"],
            optional=["weather", "fisheries"],
            excluded=["literature", "pollution", "biology"],
        ),
        Intent.SAFETY_ASSESSMENT: AgentSelection(
            required=["weather", "ocean"],
            optional=["safety"],
            excluded=["literature", "pollution", "fisheries"],
        ),
        Intent.WEATHER_QUERY: AgentSelection(
            required=["weather"],
            optional=["ocean"],
            excluded=["literature", "pollution", "fisheries", "biology"],
        ),
        Intent.TIDE_QUERY: AgentSelection(
            required=["tide"],
            optional=["ocean"],
            excluded=["literature", "pollution", "fisheries", "biology"],
        ),
        Intent.ROUTE_OPTIMIZATION: AgentSelection(
            required=["route", "weather", "ocean"],
            optional=[],
            excluded=["literature", "pollution", "biology"],
        ),
        Intent.FISHING_ACTIVITY_ANALYSIS: AgentSelection(
            required=["fisheries", "ocean", "satellite"],
            optional=[],
            excluded=["literature", "pollution"],
        ),
        Intent.ECOSYSTEM_STATUS: AgentSelection(
            required=["ocean", "satellite", "biology"],
            optional=["weather", "pollution"],
            excluded=[],
        ),
        Intent.ANOMALY_DETECTION: AgentSelection(
            required=["ocean", "satellite"],
            optional=["biology", "weather"],
            excluded=[],
        ),
        Intent.CAUSE_ANALYSIS: AgentSelection(
            required=["ocean", "satellite", "biology", "weather"],
            optional=["pollution", "fisheries", "literature"],
            excluded=[],
        ),
        Intent.REGION_COMPARISON: AgentSelection(
            required=["ocean", "satellite"],
            optional=["biology", "weather"],
            excluded=[],
        ),
        Intent.TEMPORAL_ANALYSIS: AgentSelection(
            required=["ocean", "satellite"],
            optional=["biology", "weather"],
            excluded=[],
        ),
        Intent.MARINE_CONDITION: AgentSelection(
            required=["ocean", "weather", "satellite"],
            optional=[],
            excluded=["literature", "pollution", "fisheries"],
        ),
        Intent.SATELLITE_ANALYSIS: AgentSelection(
            required=["satellite"],
            optional=["ocean"],
            excluded=["literature", "pollution", "fisheries", "weather"],
        ),
        Intent.POLLUTION_ANALYSIS: AgentSelection(
            required=["pollution", "ocean", "satellite"],
            optional=["biology", "weather"],
            excluded=[],
        ),
        Intent.GENERAL_MARINE_QUERY: AgentSelection(
            required=["ocean", "satellite"],
            optional=["weather", "biology"],
            excluded=[],
        ),
        Intent.GENERAL_QUERY: AgentSelection(
            required=[],
            optional=[],
            excluded=["literature", "pollution", "fisheries", "biology", "ocean", "satellite", "weather"],
        ),
    }

    # ── Pipeline steps per pipeline type ────────────────────────────

    PIPELINE_STEPS: dict[PipelineType, list[str]] = {
        PipelineType.FISHING_RECOMMENDATION: [
            "parse_query",
            "generate_candidate_regions",
            "retrieve_ocean_data",
            "retrieve_satellite_data",
            "retrieve_weather_data",
            "retrieve_fishing_data",
            "calculate_suitability",
            "rank_locations",
            "build_recommendation",
        ],
        PipelineType.ANOMALY: [
            "parse_query",
            "retrieve_baseline_data",
            "retrieve_current_data",
            "detect_anomalies",
            "calculate_severity",
            "build_explanation",
        ],
        PipelineType.CAUSE: [
            "parse_query",
            "retrieve_all_evidence",
            "fuse_evidence",
            "temporal_reasoning",
            "spatial_reasoning",
            "generate_hypotheses",
            "calculate_confidence",
            "build_explanation",
        ],
        PipelineType.SIMPLE_DATA: [
            "parse_query",
            "retrieve_data",
            "format_response",
        ],
        PipelineType.GENERAL: [
            "parse_query",
            "retrieve_data",
            "analyze_data",
            "build_explanation",
        ],
    }

    def plan(self, classification: QueryClassification) -> TaskPlan:
        """Create a task plan from classification."""
        agent_selection = self.AGENT_MATRIX.get(
            classification.intent,
            self.AGENT_MATRIX[Intent.GENERAL_MARINE_QUERY],
        )

        pipeline_steps = self.PIPELINE_STEPS.get(
            classification.pipeline,
            self.PIPELINE_STEPS[PipelineType.GENERAL],
        )

        return TaskPlan(
            classification=classification,
            agent_selection=agent_selection,
            data_variables=classification.variables_of_interest,
            pipeline_steps=pipeline_steps,
        )


class QueryRouter:
    """Top-level query router combining classification and planning."""

    def __init__(self):
        self.classifier = IntentClassifier()
        self.planner = TaskPlanner()

    def route(self, question: str) -> TaskPlan:
        """Route a user question to the appropriate pipeline."""
        classification = self.classifier.classify(question)
        plan = self.planner.plan(classification)

        logger.info(
            f"Query routed: intent={classification.intent.value}, "
            f"pipeline={classification.pipeline.value}, "
            f"agents_required={plan.agent_selection.required}, "
            f"agents_excluded={plan.agent_selection.excluded}"
        )

        return plan
