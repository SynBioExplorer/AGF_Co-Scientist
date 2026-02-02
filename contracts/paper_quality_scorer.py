"""
Contract: PaperQualityScorerProtocol
Version: 31f3178 (commit hash when contract was created)
Generated: 2026-02-02T10:00:00Z

Multi-factor paper quality scoring for prioritizing high-quality evidence.
Combines citation count, recency (exponential decay), and journal impact.
"""
from typing import Protocol, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.literature.citation_graph import CitationNode


class PaperQualityScorerProtocol(Protocol):
    """
    Protocol for computing multi-factor quality scores for scientific papers.

    Quality Score Formula:
        quality = w1 * citation_score + w2 * recency_score + w3 * journal_score - penalties

    Where:
        - w1 = 0.5 (citation weight)
        - w2 = 0.3 (recency weight)
        - w3 = 0.2 (journal weight)
        - citation_score = min(1.0, citation_count / 500)
        - recency_score = 0.5 ** (years_old / 5.0)  # half-life of 5 years
        - journal_score = SJR score normalized to 0-1 (or 0.5 default)
        - penalties = retraction penalty, predatory journal penalty

    Quality Labels:
        - HIGH: score > 0.7
        - MEDIUM: 0.4 <= score <= 0.7
        - LOW: score < 0.4
    """

    def compute_quality_score(self, paper: "CitationNode") -> float:
        """
        Compute multi-factor quality score for a paper.

        Args:
            paper: CitationNode with citation_count, year, and optional journal info

        Returns:
            Quality score between 0.0 and 1.0

        Example:
            >>> scorer = PaperQualityScorer()
            >>> score = scorer.compute_quality_score(paper)
            >>> assert 0.0 <= score <= 1.0
        """
        ...

    def rank_papers_by_quality(
        self,
        papers: List["CitationNode"],
        top_k: int = 20
    ) -> List["CitationNode"]:
        """
        Rank papers by quality score and return top-k.

        Args:
            papers: List of CitationNode objects to rank
            top_k: Maximum number of papers to return (default 20)

        Returns:
            List of top-k papers sorted by quality score (descending)

        Notes:
            - Papers are scored using compute_quality_score()
            - Original paper objects are returned (not copies)
            - If len(papers) < top_k, all papers are returned
        """
        ...

    def get_quality_label(self, score: float) -> str:
        """
        Convert quality score to human-readable label.

        Args:
            score: Quality score between 0.0 and 1.0

        Returns:
            One of: "HIGH", "MEDIUM", "LOW"

        Thresholds:
            - HIGH: score > 0.7
            - MEDIUM: 0.4 <= score <= 0.7
            - LOW: score < 0.4
        """
        ...


# Type alias for implementations
PaperQualityScorer = PaperQualityScorerProtocol
