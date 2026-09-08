"""ORCA Marine Safety Agent — Assesses sea safety conditions."""

from __future__ import annotations

import logging

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType

logger = logging.getLogger("orca.agents.safety")


class MarineSafetyAgent(BaseMarineAgent):
    """Analyzes marine safety conditions for a given location and time."""

    def __init__(self):
        super().__init__(agent_type=AgentType.OCEAN)  # Uses ocean data for safety

    async def analyze(self, task: AgentTask):
        """Run safety analysis. Returns (findings, evidence, hypotheses, confidence)."""
        observations = []
        findings = []
        hypotheses = []
        risk_factors = []

        # Fetch weather + ocean data
        try:
            weather_batch = await self.data_service.get_observations(
                bbox=task.bbox,
                start_date=task.start_date,
                end_date=task.end_date,
                variables=["wind_speed", "wind_direction", "wave_height",
                           "sea_surface_temperature"],
                preferred_sources=["ERA5", "DEMO"],
            )
            obs_list = weather_batch.observations if hasattr(weather_batch, "observations") else weather_batch
            observations.extend(obs_list)
        except Exception as e:
            logger.warning(f"Safety agent data fetch failed: {e}")

        # Vessel specific thresholds (default to conservative Artisanal limits)
        from agents.route import VesselProfile
        vessel_class = getattr(task, "parameters", {}).get("vessel_class") if hasattr(task, "parameters") else None
        v_prof = VesselProfile.from_vessel_class(vessel_class or "Artisanal")

        safety_level = "SAFE"
        max_safe_wave = v_prof.maximum_safe_wave_m
        max_safe_wind = v_prof.maximum_safe_wind_ms

        for obs in observations:
            if obs.variable == "wind_speed" and obs.value > (max_safe_wind * 0.75):
                risk_factors.append(f"Strong winds: {obs.value:.1f} m/s (limit: {max_safe_wind:.1f} m/s)")
                safety_level = "CAUTION" if safety_level != "DANGER" else "DANGER"
                if obs.value > max_safe_wind:
                    safety_level = "DANGER"
            elif obs.variable == "wave_height" and obs.value > (max_safe_wave * 0.75):
                risk_factors.append(f"High waves: {obs.value:.1f} m (limit: {max_safe_wave:.1f} m)")
                safety_level = "CAUTION" if safety_level != "DANGER" else "DANGER"
                if obs.value > max_safe_wave:
                    safety_level = "DANGER"

            findings.append(AgentFinding(
                variable=obs.variable,
                description=f"{obs.variable}: {obs.value:.1f} {obs.unit}",
                value=obs.value,
                unit=obs.unit,
                anomaly_detected=(obs.variable == "wind_speed" and obs.value > max_safe_wind) or
                                 (obs.variable == "wave_height" and obs.value > max_safe_wave),
            ))

        if safety_level == "SAFE":
            summary = f"Current marine conditions remain within safe limits for {v_prof.boat_type} (wave < {max_safe_wave}m, wind < {max_safe_wind} m/s)."
        elif safety_level == "CAUTION":
            summary = f"Exercise caution for {v_prof.boat_type}: {len(risk_factors)} operational warning(s) flagged."
        else:
            summary = f"🚨 DANGER: Severe marine hazard detected for {v_prof.boat_type}. Swell or wind exceeds safe threshold. Strictly advise postponing departure."

        hypotheses.append(summary)
        confidence = 0.85 if observations else 0.3

        return findings, observations, hypotheses, confidence
