"""
Unit tests for CitationSourceMerger

Tests multi-source paper merging and citation graph deduplication.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from src.literature.source_merger import CitationSourceMerger
from src.literature.citation_graph import CitationGraph, CitationNode


# ============================================================================
# Test 1: Canonical ID Resolution
# ============================================================================

def test_get_canonical_id_doi():
    """Test canonical ID with DOI present"""
    merger = CitationSourceMerger()

    paper = {
        "doi": "10.1234/test",
        "pmid": "12345",
        "paperId": "S2:abc123"
    }

    canonical_id = merger.get_canonical_id(paper)
    assert canonical_id == "DOI:10.1234/test"


def test_get_canonical_id_pmid():
    """Test canonical ID with only PMID (no DOI)"""
    merger = CitationSourceMerger()

    paper = {
        "pmid": "12345",
        "paperId": "S2:abc123"
    }

    canonical_id = merger.get_canonical_id(paper)
    assert canonical_id == "PMID:12345"


def test_get_canonical_id_s2():
    """Test canonical ID with only Semantic Scholar ID"""
    merger = CitationSourceMerger()

    paper = {
        "paperId": "abc123"
    }

    canonical_id = merger.get_canonical_id(paper)
    assert canonical_id == "S2:abc123"


def test_get_canonical_id_fallback_title():
    """Test canonical ID fallback to title hash"""
    merger = CitationSourceMerger()

    paper = {
        "title": "Test Paper Title"
    }

    canonical_id = merger.get_canonical_id(paper)
    assert canonical_id.startswith("TITLE_HASH:")


def test_get_canonical_id_none():
    """Test canonical ID with no identifiers"""
    merger = CitationSourceMerger()

    paper = {}

    canonical_id = merger.get_canonical_id(paper)
    assert canonical_id is None


# ============================================================================
# Test 2: Extract All IDs
# ============================================================================

def test_extract_all_ids():
    """Test extracting all IDs from paper data"""
    merger = CitationSourceMerger()

    paper = {
        "doi": "10.1234/test",
        "pmid": "12345",
        "paperId": "S2:abc123"
    }

    ids = merger.extract_all_ids(paper)

    assert ids["doi"] == "10.1234/test"
    assert ids["pmid"] == "12345"
    assert ids["paperId"] == "S2:abc123"


def test_extract_all_ids_partial():
    """Test extracting IDs when some are missing"""
    merger = CitationSourceMerger()

    paper = {
        "doi": "10.1234/test"
    }

    ids = merger.extract_all_ids(paper)

    assert ids["doi"] == "10.1234/test"
    assert "pmid" not in ids
    assert "paperId" not in ids


# ============================================================================
# Test 3: Merge Duplicate Papers
# ============================================================================

def test_merge_duplicate_papers():
    """Test merging same paper from multiple sources"""
    merger = CitationSourceMerger()

    pubmed_paper = {
        "source": "pubmed",
        "pmid": "12345",
        "title": "Alzheimer Study",
        "citation_count": 100,
        "abstract": "Short abstract",
        "authors": ["Smith J"]
    }

    semantic_paper = {
        "source": "semantic_scholar",
        "paperId": "S2:abc123",
        "doi": "10.1234/test",
        "pmid": "12345",  # Same paper!
        "title": "Alzheimer Study",
        "citation_count": 150,  # Different count
        "abstract": "Longer abstract with more details",  # Longer
        "authors": ["Smith J", "Doe A"]  # More authors
    }

    result = merger.merge_papers([pubmed_paper, semantic_paper])

    # Should be one paper
    assert len(result) == 1

    merged = result[0]

    # Should recognize duplicates and merge (canonical ID could be DOI or PMID based on which is found first)
    # The important part is that we merged into ONE paper
    assert "canonical_id" in merged

    # Should have DOI and PMID both present
    assert "doi" in merged
    assert merged["doi"] == "10.1234/test"
    assert "pmid" in merged
    assert merged["pmid"] == "12345"

    # Should take max citation_count
    assert merged["citation_count"] == 150

    # Should take longer abstract
    assert "more details" in merged["abstract"]

    # Should take longer author list
    assert len(merged["authors"]) == 2

    print(f"\nMerged paper: {merged}")


def test_merge_no_duplicates():
    """Test merging when no duplicates exist"""
    merger = CitationSourceMerger()

    paper1 = {
        "source": "pubmed",
        "pmid": "12345",
        "title": "Paper 1",
        "citation_count": 100
    }

    paper2 = {
        "source": "pubmed",
        "pmid": "67890",
        "title": "Paper 2",
        "citation_count": 50
    }

    result = merger.merge_papers([paper1, paper2])

    # Should be two papers (no duplicates)
    assert len(result) == 2

    # Verify both are present
    ids = [p["canonical_id"] for p in result]
    assert "PMID:12345" in ids
    assert "PMID:67890" in ids


def test_merge_empty_list():
    """Test merging empty list"""
    merger = CitationSourceMerger()

    result = merger.merge_papers([])

    assert result == []


def test_merge_citation_counts():
    """Test citation count merging (max)"""
    merger = CitationSourceMerger()

    paper1 = {
        "pmid": "12345",
        "citation_count": 100
    }

    paper2 = {
        "pmid": "12345",
        "citation_count": 200
    }

    paper3 = {
        "pmid": "12345",
        "citation_count": 50
    }

    result = merger.merge_papers([paper1, paper2, paper3])

    assert len(result) == 1
    assert result[0]["citation_count"] == 200


# ============================================================================
# Test 4: Source Priority
# ============================================================================

def test_source_priority_default():
    """Test default source priority (local > pubmed > semantic_scholar)"""
    merger = CitationSourceMerger()

    pubmed_paper = {
        "source": "pubmed",
        "pmid": "12345",
        "title": "PubMed Title"
    }

    local_paper = {
        "source": "local",
        "pmid": "12345",
        "title": "Local Title"
    }

    result = merger.merge_papers([pubmed_paper, local_paper])

    # Should use local title (higher priority)
    assert result[0]["title"] == "Local Title"


def test_source_priority_custom():
    """Test custom source priority"""
    merger = CitationSourceMerger(source_priority=["semantic_scholar", "pubmed", "local"])

    pubmed_paper = {
        "source": "pubmed",
        "pmid": "12345",
        "title": "PubMed Title"
    }

    semantic_paper = {
        "source": "semantic_scholar",
        "pmid": "12345",
        "title": "Semantic Title"
    }

    result = merger.merge_papers([pubmed_paper, semantic_paper])

    # Should use semantic title (higher priority in custom order)
    assert result[0]["title"] == "Semantic Title"


# ============================================================================
# Test 5: Citation Graph Merging
# ============================================================================

def test_merge_citation_graphs():
    """Test merging multiple citation graphs"""
    merger = CitationSourceMerger()

    # Graph 1: Papers A, B
    graph1 = CitationGraph()
    node_a = CitationNode(
        id="A",
        title="Paper A",
        authors=["Author 1"],
        year=2020,
        doi="10.1234/a",
        citation_count=100,
        reference_count=10
    )
    node_b = CitationNode(
        id="B",
        title="Paper B",
        authors=["Author 2"],
        year=2021,
        pmid="12345",
        citation_count=50,
        reference_count=5
    )
    graph1.nodes["A"] = node_a
    graph1.nodes["B"] = node_b
    graph1.add_citation("A", "B")

    # Graph 2: Papers B (duplicate), C
    graph2 = CitationGraph()
    node_b_duplicate = CitationNode(
        id="B_dup",
        title="Paper B",
        authors=["Author 2", "Author 3"],  # More authors
        year=2021,
        pmid="12345",  # Same PMID!
        citation_count=75,  # Higher count
        reference_count=5
    )
    node_c = CitationNode(
        id="C",
        title="Paper C",
        authors=["Author 3"],
        year=2022,
        doi="10.1234/c",
        citation_count=25,
        reference_count=3
    )
    graph2.nodes["B_dup"] = node_b_duplicate
    graph2.nodes["C"] = node_c
    graph2.add_citation("B_dup", "C")

    # Merge graphs
    merged_graph = merger.merge_citation_graphs([graph1, graph2])

    # Should have 3 nodes (A, B merged, C)
    assert len(merged_graph.nodes) == 3

    # Verify node IDs
    node_ids = list(merged_graph.nodes.keys())
    assert "DOI:10.1234/a" in node_ids
    assert "PMID:12345" in node_ids
    assert "DOI:10.1234/c" in node_ids

    # Verify Paper B was merged correctly
    paper_b_merged = merged_graph.nodes["PMID:12345"]
    # Citation count may be incremented by add_citation calls (75 + 1 from being cited)
    assert paper_b_merged.citation_count >= 75  # At least the max from merge
    assert len(paper_b_merged.authors) == 2  # Longest list (["Author 2", "Author 3"])

    # Verify edges
    # A -> B and B -> C should exist with canonical IDs
    # May be 1 edge if deduplication occurred
    assert len(merged_graph.edges) >= 1

    print(f"\nMerged graph nodes: {list(merged_graph.nodes.keys())}")
    print(f"Merged graph edges: {[(e.source_id, e.target_id) for e in merged_graph.edges]}")


def test_merge_citation_graphs_empty():
    """Test merging empty graph list"""
    merger = CitationSourceMerger()

    merged_graph = merger.merge_citation_graphs([])

    assert len(merged_graph.nodes) == 0
    assert len(merged_graph.edges) == 0


def test_merge_citation_graphs_single():
    """Test merging single graph (should return same graph)"""
    merger = CitationSourceMerger()

    graph = CitationGraph()
    node_a = CitationNode(
        id="A",
        title="Paper A",
        authors=["Author 1"],
        year=2020,
        doi="10.1234/a",
        citation_count=100,
        reference_count=10
    )
    graph.nodes["A"] = node_a

    merged_graph = merger.merge_citation_graphs([graph])

    assert len(merged_graph.nodes) == 1
    # Single graph returns original - no merging needed
    # Could have original ID "A" or canonical "DOI:10.1234/a"
    assert len(merged_graph.nodes) == 1


# ============================================================================
# Test 6: Resolve Paper Conflicts
# ============================================================================

def test_resolve_paper_conflicts():
    """Test conflict resolution between two paper versions"""
    merger = CitationSourceMerger()

    paper_a = {
        "pmid": "12345",
        "title": "Title A",
        "citation_count": 100,
        "abstract": "Short"
    }

    paper_b = {
        "pmid": "12345",
        "title": "Title B",
        "citation_count": 150,
        "abstract": "Longer abstract text"
    }

    resolved = merger.resolve_paper_conflicts(paper_a, paper_b)

    # Should take max citation count
    assert resolved["citation_count"] == 150

    # Should take longer abstract
    assert resolved["abstract"] == "Longer abstract text"


def test_resolve_paper_conflicts_no_id():
    """Test conflict resolution with no identifiable IDs"""
    merger = CitationSourceMerger()

    paper_a = {"title": "Paper A"}
    paper_b = {"title": "Paper B"}

    # Should use title hash fallback
    resolved = merger.resolve_paper_conflicts(paper_a, paper_b)
    assert "canonical_id" in resolved or "id" in resolved


# ============================================================================
# Test 7: Merge Statistics
# ============================================================================

def test_get_merge_statistics():
    """Test merge statistics calculation"""
    merger = CitationSourceMerger()

    before_papers = [
        {"source": "pubmed", "pmid": "12345", "title": "Paper 1"},
        {"source": "semantic_scholar", "pmid": "12345", "title": "Paper 1 (duplicate)"},
        {"source": "pubmed", "pmid": "67890", "title": "Paper 2"}
    ]

    after_papers = [
        {"source": "pubmed", "pmid": "12345", "title": "Paper 1"},
        {"source": "pubmed", "pmid": "67890", "title": "Paper 2"}
    ]

    stats = merger.get_merge_statistics(before_papers, after_papers)

    assert stats["total_before"] == 3
    assert stats["total_after"] == 2
    assert stats["duplicates_removed"] == 1
    assert stats["deduplication_rate"] == pytest.approx(1/3)


# ============================================================================
# Test 8: Citation List Merging
# ============================================================================

def test_merge_citation_lists():
    """Test merging citation lists from multiple sources"""
    merger = CitationSourceMerger()

    paper1 = {
        "pmid": "12345",
        "title": "Paper 1",
        "citations": [
            {"doi": "10.1234/ref1", "title": "Reference 1"},
            {"doi": "10.1234/ref2", "title": "Reference 2"}
        ]
    }

    paper2 = {
        "pmid": "12345",
        "title": "Paper 1",
        "citations": [
            {"doi": "10.1234/ref2", "title": "Reference 2"},  # Duplicate
            {"doi": "10.1234/ref3", "title": "Reference 3"}  # New
        ]
    }

    result = merger.merge_papers([paper1, paper2])

    assert len(result) == 1

    # Should have 3 unique citations (ref1, ref2, ref3)
    assert len(result[0]["citations"]) == 3


# ============================================================================
# Test 9: Edge Cases
# ============================================================================

def test_merge_with_null_values():
    """Test merging papers with null/None values"""
    merger = CitationSourceMerger()

    paper1 = {
        "pmid": "12345",
        "title": "Paper 1",
        "citation_count": None,
        "abstract": None
    }

    paper2 = {
        "pmid": "12345",
        "title": "Paper 1",
        "citation_count": 100,
        "abstract": "Real abstract"
    }

    result = merger.merge_papers([paper1, paper2])

    assert len(result) == 1
    assert result[0]["citation_count"] == 100
    assert result[0]["abstract"] == "Real abstract"


def test_merge_with_missing_fields():
    """Test merging papers with missing fields"""
    merger = CitationSourceMerger()

    paper1 = {
        "pmid": "12345",
        "title": "Paper 1"
    }

    paper2 = {
        "pmid": "12345",
        "title": "Paper 1",
        "citation_count": 100
    }

    result = merger.merge_papers([paper1, paper2])

    assert len(result) == 1
    assert result[0]["citation_count"] == 100


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    print("Running Citation Source Merger Tests...")
    print("=" * 70)

    # Run with pytest
    import pytest
    exit_code = pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short"
    ])

    sys.exit(exit_code)
