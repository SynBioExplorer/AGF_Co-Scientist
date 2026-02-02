#!/usr/bin/env python3
"""
Phase 6: Refutation Search Tests

Tests for the refutation search system that finds contradictory evidence,
failed replications, and retracted papers.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from src.tools.refutation_search import RefutationSearchTool
from src.tools.base import ToolResult


class MockCitationNode:
    """Mock CitationNode for testing."""

    def __init__(
        self,
        title: str = "Test Paper",
        doi: str = None,
        pmid: str = None,
        abstract: str = "",
        paper_id: str = None
    ):
        self.id = paper_id or f"paper_{hash(title) % 10000}"
        self.paper_id = paper_id
        self.title = title
        self.doi = doi
        self.pmid = pmid
        self.abstract = abstract
        self.year = 2024
        self.authors = ["Author A"]

    def model_dump(self):
        return {
            "id": self.id,
            "title": self.title,
            "doi": self.doi,
            "pmid": self.pmid,
            "abstract": self.abstract
        }


class TestNegationQueryGeneration:
    """Tests for negation query generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = RefutationSearchTool()

    def test_basic_negation_queries(self):
        """Test that negation queries are generated correctly."""
        claim = "Protein A inhibits Gene B"
        queries = self.tool.generate_negation_queries(claim)

        # Should generate multiple queries
        assert len(queries) >= 5

        # Should include NOT version
        assert any("NOT" in q for q in queries)

        # Should include "no effect" version
        assert any("no effect" in q for q in queries)

        # Should include contradiction keywords
        assert any("contradicts" in q or "inconsistent" in q for q in queries)

    def test_opposite_effect_queries(self):
        """Test that opposite effect queries are generated."""
        claim = "Drug X increases survival"
        queries = self.tool.generate_negation_queries(claim)

        # Should generate opposite effect query
        assert any("decreases" in q.lower() for q in queries)

    def test_activation_inhibition_swap(self):
        """Test that activates/inhibits are swapped."""
        claim = "Compound Y activates receptor Z"
        queries = self.tool.generate_negation_queries(claim)

        # Should generate inhibits version
        assert any("inhibits" in q.lower() for q in queries)

    def test_replication_failure_queries(self):
        """Test that replication failure queries are included."""
        claim = "Treatment shows effect"
        queries = self.tool.generate_negation_queries(claim)

        # Should include replication failure queries
        assert any("failed to replicate" in q or "could not reproduce" in q for q in queries)


class TestContradictionFiltering:
    """Tests for contradiction filtering."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = RefutationSearchTool()

    def test_identifies_contradiction_keywords(self):
        """Test that abstracts with contradiction keywords are identified."""
        # Abstract with clear contradiction
        abstract_contradiction = (
            "We did not find any significant effect of Drug X on survival. "
            "Our results contradict previous studies that reported positive effects. "
            "The null result suggests the initial findings may have been spurious."
        )

        is_contradiction = self.tool._is_contradiction(abstract_contradiction, "Drug X improves survival")
        assert is_contradiction is True

    def test_rejects_supporting_evidence(self):
        """Test that supporting abstracts are not flagged as contradictions."""
        abstract_supporting = (
            "We confirmed that Drug X significantly improves survival in mice. "
            "Our results support the mechanism proposed by earlier studies. "
            "The treatment showed clear benefits across all dosage groups."
        )

        is_contradiction = self.tool._is_contradiction(abstract_supporting, "Drug X improves survival")
        assert is_contradiction is False

    def test_empty_abstract_handling(self):
        """Test handling of empty abstracts."""
        is_contradiction = self.tool._is_contradiction("", "Any claim")
        assert is_contradiction is False

        is_contradiction = self.tool._is_contradiction(None, "Any claim")
        assert is_contradiction is False


class TestRefutationSearch:
    """Tests for full refutation search functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_semantic_scholar = MagicMock()
        self.mock_pubmed = MagicMock()

        self.tool = RefutationSearchTool(
            pubmed_tool=self.mock_pubmed,
            semantic_scholar_tool=self.mock_semantic_scholar
        )

    @pytest.mark.asyncio
    async def test_search_contradictions_returns_results(self):
        """Test that contradiction search returns results."""
        # Mock semantic scholar response
        mock_response = ToolResult.success_result(
            data=[
                {
                    "title": "No effect of Drug X on survival",
                    "abstract": "We did not find any effect. The results contradict earlier findings.",
                    "doi": "10.1000/test",
                    "year": 2024
                }
            ],
            metadata={}
        )

        self.mock_semantic_scholar.execute = AsyncMock(return_value=mock_response)

        contradictions = await self.tool.search_contradictions(
            hypothesis_statement="Drug X improves survival",
            core_claim="Drug X survival"
        )

        assert len(contradictions) >= 1
        assert contradictions[0]["title"] == "No effect of Drug X on survival"

    @pytest.mark.asyncio
    async def test_deduplication_by_doi(self):
        """Test that duplicate papers are removed."""
        # Mock responses with duplicates
        mock_response = ToolResult.success_result(
            data=[
                {"title": "Paper A", "doi": "10.1000/same", "abstract": "Did not find effect. No significant result."},
                {"title": "Paper A Duplicate", "doi": "10.1000/same", "abstract": "Did not find effect. Contradicts hypothesis."},
            ],
            metadata={}
        )

        self.mock_semantic_scholar.execute = AsyncMock(return_value=mock_response)
        self.mock_pubmed.execute = AsyncMock(return_value=ToolResult.success_result(data=[], metadata={}))

        contradictions = await self.tool.search_contradictions(
            hypothesis_statement="Test",
            core_claim="Test"
        )

        # Should deduplicate
        assert len(contradictions) <= 1


