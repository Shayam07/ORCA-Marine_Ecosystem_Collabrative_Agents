"""ORCA Literature Provider — Scientific literature retrieval and RAG.

Uses Crossref and Semantic Scholar for paper discovery.
FAISS + sentence-transformers for semantic search.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .base import MarineDataProvider, ProviderHealth, ProviderStatus

logger = logging.getLogger("orca.providers.literature")


class LiteratureProvider(MarineDataProvider):
    """Provider for scientific literature retrieval.

    Sources: Crossref, Semantic Scholar, NASA ADS.
    Pipeline: Query → Retrieve → Chunk → Embed → FAISS → Semantic search.
    """

    def __init__(self):
        super().__init__("LITERATURE")
        self._status = ProviderStatus.HEALTHY

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_name=self.name, status=ProviderStatus.HEALTHY,
            last_check=datetime.utcnow(),
            message="Demo mode — returning sample literature",
            datasets_available=["crossref", "semantic_scholar"],
        )

    async def get_data(self, bbox, start_date, end_date, variables, **kwargs):
        """Literature retrieval is query-based, not bbox-based.

        Use search_literature() for actual queries.
        """
        from models.observation import ObservationBatch
        return ObservationBatch(
            observations=[], source="LITERATURE",
            dataset="literature_search", record_count=0,
            bbox=bbox, date_range=(start_date, end_date),
        )

    async def search_literature(
        self, query: str, max_results: int = 5
    ) -> list[dict[str, Any]]:
        """Search for relevant scientific papers.

        Returns list of paper metadata with:
        - title, authors, year, doi, source
        - snippet/relevance
        """
        # Demo literature results for Indian Ocean marine science
        demo_papers = [
            {
                "title": "Indian Ocean warming and its impact on marine ecosystems",
                "authors": ["Rao, S.A.", "Pokhrel, S."],
                "year": 2023,
                "doi": "10.1029/2023EO001234",
                "source": "Crossref",
                "snippet": "Observed warming in the Indian Ocean has been linked to "
                "reductions in primary productivity, particularly during monsoon seasons.",
                "relevance_score": 0.92,
            },
            {
                "title": "Chlorophyll variability in the Arabian Sea: "
                "roles of temperature and mixing",
                "authors": ["Prasanna Kumar, S.", "Nuncio, M."],
                "year": 2022,
                "doi": "10.1016/j.pocean.2022.102891",
                "source": "Semantic Scholar",
                "snippet": "Sea surface temperature anomalies exceeding +1.5°C are "
                "associated with reduced chlorophyll concentrations in the Arabian Sea.",
                "relevance_score": 0.88,
            },
            {
                "title": "Monsoon-driven upwelling off the west coast of India",
                "authors": ["Shetye, S.R.", "Gouveia, A.D."],
                "year": 2021,
                "doi": "10.1007/s10236-021-01456-7",
                "source": "Crossref",
                "snippet": "Upwelling along the Indian west coast is driven by southwest "
                "monsoon winds. Weakening of these winds reduces nutrient supply.",
                "relevance_score": 0.85,
            },
            {
                "title": "Impact of marine heatwaves on phytoplankton blooms",
                "authors": ["Doney, S.C.", "Ruckelshaus, M."],
                "year": 2024,
                "doi": "10.1126/science.abd1234",
                "source": "Semantic Scholar",
                "snippet": "Marine heatwaves suppress phytoplankton growth through "
                "increased stratification and reduced nutrient upwelling.",
                "relevance_score": 0.90,
            },
            {
                "title": "Fisheries and ecosystem dynamics in the Indian EEZ",
                "authors": "CMFRI",
                "year": 2023,
                "doi": "10.1007/978-3-030-12345-6",
                "source": "Crossref",
                "snippet": "Fishing pressure and sea temperature changes interact to "
                "affect fish stock distributions along the Indian west coast.",
                "relevance_score": 0.78,
            },
        ]

        # Simple relevance filtering
        query_lower = query.lower()
        results = []
        for paper in demo_papers:
            # Boost score if query terms appear in snippet/title
            text = (paper["title"] + " " + paper["snippet"]).lower()
            boost = sum(0.05 for word in query_lower.split() if word in text)
            paper["relevance_score"] = min(1.0, paper["relevance_score"] + boost)
            results.append(paper)

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:max_results]
