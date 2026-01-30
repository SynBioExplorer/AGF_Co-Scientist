"""
Integration tests for Semantic Scholar tool (requires API access)

Run these tests manually to verify real API integration:
python 05_tests/test_semantic_scholar_integration.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest

from src.tools.semantic_scholar import SemanticScholarTool
from src.literature.citation_graph import CitationGraph
from src.literature.graph_expander import CitationGraphExpander, ExpansionStrategy


@pytest.mark.skip(reason="Requires live Semantic Scholar API access")
@pytest.mark.asyncio
async def test_search_papers_real_api():
    """Test real API search"""
    tool = SemanticScholarTool()

    papers = await tool.search_papers("transformers attention", limit=5)

    assert len(papers) > 0
    assert papers[0].title
    assert papers[0].paper_id
    print(f"Found {len(papers)} papers")
    print(f"First paper: {papers[0].title}")


@pytest.mark.skip(reason="Requires live Semantic Scholar API access")
@pytest.mark.asyncio
async def test_get_paper_by_doi_real_api():
    """Test fetching paper by DOI"""
    tool = SemanticScholarTool()

    # Famous "Attention is All You Need" paper
    paper = await tool.get_paper("DOI:10.48550/arXiv.1706.03762")

    assert paper.title == "Attention is All You Need"
    assert len(paper.authors) > 0
    print(f"Paper: {paper.title}")
    print(f"Authors: {', '.join(paper.authors[:3])}")
    print(f"Citations: {paper.citation_count}")


@pytest.mark.skip(reason="Requires live Semantic Scholar API access")
@pytest.mark.asyncio
async def test_citation_expansion_real_api():
    """Test citation graph expansion"""
    tool = SemanticScholarTool()
    graph = CitationGraph()
    expander = CitationGraphExpander(
        graph=graph,
        tools={"semantic_scholar": tool}
    )

    # Expand from "Attention is All You Need"
    result = await expander.expand_from_paper(
        paper_id="DOI:10.48550/arXiv.1706.03762",
        strategy=ExpansionStrategy.BACKWARD,
        max_depth=1,
        limit_per_direction=10
    )

    assert result.papers_added > 0
    assert result.total_papers > 1
    print(f"Expansion result:")
    print(f"  Papers added: {result.papers_added}")
    print(f"  Total papers: {result.total_papers}")
    print(f"  API calls: {result.api_calls_made}")
    print(f"  Time: {result.expansion_time_seconds:.2f}s")


async def manual_test():
    """Manual test function - run directly"""
    print("Testing Semantic Scholar Tool...")
    print("=" * 70)

    tool = SemanticScholarTool()

    # Test 1: Search
    print("\n1. Testing search...")
    papers = await tool.search_papers("machine learning", limit=3)
    print(f"   Found {len(papers)} papers")
    if papers:
        print(f"   First: {papers[0].title[:60]}...")

    # Test 2: Get paper by DOI
    print("\n2. Testing get_paper by DOI...")
    try:
        paper = await tool.get_paper("DOI:10.48550/arXiv.1706.03762")
        print(f"   Title: {paper.title}")
        print(f"   Year: {paper.year}")
        print(f"   Citations: {paper.citation_count}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Citation graph expansion
    print("\n3. Testing citation graph expansion...")
    graph = CitationGraph()
    expander = CitationGraphExpander(
        graph=graph,
        tools={"semantic_scholar": tool}
    )

    try:
        result = await expander.expand_from_paper(
            paper_id="DOI:10.48550/arXiv.1706.03762",
            strategy=ExpansionStrategy.BACKWARD,
            max_depth=1,
            limit_per_direction=5
        )
        print(f"   Papers added: {result.papers_added}")
        print(f"   Total papers: {result.total_papers}")
        print(f"   Time: {result.expansion_time_seconds:.2f}s")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 70)
    print("✅ All manual tests completed!")


if __name__ == "__main__":
    # Run manual test
    print("Running manual integration test...")
    print("NOTE: This requires internet access and will call the real Semantic Scholar API")
    print()

    asyncio.run(manual_test())
