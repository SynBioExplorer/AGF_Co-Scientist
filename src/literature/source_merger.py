"""
Citation Source Merger

Intelligently merges citation data from multiple sources (PubMed, Semantic Scholar,
local PDFs) into a unified citation graph with proper deduplication and metadata
resolution.

Implements Phase 6 Week 4: Multi-Source Citation Merging
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import hashlib
import uuid
import structlog

from src.literature.citation_graph import CitationGraph, CitationNode

logger = structlog.get_logger()


class CitationSourceMerger:
    """
    Merge citation data from multiple sources.

    Handles:
    - Deduplication by canonical ID (DOI > PMID > S2 paper_id)
    - Metadata conflict resolution with source priority
    - Citation list merging (union)
    - Citation graph merging with edge deduplication
    """

    def __init__(self, source_priority: Optional[List[str]] = None):
        """
        Initialize merger.

        Args:
            source_priority: Order of preference for metadata
                Default: ["local", "pubmed", "semantic_scholar"]
        """
        self.source_priority = source_priority or ["local", "pubmed", "semantic_scholar"]
        self.logger = logger.bind(component="CitationSourceMerger")

    def get_canonical_id(self, paper_data: Dict[str, Any]) -> Optional[str]:
        """
        Get canonical ID for a paper with priority: DOI > PMID > S2 paper_id.

        Args:
            paper_data: Paper metadata dict

        Returns:
            Canonical ID string or None
        """
        # Try DOI first (most universal)
        doi = paper_data.get("doi")
        if doi:
            # Normalize DOI (remove prefixes)
            doi_clean = doi.replace("https://doi.org/", "").replace("DOI:", "")
            return f"DOI:{doi_clean}"

        # Try PMID (PubMed ID)
        pmid = paper_data.get("pmid")
        if pmid:
            return f"PMID:{str(pmid)}"

        # Try Semantic Scholar paper ID
        paper_id = paper_data.get("paperId") or paper_data.get("paper_id")
        if paper_id:
            return f"S2:{paper_id}"

        # Fallback: use title hash if available (SHA256 for deterministic hashing)
        if "title" in paper_data:
            title_hash = hashlib.sha256(paper_data["title"].encode()).hexdigest()[:16]
            return f"TITLE_HASH:{title_hash}"

        return None

    def extract_all_ids(self, paper_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract all available IDs from paper data.

        Args:
            paper_data: Paper metadata dict

        Returns:
            Dict mapping ID types to values
        """
        ids = {}

        if "doi" in paper_data and paper_data["doi"]:
            ids["doi"] = paper_data["doi"]

        if "pmid" in paper_data and paper_data["pmid"]:
            ids["pmid"] = str(paper_data["pmid"])

        paper_id = paper_data.get("paperId") or paper_data.get("paper_id")
        if paper_id:
            ids["paperId"] = paper_id

        return ids

    def merge_papers(
        self,
        papers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge duplicate papers from multiple sources.

        Algorithm:
        1. Group by ANY matching ID (DOI, PMID, or S2 paper_id)
        2. For each group, merge metadata:
           - Use source_priority for conflicts
           - Take max citation_count
           - Take longest abstract
           - Union citation lists
        3. Return deduplicated list

        Args:
            papers: List of paper dicts from various sources

        Returns:
            Deduplicated list of merged papers
        """
        if not papers:
            return []

        # Group papers by ANY matching ID (not just canonical)
        # Build ID index: any_id -> canonical_group_id
        id_to_group = {}
        paper_groups = defaultdict(list)

        for paper in papers:
            # Extract all IDs from this paper
            all_ids = self.extract_all_ids(paper)

            # Check if any ID already mapped to a group
            group_id = None
            for id_type, id_value in all_ids.items():
                id_key = f"{id_type}:{id_value}"
                if id_key in id_to_group:
                    group_id = id_to_group[id_key]
                    break

            # If no existing group, create new one
            if group_id is None:
                group_id = self.get_canonical_id(paper)
                if not group_id:
                    # No ID found - generate UUID to preserve paper
                    group_id = f"UUID:{uuid.uuid4()}"
                    self.logger.warning(
                        "Generated UUID for paper without IDs",
                        group_id=group_id,
                        title=paper.get("title", "NO_TITLE")[:50]
                    )

            # Map all IDs from this paper to the group
            for id_type, id_value in all_ids.items():
                id_key = f"{id_type}:{id_value}"
                id_to_group[id_key] = group_id

            # Add paper to group
            paper_groups[group_id].append(paper)

        # Merge each group
        merged_papers = []

        for canonical_id, group in paper_groups.items():
            if len(group) == 1:
                # No duplicates - use as is
                merged = group[0]
            else:
                # Multiple sources - merge
                merged = self._merge_paper_group(canonical_id, group)

            # Add canonical ID to merged paper
            merged["canonical_id"] = canonical_id

            merged_papers.append(merged)

        self.logger.info(
            "Papers merged",
            input_count=len(papers),
            output_count=len(merged_papers),
            duplicates_removed=len(papers) - len(merged_papers)
        )

        return merged_papers

    def _merge_paper_group(
        self,
        canonical_id: str,
        papers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge a group of duplicate papers.

        Args:
            canonical_id: Canonical ID for this group
            papers: List of duplicate paper dicts

        Returns:
            Merged paper dict
        """
        # Start with empty merged paper
        merged: Dict[str, Any] = {"id": canonical_id}

        # Sort papers by source priority
        papers_sorted = self._sort_by_source_priority(papers)

        # Get source with highest priority as base
        base_paper = papers_sorted[0]
        merged.update(base_paper)

        # Merge specific fields from all sources
        self._merge_citation_counts(merged, papers)
        self._merge_abstracts(merged, papers)
        self._merge_authors(merged, papers)
        self._merge_ids(merged, papers)
        self._merge_citation_lists(merged, papers)

        self.logger.debug(
            "Paper group merged",
            canonical_id=canonical_id,
            source_count=len(papers),
            base_source=merged.get("source", "unknown")
        )

        return merged

    def _sort_by_source_priority(
        self,
        papers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort papers by source priority (highest first)."""
        def get_priority(paper: Dict[str, Any]) -> int:
            source = paper.get("source", "unknown").lower()
            try:
                # Lower index = higher priority
                return self.source_priority.index(source)
            except ValueError:
                # Unknown source - lowest priority
                return len(self.source_priority)

        return sorted(papers, key=get_priority)

    def _merge_citation_counts(
        self,
        merged: Dict[str, Any],
        papers: List[Dict[str, Any]]
    ):
        """Take maximum citation count across sources."""
        counts = [p.get("citation_count", 0) or 0 for p in papers]
        if counts:
            merged["citation_count"] = max(counts)

    def _merge_abstracts(
        self,
        merged: Dict[str, Any],
        papers: List[Dict[str, Any]]
    ):
        """Take longest abstract across sources."""
        abstracts = [p.get("abstract", "") or "" for p in papers]
        if abstracts:
            longest = max(abstracts, key=len)
            if longest:
                merged["abstract"] = longest

    def _merge_authors(
        self,
        merged: Dict[str, Any],
        papers: List[Dict[str, Any]]
    ):
        """Merge author lists (prefer most complete)."""
        author_lists = [p.get("authors", []) or [] for p in papers]
        if author_lists:
            # Take longest author list
            longest = max(author_lists, key=len)
            if longest:
                merged["authors"] = longest

    def _merge_ids(
        self,
        merged: Dict[str, Any],
        papers: List[Dict[str, Any]]
    ):
        """Merge all IDs from all sources."""
        all_ids = {}

        for paper in papers:
            ids = self.extract_all_ids(paper)
            all_ids.update(ids)

        # Add all IDs to merged paper
        merged.update(all_ids)

    def _merge_citation_lists(
        self,
        merged: Dict[str, Any],
        papers: List[Dict[str, Any]]
    ):
        """Merge citation lists (union)."""
        all_citations = []

        for paper in papers:
            citations = paper.get("citations", []) or []
            all_citations.extend(citations)

        if all_citations:
            # Deduplicate citations by ID
            unique_citations = {}
            seen_titles = set()  # For citations without IDs

            for citation in all_citations:
                citation_id = self.get_canonical_id(citation)

                if citation_id:
                    # Has ID - use standard deduplication
                    if citation_id not in unique_citations:
                        # Set canonical_id in the citation dict for reference
                        citation["canonical_id"] = citation_id
                        unique_citations[citation_id] = citation
                else:
                    # No ID - use title as fallback, generate UUID if needed
                    title = citation.get("title", "").strip()
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        # Generate UUID for citations without any identifier
                        generated_id = f"UUID:{uuid.uuid4()}"
                        citation["canonical_id"] = generated_id
                        unique_citations[generated_id] = citation
                        self.logger.warning(
                            "Citation without IDs preserved with UUID",
                            title=title[:50]
                        )
                    elif not title:
                        # No title either - generate UUID but log as problematic
                        generated_id = f"UUID:{uuid.uuid4()}"
                        citation["canonical_id"] = generated_id
                        unique_citations[generated_id] = citation
                        self.logger.warning(
                            "Citation without IDs or title preserved with UUID",
                            uuid=generated_id
                        )

            merged["citations"] = list(unique_citations.values())

    def merge_citation_graphs(
        self,
        graphs: List[CitationGraph]
    ) -> CitationGraph:
        """
        Merge multiple citation graphs into one.

        Algorithm:
        1. Collect all nodes from all graphs
        2. Merge nodes using merge_papers()
        3. Collect all edges
        4. Deduplicate edges by (source, target)
        5. Recalculate graph metrics

        Args:
            graphs: List of CitationGraph objects

        Returns:
            Unified CitationGraph
        """
        if not graphs:
            return CitationGraph()

        if len(graphs) == 1:
            return graphs[0]

        self.logger.info("Merging citation graphs", count=len(graphs))

        # Collect all nodes
        all_nodes = []
        for graph in graphs:
            for node in graph.nodes.values():
                # Convert CitationNode to dict for merging
                node_dict = node.model_dump()
                all_nodes.append(node_dict)

        # Merge nodes (deduplicate papers)
        merged_node_dicts = self.merge_papers(all_nodes)

        # Create merged graph
        merged_graph = CitationGraph()

        # Add merged nodes to graph
        node_id_map = {}  # Old ID → new canonical ID

        for node_dict in merged_node_dicts:
            canonical_id = node_dict.get("canonical_id") or node_dict.get("id")

            # Create CitationNode
            node = CitationNode(
                id=canonical_id,
                title=node_dict.get("title", "Unknown"),
                authors=node_dict.get("authors", []),
                year=node_dict.get("year"),
                doi=node_dict.get("doi"),
                pmid=node_dict.get("pmid"),
                citation_count=node_dict.get("citation_count", 0),
                reference_count=node_dict.get("reference_count", 0),
                abstract=node_dict.get("abstract")
            )

            merged_graph.nodes[canonical_id] = node

            # Track old IDs → canonical ID mapping
            # Include original ID from node_dict
            original_id = node_dict.get("id")
            if original_id and original_id != canonical_id:
                node_id_map[original_id] = canonical_id

            # Also map all ID variants
            if "doi" in node_dict:
                node_id_map[f"DOI:{node_dict['doi']}"] = canonical_id
                node_id_map[node_dict['doi']] = canonical_id  # Also without prefix
            if "pmid" in node_dict:
                node_id_map[f"PMID:{node_dict['pmid']}"] = canonical_id
                node_id_map[str(node_dict['pmid'])] = canonical_id  # Also without prefix
            if "paperId" in node_dict:
                node_id_map[f"S2:{node_dict['paperId']}"] = canonical_id
                node_id_map[node_dict['paperId']] = canonical_id  # Also without prefix

        # Collect and deduplicate edges
        edge_set = set()  # (source_canonical, target_canonical)

        for graph in graphs:
            for edge in graph.edges:
                # Map old IDs to canonical IDs
                source_canonical = node_id_map.get(edge.source_id, edge.source_id)
                target_canonical = node_id_map.get(edge.target_id, edge.target_id)

                # Only add edge if both nodes exist in merged graph
                if source_canonical in merged_graph.nodes and target_canonical in merged_graph.nodes:
                    edge_set.add((source_canonical, target_canonical))

        # Add edges to merged graph using add_citation
        for source, target in edge_set:
            merged_graph.add_citation(source, target)

        # Recalculate citation counts from actual edges to prevent double-counting
        # (node_dict may have citation_count that gets incremented again by add_citation)
        for node_id, node in merged_graph.nodes.items():
            incoming_edges = [e for e in merged_graph.edges if e.target_id == node_id]
            outgoing_edges = [e for e in merged_graph.edges if e.source_id == node_id]
            node.citation_count = len(incoming_edges)
            node.reference_count = len(outgoing_edges)

        # Validate graph integrity before returning
        validation = self.validate_graph_integrity(merged_graph)

        if validation["mismatched_counts"]:
            self.logger.warning(
                "Citation count mismatches detected (should not occur after recalculation)",
                issues=validation["mismatched_counts"]
            )

        if validation["duplicate_edges"]:
            self.logger.warning(
                "Duplicate edges detected",
                count=len(validation["duplicate_edges"])
            )

        self.logger.info(
            "Citation graphs merged",
            input_graphs=len(graphs),
            input_nodes=sum(len(g.nodes) for g in graphs),
            input_edges=sum(len(g.edges) for g in graphs),
            output_nodes=len(merged_graph.nodes),
            output_edges=len(merged_graph.edges)
        )

        return merged_graph

    def resolve_paper_conflicts(
        self,
        paper_a: Dict[str, Any],
        paper_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve conflicts between two versions of the same paper.

        Used when merging fails or manual conflict resolution needed.

        Args:
            paper_a: First paper version
            paper_b: Second paper version

        Returns:
            Merged paper with conflicts resolved
        """
        # Use merge_paper_group logic for two papers
        canonical_id = self.get_canonical_id(paper_a) or self.get_canonical_id(paper_b)

        if not canonical_id:
            raise ValueError("Cannot resolve conflicts for papers without identifiable IDs")

        return self._merge_paper_group(canonical_id, [paper_a, paper_b])

    def validate_graph_integrity(self, graph: CitationGraph) -> Dict[str, Any]:
        """
        Validate citation graph integrity after merge.

        Checks for:
        - Orphaned edges (edges referencing non-existent nodes)
        - Citation count mismatches (stored count != actual edge count)
        - Duplicate edges

        Args:
            graph: CitationGraph to validate

        Returns:
            Dict with validation results and warnings

        Raises:
            ValueError if critical issues found (orphaned edges)
        """
        issues = {
            "orphaned_edges": [],
            "mismatched_counts": [],
            "duplicate_edges": []
        }

        # Check all edges reference existing nodes
        for edge in graph.edges:
            if edge.source_id not in graph.nodes:
                issues["orphaned_edges"].append(
                    f"Source {edge.source_id} not in nodes"
                )
            if edge.target_id not in graph.nodes:
                issues["orphaned_edges"].append(
                    f"Target {edge.target_id} not in nodes"
                )

        # Check citation counts match edges
        for node_id, node in graph.nodes.items():
            incoming = [e for e in graph.edges if e.target_id == node_id]
            actual = len(incoming)

            if node.citation_count != actual:
                issues["mismatched_counts"].append({
                    "node": node_id,
                    "stored": node.citation_count,
                    "actual": actual
                })

        # Check for duplicate edges
        edge_set = set()
        for edge in graph.edges:
            edge_key = f"{edge.source_id}->{edge.target_id}"
            if edge_key in edge_set:
                issues["duplicate_edges"].append(edge_key)
            edge_set.add(edge_key)

        # Raise on critical issues
        if issues["orphaned_edges"]:
            raise ValueError(
                f"Graph integrity violation: {issues['orphaned_edges']}"
            )

        return issues

    def get_merge_statistics(
        self,
        before_papers: List[Dict[str, Any]],
        after_papers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get statistics about merge operation.

        Args:
            before_papers: Original paper list
            after_papers: Merged paper list

        Returns:
            Dict with merge statistics
        """
        duplicates_removed = len(before_papers) - len(after_papers)
        deduplication_rate = duplicates_removed / len(before_papers) if before_papers else 0

        # Count papers by source
        source_counts_before = defaultdict(int)
        for paper in before_papers:
            source = paper.get("source", "unknown")
            source_counts_before[source] += 1

        source_counts_after = defaultdict(int)
        for paper in after_papers:
            source = paper.get("source", "unknown")
            source_counts_after[source] += 1

        return {
            "total_before": len(before_papers),
            "total_after": len(after_papers),
            "duplicates_removed": duplicates_removed,
            "deduplication_rate": deduplication_rate,
            "source_counts_before": dict(source_counts_before),
            "source_counts_after": dict(source_counts_after)
        }