class TestRetractionDetection:
    """Tests for retraction detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_pubmed = MagicMock()
        self.tool = RefutationSearchTool(pubmed_tool=self.mock_pubmed)

    @pytest.mark.asyncio
    async def test_detects_retracted_paper(self):
        """Test that retracted papers are detected."""
        # Mock PubMed response indicating retraction
        mock_retraction = ToolResult.success_result(
            data=[
                {"title": "Retraction: Original Paper", "year": 2024}
            ],
            metadata={}
        )

        self.mock_pubmed.execute = AsyncMock(return_value=mock_retraction)

        paper = {"pmid": "12345678", "title": "Original Paper"}
        status = await self.tool.check_retractions(paper)

        assert status["is_retracted"] is True
        assert len(status["notices"]) >= 1

    @pytest.mark.asyncio
    async def test_detects_correction(self):
        """Test that corrections are detected."""
        # First call (retraction) - no results
        # Second call (correction) - has results
        mock_no_result = ToolResult.success_result(data=[], metadata={})
        mock_correction = ToolResult.success_result(
            data=[{"title": "Correction to Original Paper", "year": 2024}],
            metadata={}
        )

        self.mock_pubmed.execute = AsyncMock(
            side_effect=[mock_no_result, mock_correction, mock_no_result]
        )

        paper = {"pmid": "12345678", "title": "Original Paper"}
        status = await self.tool.check_retractions(paper)

        assert status["has_correction"] is True

    @pytest.mark.asyncio
    async def test_no_pmid_returns_empty(self):
        """Test that papers without PMID return empty status."""
        paper = {"title": "Paper without PMID", "doi": "10.1000/test"}
        status = await self.tool.check_retractions(paper)

        assert status["is_retracted"] is False
        assert status["has_correction"] is False
        assert len(status["notices"]) == 0


class TestHydroxychloroquineCase:
    """Real-world test case: Hydroxychloroquine for COVID-19."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = RefutationSearchTool()

    def test_generates_relevant_queries(self):
        """Test that relevant negation queries are generated for HCQ."""
        claim = "hydroxychloroquine effective COVID-19"
        queries = self.tool.generate_negation_queries(claim)

        # Should generate queries that would find contradictory RCTs
        assert any("no effect" in q.lower() for q in queries)
        assert any("not" in q.lower() for q in queries)

    def test_identifies_negative_trial_abstract(self):
        """Test identification of negative trial results."""
        # RECOVERY trial-like abstract
        recovery_abstract = (
            "In patients hospitalized with COVID-19, hydroxychloroquine was not "
            "associated with reductions in 28-day mortality. There was no significant "
            "difference in hospital stay duration. These findings do not support the "
            "use of hydroxychloroquine for treatment of patients hospitalized with COVID-19."
        )

        is_contradiction = self.tool._is_contradiction(
            recovery_abstract,
            "hydroxychloroquine effective COVID-19"
        )

        assert is_contradiction is True


class TestContextFormatting:
    """Tests for formatting contradictions for LLM context."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = RefutationSearchTool()

    def test_formats_contradictions(self):
        """Test that contradictions are formatted correctly."""
        contradictions = [
            {
                "title": "No Effect Study",
                "year": 2024,
                "abstract": "We found no significant effect...",
                "contradiction_source": "semantic_scholar"
            }
        ]

        retraction_status = {}

        formatted = self.tool.format_contradictions_for_context(
            contradictions,
            retraction_status
        )

        assert "CONTRADICTORY EVIDENCE FOUND" in formatted
        assert "No Effect Study" in formatted
        assert "2024" in formatted

    def test_includes_retraction_warning(self):
        """Test that retraction warnings are included."""
        contradictions = []
        retraction_status = {
            "Retracted Paper": {"is_retracted": True}
        }

        formatted = self.tool.format_contradictions_for_context(
            contradictions,
            retraction_status
        )

        assert "RETRACTED" in formatted
        assert "Retracted Paper" in formatted


def run_tests():
    """Run all refutation search tests."""
    print("=" * 60)
    print("Phase 6: Refutation Search Tests")
    print("=" * 60)

    # Run pytest programmatically
    exit_code = pytest.main([__file__, "-v", "--tb=short"])

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
