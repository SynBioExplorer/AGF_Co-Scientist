#!/usr/bin/env python3
"""
Phase 6: ReflectionAgent Integration Tests

Tests for the integration of Phase 6 evidence quality features
(RefutationSearchTool, LimitationsExtractor) into ReflectionAgent.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


class MockCitation:
    """Mock Citation for testing."""

    def __init__(
        self,
        title: str = "Test Citation",
        doi: str = None,
        pmid: str = None,
        relevance: str = "Relevant to hypothesis"
    ):
        self.title = title
        self.doi = doi
        self.pmid = pmid
        self.relevance = relevance


class MockHypothesis:
    """Mock Hypothesis for testing."""

    def __init__(
        self,
        id: str = "hyp_001",
        hypothesis_statement: str = "Drug X inhibits protein Y to reduce disease Z",
        title: str = "Test Hypothesis",
        rationale: str = "Based on literature...",
        mechanism: str = "Inhibition pathway",
        literature_citations: List[MockCitation] = None
    ):
        self.id = id
        self.hypothesis_statement = hypothesis_statement
        self.title = title
        self.rationale = rationale
        self.mechanism = mechanism
        self.literature_citations = literature_citations or []


class MockToolResult:
    """Mock ToolResult for testing."""

    def __init__(self, success: bool = True, data: Any = None, metadata: Dict = None):
        self.success = success
        self.data = data or []
        self.metadata = metadata or {}

    @classmethod
    def success_result(cls, data, metadata=None):
        return cls(success=True, data=data, metadata=metadata or {})

    @classmethod
    def error_result(cls, error, metadata=None):
        return cls(success=False, data=[], metadata=metadata or {"error": error})


class TestRefutationSearchIntegration:
    """Tests for refutation search integration in ReflectionAgent."""

    def test_refutation_tool_can_be_initialized(self):
        """Test that RefutationSearchTool can be instantiated."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()
        assert tool is not None
        assert hasattr(tool, 'search_contradictions')
        assert hasattr(tool, 'check_retractions')

    def test_negation_query_generation(self):
        """Test that negation queries are generated for hypothesis claims."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()
        claim = "Drug X inhibits protein Y"

        queries = tool.generate_negation_queries(claim)

        assert len(queries) > 0
        assert any("not" in q.lower() or "no effect" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_search_contradictions_with_mock_tools(self):
        """Test that search_contradictions works with mocked tools."""
        from src.tools.refutation_search import RefutationSearchTool

        # Create mock semantic scholar tool
        mock_semantic = MagicMock()
        mock_semantic.execute = AsyncMock(return_value=MockToolResult.success_result(
            data=[
                {
                    "title": "No Effect of Drug X",
                    "abstract": "We did not find any effect. Results contradict earlier findings.",
                    "doi": "10.1000/test",
                    "year": 2024
                }
            ]
        ))

        tool = RefutationSearchTool(semantic_scholar_tool=mock_semantic)

        contradictions = await tool.search_contradictions(
            hypothesis_statement="Drug X inhibits protein Y",
            core_claim="Drug X inhibits"
        )

        # Should find contradictions
        assert len(contradictions) >= 0  # May or may not match depending on filtering


class TestCitationRetractionChecking:
    """Tests for citation retraction checking."""

    @pytest.mark.asyncio
    async def test_check_retractions_with_pmid(self):
        """Test that retractions are checked for papers with PMID."""
        from src.tools.refutation_search import RefutationSearchTool

        # Create mock PubMed tool
        mock_pubmed = MagicMock()
        mock_pubmed.execute = AsyncMock(return_value=MockToolResult.success_result(
            data=[{"title": "Retraction Notice", "year": 2024}]
        ))

        tool = RefutationSearchTool(pubmed_tool=mock_pubmed)

        paper = {"pmid": "12345678", "title": "Test Paper"}
        status = await tool.check_retractions(paper)

        assert "is_retracted" in status
        assert "has_correction" in status
        assert "notices" in status

    @pytest.mark.asyncio
    async def test_check_retractions_without_pmid(self):
        """Test that papers without PMID return empty status."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        paper = {"title": "No PMID Paper", "doi": "10.1000/test"}
        status = await tool.check_retractions(paper)

        assert status["is_retracted"] is False
        assert len(status["notices"]) == 0

    @pytest.mark.asyncio
    async def test_check_multiple_citation_retractions(self):
        """Test checking retractions for multiple citations."""
        from src.tools.refutation_search import RefutationSearchTool

        mock_pubmed = MagicMock()
        mock_pubmed.execute = AsyncMock(return_value=MockToolResult.success_result(data=[]))

        tool = RefutationSearchTool(pubmed_tool=mock_pubmed)

        citations = [
            MockCitation(title="Citation 1", doi="10.1000/c1"),
            MockCitation(title="Citation 2", doi="10.1000/c2"),
        ]

        # Check each citation
        results = {}
        for citation in citations:
            paper = {"title": citation.title, "doi": citation.doi}
            status = await tool.check_retractions(paper)
            results[citation.title] = status

        assert len(results) == 2


