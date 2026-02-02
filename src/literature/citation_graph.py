"""
Citation Graph

Build and analyze citation networks between papers.
Supports finding citation paths, common citations, and ranking by citation count.

Phase 6 Enhancements:
- quality_score: Multi-factor quality score (citation + recency + journal)
- is_retracted: Whether paper has been retracted
- retraction_notices: List of retraction/correction notices
- known_limitations: Extracted limitation statements from paper
- limitations_confidence: Confidence score for limitations extraction
"""

from typing import Optional
from collections import defaultdict, deque
from pydantic import BaseModel, Field


class CitationNode(BaseModel):
    """A paper node in the citation graph."""

    id: str = Field(..., description="Unique paper identifier")
    title: str = Field(..., description="Paper title")
    authors: list[str] = Field(default_factory=list, description="Author names")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="DOI")
    pmid: Optional[str] = Field(None, description="PubMed ID")
    citation_count: int = Field(0, description="Number of times cited")
    reference_count: int = Field(0, description="Number of references")
    abstract: Optional[str] = Field(None, description="Paper abstract (Phase 6 Week 3)")
    venue: Optional[str] = Field(None, description="Publication venue/journal")

    # Phase 6: Paper Quality Scoring
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Multi-factor quality score (citation + recency + journal)"
    )

    # Phase 6: Refutation Search
    is_retracted: Optional[bool] = Field(
        None,
        description="Whether paper has been retracted"
    )
    retraction_notices: list[str] = Field(
        default_factory=list,
        description="Retraction or correction notices"
    )

    # Phase 6: Limitations Extraction
    known_limitations: list[str] = Field(
        default_factory=list,
        description="Extracted limitation statements from paper"
    )
    limitations_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Confidence score for limitations extraction (0.0-1.0)"
    )


class CitationEdge(BaseModel):
    """A citation edge (citing -> cited)."""

    source_id: str = Field(..., description="Paper that cites")
    target_id: str = Field(..., description="Paper being cited")


