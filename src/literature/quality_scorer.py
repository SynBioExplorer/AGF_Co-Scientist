"""
Paper Quality Scoring - Phase 6 Feature

Multi-factor quality scoring for prioritizing high-quality evidence in hypothesis
generation and review. Combines citation count, recency, and journal impact.

Quality Score Formula:
    quality = w1 * citation_score + w2 * recency_score + w3 * journal_score - penalties

Where:
    - w1 = 0.5 (citation weight)
    - w2 = 0.3 (recency weight)
    - w3 = 0.2 (journal weight)
    - citation_score = min(1.0, citation_count / 500)
    - recency_score = 0.5 ** (years_old / 5.0)  # half-life of 5 years
    - journal_score = SJR score normalized to 0-1 (or 0.5 default)

Reference: 03_architecture/Phase6/phase6_paper_quality_scoring.md
"""

from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
import structlog

if TYPE_CHECKING:
    from src.literature.citation_graph import CitationNode

logger = structlog.get_logger()

# Current year for recency calculation
CURRENT_YEAR = datetime.now().year


class PaperQualityScorer:
    """
    Compute multi-factor quality scores for scientific papers.

    Prioritizes papers that are:
    - Highly cited (normalized by field/year)
    - Recent (exponential decay with half-life of 5 years)
    - Published in high-impact journals

    Penalizes papers that are:
    - Retracted
    - From predatory journals
    """

    def __init__(
        self,
        citation_weight: float = 0.5,
        recency_weight: float = 0.3,
        journal_weight: float = 0.2,
        recency_halflife_years: int = 5,
        citation_normalization: int = 500,
        min_threshold: float = 0.3
    ):
        """
        Initialize the quality scorer.

        Args:
            citation_weight: Weight for citation score (default 0.5)
            recency_weight: Weight for recency score (default 0.3)
            journal_weight: Weight for journal impact score (default 0.2)
            recency_halflife_years: Half-life for recency decay (default 5 years)
            citation_normalization: Citation count for max score (default 500)
            min_threshold: Minimum quality threshold for filtering (default 0.3)
        """
        self.citation_weight = citation_weight
        self.recency_weight = recency_weight
        self.journal_weight = journal_weight
        self.recency_halflife_years = recency_halflife_years
        self.citation_normalization = citation_normalization
        self.min_threshold = min_threshold

        # Validate weights sum to 1.0
        total_weight = citation_weight + recency_weight + journal_weight
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(
                "Quality score weights do not sum to 1.0",
                total=total_weight,
                citation=citation_weight,
                recency=recency_weight,
                journal=journal_weight
            )

    def compute_quality_score(self, paper: "CitationNode") -> float:
        """
        Compute multi-factor quality score for a paper.

        Args:
            paper: CitationNode with citation_count, year, and optional journal info

        Returns:
            Quality score between 0.0 and 1.0
        """
        # Citation score (normalized)
        # Top 1% of papers have ~1000+ citations, median ~10
        citation_count = getattr(paper, 'citation_count', 0) or 0
        citation_score = min(1.0, citation_count / self.citation_normalization)

        # Recency score (exponential decay, half-life = 5 years)
        paper_year = getattr(paper, 'year', None)
        if paper_year and paper_year > 1900:
            years_old = max(0, CURRENT_YEAR - paper_year)
            recency_score = 0.5 ** (years_old / self.recency_halflife_years)
        else:
            # Unknown year - assume moderate age
            recency_score = 0.3

        # Journal score (placeholder - could integrate Scimago SJR)
        # TODO: Integrate actual journal impact scores
        journal_score = self._get_journal_score(paper)

        # Compute weighted average
        quality = (
            self.citation_weight * citation_score +
            self.recency_weight * recency_score +
            self.journal_weight * journal_score
        )

        # Apply penalties
        penalties = self._compute_penalties(paper)
        quality -= penalties

        # Clamp to [0.0, 1.0]
        return min(1.0, max(0.0, quality))

    def _get_journal_score(self, paper: "CitationNode") -> float:
        """
        Get journal impact score for a paper.

        Currently returns a default value. In production, this would
        integrate with Scimago SJR or similar journal ranking database.

        Args:
            paper: CitationNode with optional venue/journal field

        Returns:
            Journal score between 0.0 and 1.0
        """
        # Check for high-impact journal keywords (simplified heuristic)
        title = getattr(paper, 'title', '') or ''
        venue = getattr(paper, 'venue', '') or ''

        high_impact_keywords = [
            'nature', 'science', 'cell', 'lancet', 'nejm',
            'jama', 'pnas', 'plos medicine', 'bmj'
        ]

        text_lower = (title + ' ' + venue).lower()

        for keyword in high_impact_keywords:
            if keyword in text_lower:
                return 0.9  # High impact

        # Default mid-range score
        return 0.5

    def _compute_penalties(self, paper: "CitationNode") -> float:
        """
        Compute penalty score for problematic papers.

        Args:
            paper: CitationNode with optional is_retracted field

        Returns:
            Penalty to subtract from quality score
        """
        penalty = 0.0

        # Retraction penalty
        is_retracted = getattr(paper, 'is_retracted', None)
        if is_retracted:
            penalty += 0.5  # Major penalty for retracted papers

        # TODO: Add predatory journal detection
        # Could check against Beall's List or similar databases

        return penalty

    def rank_papers_by_quality(
        self,
        papers: List["CitationNode"],
        top_k: int = 20
    ) -> List["CitationNode"]:
        """
        Rank papers by quality score and return top-k.

        Args:
            papers: List of CitationNode objects to rank
            top_k: Maximum number of papers to return

        Returns:
            List of top-k papers sorted by quality score (descending)
        """
        if not papers:
            return []

        # Score all papers
        scored_papers = []
        for paper in papers:
            score = self.compute_quality_score(paper)
            # Store score on paper for later use
            if hasattr(paper, 'quality_score'):
                paper.quality_score = score
            scored_papers.append((score, paper))

        # Sort by score descending
        scored_papers.sort(reverse=True, key=lambda x: x[0])

        # Return top-k
        result = [paper for (score, paper) in scored_papers[:top_k]]

        logger.info(
            "Papers ranked by quality",
            total=len(papers),
            returned=len(result),
            top_k=top_k
        )

        return result

    def filter_by_quality(
        self,
        papers: List["CitationNode"],
        min_score: Optional[float] = None
    ) -> List["CitationNode"]:
        """
        Filter papers below minimum quality threshold.

        Args:
            papers: List of CitationNode objects to filter
            min_score: Minimum quality score (uses self.min_threshold if None)

        Returns:
            List of papers with quality score >= min_score
        """
        threshold = min_score if min_score is not None else self.min_threshold

        filtered = []
        for paper in papers:
            score = self.compute_quality_score(paper)
            if score >= threshold:
                if hasattr(paper, 'quality_score'):
                    paper.quality_score = score
                filtered.append(paper)

        logger.info(
            "Papers filtered by quality",
            total=len(papers),
            passed=len(filtered),
            threshold=threshold
        )

        return filtered

    def get_quality_label(self, score: float) -> str:
        """
        Convert quality score to human-readable label.

        Args:
            score: Quality score between 0.0 and 1.0

        Returns:
            One of: "HIGH", "MEDIUM", "LOW"
        """
        if score > 0.7:
            return "HIGH"
        elif score >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"

    def format_quality_context(
        self,
        papers: List["CitationNode"],
        max_papers: int = 20
    ) -> str:
        """
        Format papers with quality labels for LLM context.

        Args:
            papers: List of CitationNode objects
            max_papers: Maximum papers to include

        Returns:
            Formatted string with paper info and quality labels
        """
        # Rank and limit papers
        ranked = self.rank_papers_by_quality(papers, top_k=max_papers)

        context_parts = []
        for paper in ranked:
            score = self.compute_quality_score(paper)
            label = self.get_quality_label(score)

            title = getattr(paper, 'title', 'Unknown')
            authors = getattr(paper, 'authors', [])
            year = getattr(paper, 'year', 'N/A')
            citation_count = getattr(paper, 'citation_count', 0)
            abstract = getattr(paper, 'abstract', '')

            author_str = ', '.join(authors[:3])
            if len(authors) > 3:
                author_str += '...'

            context_parts.append(
                f"Title: {title}\n"
                f"Authors: {author_str}\n"
                f"Year: {year}\n"
                f"Citations: {citation_count}\n"
                f"[QUALITY: {label}]\n"
                f"Abstract: {abstract[:300]}..."
            )

        return "\n\n".join(context_parts)


# Default scorer instance with standard weights
default_scorer = PaperQualityScorer()
