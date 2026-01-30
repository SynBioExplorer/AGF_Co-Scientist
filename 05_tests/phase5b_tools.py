"""
Tests for Phase 5B: Literature Tool Integration

This test suite validates:
- Tool registry operations
- PubMed search functionality
- Rate limiting behavior
- Error handling
- API endpoints
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import xml.etree.ElementTree as ET

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.base import BaseTool, ToolResult
from src.tools.registry import ToolRegistry
from src.tools.pubmed import PubMedTool, PubMedArticle


# ==============================================================================
# Test Tool Base Classes
# ==============================================================================


class MockTool(BaseTool):
    """Mock tool for testing"""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def domain(self) -> str:
        return "testing"

    async def execute(self, query: str, **kwargs) -> ToolResult:
        return ToolResult.success_result(
            data={"query": query, "kwargs": kwargs},
            metadata={"tool": "mock"}
        )


def test_tool_result_success():
    """Test creating a successful tool result"""
    result = ToolResult.success_result(
        data={"test": "data"},
        metadata={"key": "value"}
    )

    assert result.success is True
    assert result.data == {"test": "data"}
    assert result.error is None
    assert result.metadata == {"key": "value"}


def test_tool_result_error():
    """Test creating an error tool result"""
    result = ToolResult.error_result(
        error="Test error",
        metadata={"key": "value"}
    )

    assert result.success is False
    assert result.data is None
    assert result.error == "Test error"
    assert result.metadata == {"key": "value"}


def test_base_tool_to_dict():
    """Test converting tool to dictionary"""
    tool = MockTool()
    tool_dict = tool.to_dict()

    assert tool_dict["name"] == "mock_tool"
    assert tool_dict["description"] == "A mock tool for testing"
    assert tool_dict["domain"] == "testing"


# ==============================================================================
# Test Tool Registry
# ==============================================================================


def test_registry_register():
    """Test registering a tool"""
    registry = ToolRegistry()
    tool = MockTool()

    registry.register(tool)

    assert "mock_tool" in registry.list_tools()
    assert registry.get("mock_tool") is tool


def test_registry_register_duplicate():
    """Test registering a duplicate tool raises error"""
    registry = ToolRegistry()
    tool1 = MockTool()
    tool2 = MockTool()

    registry.register(tool1)

    with pytest.raises(Exception):  # CoScientistError
        registry.register(tool2)


def test_registry_get_nonexistent():
    """Test getting a non-existent tool"""
    registry = ToolRegistry()

    result = registry.get("nonexistent")

    assert result is None


def test_registry_get_tools_for_domain():
    """Test getting tools by domain"""
    registry = ToolRegistry()
    tool = MockTool()
    registry.register(tool)

    testing_tools = registry.get_tools_for_domain("testing")
    biomedical_tools = registry.get_tools_for_domain("biomedical")

    assert len(testing_tools) == 1
    assert testing_tools[0] is tool
    assert len(biomedical_tools) == 0


def test_registry_list_all_tools():
    """Test listing all tools with details"""
    registry = ToolRegistry()
    tool = MockTool()
    registry.register(tool)

    all_tools = registry.list_all_tools()

    assert len(all_tools) == 1
    assert all_tools[0]["name"] == "mock_tool"
    assert all_tools[0]["domain"] == "testing"


def test_registry_unregister():
    """Test unregistering a tool"""
    registry = ToolRegistry()
    tool = MockTool()
    registry.register(tool)

    result = registry.unregister("mock_tool")

    assert result is True
    assert "mock_tool" not in registry.list_tools()


def test_registry_unregister_nonexistent():
    """Test unregistering a non-existent tool"""
    registry = ToolRegistry()

    result = registry.unregister("nonexistent")

    assert result is False


# ==============================================================================
# Test PubMed Tool
# ==============================================================================


def test_pubmed_article_model():
    """Test PubMedArticle data model"""
    article = PubMedArticle(
        pmid="12345678",
        title="Test Article",
        abstract="This is a test abstract.",
        authors=["John Doe", "Jane Smith"],
        journal="Test Journal",
        year=2024,
        doi="10.1234/test"
    )

    assert article.pmid == "12345678"
    assert article.title == "Test Article"
    assert len(article.authors) == 2
    assert article.year == 2024


def test_pubmed_tool_properties():
    """Test PubMed tool properties"""
    tool = PubMedTool()

    assert tool.name == "pubmed"
    assert tool.domain == "biomedical"
    assert "PubMed" in tool.description


def test_pubmed_tool_rate_limiting():
    """Test that rate limiting parameters are set correctly"""
    # Without API key
    tool_no_key = PubMedTool(api_key=None)
    assert tool_no_key.requests_per_second == 3
    assert tool_no_key.min_request_interval == pytest.approx(1.0 / 3)

    # With API key
    tool_with_key = PubMedTool(api_key="test_key")
    assert tool_with_key.requests_per_second == 10
    assert tool_with_key.min_request_interval == pytest.approx(1.0 / 10)


@pytest.mark.asyncio
async def test_pubmed_search_mock():
    """Test PubMed search with mocked HTTP responses"""
    # Mock XML responses
    search_xml = """<?xml version="1.0"?>
    <eSearchResult>
        <IdList>
            <Id>12345678</Id>
            <Id>87654321</Id>
        </IdList>
    </eSearchResult>
    """

    fetch_xml = """<?xml version="1.0"?>
    <PubmedArticleSet>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>12345678</PMID>
                <Article>
                    <ArticleTitle>Test Article Title</ArticleTitle>
                    <Abstract>
                        <AbstractText>This is a test abstract.</AbstractText>
                    </Abstract>
                    <Journal>
                        <Title>Test Journal</Title>
                    </Journal>
                    <AuthorList>
                        <Author>
                            <LastName>Doe</LastName>
                            <ForeName>John</ForeName>
                        </Author>
                    </AuthorList>
                    <PubDate>
                        <Year>2024</Year>
                    </PubDate>
                </Article>
            </MedlineCitation>
            <PubmedData>
                <ArticleIdList>
                    <ArticleId IdType="doi">10.1234/test</ArticleId>
                </ArticleIdList>
            </PubmedData>
        </PubmedArticle>
    </PubmedArticleSet>
    """

    # Create mock responses
    mock_search_response = Mock()
    mock_search_response.status = 200
    mock_search_response.text = AsyncMock(return_value=search_xml)
    mock_search_response.raise_for_status = Mock()

    mock_fetch_response = Mock()
    mock_fetch_response.status = 200
    mock_fetch_response.text = AsyncMock(return_value=fetch_xml)
    mock_fetch_response.raise_for_status = Mock()

    # Mock aiohttp session
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = AsyncMock()

    # First call returns search results, second call returns fetch results
    mock_get_context1 = AsyncMock()
    mock_get_context1.__aenter__ = AsyncMock(return_value=mock_search_response)
    mock_get_context1.__aexit__ = AsyncMock(return_value=None)

    mock_get_context2 = AsyncMock()
    mock_get_context2.__aenter__ = AsyncMock(return_value=mock_fetch_response)
    mock_get_context2.__aexit__ = AsyncMock(return_value=None)

    mock_session.get.side_effect = [mock_get_context1, mock_get_context2]

    # Patch aiohttp.ClientSession
    with patch('aiohttp.ClientSession', return_value=mock_session):
        tool = PubMedTool(api_key="test_key")
        result = await tool.execute("cancer research", max_results=2)

    # Verify result
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0]["pmid"] == "12345678"
    assert result.data[0]["title"] == "Test Article Title"
    assert result.data[0]["abstract"] == "This is a test abstract."
    assert "John Doe" in result.data[0]["authors"]
    assert result.metadata["num_results"] == 1


@pytest.mark.asyncio
async def test_pubmed_no_results():
    """Test PubMed search with no results"""
    search_xml = """<?xml version="1.0"?>
    <eSearchResult>
        <IdList>
        </IdList>
    </eSearchResult>
    """

    mock_response = Mock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=search_xml)
    mock_response.raise_for_status = Mock()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_get_context = AsyncMock()
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session.get = AsyncMock(return_value=mock_get_context)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        tool = PubMedTool(api_key="test_key")
        result = await tool.execute("nonexistent query", max_results=5)

    assert result.success is True
    assert result.data == []
    assert result.metadata["num_results"] == 0


@pytest.mark.asyncio
async def test_pubmed_error_handling():
    """Test PubMed error handling"""
    # Mock HTTP error
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_get_context = AsyncMock()
    mock_get_context.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session.get = AsyncMock(return_value=mock_get_context)

    with patch('aiohttp.ClientSession', return_value=mock_session):
        tool = PubMedTool(api_key="test_key")
        result = await tool.execute("test query", max_results=5)

    assert result.success is False
    assert result.error is not None
    assert "error" in result.error.lower()


def test_pubmed_parse_article():
    """Test parsing individual article from XML"""
    xml_str = """
    <PubmedArticle>
        <MedlineCitation>
            <PMID>12345678</PMID>
            <Article>
                <ArticleTitle>Test Article</ArticleTitle>
                <Abstract>
                    <AbstractText>Test abstract text</AbstractText>
                </Abstract>
                <Journal>
                    <Title>Nature</Title>
                </Journal>
                <AuthorList>
                    <Author>
                        <LastName>Smith</LastName>
                        <ForeName>Jane</ForeName>
                    </Author>
                    <Author>
                        <LastName>Doe</LastName>
                        <ForeName>John</ForeName>
                    </Author>
                </AuthorList>
                <PubDate>
                    <Year>2023</Year>
                </PubDate>
            </Article>
        </MedlineCitation>
        <PubmedData>
            <ArticleIdList>
                <ArticleId IdType="doi">10.1038/test</ArticleId>
            </ArticleIdList>
        </PubmedData>
    </PubmedArticle>
    """

    tool = PubMedTool()
    article_elem = ET.fromstring(xml_str)
    article = tool._parse_article(article_elem)

    assert article is not None
    assert article.pmid == "12345678"
    assert article.title == "Test Article"
    assert article.abstract == "Test abstract text"
    assert article.journal == "Nature"
    assert len(article.authors) == 2
    assert "Jane Smith" in article.authors
    assert "John Doe" in article.authors
    assert article.year == 2023
    assert article.doi == "10.1038/test"


# ==============================================================================
# Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_tool_integration_flow():
    """Test complete tool integration flow"""
    # Create registry
    registry = ToolRegistry()

    # Register mock tool
    mock_tool = MockTool()
    registry.register(mock_tool)

    # Get tool from registry
    tool = registry.get("mock_tool")
    assert tool is not None

    # Execute tool
    result = await tool.execute("test query", param1="value1")

    # Verify result
    assert result.success is True
    assert result.data["query"] == "test query"
    assert result.data["kwargs"]["param1"] == "value1"


def test_multiple_tools_in_registry():
    """Test managing multiple tools in registry"""
    registry = ToolRegistry()

    # Create and register multiple mock tools
    class Tool1(MockTool):
        @property
        def name(self):
            return "tool1"

        @property
        def domain(self):
            return "domain1"

    class Tool2(MockTool):
        @property
        def name(self):
            return "tool2"

        @property
        def domain(self):
            return "domain1"

    class Tool3(MockTool):
        @property
        def name(self):
            return "tool3"

        @property
        def domain(self):
            return "domain2"

    registry.register(Tool1())
    registry.register(Tool2())
    registry.register(Tool3())

    # Test listing
    assert len(registry.list_tools()) == 3

    # Test domain filtering
    domain1_tools = registry.get_tools_for_domain("domain1")
    assert len(domain1_tools) == 2

    domain2_tools = registry.get_tools_for_domain("domain2")
    assert len(domain2_tools) == 1


# ==============================================================================
# Main Test Runner
# ==============================================================================


def run_tests():
    """Run all tests"""
    print("=" * 80)
    print("Phase 5B: Literature Tool Integration Tests")
    print("=" * 80)

    # Run pytest
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
