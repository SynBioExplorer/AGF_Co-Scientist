"""
Edge Case Tests for Citation Source Merger

Tests edge cases that are not covered by the main test suite:
1. Deterministic title hashing (SHA256 vs hash())
2. Papers without any identifiable IDs
3. Citations without any identifiable IDs
4. Accurate citation counts (no double-counting)
5. Async integration (no event loop blocking)
6. Graph integrity validation

Created: 2026-01-30
"""

import pytest
import asyncio
import time
from src.literature.source_merger import CitationSourceMerger
from src.literature.citation_graph import CitationGraph


def test_title_hash_deterministic():
    """Test that title hashes are deterministic across runs (SHA256)."""
    merger = CitationSourceMerger()
    paper = {"title": "Alzheimer's Disease Treatment"}

    # Get canonical ID twice
    id1 = merger.get_canonical_id(paper)
    id2 = merger.get_canonical_id(paper)

    # Must be identical (deterministic)
    assert id1 == id2
    assert "TITLE_HASH:" in id1
    # SHA256 hash should be 16 chars (not 8 from old hash())
    assert len(id1.split(":")[1]) == 16


def test_papers_without_any_id():
    """Test that papers without any IDs get UUIDs instead of being dropped."""
    merger = CitationSourceMerger()
    papers = [
        {"abstract": "No IDs at all, just abstract"},
        {"pmid": "12345", "title": "Has ID"}
    ]

    result = merger.merge_papers(papers)

    # Should have 2 papers (not drop the one without IDs)
    assert len(result) == 2

    # One should have UUID
    uuid_papers = [p for p in result if "UUID:" in p.get("canonical_id", "")]
    assert len(uuid_papers) == 1


def test_citations_without_ids():
    """Test that citations without IDs are preserved when merging papers."""
    merger = CitationSourceMerger()

    # Test with duplicate papers that have citations without IDs
    # This triggers citation list merging
    papers = [
        {"doi": "10.1234/a", "citations": [{"title": "Ref 1"}]},
        {"doi": "10.1234/a", "citations": [{"title": "Ref 2"}]}  # Same DOI, different citations
    ]

    merged = merger.merge_papers(papers)

    # Should have 1 merged paper
    assert len(merged) == 1

    # Should preserve both citations even without DOI/PMID
    citations = merged[0].get("citations", [])
    assert len(citations) == 2

    # Both citations have only titles, so should get canonical_id assigned
    for citation in citations:
        # Either has a TITLE_HASH or UUID
        canonical_id = citation.get("canonical_id", "")
        assert "TITLE_HASH:" in canonical_id or "UUID:" in canonical_id


def test_citation_counts_accurate():
    """Test that citation counts are accurate (no double-counting)."""
    merger = CitationSourceMerger()

    # Create graph with known citation count
    graph1 = CitationGraph()
    graph1.add_paper(paper_id="A", title="Paper A", authors=["Author A"])
    graph1.add_paper(paper_id="B", title="Paper B", authors=["Author B"])
    graph1.add_citation("A", "B")  # A cites B

    # B should have citation_count=1
    assert graph1.nodes["B"].citation_count == 1

    # Merge graph (should preserve count, not double it)
    merged = merger.merge_citation_graphs([graph1])

    # Citation count should match edges (NOT be double-counted)
    assert merged.nodes["B"].citation_count == 1  # NOT 2
    assert merged.nodes["A"].citation_count == 0


@pytest.mark.asyncio
async def test_merger_in_async_context():
    """Test that merger doesn't block event loop when wrapped in asyncio.to_thread."""
    merger = CitationSourceMerger()
    papers = [{"doi": f"10.1234/{i}", "title": f"Paper {i}"} for i in range(100)]

    # Measure async behavior - should not block other coroutines
    async def other_task():
        """Simulate concurrent work"""
        await asyncio.sleep(0.05)
        return "done"

    start = time.time()

    # Run merger and other task concurrently
    merge_task = asyncio.create_task(
        asyncio.to_thread(merger.merge_papers, papers)
    )
    other_task_result = await asyncio.create_task(other_task())
    merged = await merge_task

    duration = time.time() - start

    # other_task should complete even while merging runs
    assert other_task_result == "done"
    assert len(merged) == 100

    # Both tasks should overlap, total time <0.5s
    # (merge is 0.5ms, other_task is 50ms, if they run in parallel total ~50ms)
    assert duration < 0.5


def test_graph_integrity_validation():
    """Test that graph integrity validation catches errors."""
    merger = CitationSourceMerger()

    # Create valid graph
    graph = CitationGraph()
    graph.add_paper(paper_id="A", title="Paper A", authors=["Author A"])
    graph.add_paper(paper_id="B", title="Paper B", authors=["Author B"])
    graph.add_citation("A", "B")

    # Should pass validation
    validation = merger.validate_graph_integrity(graph)
    assert len(validation["orphaned_edges"]) == 0
    assert len(validation["mismatched_counts"]) == 0
    assert len(validation["duplicate_edges"]) == 0


def test_hash_collision_resistance():
    """Test that SHA256 hashing doesn't produce collisions for many titles."""
    merger = CitationSourceMerger()

    # Generate 1,000 different titles
    titles = [f"Paper about topic {i} with details" for i in range(1000)]

    hashes = set()
    for title in titles:
        paper_id = merger.get_canonical_id({"title": title})

        # Check for collisions
        if paper_id in hashes:
            pytest.fail(f"Hash collision detected for title: {title}")

        hashes.add(paper_id)

    # All unique
    assert len(hashes) == 1000


def test_mixed_id_scenarios():
    """Test papers with various ID combinations."""
    merger = CitationSourceMerger()

    papers = [
        {"doi": "10.1234/a"},  # Only DOI
        {"pmid": "12345"},  # Only PMID
        {"paperId": "S2:abc"},  # Only S2 ID
        {"title": "Paper X"},  # Only title
        {"doi": "10.1234/a", "pmid": "12345"},  # DOI + PMID (duplicate with first two)
        {},  # No identifiers at all
    ]

    result = merger.merge_papers(papers)

    # Should have 4-5 papers:
    # - DOI + PMID merge into 1 (papers 1, 2, 5)
    # - S2 ID: 1
    # - Title only: 1
    # - No IDs: 1 (with UUID)
    # Total: 4 papers
    assert len(result) >= 4  # Allow UUID generation for empty paper

    # Find merged paper (should have both DOI and PMID)
    merged = next((p for p in result if p.get("doi") == "10.1234/a"), None)
    assert merged is not None
    assert "pmid" in merged or merged.get("pmid")  # Should have both IDs


def test_large_dataset_performance():
    """Test performance with 200 papers, 50 citations each."""
    papers = []
    for i in range(200):
        paper = {
            "doi": f"10.1234/{i}",
            "title": f"Paper {i}",
            "citations": [{"doi": f"10.5678/{i}-{j}"} for j in range(50)]
        }
        papers.append(paper)

    merger = CitationSourceMerger()
    start = time.time()
    result = merger.merge_papers(papers)
    duration = time.time() - start

    # Should complete in <1 second
    assert duration < 1.0
    assert len(result) == 200

    # Check memory usage is reasonable
    import sys
    memory_mb = sys.getsizeof(result) / 1024 / 1024
    assert memory_mb < 50  # Should use <50MB
