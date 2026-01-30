"""
Citation Graph Expander

Automatically expand citation graphs by recursively fetching neighbors through
citation networks ("cited by" and "references").

Implements "citation snowballing" to discover foundational papers.
"""

import asyncio
from typing import List, Dict, Set, Optional, Any
from enum import Enum
from collections import deque

import structlog
from pydantic import BaseModel, Field

from src.literature.citation_graph import CitationGraph, CitationNode
from src.tools.base import BaseTool

logger = structlog.get_logger()


class ExpansionStrategy(str, Enum):
    """Citation graph expansion directions"""
    BACKWARD = "backward"      # Follow references (earlier foundational work)
    FORWARD = "forward"        # Follow citations (later work building on this)
    BIDIRECTIONAL = "bidirectional"  # Both directions


class ExpansionResult(BaseModel):
    """Result of citation graph expansion"""

    papers_added: int = Field(..., description="Number of papers added to graph")
    total_papers: int = Field(..., description="Total papers in graph after expansion")
    expansion_time_seconds: float = Field(..., description="Time taken for expansion")
    api_calls_made: int = Field(..., description="Number of API calls")
    depth_reached: int = Field(..., description="Maximum depth reached")
    papers_pruned: int = Field(0, description="Papers pruned due to low relevance")


class CitationGraphExpander:
    """
    Automatically expand citation graphs by fetching neighbors.

    Supports:
    - Backward expansion: Follow references to find foundational papers
    - Forward expansion: Follow citations to find building work
    - Depth-limited expansion (default depth=1)
    - Relevance-based pruning
    - Deduplication across sources
    """

    def __init__(
        self,
        graph: CitationGraph,
        tools: Dict[str, BaseTool]
    ):
        """
        Initialize citation graph expander.

        Args:
            graph: CitationGraph instance to expand
            tools: Dictionary of tools {"semantic_scholar": tool, "pubmed": tool}
        """
        self.graph = graph
        self.tools = tools

        # Track expansion state
        self.visited_papers: Set[str] = set()  # Paper IDs we've already expanded
        self.api_call_count = 0

        # Deduplication map: DOI/PMID -> paper_id
        self.id_map: Dict[str, str] = {}

    def _get_paper_canonical_id(self, paper_data: Dict[str, Any]) -> Optional[str]:
        """
        Get canonical ID for deduplication.

        Priority: DOI > PMID > Semantic Scholar paper_id

        Args:
            paper_data: Paper metadata dict

        Returns:
            Canonical ID or None
        """
        # Try DOI first
        doi = paper_data.get("doi")
        if doi:
            return f"DOI:{doi}"

        # Try PMID
        pmid = paper_data.get("pmid")
        if pmid:
            return f"PMID:{pmid}"

        # Fall back to Semantic Scholar paper_id
        paper_id = paper_data.get("paper_id")
        if paper_id:
            return f"S2:{paper_id}"

        return None

    def _is_duplicate(self, paper_data: Dict[str, Any]) -> bool:
        """
        Check if paper is already in graph (by DOI/PMID).

        Args:
            paper_data: Paper metadata dict

        Returns:
            True if paper is duplicate
        """
        canonical_id = self._get_paper_canonical_id(paper_data)
        if not canonical_id:
            return False

        return canonical_id in self.id_map

    def _add_paper_to_graph(
        self,
        paper_data: Dict[str, Any],
        source: str = "semantic_scholar"
    ) -> Optional[str]:
        """
        Add paper to citation graph with deduplication.

        Args:
            paper_data: Paper metadata dict
            source: Source of the paper data

        Returns:
            Paper ID in graph, or None if duplicate/invalid
        """
        # Check for duplicates
        canonical_id = self._get_paper_canonical_id(paper_data)
        if canonical_id and canonical_id in self.id_map:
            # Return existing ID
            return self.id_map[canonical_id]

        # Generate paper ID
        doi = paper_data.get("doi")
        pmid = paper_data.get("pmid")

        if doi:
            paper_id = f"doi_{doi.replace('/', '_')}"
        elif pmid:
            paper_id = f"pmid_{pmid}"
        else:
            paper_id = f"s2_{paper_data.get('paper_id', 'unknown')}"

        # Add to graph
        self.graph.add_paper(
            paper_id=paper_id,
            title=paper_data.get("title", ""),
            authors=paper_data.get("authors", []),
            year=paper_data.get("year"),
            doi=doi
        )

        # Update deduplication map
        if canonical_id:
            self.id_map[canonical_id] = paper_id

        logger.debug(
            "Added paper to graph",
            paper_id=paper_id,
            title=paper_data.get("title", "")[:100],
            source=source
        )

        return paper_id

    async def expand_from_paper(
        self,
        paper_id: str,
        strategy: ExpansionStrategy = ExpansionStrategy.BACKWARD,
        max_depth: int = 1,
        min_relevance: float = 0.0,
        limit_per_direction: int = 50
    ) -> ExpansionResult:
        """
        Expand graph from a seed paper.

        Args:
            paper_id: DOI, PMID, or S2 paper ID
            strategy: Expansion direction (backward/forward/bidirectional)
            max_depth: Maximum depth to expand (1 = immediate neighbors only)
            min_relevance: Minimum relevance score (0-1), not implemented yet
            limit_per_direction: Max papers to fetch per direction

        Returns:
            ExpansionResult with statistics
        """
        import time
        start_time = time.time()

        initial_paper_count = len(self.graph.nodes)
        self.api_call_count = 0
        max_depth_reached = 0

        # Get Semantic Scholar tool
        semantic_tool = self.tools.get("semantic_scholar")
        if not semantic_tool:
            raise ValueError("Semantic Scholar tool not available")

        # BFS queue: (paper_id, current_depth)
        queue = deque([(paper_id, 0)])
        visited_in_this_expansion = set()

        while queue:
            current_id, current_depth = queue.popleft()

            # Check depth limit
            if current_depth >= max_depth:
                continue

            # Skip if already visited in this expansion
            if current_id in visited_in_this_expansion:
                continue
            visited_in_this_expansion.add(current_id)

            # Track max depth
            max_depth_reached = max(max_depth_reached, current_depth)

            try:
                # Fetch paper if not already in graph
                if current_id not in self.graph.nodes:
                    try:
                        paper = await semantic_tool.get_paper(current_id)
                        self.api_call_count += 1

                        graph_paper_id = self._add_paper_to_graph(
                            paper.model_dump(),
                            source="semantic_scholar"
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to fetch paper",
                            paper_id=current_id,
                            error=str(e)
                        )
                        continue
                else:
                    graph_paper_id = current_id

                # Expand based on strategy
                neighbors = []

                if strategy in [ExpansionStrategy.BACKWARD, ExpansionStrategy.BIDIRECTIONAL]:
                    # Fetch references (papers this paper cites)
                    try:
                        references = await semantic_tool.get_references(
                            current_id,
                            limit=limit_per_direction
                        )
                        self.api_call_count += 1

                        for ref_paper in references:
                            ref_id = self._add_paper_to_graph(
                                ref_paper.model_dump(),
                                source="semantic_scholar"
                            )

                            if ref_id and graph_paper_id:
                                # Add citation edge: current -> reference
                                self.graph.add_citation(graph_paper_id, ref_id)
                                neighbors.append((ref_id, current_depth + 1))

                    except Exception as e:
                        logger.warning(
                            "Failed to fetch references",
                            paper_id=current_id,
                            error=str(e)
                        )

                if strategy in [ExpansionStrategy.FORWARD, ExpansionStrategy.BIDIRECTIONAL]:
                    # Fetch citations (papers citing this paper)
                    try:
                        citations = await semantic_tool.get_citations(
                            current_id,
                            limit=limit_per_direction
                        )
                        self.api_call_count += 1

                        for citing_paper in citations:
                            citing_id = self._add_paper_to_graph(
                                citing_paper.model_dump(),
                                source="semantic_scholar"
                            )

                            if citing_id and graph_paper_id:
                                # Add citation edge: citing -> current
                                self.graph.add_citation(citing_id, graph_paper_id)
                                neighbors.append((citing_id, current_depth + 1))

                    except Exception as e:
                        logger.warning(
                            "Failed to fetch citations",
                            paper_id=current_id,
                            error=str(e)
                        )

                # Add neighbors to queue for next level
                for neighbor_id, neighbor_depth in neighbors:
                    if neighbor_depth < max_depth:
                        queue.append((neighbor_id, neighbor_depth))

            except Exception as e:
                logger.error(
                    "Error expanding paper",
                    paper_id=current_id,
                    depth=current_depth,
                    error=str(e)
                )
                continue

        # Calculate results
        end_time = time.time()
        final_paper_count = len(self.graph.nodes)
        papers_added = final_paper_count - initial_paper_count

        result = ExpansionResult(
            papers_added=papers_added,
            total_papers=final_paper_count,
            expansion_time_seconds=end_time - start_time,
            api_calls_made=self.api_call_count,
            depth_reached=max_depth_reached,
            papers_pruned=0  # TODO: Implement relevance pruning
        )

        logger.info(
            "Citation graph expansion complete",
            papers_added=papers_added,
            total_papers=final_paper_count,
            api_calls=self.api_call_count,
            time_seconds=round(result.expansion_time_seconds, 2)
        )

        return result

    async def expand_from_results(
        self,
        search_results: List[Dict[str, Any]],
        depth: int = 1,
        strategy: ExpansionStrategy = ExpansionStrategy.BACKWARD
    ) -> CitationGraph:
        """
        Expand graph from multiple seed papers.

        Args:
            search_results: List of paper dicts from search
            depth: Expansion depth
            strategy: Expansion direction

        Returns:
            Expanded citation graph
        """
        logger.info(
            "Starting batch expansion",
            num_seeds=len(search_results),
            depth=depth,
            strategy=strategy.value
        )

        # Add all seed papers to graph
        seed_ids = []
        for paper_data in search_results:
            paper_id = self._add_paper_to_graph(paper_data)
            if paper_id:
                seed_ids.append(paper_id)

        # Expand from each seed
        for seed_id in seed_ids:
            try:
                await self.expand_from_paper(
                    paper_id=seed_id,
                    strategy=strategy,
                    max_depth=depth
                )
            except Exception as e:
                logger.warning(
                    "Failed to expand seed paper",
                    paper_id=seed_id,
                    error=str(e)
                )
                continue

        logger.info(
            "Batch expansion complete",
            total_papers=len(self.graph.nodes),
            total_citations=len(self.graph.edges)
        )

        return self.graph

    def calculate_relevance(
        self,
        paper_data: Dict[str, Any],
        query: str
    ) -> float:
        """
        Score paper relevance to query (placeholder).

        TODO: Implement proper relevance scoring using:
        - Title/abstract similarity (embeddings)
        - Citation count (influence)
        - Recency (exponential decay)
        - Keyword overlap

        Args:
            paper_data: Paper metadata
            query: Search query or research goal

        Returns:
            Relevance score (0-1)
        """
        # Placeholder: simple keyword matching
        query_lower = query.lower()
        title = paper_data.get("title", "").lower()
        abstract = paper_data.get("abstract", "").lower()

        score = 0.0

        if query_lower in title:
            score += 0.5

        if query_lower in abstract:
            score += 0.3

        # Boost by citation count (normalized)
        citation_count = paper_data.get("citation_count", 0)
        if citation_count > 0:
            score += min(0.2, citation_count / 1000)

        return min(1.0, score)

    def prune_low_relevance(
        self,
        min_relevance: float,
        query: str
    ) -> int:
        """
        Remove papers below relevance threshold.

        TODO: Implement pruning logic

        Args:
            min_relevance: Minimum relevance score (0-1)
            query: Search query for relevance calculation

        Returns:
            Number of papers pruned
        """
        # Placeholder - not implemented yet
        return 0

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get expansion statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "total_papers": len(self.graph.nodes),
            "total_citations": len(self.graph.edges),
            "papers_visited": len(self.visited_papers),
            "api_calls_made": self.api_call_count,
            "unique_dois": len([
                node for node in self.graph.nodes.values()
                if node.doi
            ])
        }
