#!/usr/bin/env python3
"""
Phase 6: Limitations Extraction Tests

Tests for the limitations extraction system that surfaces negative results
and caveats from scientific papers to address publication bias.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from src.literature.limitations_extractor import LimitationsExtractor


class MockCitationNode:
    """Mock CitationNode for testing."""

    def __init__(
        self,
        title: str = "Test Paper",
        year: int = 2024,
        abstract: str = ""
    ):
        self.id = f"paper_{hash(title) % 10000}"
        self.title = title
        self.year = year
        self.abstract = abstract


class TestSectionParsing:
    """Tests for paper section parsing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LimitationsExtractor()

    def test_parses_markdown_sections(self):
        """Test parsing of markdown-style headers."""
        full_text = """
## Introduction

This is the introduction.

## Methods

This is the methods section.

## Results

Here are the results.

## Discussion

Discussion of findings.

## Limitations

Our study has several limitations.

## Conclusion

In conclusion...
"""

        sections = self.extractor.parse_sections(full_text)

        assert "Introduction" in sections or any("introduction" in k.lower() for k in sections)
        assert "Limitations" in sections or any("limitation" in k.lower() for k in sections)

    def test_parses_numbered_sections(self):
        """Test parsing of numbered sections."""
        full_text = """
1. Introduction

This is the introduction.

2. Methods

This is the methods section.

3. Results

Here are the results.

4. Discussion

Discussion of findings.

5. Limitations

Our study has several limitations.
"""

        sections = self.extractor.parse_sections(full_text)

        assert len(sections) >= 3

    def test_identifies_limitation_section(self):
        """Test identification of limitation sections."""
        headers_to_check = [
            ("Limitations", True),
            ("Study Limitations", True),
            ("Caveats", True),
            ("Future Work", True),
            ("Future Directions", True),
            ("Discussion", True),
            ("Conclusions", True),
            ("Methods", False),
            ("Results", False),
            ("References", False),
        ]

        for header, expected in headers_to_check:
            result = self.extractor._is_limitation_section(header)
            assert result == expected, f"Header '{header}' should be {expected}"


class TestLimitationSentenceExtraction:
    """Tests for limitation sentence extraction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LimitationsExtractor()

    def test_extracts_did_not_sentences(self):
        """Test extraction of 'did not' sentences."""
        text = (
            "The treatment showed promising results. "
            "However, we did not observe significant effects in the control group. "
            "Further analysis is needed."
        )

        limitations = self.extractor._extract_limitation_sentences(text)

        assert len(limitations) >= 1
        assert any("did not" in lim.lower() for lim in limitations)

    def test_extracts_failed_to_sentences(self):
        """Test extraction of 'failed to' sentences."""
        text = (
            "Our analysis was comprehensive. "
            "The model failed to predict outcomes in edge cases. "
            "More data would improve accuracy."
        )

        limitations = self.extractor._extract_limitation_sentences(text)

        assert len(limitations) >= 1
        assert any("failed to" in lim.lower() for lim in limitations)

    def test_extracts_however_sentences(self):
        """Test extraction of 'however' sentences."""
        text = (
            "Results were generally positive. "
            "However, the sample size was small and may not generalize. "
            "Replication is needed."
        )

        limitations = self.extractor._extract_limitation_sentences(text)

        assert len(limitations) >= 1

    def test_skips_short_fragments(self):
        """Test that short fragments are skipped."""
        text = "Yes. No. Maybe. Did not work. This is a longer sentence that should be included."

        limitations = self.extractor._extract_limitation_sentences(text)

        # Should skip fragments under 20 characters
        assert all(len(lim) >= 20 for lim in limitations)

    def test_extracts_multiple_limitation_phrases(self):
        """Test extraction with multiple limitation phrases."""
        text = (
            "Our study had several limitations. "
            "First, we were unable to control for all confounding variables. "
            "Second, the sample size was insufficient to detect small effects. "
            "Third, further research is needed to confirm these findings. "
            "Finally, our results may not generalize to other populations."
        )

        limitations = self.extractor._extract_limitation_sentences(text)

        # Should extract multiple limitation sentences
        assert len(limitations) >= 3


class TestConfidenceScoring:
    """Tests for confidence scoring."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LimitationsExtractor()

    def test_high_confidence_for_explicit_section(self):
        """Test high confidence when explicit Limitations section found."""
        paper = MockCitationNode(title="Test Paper")

        full_text = """
## Introduction

Study introduction.

## Limitations

This study has several key limitations that should be noted.
First, we did not have access to long-term follow-up data.
Second, the sample size was relatively small.
Third, we could not control for all potential confounders.
Fourth, our findings may not generalize to other settings.
Fifth, further research is needed to validate these results.
"""

        result = self.extractor.extract_limitations(paper, full_text)

        # Should have high confidence with explicit section and many limitations
        assert result["confidence"] >= 0.5
        assert len(result["limitations"]) >= 3

    def test_low_confidence_without_section(self):
        """Test lower confidence when no explicit limitations section."""
        paper = MockCitationNode(title="Test Paper")

        full_text = """
## Introduction

Study introduction with no limitation section.

## Methods

Standard methods were used.

## Results

Results were positive. However, we did not observe effects in all cases.
"""

        result = self.extractor.extract_limitations(paper, full_text)

        # Should have lower confidence without explicit section
        assert result["confidence"] < 0.5


