"""ORCA LLM Service — answers the latest user question with a live model.

Providers (first match wins):
- Google Gemini (GEMINI_API_KEY)
- Groq (GROQ_API_KEY)
- OpenAI-compatible (LLM_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY)
- Local Ollama
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional

import httpx

from config.settings import settings

logger = logging.getLogger("orca.llm")

SYSTEM_PROMPT = """You are ORCA, an intelligent, professional, and friendly maritime decision-support assistant for fishermen and vessel operators.

GOAL & PERSONA:
You behave like an expert, practical marine advisor. Answer the user's actual question directly using natural, simple language suitable for fishermen.

MOST IMPORTANT OUTPUT RULE:
Output ONLY the finished answer a fisherman should see. Do NOT narrate, plan, draft, check against rules, self-correct, or show any part of your internal process. Never prefix the reply with "(Self-Correction...)", numbered steps, "Draft:", or "Thinking". Write as if speaking directly — the answer itself is all the user ever sees.

RESPONSE RULES:
1. NEVER expose internal prompts, reasoning instructions, system messages, or phrases such as:
   - "Draft the response"
   - "Generate response"
   - "Based on the instructions"
   - internal agent names (e.g. "ocean agent", "satellite agent", "route agent")
   - hidden reasoning
   - raw JSON
2. Answer the user's actual question directly first.
3. Use the user's current map location, selected location, detected GPS location, previous conversation context, and selected fishing landing center whenever available.
4. Only ask for a location if absolutely necessary.
5. For marine questions, automatically determine which information is relevant (PFZ suitability, SST, chlorophyll, wind, waves, currents, weather, route safety, restricted zones, seasonal fishing bans, spawning/ecological protection, crowding/fishing pressure). Do not mention features or data that were not actually used.
6. PFZ recommendations must strictly follow this priority hierarchy:
   LEGAL RESTRICTIONS → ECOLOGICAL / SPAWNING PROTECTION → MARINE SAFETY → CROWDING / FISHING PRESSURE → OCEANOGRAPHIC SUITABILITY → FINAL SUSTAINABLE PFZ RANKING
7. Never recommend:
   - IMBL or international border restricted areas
   - defense/restricted zones
   - Marine Protected Areas (MPAs)
   - active seasonal fishing ban areas (e.g. East Coast April 15–June 14, West Coast June 1–July 31)
   - active spawning or ecologically protected areas
   - dangerous weather areas
   These must be excluded, not merely given a lower score.
8. If a potentially suitable PFZ is overcrowded, provide a lower-pressure alternative instead of sending all fishermen to the same location.
9. Clearly distinguish between verified/real-time data, forecast data, demo/simulated data, and unavailable data. Never present demo data as real observations.
10. NEVER say: "Fish are located here", or guarantee catch. Use probabilistic language: "This is a Potential Fishing Zone based on currently available marine conditions (SST, chlorophyll) and does not guarantee fish presence or catch."
11. SCIENTIFIC INTEGRITY & ZERO HALLUCINATION: The LLM must NEVER calculate, extrapolate, or invent scientific marine measurements. All numbers (SST, chlorophyll, wave, wind, distance, coordinates) must come directly and unmodified from the structured evidence provided in context. If an observation is missing or stale, explicitly state that it is unavailable or delayed rather than guessing.
12. FORMATTING RULES:
   - NEVER display ** symbols anywhere. Do not use double asterisks for bolding. Use clean plain text and standard bullets (•).
   - Never display unfinished template placeholders or raw code blocks for numbers.
   - Use clean, short bullet points.
   - Keep answers concise and avoid long, repetitive technical disclaimers.

PREFERRED STRUCTURE:
Direct Answer
Key Conditions
Recommendation / Alternative
Safety Note
(Adapt naturally to the question; do not force unnecessary sections).

CONVERSATION EXAMPLES:
USER: Where can I fish today?
ORCA:
Based on your current location and available marine conditions, I found a potentially suitable fishing area approximately 15 km offshore.

• Conditions: SST is suitable and chlorophyll levels are favorable.
• Safety: Wind and wave conditions are currently within the configured safe range.
• Fishing pressure: Moderate.
• Alternative: A lower-pressure zone is available further south.

This is a potential fishing recommendation based on available marine conditions and does not guarantee catch.

USER: Is it safe to go fishing tomorrow?
ORCA:
Tomorrow currently looks moderately safe for fishing in your selected area. Wind is expected to remain manageable, but wave conditions may increase later in the day.

• Departure window: Morning recommended.
• Wind: 10–12 m/s.
• Waves: 1.2–1.8 m swell.

Avoid the marked hazard zones on the map. Check again before departure because marine forecasts can change.

USER: Give me the nearest PFZ.
ORCA:
The nearest sustainable PFZ is approximately 12 km from your selected landing center.

• Suitability: High
• Crowding: Low
• Safety: Safe under current forecast conditions

I have highlighted it on the map.

USER: Can I cross this border?
ORCA:
No. The selected area is within or approaching a restricted maritime boundary. ORCA will not recommend routes or fishing zones that cross restricted or international maritime boundaries.

I can show you a safe alternative route.

