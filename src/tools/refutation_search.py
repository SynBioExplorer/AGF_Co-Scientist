"""
Refutation Search Tool - Phase 6 Feature

Search for contradictory evidence, failed replications, and retracted papers.
Implements Popperian falsification - science advances through refutation.

Three core capabilities:
1. Contradiction search - Find papers with opposing conclusions
2. Failed replication search - Find replication failures
3. Retraction detection - Check PubMed for retractions/corrections

Reference: 03_architecture/Phase6/phase6_refutation_search.md
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

from src.tools.base import BaseTool, ToolResult
from src.utils.errors import CoScientistError
import structlog

if TYPE_CHECKING:
    from src.literature.citation_graph import CitationNode

logger = structlog.get_logger()


# Keywords indicating contradiction or negative results
CONTRADICTION_KEYWORDS = [
    "not", "no effect", "no significant",
    "contradicts", "inconsistent", "contrary",
    "failed to", "unable to", "did not",
    "opposite", "conflicting", "disagree",
    "refutes", "challenges", "disputes",
    "no evidence", "insufficient evidence",
    "non-significant", "null result"
]

# Keywords indicating replication attempts
REPLICATION_KEYWORDS = [
    "failed to replicate",
    "could not reproduce",
    "replication failure",
    "non-replication",
    "reproducibility",
    "unsuccessful replication",
    "unable to reproduce",
    "failed replication"
]

# PubMed publication types for retractions
RETRACTION_PUBLICATION_TYPES = [
    "retracted publication",
    "retraction of publication",
    "retraction",
    "correction",
    "erratum",
    "expression of concern"
]


class RefutationSearchTool(BaseTool):
    """
    Search for contradictory evidence, failed replications, and retractions.

    Implements the scientific method's emphasis on falsification by actively
    searching for evidence that contradicts hypotheses.
    """

    def __init__(
        self,
        pubmed_tool: Optional["BaseTool"] = None,
        semantic_scholar_tool: Optional["BaseTool"] = None,
        max_results: int = 10,
        min_quality_score: float = 0.4
    ):
        """
        Initialize the refutation search tool.

        Args:
            pubmed_tool: PubMed tool for retraction checking
            semantic_scholar_tool: Semantic Scholar tool for citation search
            max_results: Maximum results per search
            min_quality_score: Minimum quality score for contradictions
        """
        self.pubmed_tool = pubmed_tool
        self.semantic_scholar_tool = semantic_scholar_tool
        self.max_results = max_results
        self.min_quality_score = min_quality_score

    @property
    def name(self) -> str:
        return "refutation_search"

    @property
    def description(self) -> str:
        return "Search for contradictory evidence, failed replications, and retracted papers"

    @property
    def domain(self) -> str:
        return "scientific_rigor"

    def generate_negation_queries(self, claim: str) -> List[str]:
        """
        Generate negation queries for a claim.

        Args:
            claim: Core claim to negate (e.g., "Protein A inhibits Gene B")

        Returns:
            List of search queries designed to find contradictions
        """
        # Clean the claim
        claim = claim.strip()

        # Generate negation templates
        negation_templates = [
            f"{claim} NOT",
            f"{claim} does not",
            f"no effect {claim}",
            f"contradicts {claim}",
            f"inconsistent with {claim}",
            f"failed to replicate {claim}",
            f"could not reproduce {claim}",
            f"challenges {claim}",
            f"refutes {claim}"
        ]

        # Extract key terms and create opposite queries
        # Simple heuristic: look for common effect verbs and negate them
        effect_patterns = [
            (r"(\w+)\s+inhibits\s+(\w+)", r"\1 activates \2"),
            (r"(\w+)\s+activates\s+(\w+)", r"\1 inhibits \2"),
            (r"(\w+)\s+increases\s+(\w+)", r"\1 decreases \2"),
            (r"(\w+)\s+decreases\s+(\w+)", r"\1 increases \2"),
            (r"(\w+)\s+promotes\s+(\w+)", r"\1 suppresses \2"),
            (r"(\w+)\s+suppresses\s+(\w+)", r"\1 promotes \2"),
            (r"(\w+)\s+causes\s+(\w+)", r"\1 does not cause \2"),
            (r"(\w+)\s+prevents\s+(\w+)", r"\1 does not prevent \2"),
        ]

        for pattern, replacement in effect_patterns:
            match = re.search(pattern, claim, re.IGNORECASE)
            if match:
                opposite = re.sub(pattern, replacement, claim, flags=re.IGNORECASE)
                negation_templates.append(opposite)

        return negation_templates

    def _is_contradiction(self, abstract: str, original_claim: str) -> bool:
        """
        Check if an abstract contains contradictory evidence.

        Args:
            abstract: Paper abstract text
            original_claim: The original claim being checked

        Returns:
            True if abstract appears to contradict the claim
        """
        if not abstract:
            return False

        abstract_lower = abstract.lower()

        # Whole words only: as substrings "not" matched "another" and "notably".
        contradiction_count = sum(
            1 for keyword in CONTRADICTION_KEYWORDS
            if re.search(rf"\b{re.escape(keyword)}\b", abstract_lower)
        )

        # Require at least 2 contradiction keywords to reduce false positives
        return contradiction_count >= 2

    async def search_contradictions(
        self,
        hypothesis_statement: str,
        core_claim: str,
        return_status: bool = False,
    ):
        """
        Search for papers that contradict the hypothesis.

        Args:
            hypothesis_statement: Full hypothesis text
            core_claim: Extracted core claim to negate
            return_status: Also return what was searched

        Returns:
            List of paper dictionaries representing contradictory papers; with
            return_status, a tuple of that list and a dict with "attempted"
            (searches sent), "failed" (searches that raised or returned an
            error) and "queries" (the queries of the searches that worked).
        """
        logger.info(
            "Searching for contradictions",
            hypothesis=hypothesis_statement[:100],
            core_claim=core_claim[:100]
        )

        contradictions = []
        status = {"attempted": 0, "failed": 0, "queries": []}

        # Generate negation queries
        queries = self.generate_negation_queries(core_claim)

        # Search using available tools. A search that fails is counted, so a
        # caller can tell "nothing found" from "could not search".
        for source, tool in (("semantic_scholar", self.semantic_scholar_tool),
                             ("pubmed", self.pubmed_tool)):
            if not tool:
                continue
            for query in queries[:3]:  # Limit to avoid rate limits
                status["attempted"] += 1
                try:
                    result = await tool.execute(
                        query,
                        max_results=self.max_results // 3
                    )
                    if not result.success:
                        status["failed"] += 1
                        logger.warning("Contradiction search failed", source=source,
                                       error=result.error)
                        continue
                    found = []
                    for paper in result.data:
                        abstract = paper.get('abstract', '')
                        if self._is_contradiction(abstract, core_claim):
                            paper['contradiction_source'] = source
                            paper['query_used'] = query
                            found.append(paper)
                except Exception as e:
                    status["failed"] += 1
                    logger.warning("Contradiction search failed", source=source, error=str(e))
                    continue
                contradictions.extend(found)
                if query not in status["queries"]:
                    status["queries"].append(query)

        # Deduplicate by DOI/PMID
        seen = set()
        unique_contradictions = []
        for paper in contradictions:
            key = paper.get('doi') or paper.get('pmid') or paper.get('title', '')
            if key and key not in seen:
                seen.add(key)
                unique_contradictions.append(paper)

        logger.info(
            "Contradiction search complete",
            total_found=len(unique_contradictions),
            searches_failed=status["failed"],
            searches_attempted=status["attempted"],
        )

        if return_status:
            return unique_contradictions[:self.max_results], status
        return unique_contradictions[:self.max_results]

    async def search_failed_replications(
        self,
        target_paper: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find papers that failed to replicate the target paper.

        Args:
            target_paper: The paper to check for replication failures

        Returns:
            List of papers that cite target and report replication failure
        """
        logger.info(
            "Searching for failed replications",
            target_title=target_paper.get('title', '')[:100]
        )

        failed_replications = []

        # Get paper ID for citation lookup
        paper_id = (
            target_paper.get('paper_id') or
            f"DOI:{target_paper.get('doi')}" if target_paper.get('doi') else
            f"PMID:{target_paper.get('pmid')}" if target_paper.get('pmid') else
            None
        )

        if not paper_id or not self.semantic_scholar_tool:
            return []

        try:
            # Get citing papers (forward expansion)
            if hasattr(self.semantic_scholar_tool, 'get_citations'):
                citing_papers = await self.semantic_scholar_tool.get_citations(
                    paper_id,
                    limit=100
                )

                # Filter for replication failure keywords
                for paper in citing_papers:
                    abstract = paper.abstract if hasattr(paper, 'abstract') else ''
                    title = paper.title if hasattr(paper, 'title') else ''
                    text = (abstract or '') + ' ' + (title or '')
                    text_lower = text.lower()

                    # Check for replication keywords
                    for keyword in REPLICATION_KEYWORDS:
                        if keyword in text_lower:
                            paper_dict = paper.model_dump() if hasattr(paper, 'model_dump') else paper
                            paper_dict['replication_keyword'] = keyword
                            failed_replications.append(paper_dict)
                            break

        except Exception as e:
            logger.warning("Failed replication search failed", error=str(e))

        logger.info(
            "Failed replication search complete",
            total_found=len(failed_replications)
        )

        return failed_replications

    async def check_retractions(
        self,
        paper: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check PubMed whether a paper has been retracted.

        Args:
            paper: Paper dictionary with a pmid or doi field

        Returns:
            Dictionary with retraction status and notices. check_status says
            whether is_retracted is a finding: "checked", "lookup_failed" (the
            PubMed call failed) or "not_checked" (no identifier or no PubMed
            tool); is_retracted is False unless checked and retracted.
        """
        # has_correction and has_expression_of_concern are None (unknown):
        # PubMed links an erratum or a concern to the article only in efetch's
        # CommentsCorrections, which this check does not read (correction[pt]
        # and erratum[pt] match no record at all).
        result = {
            "is_retracted": False,
            "check_status": "not_checked",
            "has_correction": None,
            "has_expression_of_concern": None,
            "notices": []
        }

        pmid = paper.get('pmid')
        # PubMed indexes the bare DOI, not a doi.org URL or a "doi:" form
        doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '',
                     (paper.get('doi') or '').strip(), flags=re.IGNORECASE)
        if not (pmid or doi) or not self.pubmed_tool:
            return result

        logger.info("Checking retraction status", pmid=pmid, doi=doi)

        try:
            # A retracted article has the publication type "Retracted
            # Publication"; retracted[pt] and retraction[pt] match nothing.
            identifier = f"{pmid}[PMID]" if pmid else f'"{doi}"[doi]'
            retraction_result = await self.pubmed_tool.execute(
                f'{identifier} AND "retracted publication"[pt]',
                max_results=5
            )

            if not retraction_result.success:
                result["check_status"] = "lookup_failed"
                logger.warning("Retraction check failed", pmid=pmid, doi=doi,
                               error=retraction_result.error)
            else:
                result["check_status"] = "checked"
                if retraction_result.data:
                    result["is_retracted"] = True
                    for notice in retraction_result.data:
                        result["notices"].append({
                            "type": "retraction",
                            "title": notice.get('title', ''),
                            "date": notice.get('year', '')
                        })

        except Exception as e:
            result["check_status"] = "lookup_failed"
            logger.warning("Retraction check failed", pmid=pmid, doi=doi, error=str(e))

        logger.info(
            "Retraction check complete",
            pmid=pmid,
            doi=doi,
            is_retracted=result["is_retracted"]
        )

        return result

    def format_contradictions_for_context(
        self,
        contradictions: List[Dict[str, Any]],
        retraction_status: Dict[str, Dict[str, Any]],
        search_status: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Format contradictions and retraction status for LLM context.

        Args:
            contradictions: List of contradictory papers
            retraction_status: Dict mapping paper title to retraction info
            search_status: search_contradictions' status, if known

        Returns:
            Formatted string for inclusion in LLM prompts
        """
        parts = []
        attempted = (search_status or {}).get("attempted", 0)
        failed = (search_status or {}).get("failed", 0)

        # The papers are what negated-claim queries returned with negative-
        # result wording in the abstract (_is_contradiction); nothing has
        # checked that they contradict this hypothesis.
        if contradictions:
            parts.append(
                f"PAPERS FROM NEGATED-CLAIM SEARCHES ({len(contradictions)}): their abstracts "
                f"contain negative-result wording (a keyword heuristic). Whether each one "
                f"contradicts THIS hypothesis has not been checked; judge that yourself."
            )
            for i, paper in enumerate(contradictions, 1):
                title = paper.get('title', 'Unknown')
                year = paper.get('year', 'N/A')
                abstract = paper.get('abstract', '')[:200]
                source = paper.get('contradiction_source', 'unknown')

                parts.append(
                    f"\n[{i}] {title} ({year})\n"
                    f"    Source: {source}\n"
                    f"    Abstract: {abstract}..."
                )
        elif attempted and failed >= attempted:
            parts.append(
                f"The contradiction search could not be completed ({failed} of {attempted} "
                f"searches failed): whether contradicting papers exist is unknown, not ruled out."
            )
        else:
            parts.append("Negated-claim searches returned no papers with negative-result wording.")

        if failed and failed < attempted:
            parts.append(f"Note: {failed} of {attempted} contradiction searches failed, so "
                         f"this list may be incomplete.")

        if retraction_status:
            retracted = [
                title for title, status in retraction_status.items()
                if status.get('is_retracted')
            ]
            if retracted:
                parts.append(f"\nWARNING: {len(retracted)} contradicting paper(s) have been RETRACTED:")
                for title in retracted:
                    parts.append(f"  - {title}")

        return "\n".join(parts)

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Execute refutation search for a query.

        Args:
            query: Hypothesis or claim to find contradictions for
            **kwargs: Optional parameters

        Returns:
            ToolResult with contradictory papers
        """
        try:
            contradictions = await self.search_contradictions(
                hypothesis_statement=query,
                core_claim=kwargs.get('core_claim', query)
            )

            return ToolResult.success_result(
                data=contradictions,
                metadata={
                    'query': query,
                    'num_contradictions': len(contradictions),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            logger.error("Refutation search failed", error=str(e))
            return ToolResult.error_result(
                error=str(e),
                metadata={
                    'query': query,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
