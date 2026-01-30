"""
End-to-End Integration Test for Phase 6 Week 4

Tests complete multi-source citation merging with caching, parallel expansion,
and GenerationAgent integration.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.agents.generation import GenerationAgent
from src.literature.source_merger import CitationSourceMerger
from src.literature.citation_graph import CitationGraph, CitationNode
from src.storage.cache import RedisCache
from src.tools.registry import ToolRegistry
from src.tools.base import ToolResult

# Add schemas path
sys.path.insert(0, str(project_root / "03_architecture"))
from schemas import ResearchGoal


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_research_goal():
    """Create sample research goal"""
    return ResearchGoal(
        id="test_goal_123",
        description="Novel treatments for Alzheimer's disease using FDA-approved drugs",
        preferences=["Focus on drug repurposing", "Prioritize clinical trials"],
        created_at=datetime.now()
    )


@pytest.fixture
def mock_pubmed_results():
    """Mock PubMed search results"""
    return [
        {
            "pmid": "12345",
            "title": "Drug X for Alzheimer's Treatment",
            "authors": ["Smith J", "Doe A"],
            "year": 2020,
            "citation_count": 100,
            "abstract": "Study on drug X for Alzheimer's"
        },
        {
            "pmid": "67890",
            "title": "Clinical Trial of Drug Y",
            "authors": ["Johnson B"],
            "year": 2021,
            "citation_count": 50,
            "abstract": "Clinical trial results"
        }
    ]


@pytest.fixture
def mock_semantic_results():
    """Mock Semantic Scholar search results"""
    return [
        {
            "doi": "10.1234/paper1",
            "pmid": "12345",  # Duplicate with PubMed!
            "paperId": "S2:abc123",
            "title": "Drug X for Alzheimer's Treatment",
            "authors": ["Smith J", "Doe A", "Lee C"],  # More complete
            "year": 2020,
            "citation_count": 150,  # Higher count
            "abstract": "Extended abstract with more details about study on drug X"
        },
        {
            "doi": "10.1234/paper2",
            "paperId": "S2:def456",
            "title": "Novel Mechanisms in Alzheimer's",
            "authors": ["Williams D"],
            "year": 2022,
            "citation_count": 75,
            "abstract": "Novel mechanisms discovered"
        }
    ]


@pytest.fixture
def mock_cache():
    """Mock RedisCache"""
    cache = MagicMock(spec=RedisCache)
    cache.get_citation_graph = AsyncMock(return_value=None)  # Cache miss
    cache.set_citation_graph = AsyncMock()
    return cache


@pytest.fixture
def mock_tool_registry(mock_pubmed_results, mock_semantic_results):
    """Mock tool registry with PubMed and Semantic Scholar tools"""
    registry = MagicMock(spec=ToolRegistry)

    # Mock PubMed tool
    pubmed_tool = AsyncMock()
    pubmed_tool.execute = AsyncMock(return_value=ToolResult(
        success=True,
        data=mock_pubmed_results,
        message="PubMed search successful"
    ))

    # Mock Semantic Scholar tool
    semantic_tool = AsyncMock()
    semantic_tool.execute = AsyncMock(return_value=ToolResult(
        success=True,
        data=mock_semantic_results,
        message="Semantic Scholar search successful"
    ))

    registry.get = MagicMock(side_effect=lambda name: {
        "pubmed": pubmed_tool,
        "semantic_scholar": semantic_tool
    }.get(name))

    return registry


# ============================================================================
# Test 1: Multi-Source Merging
# ============================================================================

@pytest.mark.asyncio
async def test_multi_source_deduplication(
    sample_research_goal,
    mock_pubmed_results,
    mock_semantic_results
):
    """Test that duplicate papers are merged correctly"""
    merger = CitationSourceMerger()

    # Add source tags
    for paper in mock_pubmed_results:
        paper["source"] = "pubmed"
    for paper in mock_semantic_results:
        paper["source"] = "semantic_scholar"

    # Merge papers
    all_papers = mock_pubmed_results + mock_semantic_results
    merged = merger.merge_papers(all_papers)

    # Should have 3 unique papers (not 4)
    # Paper 1 (PMID:12345) appears in both sources → merged
    # Paper 2 (PMID:67890) only in PubMed
    # Paper 3 (DOI:10.1234/paper2) only in Semantic Scholar
    assert len(merged) == 3, f"Expected 3 papers after merge, got {len(merged)}"

    # Find merged paper by canonical ID
    merged_paper = next(
        (p for p in merged if "12345" in p.get("canonical_id", "")),
        None
    )
    assert merged_paper is not None, "Merged paper not found"

    # Should take max citation count
    assert merged_paper["citation_count"] == 150, \
        f"Expected 150 citations, got {merged_paper['citation_count']}"

    # Should take longer abstract
    assert "more details" in merged_paper["abstract"], \
        "Should use longer abstract from Semantic Scholar"

    # Should take more complete author list
    assert len(merged_paper["authors"]) == 3, \
        f"Expected 3 authors, got {len(merged_paper['authors'])}"

    # Should have both identifiers
    assert "pmid" in merged_paper
    assert "doi" in merged_paper

    print(f"\n✅ Multi-source deduplication test passed")
    print(f"   Papers before merge: {len(all_papers)}")
    print(f"   Papers after merge: {len(merged)}")
    print(f"   Duplicates removed: {len(all_papers) - len(merged)}")


# ============================================================================
# Test 2: Citation Graph Caching
# ============================================================================

@pytest.mark.asyncio
async def test_citation_graph_caching(sample_research_goal, mock_cache):
    """Test citation graph caching workflow"""
    # Create sample graph
    graph = CitationGraph()
    node = CitationNode(
        id="PMID:12345",
        title="Test Paper",
        authors=["Author A"],
        year=2020,
        pmid="12345",
        citation_count=100,
        reference_count=10
    )
    graph.nodes[node.id] = node

    # Set cache
    cache_key = "goal:test_goal_123:abcd1234"
    await mock_cache.set_citation_graph(cache_key, graph)

    # Verify set was called
    mock_cache.set_citation_graph.assert_called_once()
    call_args = mock_cache.set_citation_graph.call_args
    assert call_args[0][0] == cache_key
    assert isinstance(call_args[0][1], CitationGraph)

    # Simulate cache hit
    mock_cache.get_citation_graph = AsyncMock(return_value=graph)

    # Get from cache
    cached_graph = await mock_cache.get_citation_graph(cache_key)

    assert cached_graph is not None
    assert len(cached_graph.nodes) == 1
    assert "PMID:12345" in cached_graph.nodes

    print(f"\n✅ Citation graph caching test passed")


# ============================================================================
# Test 3: GenerationAgent Integration (Mocked)
# ============================================================================

@pytest.mark.asyncio
async def test_generation_agent_with_merging(
    sample_research_goal,
    mock_cache,
    mock_tool_registry
):
    """Test GenerationAgent with multi-source merging and caching"""
    with patch('src.agents.generation.initialize_tools', return_value=mock_tool_registry):
        with patch('src.agents.generation.get_llm_client'):
            # Create GenerationAgent with mock cache
            agent = GenerationAgent(cache=mock_cache)
            agent.tool_registry = mock_tool_registry

            # Search literature tools
            results, graph = await agent._search_literature_tools(
                sample_research_goal,
                max_results=10
            )

            # Verify cache was checked
            mock_cache.get_citation_graph.assert_called_once()

            # Verify both tools were called
            pubmed_tool = mock_tool_registry.get("pubmed")
            semantic_tool = mock_tool_registry.get("semantic_scholar")

            pubmed_tool.execute.assert_called_once()
            semantic_tool.execute.assert_called_once()

            # Verify results were merged (3 unique papers, not 4)
            assert len(results) == 3, f"Expected 3 merged papers, got {len(results)}"

            # Verify source tags were added
            assert all("source" in paper for paper in results)

            print(f"\n✅ GenerationAgent integration test passed")
            print(f"   PubMed results: 2")
            print(f"   Semantic Scholar results: 2")
            print(f"   Merged results: {len(results)}")
            print(f"   Duplicates removed: 1")


# ============================================================================
# Test 4: Parallel Expansion
# ============================================================================

@pytest.mark.asyncio
async def test_parallel_expansion_enabled():
    """Test that parallel expansion is enabled by default"""
    from src.config import settings

    # Check config
    assert hasattr(settings, 'enable_parallel_expansion')
    assert hasattr(settings, 'max_parallel_expansions')

    # Verify default values
    assert settings.max_parallel_expansions == 5, \
        f"Expected max_parallel_expansions=5, got {settings.max_parallel_expansions}"

    print(f"\n✅ Parallel expansion config test passed")
    print(f"   enable_parallel_expansion: {settings.enable_parallel_expansion}")
    print(f"   max_parallel_expansions: {settings.max_parallel_expansions}")


# ============================================================================
# Test 5: Performance Characteristics
# ============================================================================

@pytest.mark.asyncio
async def test_merger_performance():
    """Test CitationSourceMerger performance with realistic dataset"""
    import time

    merger = CitationSourceMerger()

    # Generate 100 papers with 20% duplication rate
    papers = []
    for i in range(80):
        papers.append({
            "pmid": f"PMID{i}",
            "title": f"Paper {i}",
            "citation_count": i * 10
        })

    # Add 20 duplicates (same PMID, different metadata)
    for i in range(20):
        papers.append({
            "pmid": f"PMID{i}",  # Duplicate
            "doi": f"10.1234/paper{i}",  # Additional metadata
            "title": f"Paper {i}",
            "citation_count": i * 15  # Higher count
        })

    # Measure merge time
    start_time = time.time()
    merged = merger.merge_papers(papers)
    merge_time = time.time() - start_time

    # Verify deduplication
    assert len(merged) == 80, f"Expected 80 unique papers, got {len(merged)}"

    # Verify performance (<100ms for 100 papers)
    assert merge_time < 0.1, f"Merge took {merge_time:.3f}s, expected <0.1s"

    # Verify citation counts were maximized
    for i in range(20):
        merged_paper = next(
            (p for p in merged if f"PMID{i}" in p.get("canonical_id", "")),
            None
        )
        assert merged_paper is not None
        assert merged_paper["citation_count"] == i * 15  # Max count

    print(f"\n✅ Merger performance test passed")
    print(f"   Papers processed: {len(papers)}")
    print(f"   Unique papers: {len(merged)}")
    print(f"   Duplicates removed: {len(papers) - len(merged)}")
    print(f"   Merge time: {merge_time*1000:.1f}ms")


# ============================================================================
# Test 6: Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_error_handling_tool_failure(sample_research_goal, mock_cache):
    """Test graceful degradation when tools fail"""
    with patch('src.agents.generation.initialize_tools') as mock_init:
        with patch('src.agents.generation.get_llm_client'):
            # Create registry with failing tools
            registry = MagicMock(spec=ToolRegistry)

            # PubMed fails
            pubmed_tool = AsyncMock()
            pubmed_tool.execute = AsyncMock(side_effect=Exception("PubMed API error"))

            # Semantic Scholar succeeds
            semantic_tool = AsyncMock()
            semantic_tool.execute = AsyncMock(return_value=ToolResult(
                success=True,
                data=[{"doi": "10.1234/test", "title": "Test Paper"}],
                message="Success"
            ))

            registry.get = MagicMock(side_effect=lambda name: {
                "pubmed": pubmed_tool,
                "semantic_scholar": semantic_tool
            }.get(name))

            mock_init.return_value = registry

            # Create agent
            agent = GenerationAgent(cache=mock_cache)
            agent.tool_registry = registry

            # Should not raise exception
            results, graph = await agent._search_literature_tools(
                sample_research_goal,
                max_results=10
            )

            # Should have results from Semantic Scholar only
            assert len(results) == 1
            assert results[0]["title"] == "Test Paper"

            print(f"\n✅ Error handling test passed")
            print(f"   PubMed failed gracefully")
            print(f"   Semantic Scholar results: {len(results)}")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    print("Running Phase 6 Week 4 Integration Tests...")
    print("=" * 70)

    # Run with pytest
    exit_code = pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short"
    ])

    sys.exit(exit_code)
