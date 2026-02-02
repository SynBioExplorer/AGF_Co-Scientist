"""
Contract: RefutationSearchProtocol
Version: 31f3178 (commit hash when contract was created)
Generated: 2026-02-02T10:00:00Z

Search for contradictory evidence, failed replications, and retracted papers.
Implements Popperian falsification - science advances through refutation.
"""
from typing import Protocol, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.literature.citation_graph import CitationNode


class RefutationSearchProtocol(Protocol):
    """
    Protocol for searching contradictory evidence and negative results.

    Three core capabilities:
    1. Contradiction search - Find papers with opposing conclusions
    2. Failed replication search - Find replication failures
    3. Retraction detection - Check PubMed for retractions/corrections

    Negation Query Strategy:
        - Generate queries with negation keywords ("NOT", "no effect", "failed to")
        - Filter results by contradiction keywords in abstract
        - Rank by quality score to prioritize high-quality contradictions
    """

    async def search_contradictions(
        self,
        hypothesis_statement: str,
        core_claim: str
    ) -> List["CitationNode"]:
        """
        Search for papers that contradict the hypothesis.

        Args:
            hypothesis_statement: Full hypothesis text
            core_claim: Extracted core claim to negate (e.g., "Protein A inhibits Gene B")

        Returns:
            List of CitationNode objects representing contradictory papers

        Strategy:
            1. Generate negation queries using generate_negation_queries()
            2. Search Semantic Scholar + PubMed
            3. Filter by contradiction keywords in abstract
            4. Rank by quality score
            5. Return top 10 contradictions

        Example:
            >>> tool = RefutationSearchTool()
            >>> contradictions = await tool.search_contradictions(
            ...     "Hydroxychloroquine is effective for COVID-19",
            ...     "hydroxychloroquine effective COVID-19"
            ... )
            >>> # Should find RECOVERY trial, SOLIDARITY trial, etc.
        """
        ...

    async def search_failed_replications(
        self,
        target_paper: "CitationNode"
    ) -> List["CitationNode"]:
        """
        Find papers that failed to replicate the target paper.

        Args:
            target_paper: The paper to check for replication failures

        Returns:
            List of papers that cite target_paper and report replication failure

        Strategy:
            1. Get papers citing the target (forward expansion)
            2. Filter for replication keywords:
               - "failed to replicate"
               - "could not reproduce"
               - "replication failure"
               - "non-replication"
            3. Return matching papers
        """
        ...

    async def check_retractions(
        self,
        paper: "CitationNode"
    ) -> Dict[str, Any]:
        """
        Check PubMed for retraction notices or corrections.

        Args:
            paper: CitationNode with pmid field

        Returns:
            Dictionary with:
                - is_retracted: bool - Whether paper has been retracted
                - has_correction: bool - Whether correction/erratum exists
                - notices: List[str] - Text of retraction/correction notices

        Notes:
            - Requires paper.pmid to be set
            - Uses PubMed publication types: retracted[pt], correction[pt], erratum[pt]
            - Returns empty result if no PMID available

        Example:
            >>> status = await tool.check_retractions(paper)
            >>> if status["is_retracted"]:
            ...     print("WARNING: Paper has been retracted!")
        """
        ...

    def generate_negation_queries(self, claim: str) -> List[str]:
        """
        Generate negation queries for a claim.

        Args:
            claim: Core claim to negate (e.g., "Protein A inhibits Gene B")

        Returns:
            List of search queries designed to find contradictions

        Examples:
            Input: "Protein A inhibits Gene B"
            Output: [
                "Protein A does NOT inhibit Gene B",
                "Protein A activates Gene B",  # opposite effect
                "no effect Protein A Gene B",
                "contradicts Protein A Gene B",
                "failed to replicate Protein A Gene B"
            ]

        Negation Templates:
            - "{claim} NOT"
            - "{claim} does not"
            - "no effect {claim}"
            - "contradicts {claim}"
            - "inconsistent with {claim}"
            - "failed to replicate {claim}"
            - "could not reproduce {claim}"
        """
        ...


# Type alias for implementations
RefutationSearchTool = RefutationSearchProtocol
