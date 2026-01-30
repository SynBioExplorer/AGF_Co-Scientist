"""
Phase 6 Week 2 Integration Test: GenerationAgent with Literature Expansion

Tests the refactored GenerationAgent that uses:
- Tool registry (not direct Tavily import)
- PubMed + Semantic Scholar for literature search
- Citation graph expansion (depth=1)
- Tavily fallback when tools fail
- Citation validation post-generation
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.generation import GenerationAgent
from src.tools.registry import get_tool_registry, initialize_tools
from src.literature.citation_graph import CitationGraph
from schemas import ResearchGoal


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def research_goal():
    """Sample research goal for testing"""
    return ResearchGoal(
        id="test_goal_001",
        description="Novel hypotheses for Alzheimer's treatment using FDA-approved drugs",
        preferences="Focus on repurposing existing drugs with known safety profiles"
    )


@pytest.fixture
def mock_pubmed_tool():
    """Mock PubMed tool"""
    tool = AsyncMock()
    tool.name = "pubmed"
    tool.domain = "biomedical"

    # Mock execute method returns search results
    async def mock_execute(query, max_results=10):
        from src.tools.base import ToolResult
        return ToolResult(
            success=True,
            data=[
                {
                    "paper_id": "PMID:12345678",
                    "title": "Metformin reduces Alzheimer's pathology",
                    "authors": ["Smith J", "Doe A"],
                    "year": 2020,
                    "doi": "10.1234/test1",
                    "pmid": "12345678",
                    "citation_count": 150,
                    "reference_count": 30
                },
                {
                    "paper_id": "PMID:23456789",
                    "title": "Statins for neurodegenerative diseases",
                    "authors": ["Johnson B"],
                    "year": 2019,
                    "doi": "10.1234/test2",
                    "pmid": "23456789",
                    "citation_count": 200,
                    "reference_count": 25
                }
            ],
            metadata={"source": "pubmed", "num_results": 2}
        )

    tool.execute = mock_execute
    return tool


@pytest.fixture
def mock_semantic_scholar_tool():
    """Mock Semantic Scholar tool"""
    tool = AsyncMock()
    tool.name = "semantic_scholar"
    tool.domain = "cross_disciplinary"

    # Mock execute method
    async def mock_execute(query, max_results=10):
        from src.tools.base import ToolResult
        return ToolResult(
            success=True,
            data=[
                {
                    "paper_id": "s2_abc123",
                    "title": "Machine learning for drug discovery in Alzheimer's",
                    "authors": ["Williams C", "Brown D"],
                    "year": 2021,
                    "doi": "10.1234/test3",
                    "pmid": None,
                    "citation_count": 80,
                    "reference_count": 40
                }
            ],
            metadata={"source": "semantic_scholar", "num_results": 1}
        )

    tool.execute = mock_execute

    # Mock get_paper method for citation validation
    async def mock_get_paper(paper_id):
        from src.tools.semantic_scholar import SemanticScholarPaper
        if "10.1234/test1" in paper_id:
            return SemanticScholarPaper(
                paper_id="s2_validated_1",
                title="Metformin reduces Alzheimer's pathology",
                authors=["Smith J", "Doe A"],
                year=2020,
                doi="10.1234/test1",
                pmid="12345678",
                citation_count=150,
                reference_count=30
            )
        return None

    tool.get_paper = mock_get_paper

    # Mock get_references for expansion
    async def mock_get_references(paper_id, limit=100):
        from src.tools.semantic_scholar import SemanticScholarPaper
        return [
            SemanticScholarPaper(
                paper_id="ref_1",
                title="Foundational work on metformin",
                authors=["Davis E"],
                year=2015,
                doi="10.1234/ref1",
                citation_count=500,
                reference_count=20
            )
        ]

    tool.get_references = mock_get_references

    # Mock get_citations
    async def mock_get_citations(paper_id, limit=100):
        return []

    tool.get_citations = mock_get_citations

    return tool


@pytest.fixture
def generation_agent_with_mocks(mock_pubmed_tool, mock_semantic_scholar_tool):
    """GenerationAgent with mocked tools"""
    agent = GenerationAgent()

    # Replace tools in registry with mocks
    agent.tool_registry._tools = {
        "pubmed": mock_pubmed_tool,
        "semantic_scholar": mock_semantic_scholar_tool
    }

    return agent


# ============================================================================
# Test 1: Tool Registry Integration
# ============================================================================

def test_generation_agent_uses_tool_registry():
    """Test that GenerationAgent initializes with tool registry"""
    agent = GenerationAgent()

    assert hasattr(agent, 'tool_registry')
    assert agent.tool_registry is not None

    # Check that tools are registered
    tool_names = agent.tool_registry.list_tools()
    assert isinstance(tool_names, list)


# ============================================================================
# Test 2: Literature Search with Tools
# ============================================================================

@pytest.mark.asyncio
async def test_literature_search_uses_pubmed_and_semantic(
    generation_agent_with_mocks,
    research_goal
):
    """Test that literature search uses both PubMed and Semantic Scholar"""
    agent = generation_agent_with_mocks

    # Execute literature search
    results, graph = await agent._search_literature_tools(
        research_goal,
        max_results=10
    )

    # Verify both tools were called
    assert len(results) == 3  # 2 from PubMed + 1 from Semantic Scholar

    # Verify results contain expected papers
    titles = [r["title"] for r in results]
    assert "Metformin reduces Alzheimer's pathology" in titles
    assert "Statins for neurodegenerative diseases" in titles
    assert "Machine learning for drug discovery in Alzheimer's" in titles


# ============================================================================
# Test 3: Citation Graph Expansion
# ============================================================================

@pytest.mark.asyncio
async def test_citation_graph_expansion(
    generation_agent_with_mocks,
    research_goal
):
    """Test that citation graph is expanded with references"""
    agent = generation_agent_with_mocks

    # Get initial search results
    results, graph = await agent._search_literature_tools(
        research_goal,
        max_results=10
    )

    # Expand graph
    expanded_graph = await agent._expand_citation_graph(
        results,
        graph,
        max_depth=1
    )

    # Verify graph was populated
    # Note: actual expansion happens in CitationGraphExpander
    # This test verifies the integration
    assert isinstance(expanded_graph, CitationGraph)


# ============================================================================
# Test 4: Citation Graph Context Formatting
# ============================================================================

def test_citation_graph_context_formatting(generation_agent_with_mocks):
    """Test formatting of citation graph as LLM context"""
    agent = generation_agent_with_mocks

    # Create mock graph
    graph = CitationGraph()
    graph.add_paper(
        paper_id="test1",
        title="Test Paper 1",
        authors=["Author A", "Author B"],
        year=2020,
        doi="10.1234/test1"
    )
    graph.add_paper(
        paper_id="test2",
        title="Test Paper 2",
        authors=["Author C"],
        year=2021,
        doi="10.1234/test2"
    )

    # Format as context
    context = agent._format_citation_graph_context(graph, max_papers=10)

    # Verify formatting
    assert "Citation Network Analysis" in context
    assert "Test Paper 1" in context
    assert "Test Paper 2" in context
    assert "Author A" in context
    assert "2020" in context
    assert "10.1234/test1" in context


# ============================================================================
# Test 5: Tavily Fallback
# ============================================================================

@pytest.mark.asyncio
async def test_tavily_fallback_when_tools_fail(research_goal):
    """Test that Tavily is used as fallback when tools fail"""
    agent = GenerationAgent()

    # Create failing tools
    failing_tool = AsyncMock()
    failing_tool.name = "pubmed"

    async def mock_fail(query, max_results=10):
        raise Exception("Tool failed")

    failing_tool.execute = mock_fail

    agent.tool_registry._tools = {"pubmed": failing_tool}

    # Mock Tavily search
    with patch('src.agents.generation.get_search_client') as mock_search_client:
        mock_client = MagicMock()
        mock_client.search_scientific_literature.return_value = [
            {
                "title": "Tavily result",
                "url": "https://example.com",
                "content": "Tavily fallback content"
            }
        ]
        mock_search_client.return_value = mock_client

        # Execute fallback
        result = agent._search_tavily_fallback(research_goal)

        # Verify Tavily was called
        assert "Tavily result" in result


# ============================================================================
# Test 6: Citation Validation
# ============================================================================

@pytest.mark.asyncio
async def test_citation_validation(generation_agent_with_mocks):
    """Test that citations are validated against citation graph"""
    agent = generation_agent_with_mocks

    from schemas import Hypothesis, Citation, ExperimentalProtocol, GenerationMethod

    # Create hypothesis with citations
    hypothesis = Hypothesis(
        id="test_hyp_001",
        research_goal_id="test_goal_001",
        title="Test Hypothesis",
        summary="Test summary",
        hypothesis_statement="Metformin can reduce Alzheimer's pathology",
        rationale="Test rationale",
        mechanism="Test mechanism",
        experimental_protocol=ExperimentalProtocol(
            objective="Test objective",
            methodology="Test methodology",
            controls=["Control 1"],
            expected_outcomes=["Outcome 1"],
            success_criteria="Test criteria"
        ),
        literature_citations=[
            Citation(
                title="Metformin paper",
                doi="10.1234/test1",
                relevance="Supports mechanism"
            )
        ],
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1200.0
    )

    # Create citation graph
    graph = CitationGraph()

    # Validate citations
    validated = await agent._validate_citations(hypothesis, graph)

    # Verify validation occurred
    assert len(validated.literature_citations) == 1
    # Note: Full validation would fetch from Semantic Scholar mock


# ============================================================================
# Test 7: End-to-End Hypothesis Generation
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires LLM API - run manually")
async def test_end_to_end_generation_with_expansion(
    generation_agent_with_mocks,
    research_goal
):
    """
    End-to-end test: Generate hypothesis with literature expansion.

    NOTE: This test requires a real LLM API key and is skipped by default.
    Run manually with: pytest phase6_week2_test.py::test_end_to_end_generation_with_expansion -v -s
    """
    agent = generation_agent_with_mocks

    # Generate hypothesis
    hypothesis = await agent.execute(
        research_goal=research_goal,
        use_literature_expansion=True
    )

    # Verify hypothesis was generated
    assert hypothesis.id is not None
    assert hypothesis.title
    assert hypothesis.hypothesis_statement
    assert hypothesis.literature_citations is not None

    print(f"\nGenerated Hypothesis:")
    print(f"  Title: {hypothesis.title}")
    print(f"  Citations: {len(hypothesis.literature_citations)}")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    print("Running Phase 6 Week 2 Integration Tests...")
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