LANGUAGE:
If the user writes in Tamil, Telugu, Hindi, Malayalam, or another Indian language, answer directly in that language using simple local-language wording."""


MARINE_INTENTS = {
    "FISHING_LOCATION_RECOMMENDATION",
    "PFZ_ANALYSIS",
    "SAFETY_ASSESSMENT",
    "WEATHER_QUERY",
    "MARINE_CONDITION",
    "TIDE_QUERY",
    "ROUTE_OPTIMIZATION",
    "NAVIGATION_QUERY",
    "ANOMALY_DETECTION",
    "CAUSE_ANALYSIS",
    "ECOSYSTEM_STATUS",
    "POLLUTION_ANALYSIS",
    "FISHING_ACTIVITY_ANALYSIS",
    "GENERAL_MARINE_QUERY",
    "SATELLITE_ANALYSIS",
}


class LLMService:
    """Multi-provider LLM with query-first prompting."""

    def __init__(self):
        self._client = None
        self._provider = "none"
        self._model = settings.LLM_MODEL
        self._api_key: Optional[str] = None
        self._base_url: Optional[str] = None
        self._initialized = False

    def _get_client(self):
        """Initialize provider credentials (OpenAI SDK used only for OpenAI-compatible APIs)."""
        if self._initialized:
            return self._client

        self._initialized = True

        gemini_key = (
            os.environ.get("GEMINI_API_KEY")
            or getattr(settings, "GEMINI_API_KEY", None)
            or (settings.LLM_API_KEY if settings.LLM_MODEL.lower().startswith("gemini") else None)
        )
        groq_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
        api_key = (
            settings.LLM_API_KEY
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or groq_key
        )
        base_url = settings.LLM_BASE_URL or os.environ.get("LLM_BASE_URL")

        if gemini_key and not base_url:
            self._provider = "gemini"
            self._api_key = gemini_key
            self._model = settings.LLM_MODEL if "gemini" in settings.LLM_MODEL.lower() else "gemini-3.6-flash"
            logger.info("LLM provider: Gemini (%s)", self._model)
            return None

        if groq_key and not base_url:
            self._provider = "groq"
            self._api_key = groq_key
            self._base_url = "https://api.groq.com/openai/v1"
            self._model = (
                settings.LLM_MODEL
                if settings.LLM_MODEL and not settings.LLM_MODEL.startswith("gpt-")
                else "qwen/qwen3.6-27b"
            )
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=groq_key, base_url=self._base_url)
                logger.info("LLM provider: Groq (%s)", self._model)
                return self._client
            except ImportError:
                logger.info("LLM provider: Groq via HTTP (%s)", self._model)
                return None

        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        if not api_key:
            try:
                tags_url = ollama_url.replace("/v1", "") + "/api/tags"
                with httpx.Client(timeout=0.8) as client:
                    response = client.get(tags_url, headers={"User-Agent": "ORCA"})
                if response.status_code == 200:
                    from openai import OpenAI
                    self._client = OpenAI(base_url=ollama_url, api_key="ollama")
                    self._provider = "ollama"
                    self._model = os.environ.get("OLLAMA_MODEL", "llama3")
                    logger.info("LLM provider: Ollama (%s)", self._model)
                    return self._client
            except Exception:
                pass
            logger.warning("No LLM API key found (set GEMINI_API_KEY or GROQ_API_KEY). Chat will not use a live model.")
            return None

        try:
            from openai import OpenAI

            client_kwargs = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            elif os.environ.get("OPENROUTER_API_KEY") and api_key == os.environ.get("OPENROUTER_API_KEY"):
                client_kwargs["base_url"] = "https://openrouter.ai/api/v1"

            self._client = OpenAI(**client_kwargs)
            self._provider = "openai_compatible"
            self._api_key = api_key
            self._base_url = client_kwargs.get("base_url")
            logger.info("LLM service initialized with model: %s", self._model)
            return self._client
        except ImportError:
            logger.warning("openai package not installed.")
            self._api_key = api_key
            self._base_url = base_url
            self._provider = "http"
            return None
        except Exception as e:
            logger.error("Failed to initialize LLM client: %s", e)
            return None

    def is_available(self) -> bool:
        self._get_client()
        return self._provider not in ("none", "fallback")

    async def generate_chat_response(
        self,
        query: str,
        chat_history: List[Dict[str, str]],
        location_info: Dict[str, Any],
        agent_results: List[Dict[str, Any]],
        all_observations: List[Any],
        intent: str,
        lang: str = "en",
        pfz_zones: Optional[List[Dict[str, Any]]] = None,
        route_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Answer the current query. Marine evidence is used only when relevant."""
        self._get_client()
        marine_question = any(x in intent for x in MARINE_INTENTS)

        evidence_summary = ""
        if marine_question:
            evidence_summary = self._build_context_evidence(
                query=query,
                location_info=location_info,
                agent_results=agent_results,
                all_observations=all_observations,
                intent=intent,
                pfz_zones=pfz_zones,
                route_info=route_info,
            )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in chat_history[-6:]:
            r = h.get("role", "user")
            c = (h.get("content") or "").strip()
            if c:
                messages.append({"role": r if r in ("user", "assistant") else "user", "content": c})

        if marine_question and evidence_summary:
            user_content = (
                f"{evidence_summary}\n\n"
                f"=== LATEST USER QUESTION (answer this, not earlier messages) ===\n{query}"
            )
        else:
            user_content = (
                "Answer the latest user question below. Do not continue a previous marine topic "
                "unless this question is clearly a follow-up.\n\n"
                f"Latest question: {query}"
            )
        messages.append({"role": "user", "content": user_content})

        answer = await self._complete(messages)
        if answer and len(answer.strip()) > 1:
            cleaned = self._clean_llm_output(answer)
            if cleaned:
                return cleaned

        return self._generate_intelligent_synthesis(
            query=query,
            location_info=location_info,
            agent_results=agent_results,
            all_observations=all_observations,
            intent=intent,
            lang=lang,
            pfz_zones=pfz_zones,
            route_info=route_info,
        )

    @staticmethod
    def _clean_llm_output(text: str) -> str:
        """Strip internal reasoning tags, instructions, chain-of-thought scratchpads, and raw markdown artifacts."""
        import re
        if not text:
            return ""

        cleaned = text

        # Strip closed think/thought blocks
        cleaned = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"<thought>.*?</thought>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"```thinking.*?```", "", cleaned, flags=re.DOTALL | re.IGNORECASE)

        # Handle unclosed leading think tag
        if "<think" in cleaned.lower() and "</think" not in cleaned.lower():
            parts = cleaned.split("\n\n")
            if len(parts) > 1:
                cleaned = "\n\n".join(parts[1:])
            else:
                cleaned = re.sub(r"<think.*?>", "", cleaned, flags=re.IGNORECASE)

        # ── Visible-reasoning transcripts (e.g. Qwen3 "thinking out loud") ──────────
        # 1) Drop a leading "*(Self-Correction/Refinement during drafting)*: <meta>" line.
        cleaned = re.sub(
            r"^\s*\*?\(?(?:self[- ]correction|refinement)[^)\n]*\)?\*?:[^\n]*\n*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        # 2) If numbered "N. Draft ... :" sections (or a standalone "Draft:") appear,
        #    keep only the LAST draft body, cut at the next reasoning/check section.
        draft_starts = [
            m.end()
            for m in re.finditer(
                r"(?im)^\s*\d+\.\s+draft(?: construction| response)?(?: \([^)]*\))?:\s*$",
                cleaned,
            )
        ]
        draft_starts += [m.end() for m in re.finditer(r"(?im)^\s*draft:\s*$", cleaned)]
        if draft_starts:
            rest = cleaned[max(draft_starts):]
            reasoning_cut = re.search(
                r"(?im)^\s*(?:\d+\.\s+)?"
                r"(?:check|refin|verify|apply|re-?evaluat|confirm|review|one minor|all constraints)[^\n]*:\s*$"
                r"|^\s*[-•]\s*(?:direct answer|no internal|uses location|only asks"
                r"|pfz hierarchy|excluded|probabilistic|scientific|formatting\?|structure matches"
                r"|concise\?|language\?|check rule|rule \d+)"
                r"|^\s*(?:one minor|all (?:good|constraints|set)|this matches all|matches all constraints"
                r"|let's (?:verify|draft|check)|output (?:matches|generation)|proceed|ready\.?"
                r"|\[self-correction|\[final check|i will generate|note: i'll|the draft looks solid)",
                rest,
            )
            if reasoning_cut:
                rest = rest[: reasoning_cut.start()]
            cleaned = rest

        # Extract actual response when preceded by scratchpad or dividers
        divider_match = list(re.finditer(
            r"(?:(?:^|\n)\s*(?:refined:?|draft structure:?|draft(?:ing)? (?:the )?response:?|final response:?|here(?:\'s| is) (?:the )?response:?|\[output generation\][^\n]*)\s*\n+)",
            cleaned,
            flags=re.IGNORECASE
        ))
        if divider_match:
            cleaned = cleaned[divider_match[-1].end():]

        # If the response was enclosed in quotes followed by self-correction or completion notes
        quote_match = re.search(r'^\s*["“](.+?)["”]\s*(?:->|\*|\[|matches|$)', cleaned, flags=re.DOTALL)
        if quote_match:
            cleaned = quote_match.group(1)

        # Strip trailing self-correction or completion thought notes
        cleaned = re.split(r"(?i)\n\s*(?:checks:|\*?checks against|ready\.?✅|\*?self-correction|\*?note during thought|matches all constraints|\[done\]|\[final check)", cleaned)[0]

        # If text still starts with "1.  Analyze the Request:" or numbered thinking steps
        if re.match(r"^\s*1\.\s+(?:analyze|check|read|understand)\b", cleaned, re.IGNORECASE):
            parts = cleaned.split("\n\n")
            for i in range(len(parts)-1, -1, -1):
                p = parts[i].strip()
                if not re.match(r"^(?:\d+\.|\*|-|\[)", p) and len(p) > 20:
                    cleaned = "\n\n".join(parts[i:])
                    break

        # Remove leading thinking preambles and instructions
        bad_lead_patterns = [
            r"^(?:here'?s (?:a )?thinking process:?|1\.\s+\*\*analyze (?:user )?input:?\*\*|### thinking process|thinking process:?)",
            r"^(?:draft(?:ing)? (?:the )?response:?|generate response:?|generating response:?|based on the instructions:?|here(?:'s| is) (?:a )?draft:?|internal reasoning:?|scratchpad:?|plan:?|system message:?)",
            r"^(?:response:?|orca:?|assistant:?)\s*",
        ]
        for pat in bad_lead_patterns:
            cleaned = re.sub(pat, "", cleaned.strip(), flags=re.IGNORECASE).strip()

        # Remove any inline 'based on the instructions' remnants
        cleaned = re.sub(r"(?i)\bbased on the instructions,?\s*", "", cleaned).strip()

        # Remove raw ** markdown symbols completely (turns **word** into word)
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
        cleaned = cleaned.replace("**", "")

        # Remove code backticks around numbers/measurements (e.g. `28.4°C` -> 28.4°C)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

        # Clean stray template placeholders like {location}
        cleaned = re.sub(r"\{[a-zA-Z_]+\}", "", cleaned)

        # Strip surrounding quotes if wrapped
        cleaned = cleaned.strip().strip('"').strip("'")

        # Normalize multiple consecutive blank lines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

        return cleaned.strip()

    async def _complete(self, messages: List[Dict[str, str]]) -> Optional[str]:
        self._get_client()
        try:
            if self._provider == "gemini" and self._api_key:
                return await asyncio.wait_for(self._complete_gemini(messages), timeout=6.0)
            if self._client:
                request_kwargs = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 800 if self._provider == "groq" else 2000,
                }
                if self._provider == "groq":
                    request_kwargs["extra_body"] = {"reasoning_effort": "none"}
                response = await asyncio.wait_for(
                    asyncio.to_thread(self._client.chat.completions.create, **request_kwargs),
                    timeout=6.0,
                )
                raw = (response.choices[0].message.content or "").strip()
                return self._clean_llm_output(raw)
            if self._api_key and (self._base_url or self._provider in ("groq", "http", "openai_compatible")):
                return await asyncio.wait_for(self._complete_openai_http(messages), timeout=6.0)
        except Exception as e:
            logger.warning("Live LLM completion failed or timed out (%s)", e)
            if self._provider == "gemini":
                try:
                    return await asyncio.wait_for(
                        self._complete_gemini(messages, model_override="gemini-3.6-flash"),
                        timeout=5.0,
                    )
                except Exception as e2:
                    logger.warning("Gemini fallback model failed (%s)", e2)
        return None

    async def _complete_gemini(self, messages: List[Dict[str, str]], model_override: Optional[str] = None) -> Optional[str]:
        model = model_override or self._model
        system_text = ""
        contents: List[Dict[str, Any]] = []
        for m in messages:
            if m["role"] == "system":
                system_text += m["content"] + "\n"
                continue
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2000},
        }
        if system_text.strip():
            payload["systemInstruction"] = {"parts": [{"text": system_text.strip()}]}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(url, params={"key": self._api_key}, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        cleaned = self._clean_llm_output(text)
        return cleaned or None

    async def _complete_openai_http(self, messages: List[Dict[str, str]]) -> Optional[str]:
        base = (self._base_url or "https://api.openai.com/v1").rstrip("/")
        url = f"{base}/chat/completions"
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1200,
                    **({"reasoning_effort": "none"} if self._provider == "groq" else {}),
                },
            )
            response.raise_for_status()
            data = response.json()
        raw = (data["choices"][0]["message"]["content"] or "").strip()
        return self._clean_llm_output(raw)

    def _build_context_evidence(
        self,
        query: str,
        location_info: Dict[str, Any],
        agent_results: List[Dict[str, Any]],
        all_observations: List[Any],
        intent: str,
        pfz_zones: Optional[List[Dict[str, Any]]],
        route_info: Optional[Dict[str, Any]],
    ) -> str:
        loc_name = location_info.get("name", "Unknown coastal coordinates")
        lat = location_info.get("lat")
        lon = location_info.get("lon")
        env = location_info.get("environment", "COASTAL")

        lines = [
            "=== OPTIONAL MARINE CONTEXT (use only if the latest question is marine) ===",
            f"Location: {loc_name} (Coordinates: {lat}, {lon}) | Environment: {env}",
            f"Intent Classification: {intent}",
            "",
        ]

        if agent_results:
            lines.append("Observed Conditions & Marine Telemetry:")
            for r in agent_results:
                findings = r.get("findings", [])
                hypotheses = r.get("hypotheses", [])
                for f in findings:
                    desc = f if isinstance(f, str) else f.get("description", str(f))
                    lines.append(f"• {desc}")
                for h in hypotheses:
                    hdesc = h if isinstance(h, str) else h.get("description", h.get("title", str(h)))
                    lines.append(f"• Condition Note: {hdesc}")

        if pfz_zones:
            real_zones = [z for z in pfz_zones if str(z.get("data_mode", "")).upper() not in ("DEMO", "SIMULATED")]
            provenance = "real-data" if real_zones else "fallback/simulated (no live data)"
            lines.append(f"\nPotential Fishing Zones Detected: {len(pfz_zones)} ({provenance})")
            target_match = re.search(r'\b(PFZ-SECTOR-\d+|EXCLUDED-\d+|ZONE-\d+|[A-Z0-9]+-[A-Z0-9]+)\b', query, re.IGNORECASE)
            target_qid = target_match.group(1).upper() if target_match else None
            displayed_zones = list(pfz_zones[:4])
            if target_qid:
                for z in pfz_zones:
                    if z.get("zone_id", "").upper() == target_qid and z not in displayed_zones:
                        displayed_zones.insert(0, z)
                        break
            for z in displayed_zones:
                demo = " [SIMULATED — NOT live observations]" if str(z.get("data_mode", "")).upper() in ("DEMO", "SIMULATED") else ""
                dist = z.get("distance_km")
                dist_t = f"{dist} km" if isinstance(dist, (int, float)) else "distance unknown"
                lines.append(
                    f"• {z.get('zone_id')}: Classification={z.get('classification')}, "
                    f"SST={z.get('avg_sst')}°C, Chl={z.get('avg_chlorophyll')} mg/m³, "
                    f"Distance={dist_t}, Crowding={z.get('crowding_level', 'LOW')}. Reasoning: {z.get('reasoning')}{demo}"
                )

        if route_info:
            lines.append("\nOptimized Navigation Route:")
            lines.append(
                f"• Distance: {route_info.get('distance_km')} km | ETA: {route_info.get('eta_hours')} hrs | "
                f"Fuel Savings: ~{route_info.get('fuel_saved_percent', 18)}% | Wave Hazard Max: {route_info.get('max_wave_height_m', 1.6)}m"
            )

        return "\n".join(lines)

    def _generate_intelligent_synthesis(
        self,
        query: str,
        location_info: Dict[str, Any],
        agent_results: List[Dict[str, Any]],
        all_observations: List[Any],
        intent: str,
        lang: str,
        pfz_zones: Optional[List[Dict[str, Any]]],
        route_info: Optional[Dict[str, Any]],
    ) -> str:
        """Deterministic intelligent synthesis following fisherman-first conversational style."""
        q_lower = query.lower().strip()
        loc_name = location_info.get("name")
        env = location_info.get("environment", "COASTAL")

        if not loc_name or loc_name.lower() in ("unspecified", "unknown"):
            return (
                "Which coastal area or landing center would you like to check? "
                "You can enter a coastal harbor (such as Chennai, Kochi, Visakhapatnam, or Mumbai), "
                "or select a point directly on the map."
            )

        if env == "INLAND":
            from conversation.location import find_nearest_coastal_harbor
            lat = location_info.get("lat") or 13.08
            lon = location_info.get("lon") or 80.27
            nearest_h = find_nearest_coastal_harbor(lat, lon)
            nearest_km = int(nearest_h.get("distance_km") or 50)
            harbor_name = nearest_h.get("name", "Chennai Fishing Harbour")
            return (
                f"{loc_name} is inland ({nearest_km} km from the coast). "
                "Marine route planning and PFZ analysis require a coastal departure point.\n\n"
                f"Nearest harbor detected: {harbor_name} ({nearest_km} km away).\n\n"
                f"Would you like to plot the optimal fishing route departing from {harbor_name}?"
            )

        # ── 1. Border / IMBL Restriction Query ──
        if any(w in q_lower for w in ["border", "cross", "imbl", "sri lanka", "pakistan", "boundary"]):
            return (
                "No. The selected area is within or approaching a restricted maritime boundary. "
                "ORCA will not recommend routes or fishing zones that cross restricted or international maritime boundaries.\n\n"
                "I can show you a safe alternative route inside permitted Indian waters."
            )

        # Real values only — never invent a measurement when a metric is missing.
        sst_vals = [o.value for o in all_observations if hasattr(o, "variable") and o.variable in ("sea_surface_temperature", "sst")]
        chl_vals = [o.value for o in all_observations if hasattr(o, "variable") and "chlorophyll" in getattr(o, "variable", "")]
        wind_vals = [o.value for o in all_observations if hasattr(o, "variable") and o.variable in ("wind_speed",)]
        wind_dir_vals = [o.value for o in all_observations if hasattr(o, "variable") and o.variable in ("wind_direction",)]
        wave_vals = [o.value for o in all_observations if hasattr(o, "variable") and o.variable in ("wave_height",)]
        cur_vals = [o.value for o in all_observations if hasattr(o, "variable") and o.variable in ("ocean_current_velocity",)]
        cur_dir_vals = [o.value for o in all_observations if hasattr(o, "variable") and o.variable in ("ocean_current_direction",)]

        import statistics as _stats

        def _mean(vals: list) -> float | None:
            return _stats.mean(vals) if vals else None

        avg_sst = _mean(sst_vals)
        avg_chl = _mean(chl_vals)
        max_wind = _mean(wind_vals)
        avg_wind_dir = _mean(wind_dir_vals)
        avg_wave = _mean(wave_vals)
        avg_cur = _mean(cur_vals)
        avg_cur_dir = _mean(cur_dir_vals)
        is_safe = bool(
            max_wind is not None and avg_wave is not None
            and max_wind < 15.0 and avg_wave < 2.2
        )

        def _compass(deg: float) -> str:
            dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            return dirs[int(((deg % 360) + 11.25) // 22.5) % 16]

        # Bullets built ONLY from available observations (SST, chl, wind, waves, currents)
        marine_lines = []
        if avg_sst is not None:
            marine_lines.append(f"Sea surface temperature: {avg_sst:.1f}°C")
        if avg_chl is not None:
            marine_lines.append(f"Chlorophyll concentration: {avg_chl:.2f} mg/m³")
        if max_wind is not None:
            wd = f" from {_compass(avg_wind_dir)}" if avg_wind_dir is not None else ""
            marine_lines.append(f"Surface wind speed: {max_wind:.1f} m/s{wd}")
        if avg_wave is not None:
            marine_lines.append(f"Significant wave height: {avg_wave:.1f} m")
        if avg_cur is not None:
            cd = f" flowing toward {_compass(avg_cur_dir)}" if avg_cur_dir is not None else ""
            marine_lines.append(f"Ocean surface current: {avg_cur:.2f} m/s{cd}")
        if not marine_lines:
            marine_lines.append("Live marine data for this area and time window is currently unavailable.")

        # ── Regional Language Direct Responses (fishing/PFZ only, real data only) ──
        _regional_ok = (
            intent in ("PFZ_ANALYSIS", "FISHING_LOCATION_RECOMMENDATION")
            and avg_sst is not None and avg_chl is not None
            and max_wind is not None and avg_wave is not None
        )
        if lang == "ta" and _regional_ok:
            return (
                f"உங்கள் தற்போதைய இருப்பிடம் மற்றும் கிடைக்கும் கடல் நிலவரங்களின்படி, "
                f"{loc_name} கடற்கரையிலிருந்து சுமார் 15 கி.மீ தொலைவில் சாத்தியமான மீன்பிடி பகுதி கண்டறியப்பட்டுள்ளது.\n\n"
                f"• கடல் நிலை: வெப்பநிலை ({avg_sst:.1f}°C) மற்றும் பாசி உற்பத்தி ({avg_chl:.2f} mg/m³) சாதகமாக உள்ளது.\n"
                f"• பாதுகாப்பு: காற்று ({max_wind:.1f} m/s) மற்றும் அலைகள் ({avg_wave:.1f} m) பாதுகாப்பான வரம்பில் உள்ளன.\n"
                "• படகு அழுத்தம்: மிதமானது. கூட்டம் குறைந்த மாற்றுப் பகுதியும் வரைபடத்தில் உள்ளது.\n\n"
                "இது கிடைக்கக்கூடிய கடல் நிலைமைகளை அடிப்படையாகக் கொண்ட ஒரு சாத்தியமான பரிந்துரை மட்டுமே, மீன் பிடிப்பதை உறுதி செய்யாது."
            )
        elif lang == "hi" and _regional_ok:
            return (
                f"आपकी वर्तमान स्थिति और उपलब्ध समुद्री परिस्थितियों के आधार पर, "
                f"{loc_name} से लगभग 15 किमी दूर एक संभावित मत्स्य पालन क्षेत्र मिला है।\n\n"
                f"• स्थितियां: समुद्री तापमान ({avg_sst:.1f}°C) और क्लोरोफिल ({avg_chl:.2f} mg/m³) अनुकूल हैं।\n"
                f"• सुरक्षा: हवा ({max_wind:.1f} m/s) और लहरें ({avg_wave:.1f} m) सुरक्षित सीमा में हैं।\n"
                "• मछली पकड़ने का दबाव: मध्यम। कम भीड़ वाला एक वैकल्पिक क्षेत्र भी उपलब्ध है।\n\n"
                "यह उपलब्ध समुद्री परिस्थितियों पर आधारित संभावित सिफारिश है और मछली मिलने की गारंटी नहीं देती है।"
            )
        elif lang == "te" and _regional_ok:
            return (
                f"మీ ప్రస్తుత స్థానం మరియు లభ్యమైన సముద్ర పరిస్థితుల ఆధారంగా, "
                f"{loc_name} తీరానికి దాదాపు 15 కి.మీ దూరంలో సంభావ్య చేపల వేట ప్రాంతం కనుగొనబడింది.\n\n"
                f"• పరిస్థితులు: సముద్ర ఉష్ణోగ్రత ({avg_sst:.1f}°C) మరియు క్లోరోఫిల్ ({avg_chl:.2f} mg/m³) అనుకూలంగా ఉన్నాయి.\n"
                f"• భద్రత: గాలి ({max_wind:.1f} m/s) మరియు అలలు ({avg_wave:.1f} m) సురక్షిత పరిమితుల్లో ఉన్నాయి.\n"
                "• బోట్ల రద్దీ: మధ్యస్థం. తక్కువ రద్దీ గల ప్రత్యామ్నాయ ప్రాంతం కూడా అందుబాటులో ఉంది.\n\n"
                "ఇది అందుబాటులో ఉన్న సముద్ర పరిస్థితుల ఆధారంగా సంభావ్య సిఫార్సు మాత్రమే, చేపలు లభిస్తాయని హామీ ఇవ్వదు."
            )
        elif lang == "ml" and _regional_ok:
            return (
                f"നിങ്ങളുടെ നിലവിലെ സ്ഥാനവും ലഭ്യമായ സമുദ്ര വിവരങ്ങളും അനുസരിച്ച്, "
                f"{loc_name} തീരത്തുനിന്ന് ഏകദേശം 15 കിലോമീറ്റർ അകലെ അനുയോജ്യമായ മത്സ്യബന്ധന മേഖല കണ്ടെത്തി.\n\n"
                f"• അവസ്ഥ: കടൽ താപനിലയും ({avg_sst:.1f}°C) ക്ലോറോഫിലും ({avg_chl:.2f} mg/m³) അനുകൂലമാണ്.\n"
                f"• സുരക്ഷ: കാറ്റും ({max_wind:.1f} m/s) തിരമാലകളും ({avg_wave:.1f} m) സുരക്ഷിതമായ പരിധിയിലാണ്.\n"
                "• ബദൽ മാർഗ്ഗം: കുറഞ്ഞ തിരക്കുള്ള മറ്റൊരു മേഖലയും മാപ്പിൽ ലഭ്യമാണ്.\n\n"
                "ഇത് ലഭ്യമായ സമുദ്ര വിവരങ്ങളെ അടിസ്ഥാനമാക്കിയുള്ള ഒരു സാധ്യതയുള്ള ശുപാർശ മാത്രമാണ്, മീൻ ലഭിക്കുമെന്ന് ഉറപ്പുനൽകുന്നില്ല."
            )

        # ── 2. "Nearest PFZ" Direct Query ──
        if any(w in q_lower for w in ["nearest pfz", "closest pfz", "nearest zone", "closest zone"]):
            top_zone = pfz_zones[0] if pfz_zones else None
            if not top_zone or not isinstance(top_zone.get("distance_km"), (int, float)):
                return (
                    f"A validated PFZ zone near {loc_name} is not available right now — "
                    "no live SST/chlorophyll-derived zone could be produced for your area."
                )
            demo_note = " (fallback simulated zone — not from live observations)" if str(top_zone.get("data_mode", "")).upper() in ("DEMO", "SIMULATED") else ""
            return (
                f"The nearest sustainable PFZ is approximately {top_zone['distance_km']:.1f} km from your selected landing center.\n\n"
                f"• Suitability: {top_zone.get('classification', 'High')}\n"
                f"• Crowding: {str(top_zone.get('crowding_level', 'LOW')).capitalize()}\n"
                "• Safety: Safe under current forecast conditions\n\n"
                f"I have highlighted it on the map.{demo_note}"
            )

        # ── 3. Route / Navigation Query ──
        if intent in ("ROUTE_OPTIMIZATION", "NAVIGATION_QUERY") or route_info:
            if not route_info:
                return (
                    f"I could not compute a navigation route off {loc_name} — "
                    "live route data is unavailable right now. Please try again in a few minutes."
                )
            dist = route_info.get("distance_km", 0.0) or 0.0
            eta = route_info.get("eta_hours", 0.0) or 0.0
            diesel = route_info.get("estimated_diesel_liters", 0.0) or 0.0
            fuel_save = route_info.get("fuel_saved_percent", 0) or 0
            wave_txt = f"{avg_wave:.1f} m" if avg_wave is not None else "not available"
            wind_txt = f"{max_wind:.1f} m/s" if max_wind is not None else "not available"
            cur_txt = f"{avg_cur:.2f} m/s" if avg_cur is not None else "not available"
            return (
                f"Here is the recommended navigation route off {loc_name}:\n\n"
                f"• Heading & Path: Follow the plotted waypoint corridor approximately {dist:.1f} km to the target area.\n"
                f"• Estimated travel time: Approximately {eta:.1f} hours at cruising speed.\n"
                f"• Fuel efficiency: Current-assisted path provides ~{fuel_save}% diesel savings (~{diesel:.1f} L expected burn).\n"
                f"• Sea conditions along route: waves {wave_txt}, wind {wind_txt}, current {cur_txt}.\n\n"
                "The waypoint trajectory and safe corridor are marked on the map."
            )

        # ── 4. Tomorrow's Weather / Fishing Safety Query ──
        if "tomorrow" in q_lower or "is it safe" in q_lower or intent in ("SAFETY_ASSESSMENT", "WEATHER_QUERY"):
            if max_wind is None or avg_wave is None:
                return (
                    f"I can't reliably grade sea safety off {loc_name} right now because wind/wave "
                    "data is unavailable. Please check with local port authorities before departure."
                )
            if "tomorrow" in q_lower:
                return (
                    f"Tomorrow currently looks {'moderately safe' if is_safe else 'hazardous'} for fishing in your selected area.\n\n"
                    "• Recommended departure window: Morning.\n"
                    f"• Wind: {max_wind:.1f} m/s expected.\n"
                    f"• Waves: {avg_wave:.1f} m swell.\n\n"
                    "Avoid the marked hazard zones on the map. Check again before departure because marine forecasts can change."
                )
            if is_safe:
                sst_line = f"\n• Sea surface temperature: {avg_sst:.1f}°C." if avg_sst is not None else ""
                return (
                    f"Conditions currently look safe for fishing departure off {loc_name}.\n\n"
                    f"• Wind: {max_wind:.1f} m/s (moderate breeze).\n"
                    f"• Waves: {avg_wave:.1f} m swell.{sst_line}\n\n"
                    "Conditions are within the configured safe thresholds based on forecast wind and waves."
                )
            else:
                return (
                    f"Caution is advised when venturing out from {loc_name}.\n\n"
                    f"• Surface wind: {max_wind:.1f} m/s.\n"
                    f"• Significant wave height: {avg_wave:.1f} m.\n\n"
                    "Please verify with local port authorities and check your safety gear before departure."
                )

        # ── 5. PFZ & Fishing Recommendations ──
        if intent in ("PFZ_ANALYSIS", "FISHING_LOCATION_RECOMMENDATION") or pfz_zones:
            if not pfz_zones:
                return (
                    f"I couldn't produce a validated PFZ recommendation off {loc_name} right now.\n\n"
                    + "\n".join(f"• {m}" for m in marine_lines)
                    + "\n\nThis is a potential fishing recommendation based on available marine conditions and does not guarantee catch."
                )
            target_zone = None
            zone_match = re.search(r'\b(PFZ-SECTOR-\d+|EXCLUDED-\d+|ZONE-\d+|[A-Z0-9]+-[A-Z0-9]+)\b', query, re.IGNORECASE)
            if zone_match:
                qid = zone_match.group(1).upper()
                for z in pfz_zones:
                    if z.get("zone_id", "").upper() == qid:
                        target_zone = z
                        break
            top_zone = target_zone or pfz_zones[0]
            dist = top_zone.get("distance_km")
            top_crowd = top_zone.get("crowding_level", "LOW")
            demo_note = " (fallback simulated zone — not from live observations)" if str(top_zone.get("data_mode", "")).upper() in ("DEMO", "SIMULATED") else ""
            dist_txt = f"approximately {dist:.1f} km" if isinstance(dist, (int, float)) else "offshore"
            if target_zone:
                headline = (
                    f"Fishing conditions for zone {top_zone.get('zone_id')} in the {loc_name} maritime sector:"
                )
            elif str(top_crowd).upper() == "HIGH":
                headline = (
                    f"Based on your location off {loc_name}, the primary area looks productive "
                    "but is currently experiencing high fleet crowding."
                )
            else:
                headline = (
                    f"Based on your location and available marine conditions, a potentially suitable fishing area "
                    f"was identified {dist_txt} off {loc_name}."
                )
            alt_line = ""
            if len(pfz_zones) > 1 and isinstance(pfz_zones[1].get("distance_km"), (int, float)):
                alt_line = f"\n• Alternative: A lower-pressure zone is available approximately {pfz_zones[1]['distance_km']:.1f} km offshore."
            return (
                f"{headline}\n\n"
                + "\n".join(f"• {m}" for m in marine_lines)
                + f"\n• Fishing pressure: {str(top_crowd).capitalize()}.{alt_line}\n"
                + f"\nZone identified: {top_zone.get('zone_id')} — rank {top_zone.get('classification')}{demo_note}.\n\n"
                + "This is a potential fishing recommendation based on available marine conditions and does not guarantee catch."
            )

        # ── 6. General Marine Conditions Fallback ──
        return (
            f"Current oceanographic conditions off {loc_name}:\n\n"
            + "\n".join(f"• {m}" for m in marine_lines)
            + "\n\nLet me know if you would like me to check fishing suitability or plot a navigation route."
        )

    async def explain_analysis(
        self,
        question: str,
        agent_results: list[dict[str, Any]],
        hypotheses: list[dict[str, Any]],
        confidence: float,
        confidence_level: str,
        temporal_relationships: list[dict[str, Any]],
        spatial_relationships: list[str],
        uncertainties: list[str],
        data_sources: list[dict[str, Any]],
    ) -> str:
        self._get_client()
        evidence_context = self._build_evidence_context(
            question, agent_results, hypotheses, confidence, confidence_level,
            temporal_relationships, spatial_relationships, uncertainties, data_sources
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": evidence_context},
        ]
        answer = await self._complete(messages)
        if answer:
            return answer
        return self._generate_fallback_explanation(
            question, agent_results, hypotheses, confidence, confidence_level
        )

    def _build_evidence_context(
        self,
        question: str,
        agent_results: list[dict[str, Any]],
        hypotheses: list[dict[str, Any]],
        confidence: float,
        confidence_level: str,
        temporal_relationships: list[dict[str, Any]],
        spatial_relationships: list[str],
        uncertainties: list[str],
        data_sources: list[dict[str, Any]],
    ) -> str:
        lines = [f"# Latest user question\n{question}\n\n# Multi-Agent Findings"]
        for agent in agent_results:
            agent_type = agent.get("agent_type", agent.get("agent", "agent"))
            status = agent.get("status", "SUCCESS")
            conf = agent.get("confidence", 0.8)
            findings = agent.get("findings", [])
            lines.append(f"## {str(agent_type).upper()} Agent (Status: {status}, Confidence: {conf:.1%})")
            for f in findings[:5]:
                desc = f if isinstance(f, str) else f.get("description", str(f))
                lines.append(f"- {desc}")
            lines.append("")
        lines.append(f"# Hypotheses\nOverall confidence: {confidence:.1%} ({confidence_level})\n")
        for i, hyp in enumerate(hypotheses[:4], 1):
            title = hyp.get("title", f"Hypothesis {i}") if isinstance(hyp, dict) else str(hyp)
            desc = hyp.get("description", "") if isinstance(hyp, dict) else ""
            lines.append(f"### {title}\n{desc}\n")
        return "\n".join(lines)

    def _generate_fallback_explanation(
        self,
        question: str,
        agent_results: list[dict[str, Any]],
        hypotheses: list[dict[str, Any]],
        confidence: float,
        confidence_level: str,
    ) -> str:
        lines = [
            f"## Analysis of: {question[:100]}",
            f"**Confidence:** {confidence:.0%} ({confidence_level})",
            "",
            "### Observations",
        ]
        for agent in agent_results:
            agent_name = agent.get("agent_type", agent.get("agent", "agent"))
            for f in agent.get("findings", [])[:3]:
                desc = f if isinstance(f, str) else f.get("description", str(f))
                lines.append(f"- **[{str(agent_name).capitalize()}]** {desc}")
        if hypotheses:
            lines.append("\n### Assessment")
            for h in hypotheses[:3]:
                desc = h.get("description", h.get("title", str(h))) if isinstance(h, dict) else str(h)
                lines.append(f"• {desc}")
        return "\n".join(lines)


_llm_service: LLMService | None = None
_llm_service_lock = threading.Lock()


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        with _llm_service_lock:
            if _llm_service is None:
                _llm_service = LLMService()
    return _llm_service
