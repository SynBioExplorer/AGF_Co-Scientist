"""
Unit tests for Citation Graph Caching

Tests RedisCache citation graph caching functionality (Phase 6 Week 4).
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.storage.cache import RedisCache
from src.literature.citation_graph import CitationGraph, CitationNode


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_citation_graph():
    """Create a sample citation graph for testing"""
    graph = CitationGraph()

    node_a = CitationNode(
        id="DOI:10.1234/a",
        title="Paper A",
        authors=["Author 1"],
        year=2020,
        doi="10.1234/a",
        citation_count=100,
        reference_count=10,
        abstract="Abstract A"
    )

    node_b = CitationNode(
        id="PMID:12345",
        title="Paper B",
        authors=["Author 2"],
        year=2021,
        pmid="12345",
        citation_count=50,
        reference_count=5,
        abstract="Abstract B"
    )

    graph.nodes[node_a.id] = node_a
    graph.nodes[node_b.id] = node_b
    graph.add_citation(node_a.id, node_b.id)

    return graph


@pytest.fixture
async def mock_redis_cache():
    """Create a mock RedisCache for testing"""
    cache = RedisCache(redis_url="redis://localhost:6379/0")

    # Mock the Redis client
    cache._client = AsyncMock()

    # Mock basic Redis operations
    cache._client.get = AsyncMock(return_value=None)
    cache._client.setex = AsyncMock()
    cache._client.delete = AsyncMock()
    cache._client.scan_iter = AsyncMock()

    return cache


# ============================================================================
# Test 1: Graph Serialization/Deserialization
# ============================================================================

def test_graph_to_dict(sample_citation_graph):
    """Test serializing citation graph to dict"""
    cache = RedisCache()

    graph_dict = cache._graph_to_dict(sample_citation_graph)

    # Verify structure
    assert "nodes" in graph_dict
    assert "edges" in graph_dict
    assert "metadata" in graph_dict

    # Verify nodes
    assert len(graph_dict["nodes"]) == 2

    # Verify edges
    assert len(graph_dict["edges"]) == 1
    assert graph_dict["edges"][0]["source_id"] == "DOI:10.1234/a"
    assert graph_dict["edges"][0]["target_id"] == "PMID:12345"

    print(f"\nSerialized graph: {graph_dict['nodes'][0]['title']}")


def test_dict_to_graph(sample_citation_graph):
    """Test deserializing dict to citation graph"""
    cache = RedisCache()

    # Serialize then deserialize
    graph_dict = cache._graph_to_dict(sample_citation_graph)
    reconstructed_graph = cache._dict_to_graph(graph_dict)

    # Verify nodes
    assert len(reconstructed_graph.nodes) == 2
    assert "DOI:10.1234/a" in reconstructed_graph.nodes
    assert "PMID:12345" in reconstructed_graph.nodes

    # Verify edges
    assert len(reconstructed_graph.edges) == 1

    # Verify node details
    node_a = reconstructed_graph.nodes["DOI:10.1234/a"]
    assert node_a.title == "Paper A"
    assert node_a.citation_count == 100

    print(f"\nReconstructed graph nodes: {list(reconstructed_graph.nodes.keys())}")


def test_round_trip_serialization(sample_citation_graph):
    """Test complete round-trip serialization"""
    cache = RedisCache()

    # Serialize
    graph_dict = cache._graph_to_dict(sample_citation_graph)

    # Deserialize
    reconstructed = cache._dict_to_graph(graph_dict)

    # Verify equality
    assert len(reconstructed.nodes) == len(sample_citation_graph.nodes)
    assert len(reconstructed.edges) == len(sample_citation_graph.edges)

    for node_id in sample_citation_graph.nodes:
        assert node_id in reconstructed.nodes
        original_node = sample_citation_graph.nodes[node_id]
        reconstructed_node = reconstructed.nodes[node_id]
        assert original_node.title == reconstructed_node.title
        assert original_node.year == reconstructed_node.year


# ============================================================================
# Test 2: Citation Graph Caching
# ============================================================================

@pytest.mark.asyncio
async def test_get_citation_graph_miss(mock_redis_cache):
    """Test citation graph cache miss"""
    cache = mock_redis_cache

    # Mock cache miss
    cache._client.get.return_value = None

    result = await cache.get_citation_graph("test_key")

    assert result is None
    cache._client.get.assert_called_once()


@pytest.mark.asyncio
async def test_set_and_get_citation_graph(mock_redis_cache, sample_citation_graph):
    """Test caching and retrieving citation graph"""
    cache = mock_redis_cache

    # Set cache
    await cache.set_citation_graph("test_key", sample_citation_graph)

    # Verify setex was called
    cache._client.setex.assert_called_once()
    args = cache._client.setex.call_args
    assert args[0][0].endswith("test_key")  # Key
    assert args[0][1] == cache.CITATION_GRAPH_TTL  # TTL

    # Mock get to return the serialized graph
    import json
    graph_dict = cache._graph_to_dict(sample_citation_graph)
    cache._client.get.return_value = json.dumps(graph_dict)

    # Get cache
    result = await cache.get_citation_graph("test_key")

    assert result is not None
    assert len(result.nodes) == 2


@pytest.mark.asyncio
async def test_citation_graph_ttl_default(mock_redis_cache, sample_citation_graph):
    """Test citation graph default TTL (24 hours)"""
    cache = mock_redis_cache

    await cache.set_citation_graph("test_key", sample_citation_graph)

    args = cache._client.setex.call_args
    ttl = args[0][1]

    assert ttl == cache.CITATION_GRAPH_TTL
    assert ttl == 86400  # 24 hours


@pytest.mark.asyncio
async def test_citation_graph_custom_ttl(mock_redis_cache, sample_citation_graph):
    """Test citation graph custom TTL"""
    cache = mock_redis_cache

    custom_ttl = 3600  # 1 hour
    await cache.set_citation_graph("test_key", sample_citation_graph, ttl=custom_ttl)

    args = cache._client.setex.call_args
    ttl = args[0][1]

    assert ttl == custom_ttl


# ============================================================================
# Test 3: Paper Metadata Caching
# ============================================================================

@pytest.mark.asyncio
async def test_paper_metadata_cache_miss(mock_redis_cache):
    """Test paper metadata cache miss"""
    cache = mock_redis_cache

    cache._client.get.return_value = None

    result = await cache.get_paper_metadata("DOI:10.1234/test")

    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_paper_metadata(mock_redis_cache):
    """Test caching and retrieving paper metadata"""
    cache = mock_redis_cache

    paper_metadata = {
        "doi": "10.1234/test",
        "title": "Test Paper",
        "citation_count": 100
    }

    # Set cache
    await cache.set_paper_metadata("DOI:10.1234/test", paper_metadata)

    cache._client.setex.assert_called_once()

    # Mock get to return the metadata
    import json
    cache._client.get.return_value = json.dumps(paper_metadata)

    # Get cache
    result = await cache.get_paper_metadata("DOI:10.1234/test")

    assert result is not None
    assert result["title"] == "Test Paper"
    assert result["citation_count"] == 100


@pytest.mark.asyncio
async def test_paper_metadata_ttl_default(mock_redis_cache):
    """Test paper metadata default TTL (7 days)"""
    cache = mock_redis_cache

    await cache.set_paper_metadata("DOI:10.1234/test", {"title": "Test"})

    args = cache._client.setex.call_args
    ttl = args[0][1]

    assert ttl == cache.PAPER_METADATA_TTL
    assert ttl == 604800  # 7 days


# ============================================================================
# Test 4: Cache Invalidation
# ============================================================================

@pytest.mark.asyncio
async def test_invalidate_citation_graphs(mock_redis_cache):
    """Test invalidating citation graphs for a goal"""
    cache = mock_redis_cache

    # Mock scan_iter to return some keys
    async def mock_scan():
        yield "coscientist:citation_graph:goal:test_goal:hash1"
        yield "coscientist:citation_graph:goal:test_goal:hash2"

    cache._client.scan_iter.return_value = mock_scan()

    await cache.invalidate_citation_graphs("test_goal")

    # Verify delete was called with the keys
    cache._client.delete.assert_called_once()
    deleted_keys = cache._client.delete.call_args[0]
    assert len(deleted_keys) == 2


# ============================================================================
# Test 5: Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_get_citation_graph_error_handling(mock_redis_cache):
    """Test error handling in get_citation_graph"""
    cache = mock_redis_cache

    # Mock Redis error
    cache._client.get.side_effect = Exception("Redis connection error")

    result = await cache.get_citation_graph("test_key")

    # Should return None on error (graceful degradation)
    assert result is None


@pytest.mark.asyncio
async def test_set_citation_graph_error_handling(mock_redis_cache, sample_citation_graph):
    """Test error handling in set_citation_graph"""
    cache = mock_redis_cache

    # Mock Redis error
    cache._client.setex.side_effect = Exception("Redis connection error")

    # Should not raise exception
    await cache.set_citation_graph("test_key", sample_citation_graph)


# ============================================================================
# Test 6: Edge Cases
# ============================================================================

def test_serialize_empty_graph():
    """Test serializing empty citation graph"""
    cache = RedisCache()

    empty_graph = CitationGraph()
    graph_dict = cache._graph_to_dict(empty_graph)

    assert graph_dict["nodes"] == []
    assert graph_dict["edges"] == []


def test_deserialize_empty_graph():
    """Test deserializing empty citation graph"""
    cache = RedisCache()

    empty_dict = {
        "nodes": [],
        "edges": [],
        "metadata": {}
    }

    graph = cache._dict_to_graph(empty_dict)

    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_serialize_graph_with_metadata(sample_citation_graph):
    """Test serializing graph with metadata"""
    cache = RedisCache()

    # Metadata is optional - add it manually
    sample_citation_graph.metadata = {"research_goal_id": "test_goal"}

    graph_dict = cache._graph_to_dict(sample_citation_graph)

    assert graph_dict["metadata"]["research_goal_id"] == "test_goal"

    # Also test without metadata (default case)
    graph_no_metadata = CitationGraph()
    graph_dict2 = cache._graph_to_dict(graph_no_metadata)
    assert graph_dict2["metadata"] == {}


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    print("Running Citation Graph Caching Tests...")
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
