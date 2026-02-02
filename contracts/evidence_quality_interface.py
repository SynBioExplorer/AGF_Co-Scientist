"""
Contract: EvidenceQualityEnhancementProtocol
Version: 31f3178 (commit hash when contract was created)
Generated: 2026-02-02T12:00:00Z

Defines the interface for Phase 6 evidence quality enhancement integration
into the Generation and Reflection agents.

This contract enables parallel development of:
- Task A: GenerationAgent integration (quality scoring + limitations)
- Task B: ReflectionAgent integration (refutation search + retraction checking)
"""

from typing import Protocol, List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class QualityEnrichedPaper:
    """Paper with Phase 6 quality enrichment data."""
    paper_id: str
    title: str
    quality_score: float
    quality_label: str  # "HIGH", "MEDIUM", "LOW"
    is_retracted: bool
    retraction_notices: List[str]
    known_limitations: List[str]
    limitations_confidence: float


@dataclass
class RefutationEvidence:
    """Evidence that contradicts or challenges a hypothesis."""
    paper_title: str
    paper_doi: Optional[str]
    paper_year: Optional[int]
    contradiction_type: str  # "contradictory", "replication_failure", "retracted"
    abstract_snippet: str
    relevance_score: float


class PaperQualityScorerProtocol(Protocol):
    """Protocol for paper quality scoring in GenerationAgent."""

    def compute_quality_score(self, paper: Any) -> float:
        """
        Compute multi-factor quality score for a paper.

        Args:
            paper: CitationNode object with citation_count, year, venue

        Returns:
            Quality score between 0.0 and 1.0
        """
        ...

    def rank_papers_by_quality(
        self,
        papers: List[Any],
        top_k: int = 20
    ) -> List[Any]:
        """
        Rank papers by quality score and return top-k.

        Args:
            papers: List of CitationNode objects
            top_k: Maximum papers to return

        Returns:
            Sorted list of highest quality papers
        """
        ...

    def filter_by_quality(
        self,
        papers: List[Any],
        min_score: Optional[float] = None
    ) -> List[Any]:
        """
        Filter papers below minimum quality threshold.

        Args:
            papers: List of papers to filter
            min_score: Minimum quality (uses default if None)

        Returns:
            Filtered list of papers
        """
        ...

    def get_quality_label(self, score: float) -> str:
        """
        Convert quality score to label.

        Args:
            score: Quality score 0.0-1.0

        Returns:
            "HIGH", "MEDIUM", or "LOW"
        """
        ...

    def format_quality_context(
        self,
        papers: List[Any],
        max_papers: int = 20
    ) -> str:
        """
        Format papers with quality labels for LLM context.

        Args:
            papers: Papers to format
            max_papers: Maximum to include

        Returns:
            Formatted string with quality labels
        """
        ...


class LimitationsExtractorProtocol(Protocol):
    """Protocol for limitations extraction in GenerationAgent."""

    def extract_from_abstract(self, paper: Any) -> Dict[str, Any]:
        """
        Extract limitations from paper abstract (fallback).

        Args:
            paper: CitationNode with abstract

        Returns:
            Dict with 'limitations' list and 'confidence' float
        """
        ...

    def batch_extract(
        self,
        papers: List[Any],
        full_texts: Optional[Dict[str, str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract limitations from multiple papers.

        Args:
            papers: List of papers
            full_texts: Optional full text map

        Returns:
            Dict mapping paper ID to limitations data
        """
        ...

    def format_batch_for_context(
        self,
        papers: List[Any],
        limitations_data: Dict[str, Dict[str, Any]],
        min_confidence: Optional[float] = None
    ) -> str:
        """
        Format limitations for LLM context.

        Args:
            papers: Papers to format
            limitations_data: Extraction results
            min_confidence: Minimum confidence threshold

        Returns:
            Formatted string for LLM prompt
        """
        ...


class RefutationSearchProtocol(Protocol):
    """Protocol for refutation search in ReflectionAgent."""

    async def search_contradictions(
        self,
        hypothesis_statement: str,
        core_claim: str
    ) -> List[Dict[str, Any]]:
        """
        Search for contradictory evidence.

        Args:
            hypothesis_statement: Full hypothesis text
            core_claim: Extracted core claim to negate

        Returns:
            List of contradictory papers
        """
        ...

    async def check_retractions(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check PubMed for retraction status.

        Args:
            paper: Paper dict with 'pmid' field

        Returns:
            Dict with is_retracted, has_correction, notices
        """
        ...

    def format_contradictions_for_context(
        self,
        contradictions: List[Dict[str, Any]],
        retraction_status: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Format contradictions for LLM context.

        Args:
            contradictions: Contradictory papers
            retraction_status: Retraction info by paper

        Returns:
            Formatted warning string
        """
        ...


class GenerationAgentEvidenceProtocol(Protocol):
    """
    Protocol for enhanced GenerationAgent with Phase 6 evidence quality.

    Implementers must:
    1. Score and rank papers before including in context
    2. Include quality labels (HIGH/MEDIUM/LOW) in prompts
    3. Extract and include limitations from papers
    4. Filter out low-quality/retracted sources
    """

    async def _enrich_papers_with_quality(
        self,
        papers: List[Any]
    ) -> List[Any]:
        """
        Enrich papers with quality scores and filter low-quality.

        Args:
            papers: Raw papers from search

        Returns:
            Quality-enriched papers, filtered and ranked
        """
        ...

    async def _extract_paper_limitations(
        self,
        papers: List[Any]
    ) -> str:
        """
        Extract limitations from papers for context.

        Args:
            papers: Papers to extract limitations from

        Returns:
            Formatted limitations context string
        """
        ...

    def _format_quality_enriched_context(
        self,
        papers: List[Any],
        limitations_context: str
    ) -> str:
        """
        Format papers with quality labels and limitations for LLM.

        Args:
            papers: Quality-scored papers
            limitations_context: Extracted limitations

        Returns:
            Complete formatted context for prompt
        """
        ...


class ReflectionAgentEvidenceProtocol(Protocol):
    """
    Protocol for enhanced ReflectionAgent with Phase 6 evidence quality.

    Implementers must:
    1. Search for contradictory evidence
    2. Check retraction status of citations
    3. Evaluate against known limitations
    4. Include counter-evidence in review
    """

    async def _search_for_refutation(
        self,
        hypothesis: Any
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Search for evidence that contradicts the hypothesis.

        Args:
            hypothesis: Hypothesis object to refute

        Returns:
            Tuple of (contradictions list, retraction_status dict)
        """
        ...

    async def _check_citation_retractions(
        self,
        hypothesis: Any
    ) -> Dict[str, Dict[str, Any]]:
        """
        Check if any supporting citations have been retracted.

        Args:
            hypothesis: Hypothesis with literature_citations

        Returns:
            Dict mapping citation title to retraction status
        """
        ...

    def _format_refutation_context(
        self,
        contradictions: List[Dict[str, Any]],
        retraction_status: Dict[str, Dict[str, Any]],
        limitations_context: str
    ) -> str:
        """
        Format all refutation evidence for LLM review.

        Args:
            contradictions: Found contradictory papers
            retraction_status: Citation retraction info
            limitations_context: Known limitations from literature

        Returns:
            Complete refutation context string
        """
        ...
