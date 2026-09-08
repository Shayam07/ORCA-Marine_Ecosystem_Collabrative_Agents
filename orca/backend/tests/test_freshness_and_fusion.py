"""Tests for Data Freshness Engine, Provider Abstraction, and Dataset Disagreement Fusion."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta

from models.observation import Observation, ObservationBatch, FreshnessStatus, DataSource, EvidenceType
from models.evidence import EvidenceItem
from data.service import DataService
from reasoning.evidence_fusion import EvidenceFusionEngine


def test_data_freshness_degradation_calculation():
    """Verify that observations older than 24h are marked STALE with reduced confidence."""
    service = DataService()
    now = datetime.now(timezone.utc)

    # 3 days in the past -> should be stale
    old_date = now - timedelta(days=3)
    batch = asyncio.run(service.get_observations(
        bbox=[80.0, 12.5, 81.0, 13.5],
        start_date=old_date - timedelta(days=1),
        end_date=old_date,
        variables=["sea_surface_temperature"],
        allow_demo=True,
    ))

    assert batch.record_count > 0
    assert batch.freshness_status in (FreshnessStatus.DELAYED, FreshnessStatus.STALE)
    # Stale/delayed observation confidence should be < 1.0
    for obs in batch.observations:
        if obs.data_age_hours > 24.0:
            assert obs.freshness_status == FreshnessStatus.STALE
            assert obs.confidence <= 0.65


def test_evidence_fusion_dataset_disagreement_detection():
    """Verify that diverging observations from distinct datasets trigger contradiction notices and uncertainty."""
    engine = EvidenceFusionEngine()

    # Create 2 observations from distinct sources for SST with high disagreement
    from models.agent import AgentType
    obs_mosdac = EvidenceItem(
        source="MOSDAC",
        dataset="insat3d_sst",
        variable="sea_surface_temperature",
        value=31.5,
        unit="°C",
        quality=0.9,
        agent=AgentType.SATELLITE,
        evidence_type=EvidenceType.OBSERVATION,
    )
    obs_copernicus = EvidenceItem(
        source="COPERNICUS_MARINE",
        dataset="cmems_sst",
        variable="sea_surface_temperature",
        value=28.0,  # 3.5°C difference!
        unit="°C",
        quality=0.9,
        agent=AgentType.OCEAN,
        evidence_type=EvidenceType.OBSERVATION,
    )

    contradictions = engine._detect_contradictions([obs_mosdac, obs_copernicus])
    assert len(contradictions) > 0
    contra_text = " ".join(contradictions)
    assert "Dataset disagreement" in contra_text or "diverging" in contra_text
    assert "Uncertainty elevated" in contra_text or "Mixed signals" in contra_text
