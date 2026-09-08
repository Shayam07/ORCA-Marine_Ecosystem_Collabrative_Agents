"""ORCA Literature Agent — Searches scientific literature for relevant context.

Never fabricates citations. Every paper must have a real source.
"""

from __future__ import annotations

from .base import BaseMarineAgent
from models.agent import AgentFinding, AgentTask, AgentType
from models.observation import EvidenceType


class LiteratureAgent(BaseMarineAgent):
    """Searches scientific literature for relevant context.

    Given observed variables, finds supporting/contradicting literature.
    """

    def __init__(self):
        super().__init__(AgentType.LITERATURE)

    async def analyze(self, task: AgentTask):
        evidence = []
        findings = []
        hypotheses = []

        # Build literature search query from task context
        search_terms = []
        if task.variables:
            search_terms.extend(task.variables[:3])
        if task.question:
            search_terms.append(task.question[:100])
        search_query = " ".join(search_terms) or "marine ecosystem Indian Ocean"

        # Access literature provider through registry
        from data.providers import get_registry
        registry = get_registry()
        lit_provider = registry.get_provider("LITERATURE")

        if lit_provider is None:
            findings.append(AgentFinding(
                variable="literature_availability",
                description="Literature provider not available",
                evidence_type=EvidenceType.LITERATURE,
            ))
            return findings, evidence, hypotheses, 0.0

        try:
            papers = await lit_provider.search_literature(
                query=search_query, max_results=5
            )
        except Exception as e:
            self.logger.error(f"Literature search failed: {e}")
            findings.append(AgentFinding(
                variable="literature_search_error",
                description=f"Literature search encountered an error: {e}",
                evidence_type=EvidenceType.LITERATURE,
            ))
            return findings, evidence, hypotheses, 0.0

        if not papers:
            findings.append(AgentFinding(
                variable="literature_results",
                description="No directly relevant literature found for this query",
                evidence_type=EvidenceType.LITERATURE,
            ))
            return findings, evidence, hypotheses, 0.1

        # Process each paper
        for paper in papers:
            title = paper.get("title", "Unknown")
            authors = ", ".join(paper.get("authors", [])[:3])
            year = paper.get("year", "n/a")
            doi = paper.get("doi", "")
            snippet = paper.get("snippet", "")
            relevance = paper.get("relevance_score", 0.5)

            finding = AgentFinding(
                variable="literature_reference",
                description=(
                    f"Paper: \"{title}\" ({authors}, {year}). "
                    f"Relevance: {relevance:.0%}. "
                    f"Finding: {snippet}"
                ),
                value=relevance,
                unit="relevance_score",
                evidence_type=EvidenceType.LITERATURE,
                metadata={
                    "title": title,
                    "authors": paper.get("authors", []),
                    "year": year,
                    "doi": doi,
                    "source": paper.get("source", ""),
                    "snippet": snippet,
                },
            )
            findings.append(finding)

            # Extract hypotheses from literature
            if relevance > 0.8 and snippet:
                hypotheses.append(
                    f"Literature suggests: {snippet[:200]}"
                )

        avg_confidence = (
            sum(p.get("relevance_score", 0.5) for p in papers) / len(papers)
            if papers else 0.0
        )

        return findings, evidence, hypotheses, round(avg_confidence * 0.7, 3)