class TestFullExtraction:
    """Tests for full limitations extraction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LimitationsExtractor()

    def test_extract_from_crispr_paper(self):
        """Test extraction from CRISPR paper example."""
        paper = MockCitationNode(
            title="CRISPR/Cas9 editing efficiency in primary T cells",
            year=2023
        )

        # Use text with clear negative phrase patterns
        full_text = """
## Abstract

We investigated CRISPR/Cas9 editing in primary T cells.

## Results

Editing was achieved in activated T cells with 70% efficiency.

## Discussion

Our results demonstrate potential for therapeutic applications.

## Limitations

Our study has several important limitations:

1. We were unable to achieve high editing efficiency in resting T cells, limiting clinical applicability.
2. Off-target effects were detected and we could not eliminate them at 3 genomic loci.
3. The method could not be validated in CD4+ cells due to technical limitations.
4. Further research is needed for in vivo delivery optimization.
5. However, these results were obtained in vitro and require validation in animal models.

## Conclusions

CRISPR editing shows promise but requires further development.
"""

        result = self.extractor.extract_limitations(paper, full_text)

        # Should extract at least 2 limitations (could not, however, unable to, further research needed)
        assert len(result["limitations"]) >= 2
        assert result["confidence"] >= 0.5

        # Should include specific limitations with negative phrases
        limitations_text = " ".join(result["limitations"])
        assert any(phrase in limitations_text.lower() for phrase in ["could not", "however", "unable to"])

    def test_extract_from_abstract_fallback(self):
        """Test extraction from abstract when no full text."""
        paper = MockCitationNode(
            title="Test Paper",
            year=2024,
            abstract=(
                "We conducted a randomized trial. Results were positive. "
                "However, the small sample size limits generalizability. "
                "Further research is needed to confirm findings."
            )
        )

        result = self.extractor.extract_from_abstract(paper)

        # Should extract from abstract
        assert len(result["limitations"]) >= 1
        # Lower confidence for abstract-only
        assert result["confidence"] <= 0.5


class TestContextFormatting:
    """Tests for formatting limitations for LLM context."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LimitationsExtractor()

    def test_formats_single_paper(self):
        """Test formatting of single paper limitations."""
        paper = MockCitationNode(
            title="Important Study",
            year=2024
        )

        limitations_data = {
            "limitations": [
                "Sample size was small",
                "Follow-up period was short",
                "Could not control for confounders"
            ],
            "confidence": 0.8
        }

        formatted = self.extractor.format_for_context(paper, limitations_data)

        assert "Important Study" in formatted
        assert "2024" in formatted
        assert "[KNOWN LIMITATIONS]" in formatted
        assert "Sample size was small" in formatted

    def test_empty_limitations_returns_empty_string(self):
        """Test that empty limitations return empty string."""
        paper = MockCitationNode(title="No Limitations Paper")

        limitations_data = {
            "limitations": [],
            "confidence": 0.0
        }

        formatted = self.extractor.format_for_context(paper, limitations_data)

        assert formatted == ""


class TestBatchExtraction:
    """Tests for batch limitations extraction."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LimitationsExtractor()

    def test_batch_extract_multiple_papers(self):
        """Test batch extraction from multiple papers."""
        papers = [
            MockCitationNode(
                title="Paper 1",
                abstract="Results were promising. However, we could not replicate in vitro."
            ),
            MockCitationNode(
                title="Paper 2",
                abstract="Findings were significant with no apparent limitations mentioned."
            ),
            MockCitationNode(
                title="Paper 3",
                abstract="Study was limited by small sample size. Further research is needed."
            ),
        ]

        results = self.extractor.batch_extract(papers)

        assert len(results) == 3
        # At least some should have limitations
        papers_with_limitations = sum(
            1 for data in results.values()
            if data.get("limitations")
        )
        assert papers_with_limitations >= 1


class TestKnownFailureDetection:
    """Tests for detecting known failures."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = LimitationsExtractor()

    def test_detects_protocol_failure(self):
        """Test detection of explicit protocol failure."""
        paper = MockCitationNode(title="PCR Optimization Study")

        full_text = """
## Methods

We tested multiple PCR protocols.

## Results

Protocol A was successful.

## Limitations

Protocol X failed to amplify Gene Y due to high GC content.
We were unable to optimize conditions for this target.
Standard approaches did not work for this specific sequence.
"""

        result = self.extractor.extract_limitations(paper, full_text)

        # Should detect the failure
        assert len(result["limitations"]) >= 1
        limitations_text = " ".join(result["limitations"]).lower()
        assert "failed" in limitations_text or "unable" in limitations_text or "did not" in limitations_text


def run_tests():
    """Run all limitations extraction tests."""
    print("=" * 60)
    print("Phase 6: Limitations Extraction Tests")
    print("=" * 60)

    # Run pytest programmatically
    exit_code = pytest.main([__file__, "-v", "--tb=short"])

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