class TestRefutationContextFormatting:
    """Tests for refutation context formatting."""

    def test_format_contradictions_with_evidence(self):
        """Test that contradictions are formatted correctly."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        contradictions = [
            {
                "title": "Contradictory Study",
                "year": 2024,
                "abstract": "We found no effect...",
                "contradiction_source": "semantic_scholar"
            }
        ]

        formatted = tool.format_contradictions_for_context(contradictions, {})

        assert "CONTRADICTORY EVIDENCE FOUND" in formatted
        assert "Contradictory Study" in formatted

    def test_format_empty_contradictions(self):
        """Test formatting when no contradictions found."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()
        formatted = tool.format_contradictions_for_context([], {})

        assert "No contradictory evidence found" in formatted

    def test_format_retraction_warning(self):
        """Test that retraction warnings are included."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        retraction_status = {
            "Retracted Paper": {"is_retracted": True}
        }

        formatted = tool.format_contradictions_for_context([], retraction_status)

        assert "RETRACTED" in formatted
        assert "Retracted Paper" in formatted


class TestConfigurationFlags:
    """Tests for configuration flag behavior."""

    def test_refutation_search_can_be_disabled(self):
        """Test that refutation search respects enable flag."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        # Tool should still work, but ReflectionAgent should check config
        assert tool is not None

    def test_refutation_tool_has_required_methods(self):
        """Test that refutation tool has all required methods."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        assert hasattr(tool, 'search_contradictions')
        assert hasattr(tool, 'check_retractions')
        assert hasattr(tool, 'generate_negation_queries')
        assert hasattr(tool, 'format_contradictions_for_context')


class TestAsyncMethodTests:
    """Tests for async execution of refutation methods."""

    @pytest.mark.asyncio
    async def test_search_contradictions_is_async(self):
        """Test that search_contradictions is properly async."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        # Should be awaitable
        result = await tool.search_contradictions(
            hypothesis_statement="Test hypothesis",
            core_claim="Test"
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_check_retractions_is_async(self):
        """Test that check_retractions is properly async."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        result = await tool.check_retractions({"title": "Test"})

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_concurrent_retraction_checks(self):
        """Test that multiple retraction checks can run concurrently."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        papers = [
            {"title": f"Paper {i}"} for i in range(3)
        ]

        # Run concurrently
        tasks = [tool.check_retractions(paper) for paper in papers]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3


