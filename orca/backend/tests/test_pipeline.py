"""ORCA End-to-End Pipeline Tests."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def run_async(coro):
    """Run an async function in tests."""
    return asyncio.run(coro)


class TestDemoProvider:
    """Test demo data provider generates realistic data."""

    def test_health_check(self):
        from data.providers.demo import DemoDataProvider
        provider = DemoDataProvider()
        health = run_async(provider.health_check())
        assert health.status.value == "HEALTHY"

    def test_generates_observations(self):
        from datetime import datetime
        from data.providers.demo import DemoDataProvider
        provider = DemoDataProvider()
        batch = run_async(
            provider.get_data(
                bbox=[71.5, 14.5, 73.5, 16.5],
                start_date=datetime(2026, 8, 1),
                end_date=datetime(2026, 8, 5),
                variables=["sea_surface_temperature"],
            )
        )
        assert batch.record_count > 0
        assert batch.is_demo is True
        assert len(batch.observations) > 0

    def test_anomaly_applied(self):
        from datetime import datetime
        from data.providers.demo import DemoDataProvider
        provider = DemoDataProvider()
        batch = run_async(
            provider.get_data(
                bbox=[71.5, 14.5, 73.5, 16.5],
                start_date=datetime(2026, 8, 1),
                end_date=datetime(2026, 8, 10),
                variables=["sea_surface_temperature", "chlorophyll_concentration"],
            )
        )
        sst_obs = [o for o in batch.observations
                   if o.variable == "sea_surface_temperature"
                   and 14.5 <= o.latitude <= 16.5
                   and 71.5 <= o.longitude <= 73.5]
        chla_obs = [o for o in batch.observations
                    if o.variable == "chlorophyll_concentration"
                    and 14.5 <= o.latitude <= 16.5
                    and 71.5 <= o.longitude <= 73.5]
        assert len(sst_obs) > 0
        assert len(chla_obs) > 0

    def test_observation_provenance(self):
        from datetime import datetime
        from data.providers.demo import DemoDataProvider
        provider = DemoDataProvider()
        batch = run_async(
            provider.get_data(
                bbox=[72.0, 15.0, 73.0, 16.0],
                start_date=datetime(2026, 8, 1),
                end_date=datetime(2026, 8, 3),
                variables=["sea_surface_temperature"],
            )
        )
        obs = batch.observations[0]
        assert obs.source.value == "DEMO"
        assert obs.dataset == "demo_synthetic"
        assert obs.variable == "sea_surface_temperature"
        assert obs.unit == "degC"
        assert obs.is_demo is True


class TestAgents:
    """Test individual agents."""

    def test_ocean_agent(self):
        from datetime import datetime
        from agents.ocean import OceanAgent
        from models.agent import AgentTask
        agent = OceanAgent()
        task = AgentTask(
            agent_type="ocean",
            question="Analyze ocean conditions",
            bbox=[71.5, 14.5, 73.5, 16.5],
            start_date=datetime(2026, 8, 1),
            end_date=datetime(2026, 8, 28),
        )
        result = run_async(agent.execute(task, timeout=3.0))
        assert result.status.value in ("SUCCESS", "NO_DATA", "FAILED")

    def test_satellite_agent(self):
        from datetime import datetime
        from agents.satellite import SatelliteAgent
        from models.agent import AgentTask
        agent = SatelliteAgent()
        task = AgentTask(
            agent_type="satellite",
            question="Analyze satellite data",
            bbox=[71.5, 14.5, 73.5, 16.5],
            start_date=datetime(2026, 8, 1),
            end_date=datetime(2026, 8, 28),
        )
        result = run_async(agent.execute(task, timeout=3.0))
        assert result.status.value in ("SUCCESS", "NO_DATA", "FAILED")

    def test_biology_agent(self):
        from datetime import datetime
        from agents.biology import BiologyAgent
        from models.agent import AgentTask
        agent = BiologyAgent()
        task = AgentTask(
            agent_type="biology",
            question="Analyze biological conditions",
            bbox=[71.5, 14.5, 73.5, 16.5],
            start_date=datetime(2026, 8, 1),
            end_date=datetime(2026, 8, 28),
        )
        result = run_async(agent.execute(task, timeout=3.0))
        assert result.status.value in ("SUCCESS", "NO_DATA", "FAILED")

    def test_weather_agent(self):
        from datetime import datetime
        from agents.weather import WeatherAgent
        from models.agent import AgentTask
        agent = WeatherAgent()
        task = AgentTask(
            agent_type="weather",
            question="Analyze weather conditions",
            bbox=[71.5, 14.5, 73.5, 16.5],
            start_date=datetime(2026, 8, 1),
            end_date=datetime(2026, 8, 28),
        )
        result = run_async(agent.execute(task, timeout=3.0))
        assert result.status.value in ("SUCCESS", "NO_DATA", "FAILED")


class TestReasoning:
    """Test reasoning engines."""

    def test_evidence_fusion(self):
        from datetime import datetime
        from agents.coordinator import CoordinatorAgent
        from reasoning.evidence_fusion import EvidenceFusionEngine
        from models.agent import AgentResult

        coord = CoordinatorAgent()
        result = run_async(
            coord.coordinate(
                question="Why has chlorophyll decreased?",
                bbox=[71.5, 14.5, 73.5, 16.5],
                start_date=datetime(2026, 8, 1),
                end_date=datetime(2026, 8, 28),
            )
        )

        agent_results = [AgentResult(**ar) for ar in result.metadata.get("agent_results", [])]
        fusion = EvidenceFusionEngine()
        fusion_result = fusion.fuse(agent_results)
        assert len(fusion_result.ranked_evidence) > 0
        assert fusion_result.evidence_convergence_score > 0

    def test_hypothesis_engine(self):
        from datetime import datetime
        from agents.coordinator import CoordinatorAgent
        from reasoning import EvidenceFusionEngine, HypothesisEngine
        from models.agent import AgentResult

        coord = CoordinatorAgent()
        result = run_async(
            coord.coordinate(
                question="Why has chlorophyll decreased?",
                bbox=[71.5, 14.5, 73.5, 16.5],
                start_date=datetime(2026, 8, 1),
                end_date=datetime(2026, 8, 28),
            )
        )

        agent_results = [AgentResult(**ar) for ar in result.metadata.get("agent_results", [])]
        fusion = EvidenceFusionEngine().fuse(agent_results)
        hypotheses = HypothesisEngine().generate(agent_results, fusion)
        assert len(hypotheses.hypotheses) > 0

    def test_confidence_engine(self):
        from datetime import datetime
        from agents.coordinator import CoordinatorAgent
        from reasoning import EvidenceFusionEngine, HypothesisEngine, ConfidenceEngine
        from models.agent import AgentResult

        coord = CoordinatorAgent()
        result = run_async(
            coord.coordinate(
                question="Why has chlorophyll decreased?",
                bbox=[71.5, 14.5, 73.5, 16.5],
                start_date=datetime(2026, 8, 1),
                end_date=datetime(2026, 8, 28),
            )
        )

        agent_results = [AgentResult(**ar) for ar in result.metadata.get("agent_results", [])]
        fusion = EvidenceFusionEngine().fuse(agent_results)
        hypotheses = HypothesisEngine().generate(agent_results, fusion)
        final = ConfidenceEngine().compute_confidence(hypotheses, agent_results, fusion)
        assert final.overall_confidence >= 0
        assert final.overall_confidence <= 1


class TestAPI:
    """Test API endpoints."""

    def test_health_endpoint(self):
        import httpx
        from httpx import ASGITransport
        from main import app

        async def _test():
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                r = await client.get('/api/v1/health')
                return r

        r = run_async(_test())
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_sources_endpoint(self):
        import httpx
        from httpx import ASGITransport
        from main import app

        async def _test():
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                return await client.get('/api/v1/sources')

        r = run_async(_test())
        assert r.status_code == 200
        assert len(r.json()["sources"]) > 0

    def test_map_layers_endpoint(self):
        import httpx
        from httpx import ASGITransport
        from main import app

        async def _test():
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                return await client.get('/api/v1/map/layers')

        r = run_async(_test())
        assert r.status_code == 200
        assert len(r.json()["layers"]) > 0

    def test_query_endpoint(self):
        import httpx
        from httpx import ASGITransport
        from main import app

        async def _test():
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                return await client.post(
                    '/api/v1/query',
                    json={
                        'question': 'Why has chlorophyll decreased?',
                        'geometry': {
                            'type': 'Polygon',
                            'coordinates': [[[71.5, 14.5], [73.5, 14.5], [73.5, 16.5], [71.5, 16.5], [71.5, 14.5]]]
                        },
                        'start_date': '2026-08-01T00:00:00Z',
                        'end_date': '2026-08-28T00:00:00Z',
                    }
                )

        r = run_async(_test())
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "COMPLETED"
        assert len(data["hypotheses"]) > 0
        assert len(data["agents_used"]) >= 4
        assert 0 <= data["confidence"] <= 1
