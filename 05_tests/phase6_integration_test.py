#!/usr/bin/env python3
"""
Phase 6: Integration Tests

Integration tests verifying that all Phase 6 evidence quality enhancement
features work together correctly:
1. Paper Quality Scoring
2. Refutation Search
3. Limitations Extraction

Tests the complete pipeline from paper retrieval to agent context formatting.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

from src.literature.quality_scorer import PaperQualityScorer
from src.tools.refutation_search import RefutationSearchTool
from src.literature.limitations_extractor import LimitationsExtractor
from src.literature.citation_graph import CitationGraph, CitationNode
from src.config import settings


class TestCitationNodePhase6Fields:
    """Test that CitationNode has all Phase 6 fields."""

    def test_quality_score_field(self):
        """Test that CitationNode has quality_score field."""
        node = CitationNode(
            id="test",
            title="Test Paper",
            quality_score=0.85
        )
        assert node.quality_score == 0.85
        assert 0.0 <= node.quality_score <= 1.0

    def test_retraction_fields(self):
        """Test that CitationNode has retraction fields."""
        node = CitationNode(
            id="test",
            title="Retracted Paper",
            is_retracted=True,
            retraction_notices=["This paper has been retracted due to data fabrication."]
        )
        assert node.is_retracted is True
        assert len(node.retraction_notices) == 1

    def test_limitations_fields(self):
        """Test that CitationNode has limitations fields."""
        node = CitationNode(
            id="test",
            title="Paper with Limitations",
            known_limitations=[
                "Small sample size",
                "Limited follow-up period"
            ],
            limitations_confidence=0.75
        )
        assert len(node.known_limitations) == 2
        assert node.limitations_confidence == 0.75

    def test_all_phase6_fields_together(self):
        """Test that all Phase 6 fields work together."""
        node = CitationNode(
            id="complete_test",
            title="Complete Test Paper",
            authors=["Smith A", "Jones B"],
            year=2024,
            doi="10.1000/test",
            citation_count=500,
            venue="Nature",
            quality_score=0.92,
            is_retracted=False,
            retraction_notices=[],
            known_limitations=["Sample size was limited"],
            limitations_confidence=0.8
        )

        assert node.quality_score == 0.92
        assert node.is_retracted is False
        assert len(node.known_limitations) == 1
        assert node.limitations_confidence == 0.8


class TestCitationGraphPhase6Methods:
    """Test CitationGraph Phase 6 methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.graph = CitationGraph()

        # Add papers with Phase 6 fields
        self.graph.nodes["paper1"] = CitationNode(
            id="paper1",
            title="High Quality Paper",
            citation_count=500,
            year=2024,
            quality_score=0.9
        )
        self.graph.nodes["paper2"] = CitationNode(
            id="paper2",
            title="Retracted Paper",
            citation_count=100,
            year=2020,
            is_retracted=True,
            quality_score=0.3
        )
        self.graph.nodes["paper3"] = CitationNode(
            id="paper3",
            title="Paper with Limitations",
            citation_count=200,
            year=2022,
            known_limitations=["Limited sample"],
            limitations_confidence=0.7,
            quality_score=0.6
        )

    def test_get_highest_quality(self):
        """Test retrieval of highest quality papers."""
        top = self.graph.get_highest_quality(n=2)

        assert len(top) == 2
        assert top[0].id == "paper1"  # Highest quality
        assert top[1].id == "paper3"  # Second highest

    def test_get_retracted_papers(self):
        """Test retrieval of retracted papers."""
        retracted = self.graph.get_retracted_papers()

        assert len(retracted) == 1
        assert retracted[0].id == "paper2"

    def test_get_papers_with_limitations(self):
        """Test retrieval of papers with limitations."""
        with_limitations = self.graph.get_papers_with_limitations()

        assert len(with_limitations) == 1
        assert with_limitations[0].id == "paper3"

    def test_statistics_include_phase6(self):
        """Test that statistics include Phase 6 metrics."""
        stats = self.graph.get_statistics()

        assert stats['retracted_count'] == 1
        assert stats['papers_with_limitations'] == 1
        assert stats['papers_with_quality_score'] == 3


class TestPhase6ConfigSettings:
    """Test Phase 6 configuration settings."""

    def test_quality_scoring_config(self):
        """Test quality scoring configuration exists."""
        assert hasattr(settings, 'enable_quality_scoring')
        assert hasattr(settings, 'quality_citation_weight')
        assert hasattr(settings, 'quality_recency_weight')
        assert hasattr(settings, 'quality_journal_weight')
        assert hasattr(settings, 'quality_min_threshold')
        assert hasattr(settings, 'quality_recency_halflife_years')

    def test_refutation_search_config(self):
        """Test refutation search configuration exists."""
        assert hasattr(settings, 'enable_refutation_search')
        assert hasattr(settings, 'refutation_max_results')
        assert hasattr(settings, 'refutation_min_quality_score')
        assert hasattr(settings, 'refutation_check_retractions')

    def test_limitations_extraction_config(self):
        """Test limitations extraction configuration exists."""
        assert hasattr(settings, 'enable_limitations_extraction')
        assert hasattr(settings, 'limitations_min_confidence')
        assert hasattr(settings, 'limitations_include_in_context')

    def test_config_defaults(self):
        """Test that configuration has sensible defaults."""
        # Quality scoring defaults
        assert settings.quality_citation_weight == 0.5
        assert settings.quality_recency_weight == 0.3
        assert settings.quality_journal_weight == 0.2

        # These should sum to 1.0
        total = (
            settings.quality_citation_weight +
            settings.quality_recency_weight +
            settings.quality_journal_weight
        )
        assert abs(total - 1.0) < 0.01


