"""
Unit tests for Citation Graph Expander
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.literature.graph_expander import (
    CitationGraphExpander,
    ExpansionStrategy,
    ExpansionResult
)
from src.literature.citation_graph import CitationGraph
from src.tools.semantic_scholar import SemanticScholarPaper


# Sample test data
SAMPLE_SEED_PAPER = {
    "paper_id": "seed123",
    "title": "Seed Paper Title",
    "authors": ["Author A", "Author B"],
    "year": 2020,
    "doi": "10.1234/seed",
    "pmid": None,
    "citation_count": 100,
    "reference_count": 30
}

SAMPLE_REFERENCE_PAPERS = [
    {
        "paper_id": "ref1",
        "title": "Reference Paper 1",
        "authors": ["Author C"],
        "year": 2015,
        "doi": "10.1234/ref1",
        "pmid": None,
        "citation_count": 500,
        "reference_count": 20
    },
    {
        "paper_id": "ref2",
        "title": "Reference Paper 2",
        "authors": ["Author D"],
        "year": 2017,
        "doi": "10.1234/ref2",
        "pmid": None,
        "citation_count": 300,
        "reference_count": 25
    }
]

SAMPLE_CITATION_PAPERS = [
    {
        "paper_id": "cit1",
        "title": "Citing Paper 1",
        "authors": ["Author E"],
        "year": 2021,
        "doi": "10.1234/cit1",
        "pmid": None,
        "citation_count": 50,
        "reference_count": 15
    },
    {
        "paper_id": "cit2",
        "title": "Citing Paper 2",
        "authors": ["Author F"],
        "year": 2022,
        "doi": "10.1234/cit2",
        "pmid": None,
        "citation_count": 30,
        "reference_count": 18
    }
]


@pytest.fixture
def citation_graph():
    """Create empty citation graph"""
    return CitationGraph()


@pytest.fixture
def mock_semantic_tool():
    """Create mock Semantic Scholar tool"""
    tool = AsyncMock()
    tool.name = "semantic_scholar"

    # Mock get_paper method
    async def mock_get_paper(paper_id):
        if paper_id == "seed123":
            return SemanticScholarPaper(**SAMPLE_SEED_PAPER)
        elif paper_id == "ref1":
            return SemanticScholarPaper(**SAMPLE_REFERENCE_PAPERS[0])
        elif paper_id == "ref2":
            return SemanticScholarPaper(**SAMPLE_REFERENCE_PAPERS[1])
        elif paper_id == "cit1":
            return SemanticScholarPaper(**SAMPLE_CITATION_PAPERS[0])
        elif paper_id == "cit2":
            return SemanticScholarPaper(**SAMPLE_CITATION_PAPERS[1])
        else:
            raise ValueError(f"Paper not found: {paper_id}")

    tool.get_paper = AsyncMock(side_effect=mock_get_paper)

    # Mock get_references method
    async def mock_get_references(paper_id, limit=100):
        if paper_id == "seed123":
            return [
                SemanticScholarPaper(**paper)
                for paper in SAMPLE_REFERENCE_PAPERS
            ]
        return []

    tool.get_references = AsyncMock(side_effect=mock_get_references)

    # Mock get_citations method
    async def mock_get_citations(paper_id, limit=100):
        if paper_id == "seed123":
            return [
                SemanticScholarPaper(**paper)
                for paper in SAMPLE_CITATION_PAPERS
            ]
        return []

    tool.get_citations = AsyncMock(side_effect=mock_get_citations)

    return tool


@pytest.fixture
def expander(citation_graph, mock_semantic_tool):
    """Create CitationGraphExpander with mocked tool"""
    return CitationGraphExpander(
        graph=citation_graph,
        tools={"semantic_scholar": mock_semantic_tool}
    )


class TestCitationGraphExpanderInitialization:
    """Test expander initialization"""

    def test_init(self, expander, citation_graph, mock_semantic_tool):
        """Test initialization"""
        assert expander.graph == citation_graph
        assert "semantic_scholar" in expander.tools
        assert expander.api_call_count == 0
        assert len(expander.visited_papers) == 0


class TestPaperDeduplication:
    """Test deduplication logic"""

    def test_canonical_id_doi_priority(self, expander):
        """Test DOI takes priority for canonical ID"""
        paper_data = {
            "doi": "10.1234/test",
            "pmid": "12345678",
            "paper_id": "s2_id"
        }

        canonical_id = expander._get_paper_canonical_id(paper_data)
        assert canonical_id == "DOI:10.1234/test"

    def test_canonical_id_pmid_fallback(self, expander):
        """Test PMID used when DOI missing"""
        paper_data = {
            "doi": None,
            "pmid": "12345678",
            "paper_id": "s2_id"
        }

        canonical_id = expander._get_paper_canonical_id(paper_data)
        assert canonical_id == "PMID:12345678"

    def test_canonical_id_s2_fallback(self, expander):
        """Test S2 paper_id used when DOI/PMID missing"""
        paper_data = {
            "doi": None,
            "pmid": None,
            "paper_id": "s2_id"
        }

        canonical_id = expander._get_paper_canonical_id(paper_data)
        assert canonical_id == "S2:s2_id"

    def test_is_duplicate_detection(self, expander):
        """Test duplicate detection"""
        paper_data = SAMPLE_SEED_PAPER.copy()

        # First add should not be duplicate
        assert not expander._is_duplicate(paper_data)

        # Add paper to graph
        paper_id = expander._add_paper_to_graph(paper_data)
        assert paper_id is not None

        # Second add should be duplicate
        assert expander._is_duplicate(paper_data)


class TestAddPaperToGraph:
    """Test adding papers to graph"""

    def test_add_paper_basic(self, expander):
        """Test basic paper addition"""
        paper_data = SAMPLE_SEED_PAPER.copy()

        paper_id = expander._add_paper_to_graph(paper_data)

        assert paper_id is not None
        assert paper_id in expander.graph.nodes
        assert expander.graph.nodes[paper_id].title == "Seed Paper Title"

    def test_add_paper_duplicate_returns_existing_id(self, expander):
        """Test adding duplicate paper returns existing ID"""
        paper_data = SAMPLE_SEED_PAPER.copy()

        # Add first time
        id1 = expander._add_paper_to_graph(paper_data)

        # Add second time (duplicate)
        id2 = expander._add_paper_to_graph(paper_data)

        # Should return same ID
        assert id1 == id2

        # Should only have one node
        assert len(expander.graph.nodes) == 1

    def test_add_paper_updates_id_map(self, expander):
        """Test ID map is updated"""
        paper_data = SAMPLE_SEED_PAPER.copy()

        paper_id = expander._add_paper_to_graph(paper_data)

        canonical_id = expander._get_paper_canonical_id(paper_data)
        assert canonical_id in expander.id_map
        assert expander.id_map[canonical_id] == paper_id


@pytest.mark.asyncio
class TestBackwardExpansion:
    """Test backward (references) expansion"""

    async def test_expand_backward_depth_1(self, expander, mock_semantic_tool):
        """Test backward expansion depth=1"""
        result = await expander.expand_from_paper(
            paper_id="seed123",
            strategy=ExpansionStrategy.BACKWARD,
            max_depth=1
        )

        # Verify result
        assert isinstance(result, ExpansionResult)
        assert result.papers_added >= 2  # At least 2 references added
        assert result.depth_reached == 0  # Depth 0 means seed + immediate neighbors

        # Verify graph structure
        assert len(expander.graph.nodes) >= 3  # Seed + 2 references
        assert len(expander.graph.edges) >= 2  # 2 citation edges

        # Verify API calls
        assert expander.api_call_count > 0

    async def test_expand_backward_citations_added(self, expander, mock_semantic_tool):
        """Test citation edges are added correctly"""
        await expander.expand_from_paper(
            paper_id="seed123",
            strategy=ExpansionStrategy.BACKWARD,
            max_depth=1
        )

        # Find the seed paper in graph
        seed_node_id = None
        for node_id, node in expander.graph.nodes.items():
            if "seed" in node_id.lower():
                seed_node_id = node_id
                break

        assert seed_node_id is not None

        # Verify seed paper has citations (references it cites)
        citations = expander.graph.get_citations(seed_node_id)
        assert len(citations) >= 2  # Should have 2 references


@pytest.mark.asyncio
class TestForwardExpansion:
    """Test forward (citations) expansion"""

    async def test_expand_forward_depth_1(self, expander, mock_semantic_tool):
        """Test forward expansion depth=1"""
        result = await expander.expand_from_paper(
            paper_id="seed123",
            strategy=ExpansionStrategy.FORWARD,
            max_depth=1
        )

        # Verify result
        assert isinstance(result, ExpansionResult)
        assert result.papers_added >= 2  # At least 2 citing papers added

        # Verify graph has citing papers
        assert len(expander.graph.nodes) >= 3  # Seed + 2 citations


@pytest.mark.asyncio
class TestBidirectionalExpansion:
    """Test bidirectional expansion"""

    async def test_expand_bidirectional(self, expander, mock_semantic_tool):
        """Test bidirectional expansion"""
        result = await expander.expand_from_paper(
            paper_id="seed123",
            strategy=ExpansionStrategy.BIDIRECTIONAL,
            max_depth=1
        )

        # Verify result
        assert isinstance(result, ExpansionResult)
        # Should have papers from both directions
        # Seed + 2 references + 2 citations = 5 papers
        assert result.papers_added >= 4

        # Verify we fetched both references and citations
        assert mock_semantic_tool.get_references.called
        assert mock_semantic_tool.get_citations.called


@pytest.mark.asyncio
class TestBatchExpansion:
    """Test expanding from multiple seed papers"""

    async def test_expand_from_results(self, expander, mock_semantic_tool):
        """Test expanding from search results"""
        search_results = [
            SAMPLE_SEED_PAPER.copy(),
            SAMPLE_REFERENCE_PAPERS[0].copy()
        ]

        graph = await expander.expand_from_results(
            search_results,
            depth=1,
            strategy=ExpansionStrategy.BACKWARD
        )

        # Verify graph was returned
        assert isinstance(graph, CitationGraph)

        # Verify both seeds were added
        assert len(graph.nodes) >= 2

    async def test_expand_from_results_handles_errors(self, expander, mock_semantic_tool):
        """Test batch expansion handles errors gracefully"""
        # Add a paper that will cause an error
        search_results = [
            SAMPLE_SEED_PAPER.copy(),
            {"paper_id": "invalid_paper", "title": "Invalid"}
        ]

        # Should not raise exception
        graph = await expander.expand_from_results(
            search_results,
            depth=1
        )

        # Should still have at least the valid paper
        assert len(graph.nodes) >= 1


class TestRelevanceCalculation:
    """Test relevance scoring"""

    def test_calculate_relevance_keyword_match(self, expander):
        """Test relevance calculation with keyword matching"""
        paper_data = {
            "title": "Machine Learning for Biology",
            "abstract": "This paper discusses machine learning applications",
            "citation_count": 100
        }

        score = expander.calculate_relevance(paper_data, "machine learning")

        # Should have positive score due to title match
        assert score > 0

    def test_calculate_relevance_no_match(self, expander):
        """Test relevance calculation with no matches"""
        paper_data = {
            "title": "Unrelated Topic",
            "abstract": "Completely different subject",
            "citation_count": 0
        }

        score = expander.calculate_relevance(paper_data, "machine learning")

        # Should have low or zero score
        assert score >= 0
        assert score < 0.5


class TestStatistics:
    """Test statistics gathering"""

    def test_get_statistics_empty(self, expander):
        """Test statistics on empty graph"""
        stats = expander.get_statistics()

        assert stats["total_papers"] == 0
        assert stats["total_citations"] == 0
        assert stats["api_calls_made"] == 0

    @pytest.mark.asyncio
    async def test_get_statistics_after_expansion(self, expander, mock_semantic_tool):
        """Test statistics after expansion"""
        await expander.expand_from_paper(
            paper_id="seed123",
            strategy=ExpansionStrategy.BACKWARD,
            max_depth=1
        )

        stats = expander.get_statistics()

        assert stats["total_papers"] > 0
        assert stats["api_calls_made"] > 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