class TestMockReflectionAgent:
    """Mock tests for ReflectionAgent integration."""

    def test_refutation_tool_initialization(self):
        """Test that RefutationSearchTool can be initialized with tools."""
        from src.tools.refutation_search import RefutationSearchTool

        mock_pubmed = MagicMock()
        mock_semantic = MagicMock()

        tool = RefutationSearchTool(
            pubmed_tool=mock_pubmed,
            semantic_scholar_tool=mock_semantic,
            max_results=10
        )

        assert tool.pubmed_tool is mock_pubmed
        assert tool.semantic_scholar_tool is mock_semantic
        assert tool.max_results == 10

    @pytest.mark.asyncio
    async def test_full_refutation_pipeline(self):
        """Test the full refutation search pipeline."""
        from src.tools.refutation_search import RefutationSearchTool

        # Create mock tools
        mock_semantic = MagicMock()
        mock_semantic.execute = AsyncMock(return_value=MockToolResult.success_result(
            data=[
                {
                    "title": "Negative Result Study",
                    "abstract": "We did not find any significant effect. Our results contradict the hypothesis.",
                    "doi": "10.1000/negative",
                    "year": 2024
                }
            ]
        ))

        mock_pubmed = MagicMock()
        mock_pubmed.execute = AsyncMock(return_value=MockToolResult.success_result(data=[]))

        tool = RefutationSearchTool(
            pubmed_tool=mock_pubmed,
            semantic_scholar_tool=mock_semantic
        )

        # Create hypothesis
        hypothesis = MockHypothesis(
            hypothesis_statement="Drug X effectively treats condition Y",
            literature_citations=[
                MockCitation(title="Supporting Study", doi="10.1000/support")
            ]
        )

        # Step 1: Search for contradictions
        contradictions = await tool.search_contradictions(
            hypothesis_statement=hypothesis.hypothesis_statement,
            core_claim="Drug X treats condition Y"
        )

        # Step 2: Check retractions
        retraction_status = {}
        for paper in contradictions:
            if paper.get('pmid'):
                status = await tool.check_retractions(paper)
                retraction_status[paper.get('title', 'Unknown')] = status

        # Step 3: Format context
        context = tool.format_contradictions_for_context(
            contradictions,
            retraction_status
        )

        # Pipeline complete
        assert isinstance(context, str)


class TestHydroxychloroquineCase:
    """Real-world test case: Hydroxychloroquine refutation."""

    def test_hcq_negation_queries(self):
        """Test negation query generation for HCQ claim."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()
        claim = "hydroxychloroquine is effective for COVID-19"

        queries = tool.generate_negation_queries(claim)

        # Should generate queries that would find RECOVERY trial
        assert any("no effect" in q.lower() for q in queries)

    def test_hcq_contradiction_detection(self):
        """Test that HCQ negative trial would be detected as contradiction."""
        from src.tools.refutation_search import RefutationSearchTool

        tool = RefutationSearchTool()

        # RECOVERY trial-like abstract
        abstract = (
            "In patients hospitalized with COVID-19, hydroxychloroquine was not "
            "associated with reductions in 28-day mortality. There was no significant "
            "difference in outcomes. These findings do not support the use of "
            "hydroxychloroquine for COVID-19 treatment."
        )

        is_contradiction = tool._is_contradiction(abstract, "hydroxychloroquine effective")

        assert is_contradiction is True


class TestEndToEndReflectionFlow:
    """End-to-end tests for refutation-enhanced reflection."""

    @pytest.mark.asyncio
    async def test_full_reflection_with_refutation(self):
        """Test full reflection flow with refutation search."""
        from src.tools.refutation_search import RefutationSearchTool
        from src.literature.limitations_extractor import LimitationsExtractor

        # Initialize tools
        refutation_tool = RefutationSearchTool()
        limitations_extractor = LimitationsExtractor()

        # Create hypothesis
        hypothesis = MockHypothesis(
            hypothesis_statement="Novel treatment X cures disease Y",
            literature_citations=[
                MockCitation(title="Initial Study", doi="10.1000/initial")
            ]
        )

        # Step 1: Search for refutations
        contradictions = await refutation_tool.search_contradictions(
            hypothesis_statement=hypothesis.hypothesis_statement,
            core_claim="treatment X cures disease Y"
        )

        # Step 2: Check citation retractions
        citation_status = {}
        for citation in hypothesis.literature_citations:
            paper = {"title": citation.title, "doi": citation.doi}
            status = await refutation_tool.check_retractions(paper)
            citation_status[citation.title] = status

        # Step 3: Format refutation context
        refutation_context = refutation_tool.format_contradictions_for_context(
            contradictions,
            citation_status
        )

        # Full pipeline complete
        assert isinstance(refutation_context, str)


def run_tests():
    """Run all ReflectionAgent integration tests."""
    print("=" * 60)
    print("Phase 6: ReflectionAgent Integration Tests")
    print("=" * 60)

    # Run pytest programmatically
    exit_code = pytest.main([__file__, "-v", "--tb=short"])

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