class CitationGraph:
    """Graph structure for citation analysis."""

    def __init__(self):
        """Initialize empty citation graph."""
        self.nodes: dict[str, CitationNode] = {}
        self.edges: list[CitationEdge] = []

        # Adjacency lists for efficient traversal
        self._citations: dict[str, set[str]] = defaultdict(set)  # paper -> papers it cites
        self._cited_by: dict[str, set[str]] = defaultdict(set)  # paper -> papers citing it

    def add_paper(
        self,
        paper_id: str,
        title: str,
        authors: list[str],
        year: Optional[int] = None,
        doi: Optional[str] = None,
        **kwargs
    ) -> None:
        """Add a paper to the graph.

        Args:
            paper_id: Unique identifier
            title: Paper title
            authors: List of author names
            year: Publication year
            doi: DOI if available
            **kwargs: Additional fields (venue, abstract, etc.)
        """
        if paper_id not in self.nodes:
            self.nodes[paper_id] = CitationNode(
                id=paper_id,
                title=title,
                authors=authors,
                year=year,
                doi=doi,
                **kwargs
            )

    def add_citation(self, citing_id: str, cited_id: str) -> None:
        """Add a citation edge.

        Args:
            citing_id: ID of paper making the citation
            cited_id: ID of paper being cited
        """
        # Verify both nodes exist
        if citing_id not in self.nodes or cited_id not in self.nodes:
            return

        # Add edge
        edge = CitationEdge(source_id=citing_id, target_id=cited_id)
        self.edges.append(edge)

        # Update adjacency lists
        self._citations[citing_id].add(cited_id)
        self._cited_by[cited_id].add(citing_id)

        # Update counts
        self.nodes[citing_id].reference_count += 1
        self.nodes[cited_id].citation_count += 1

    def get_citations(self, paper_id: str) -> list[CitationNode]:
        """Get papers cited by this paper.

        Args:
            paper_id: Paper identifier

        Returns:
            List of cited papers
        """
        cited_ids = self._citations.get(paper_id, set())
        return [self.nodes[cid] for cid in cited_ids if cid in self.nodes]

    def get_cited_by(self, paper_id: str) -> list[CitationNode]:
        """Get papers that cite this paper.

        Args:
            paper_id: Paper identifier

        Returns:
            List of citing papers
        """
        citing_ids = self._cited_by.get(paper_id, set())
        return [self.nodes[cid] for cid in citing_ids if cid in self.nodes]

    def get_most_cited(self, n: int = 10) -> list[CitationNode]:
        """Get the most cited papers.

        Args:
            n: Number of papers to return

        Returns:
            List of papers sorted by citation count
        """
        sorted_nodes = sorted(
            self.nodes.values(),
            key=lambda x: x.citation_count,
            reverse=True
        )
        return sorted_nodes[:n]

    def get_highest_quality(self, n: int = 10) -> list[CitationNode]:
        """Get the highest quality papers (Phase 6).

        Args:
            n: Number of papers to return

        Returns:
            List of papers sorted by quality score
        """
        # Filter papers with quality scores, then sort
        scored = [node for node in self.nodes.values() if node.quality_score is not None]
        sorted_nodes = sorted(
            scored,
            key=lambda x: x.quality_score or 0,
            reverse=True
        )
        return sorted_nodes[:n]

    def get_common_citations(self, paper_ids: list[str]) -> list[CitationNode]:
        """Find papers cited by multiple input papers.

        Args:
            paper_ids: List of paper IDs to compare

        Returns:
            Papers cited by all input papers
        """
        if not paper_ids:
            return []

        # Get citations for first paper
        common = set(self._citations.get(paper_ids[0], set()))

        # Intersect with citations from other papers
        for paper_id in paper_ids[1:]:
            common &= self._citations.get(paper_id, set())

        return [self.nodes[cid] for cid in common if cid in self.nodes]

    def find_citation_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3
    ) -> list[list[str]]:
        """Find citation paths from source to target.

        Uses BFS to find shortest paths through citations.

        Args:
            source_id: Starting paper
            target_id: Target paper
            max_depth: Maximum path length

        Returns:
            List of paths (each path is list of paper IDs)
        """
        if source_id not in self.nodes or target_id not in self.nodes:
            return []

        # BFS with path tracking
        queue = deque([(source_id, [source_id])])
        visited = {source_id}
        paths = []

        while queue:
            current_id, path = queue.popleft()

            # Check depth limit
            if len(path) > max_depth:
                continue

            # Check if reached target
            if current_id == target_id:
                paths.append(path)
                continue

            # Explore citations
            for cited_id in self._citations.get(current_id, set()):
                if cited_id not in visited or len(path) < max_depth:
                    queue.append((cited_id, path + [cited_id]))
                    visited.add(cited_id)

        return paths

    def get_co_citation_strength(self, paper_a_id: str, paper_b_id: str) -> int:
        """Calculate co-citation strength (papers citing both).

        Args:
            paper_a_id: First paper
            paper_b_id: Second paper

        Returns:
            Number of papers citing both
        """
        citing_a = self._cited_by.get(paper_a_id, set())
        citing_b = self._cited_by.get(paper_b_id, set())
        return len(citing_a & citing_b)

    def get_bibliographic_coupling(self, paper_a_id: str, paper_b_id: str) -> int:
        """Calculate bibliographic coupling (shared references).

        Args:
            paper_a_id: First paper
            paper_b_id: Second paper

        Returns:
            Number of shared references
        """
        refs_a = self._citations.get(paper_a_id, set())
        refs_b = self._citations.get(paper_b_id, set())
        return len(refs_a & refs_b)

    def get_retracted_papers(self) -> list[CitationNode]:
        """Get all retracted papers in the graph (Phase 6).

        Returns:
            List of retracted papers
        """
        return [
            node for node in self.nodes.values()
            if node.is_retracted
        ]

    def get_papers_with_limitations(self) -> list[CitationNode]:
        """Get all papers with extracted limitations (Phase 6).

        Returns:
            List of papers with known_limitations
        """
        return [
            node for node in self.nodes.values()
            if node.known_limitations
        ]

    def to_dict(self) -> dict:
        """Serialize graph to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'nodes': {
                node_id: node.model_dump()
                for node_id, node in self.nodes.items()
            },
            'edges': [edge.model_dump() for edge in self.edges]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CitationGraph':
        """Deserialize graph from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            CitationGraph instance
        """
        graph = cls()

        # Restore nodes
        for node_id, node_data in data.get('nodes', {}).items():
            graph.nodes[node_id] = CitationNode(**node_data)

        # Restore edges
        for edge_data in data.get('edges', []):
            edge = CitationEdge(**edge_data)
            graph.edges.append(edge)

            # Rebuild adjacency lists
            source = edge.source_id
            target = edge.target_id
            graph._citations[source].add(target)
            graph._cited_by[target].add(source)

        return graph

    def get_statistics(self) -> dict:
        """Get graph statistics.

        Returns:
            Dictionary with statistics
        """
        if not self.nodes:
            return {
                'total_papers': 0,
                'total_citations': 0,
                'avg_citations_per_paper': 0.0,
                'avg_references_per_paper': 0.0,
                'max_citations': 0,
                'max_references': 0,
                'retracted_count': 0,
                'papers_with_limitations': 0,
                'papers_with_quality_score': 0
            }

        citation_counts = [node.citation_count for node in self.nodes.values()]
        reference_counts = [node.reference_count for node in self.nodes.values()]

        return {
            'total_papers': len(self.nodes),
            'total_citations': len(self.edges),
            'avg_citations_per_paper': sum(citation_counts) / len(self.nodes),
            'avg_references_per_paper': sum(reference_counts) / len(self.nodes),
            'max_citations': max(citation_counts) if citation_counts else 0,
            'max_references': max(reference_counts) if reference_counts else 0,
            'retracted_count': len(self.get_retracted_papers()),
            'papers_with_limitations': len(self.get_papers_with_limitations()),
            'papers_with_quality_score': sum(1 for n in self.nodes.values() if n.quality_score is not None)
        }
