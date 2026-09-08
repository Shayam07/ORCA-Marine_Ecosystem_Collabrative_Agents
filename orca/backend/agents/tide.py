"""ORCA Tide Agent — Provides tide predictions."""

from __future__ import annotations

import math
import logging
from datetime import datetime

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType

logger = logging.getLogger("orca.agents.tide")


def predict_tide_simplified(lat: float, lon: float, dt: datetime) -> dict:
    """Simplified astronomical tide estimate (M2 + S2 constituents)."""
    M2_period = 12.4206
    S2_period = 12.0000
    M2_amplitude = 1.2 + 0.3 * math.sin(math.radians(lat))
    S2_amplitude = 0.4

    t_hours = dt.hour + dt.minute / 60.0
    phase_m2 = 2 * math.pi * t_hours / M2_period
    phase_s2 = 2 * math.pi * t_hours / S2_period

    tide_height = M2_amplitude * math.sin(phase_m2) + S2_amplitude * math.sin(phase_s2)

    if tide_height > 0.5 * M2_amplitude:
        state = "HIGH"
    elif tide_height < -0.5 * M2_amplitude:
        state = "LOW"
    elif math.sin(phase_m2) > 0:
        state = "RISING"
    else:
        state = "FALLING"

    return {
        "height_m": round(tide_height, 2),
        "state": state,
        "is_model_estimate": True,
        "note": "Simplified astronomical estimate, not from a tide station.",
    }


class TideAgent(BaseMarineAgent):
    """Provides tide predictions for marine locations."""

    def __init__(self):
        super().__init__(agent_type=AgentType.OCEAN)

    async def analyze(self, task: AgentTask):
        """Run tide analysis."""
        lat = task.context.get("lat", 13.0)
        lon = task.context.get("lon", 80.3)
        dt = task.start_date

        tide = predict_tide_simplified(lat, lon, dt)

        findings = [AgentFinding(
            variable="tide",
            description=f"Tide: {tide['state']} — {tide['height_m']:+.2f} m (estimated)",
            value=tide["height_m"],
            unit="m",
        )]

        hypotheses = [
            f"Tide at ({lat:.2f}, {lon:.2f}): {tide['state']} — {tide['height_m']:+.2f} m. "
            f"⚠️ Model estimate only."
        ]

        return findings, [], hypotheses, 0.4
