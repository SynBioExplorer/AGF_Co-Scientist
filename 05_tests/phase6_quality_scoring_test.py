#!/usr/bin/env python3
"""
Phase 6: Paper Quality Scoring Tests

Tests for the multi-factor quality scoring system that prioritizes
high-quality evidence in hypothesis generation and review.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from src.literature.quality_scorer import PaperQualityScorer


class MockCitationNode:
    """Mock CitationNode for testing."""

    def __init__(
        self,
        title: str = "Test Paper",
        citation_count: int = 100,
        year: int = 2024,
        authors: list = None,
        venue: str = "",
        abstract: str = "",
        is_retracted: bool = False
    ):
        self.id = f"paper_{hash(title) % 10000}"
        self.title = title
        self.citation_count = citation_count
        self.year = year
        self.authors = authors or ["Author A", "Author B"]
        self.venue = venue
        self.abstract = abstract
        self.is_retracted = is_retracted
        self.quality_score = None


class TestPaperQualityScorer:
    """Tests for PaperQualityScorer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = PaperQualityScorer()

    def test_citation_score_normalization(self):
        """Test that citation scores are normalized correctly."""
        # Low citations
        paper_low = MockCitationNode(citation_count=10)
        score_low = self.scorer.compute_quality_score(paper_low)

        # Medium citations
        paper_med = MockCitationNode(citation_count=250)
        score_med = self.scorer.compute_quality_score(paper_med)

        # High citations (at normalization threshold)
        paper_high = MockCitationNode(citation_count=500)
        score_high = self.scorer.compute_quality_score(paper_high)

        # Very high citations (above threshold)
        paper_very_high = MockCitationNode(citation_count=1000)
        score_very_high = self.scorer.compute_quality_score(paper_very_high)

        # Scores should increase with citations
        assert score_low < score_med < score_high
        # But cap at max
        assert score_high <= score_very_high
        # All scores in valid range
        assert 0.0 <= score_low <= 1.0
        assert 0.0 <= score_very_high <= 1.0

    def test_recency_scoring(self):
        """Test that recency scoring uses exponential decay."""
        # Recent paper (2024)
        paper_recent = MockCitationNode(year=2024, citation_count=100)
        score_recent = self.scorer.compute_quality_score(paper_recent)

        # 5 years old (2019) - should be ~half recency score
        paper_5yr = MockCitationNode(year=2019, citation_count=100)
        score_5yr = self.scorer.compute_quality_score(paper_5yr)

        # 10 years old (2014) - should be ~quarter recency score
        paper_10yr = MockCitationNode(year=2014, citation_count=100)
        score_10yr = self.scorer.compute_quality_score(paper_10yr)

        # Old paper (2004) - low recency score
        paper_old = MockCitationNode(year=2004, citation_count=100)
        score_old = self.scorer.compute_quality_score(paper_old)

        # Recent papers should score higher
        assert score_recent > score_5yr > score_10yr > score_old

    def test_old_high_citation_vs_recent_moderate_citation(self):
        """Test that recency balances against high citations."""
        # Old paper with very high citations
        paper_old_high = MockCitationNode(year=2010, citation_count=1000)
        score_old_high = self.scorer.compute_quality_score(paper_old_high)

        # Recent paper with moderate citations
        paper_recent_mod = MockCitationNode(year=2024, citation_count=500)
        score_recent_mod = self.scorer.compute_quality_score(paper_recent_mod)

        # With default weights (0.5 citation, 0.3 recency), recent with 500 citations
        # should be competitive with old paper with 1000 citations
        # Both should be high quality
        assert score_old_high > 0.5
        assert score_recent_mod > 0.5

    def test_quality_filtering(self):
        """Test that low-quality papers are filtered correctly."""
        papers = [
            MockCitationNode(title="High Quality", citation_count=500, year=2024),
            MockCitationNode(title="Medium Quality", citation_count=100, year=2020),
            MockCitationNode(title="Low Quality", citation_count=5, year=2005),
        ]

        # Filter with default threshold (0.3)
        filtered = self.scorer.filter_by_quality(papers)

        # Should exclude very low quality papers
        assert len(filtered) >= 2
        titles = [p.title for p in filtered]
        assert "High Quality" in titles
        assert "Medium Quality" in titles

    def test_quality_ranking(self):
        """Test that papers are ranked correctly by quality."""
        papers = [
            MockCitationNode(title="Low", citation_count=10, year=2015),
            MockCitationNode(title="High", citation_count=500, year=2024),
            MockCitationNode(title="Medium", citation_count=100, year=2020),
        ]

        ranked = self.scorer.rank_papers_by_quality(papers, top_k=3)

        # High should be first
        assert ranked[0].title == "High"
        # Low should be last
        assert ranked[-1].title == "Low"

    def test_quality_labels(self):
        """Test quality label assignment."""
        assert self.scorer.get_quality_label(0.8) == "HIGH"
        assert self.scorer.get_quality_label(0.7) == "MEDIUM"  # Boundary
        assert self.scorer.get_quality_label(0.5) == "MEDIUM"
        assert self.scorer.get_quality_label(0.4) == "MEDIUM"  # Boundary
        assert self.scorer.get_quality_label(0.3) == "LOW"
        assert self.scorer.get_quality_label(0.1) == "LOW"

    def test_llm_context_quality_labels(self):
        """Test that quality labels appear in formatted context."""
        papers = [
            MockCitationNode(
                title="Important CRISPR Study",
                citation_count=1000,
                year=2024,
                authors=["Smith A", "Jones B"],
                abstract="We demonstrate a novel CRISPR technique...",
                venue="Nature"
            ),
            MockCitationNode(
                title="Low Tier Journal Paper",
                citation_count=5,
                year=2010,
                authors=["Unknown X"],
                abstract="Some results about something...",
                venue="Obscure Journal"
            ),
        ]

        context = self.scorer.format_quality_context(papers, max_papers=2)

        # Should include quality labels
        assert "[QUALITY: HIGH]" in context or "[QUALITY: MEDIUM]" in context
        assert "Important CRISPR Study" in context

    def test_retracted_paper_penalty(self):
        """Test that retracted papers receive penalty."""
        paper_normal = MockCitationNode(citation_count=500, year=2024)
        paper_retracted = MockCitationNode(
            citation_count=500,
            year=2024,
            is_retracted=True
        )

        score_normal = self.scorer.compute_quality_score(paper_normal)
        score_retracted = self.scorer.compute_quality_score(paper_retracted)

        # Retracted paper should score lower
        assert score_retracted < score_normal
        # Significant penalty
        assert score_normal - score_retracted >= 0.3

    def test_missing_year_handling(self):
        """Test handling of papers with missing year."""
        paper_no_year = MockCitationNode(citation_count=100, year=None)

        score = self.scorer.compute_quality_score(paper_no_year)

        # Should still compute a valid score
        assert 0.0 <= score <= 1.0

    def test_high_impact_journal_boost(self):
        """Test that high-impact journals receive boost."""
        # Use a clear high-impact journal name
        paper_nature = MockCitationNode(
            title="Study on Gene Expression",
            citation_count=100,
            year=2024,
            venue="Nature"
        )
        # Use a journal name that doesn't match any high-impact keywords
        paper_unknown = MockCitationNode(
            title="Study on Gene Expression",
            citation_count=100,
            year=2024,
            venue="Regional Journal of Biology"
        )

        score_nature = self.scorer.compute_quality_score(paper_nature)
        score_unknown = self.scorer.compute_quality_score(paper_unknown)

        # Nature paper should score higher
        assert score_nature > score_unknown

    def test_top_k_limiting(self):
        """Test that rank_papers_by_quality respects top_k limit."""
        papers = [MockCitationNode(title=f"Paper {i}") for i in range(10)]

        ranked = self.scorer.rank_papers_by_quality(papers, top_k=3)

        assert len(ranked) == 3

    def test_empty_papers_list(self):
        """Test handling of empty papers list."""
        ranked = self.scorer.rank_papers_by_quality([], top_k=10)
        assert ranked == []

        filtered = self.scorer.filter_by_quality([])
        assert filtered == []


def run_tests():
    """Run all quality scoring tests."""
    print("=" * 60)
    print("Phase 6: Paper Quality Scoring Tests")
    print("=" * 60)

    # Run pytest programmatically
    exit_code = pytest.main([__file__, "-v", "--tb=short"])

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