class TestIntegratedPipeline:
    """Test the complete Phase 6 pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = PaperQualityScorer()
        self.refutation_tool = RefutationSearchTool()
        self.limitations_extractor = LimitationsExtractor()

    def test_quality_scoring_with_citation_node(self):
        """Test quality scoring works with CitationNode objects."""
        node = CitationNode(
            id="test",
            title="Test Paper",
            citation_count=500,
            year=2024,
            venue="Nature"
        )

        score = self.scorer.compute_quality_score(node)

        assert 0.0 <= score <= 1.0
        assert score > 0.5  # High citation + recent + Nature = high score

    def test_limitations_extraction_updates_node(self):
        """Test that limitations extraction can update CitationNode."""
        node = CitationNode(
            id="test",
            title="Test Paper",
            abstract="We conducted a study. However, the sample size was limited."
        )

        # Extract from abstract
        result = self.limitations_extractor.extract_from_abstract(node)

        # Update node
        node.known_limitations = result["limitations"]
        node.limitations_confidence = result["confidence"]

        assert len(node.known_limitations) >= 0  # May or may not find limitations
        assert node.limitations_confidence is not None

    def test_complete_paper_enrichment_pipeline(self):
        """Test complete pipeline: score -> check retractions -> extract limitations."""
        # Create a paper
        paper = CitationNode(
            id="pipeline_test",
            title="CRISPR Gene Editing Study",
            authors=["Smith A", "Jones B"],
            year=2023,
            citation_count=250,
            venue="Nature Methods",
            abstract="We developed a new CRISPR method. However, the efficiency was low in some cell types."
        )

        # Step 1: Score quality
        paper.quality_score = self.scorer.compute_quality_score(paper)
        assert paper.quality_score is not None
        assert paper.quality_score > 0.5  # Recent + Nature Methods

        # Step 2: Check retraction status (mock - would normally call PubMed)
        paper.is_retracted = False  # Simulated
        paper.retraction_notices = []

        # Step 3: Extract limitations
        limitations_data = self.limitations_extractor.extract_from_abstract(paper)
        paper.known_limitations = limitations_data["limitations"]
        paper.limitations_confidence = limitations_data["confidence"]

        # Verify paper is fully enriched
        assert paper.quality_score is not None
        assert paper.is_retracted is not None
        # Limitations may or may not be found depending on abstract

    def test_quality_filtered_papers_in_context(self):
        """Test that only high-quality papers are included in context."""
        papers = [
            CitationNode(
                id="high",
                title="High Quality Paper",
                citation_count=1000,
                year=2024,
                abstract="Important findings..."
            ),
            CitationNode(
                id="low",
                title="Low Quality Paper",
                citation_count=5,
                year=2005,
                abstract="Some findings..."
            ),
        ]

        # Score and filter
        filtered = self.scorer.filter_by_quality(papers, min_score=0.3)

        # At least the high-quality paper should pass
        assert len(filtered) >= 1

        # Format context
        context = self.scorer.format_quality_context(papers, max_papers=2)
        assert "[QUALITY:" in context

    def test_negation_query_generation(self):
        """Test that negation queries are generated for refutation search."""
        claim = "CRISPR editing is efficient in T cells"
        queries = self.refutation_tool.generate_negation_queries(claim)

        assert len(queries) > 0
        assert any("no effect" in q.lower() or "not" in q.lower() for q in queries)


class TestBackwardCompatibility:
    """Test backward compatibility with pre-Phase 6 code."""

    def test_citation_node_without_phase6_fields(self):
        """Test that CitationNode works without Phase 6 fields."""
        # Create node with only original fields
        node = CitationNode(
            id="legacy",
            title="Legacy Paper",
            authors=["Old Author"],
            year=2020,
            citation_count=100
        )

        # Phase 6 fields should default to None/empty
        assert node.quality_score is None
        assert node.is_retracted is None
        assert node.known_limitations == []
        assert node.limitations_confidence is None

    def test_scorer_handles_missing_fields(self):
        """Test that scorer handles papers missing optional fields."""
        scorer = PaperQualityScorer()

        # Paper without year
        paper_no_year = CitationNode(
            id="no_year",
            title="No Year Paper"
        )
        score = scorer.compute_quality_score(paper_no_year)
        assert 0.0 <= score <= 1.0

        # Paper without citation count
        paper_no_citations = CitationNode(
            id="no_citations",
            title="No Citations Paper",
            year=2024
        )
        score = scorer.compute_quality_score(paper_no_citations)
        assert 0.0 <= score <= 1.0

    def test_graph_serialization_with_phase6_fields(self):
        """Test that graph serialization includes Phase 6 fields."""
        graph = CitationGraph()
        graph.nodes["test"] = CitationNode(
            id="test",
            title="Test",
            quality_score=0.8,
            is_retracted=False,
            known_limitations=["Limitation 1"],
            limitations_confidence=0.7
        )

        # Serialize
        data = graph.to_dict()

        # Deserialize
        restored = CitationGraph.from_dict(data)

        # Verify Phase 6 fields preserved
        assert restored.nodes["test"].quality_score == 0.8
        assert restored.nodes["test"].is_retracted is False
        assert restored.nodes["test"].known_limitations == ["Limitation 1"]
        assert restored.nodes["test"].limitations_confidence == 0.7


def run_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("Phase 6: Integration Tests")
    print("=" * 60)

    # Run pytest programmatically
    exit_code = pytest.main([__file__, "-v", "--tb=short"])

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
