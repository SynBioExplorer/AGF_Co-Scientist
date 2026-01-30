"""
Unit tests for Semantic Scholar tool
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.tools.semantic_scholar import (
    SemanticScholarTool,
    SemanticScholarPaper
)
from src.tools.base import ToolResult


# Sample API responses for mocking
SAMPLE_SEARCH_RESPONSE = {
    "data": [
        {
            "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
            "title": "Attention Is All You Need",
            "abstract": "The dominant sequence transduction models...",
            "authors": [
                {"name": "Ashish Vaswani"},
                {"name": "Noam Shazeer"}
            ],
            "year": 2017,
            "venue": "NeurIPS",
            "externalIds": {
                "DOI": "10.48550/arXiv.1706.03762",
                "PubMed": None
            },
            "citationCount": 50000,
            "referenceCount": 35,
            "isOpenAccess": True,
            "url": "https://www.semanticscholar.org/paper/..."
        }
    ]
}

SAMPLE_PAPER_RESPONSE = {
    "paperId": "649def34f8be52c8b66281af98ae884c09aef38b",
    "title": "Attention Is All You Need",
    "abstract": "The dominant sequence transduction models...",
    "authors": [
        {"name": "Ashish Vaswani"},
        {"name": "Noam Shazeer"}
    ],
    "year": 2017,
    "venue": "NeurIPS",
    "externalIds": {
        "DOI": "10.48550/arXiv.1706.03762",
        "PubMed": None
    },
    "citationCount": 50000,
    "referenceCount": 35,
    "isOpenAccess": True,
    "url": "https://www.semanticscholar.org/paper/..."
}

SAMPLE_CITATIONS_RESPONSE = {
    "data": [
        {
            "citingPaper": {
                "paperId": "abc123",
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "authors": [{"name": "Jacob Devlin"}],
                "year": 2018,
                "venue": "NAACL",
                "externalIds": {"DOI": "10.18653/v1/N19-1423"},
                "citationCount": 30000,
                "referenceCount": 40,
                "isOpenAccess": True,
                "url": "https://www.semanticscholar.org/paper/..."
            }
        }
    ]
}

SAMPLE_REFERENCES_RESPONSE = {
    "data": [
        {
            "citedPaper": {
                "paperId": "xyz789",
                "title": "Long Short-Term Memory",
                "authors": [{"name": "Sepp Hochreiter"}],
                "year": 1997,
                "venue": "Neural Computation",
                "externalIds": {"DOI": "10.1162/neco.1997.9.8.1735"},
                "citationCount": 60000,
                "referenceCount": 25,
                "isOpenAccess": False,
                "url": "https://www.semanticscholar.org/paper/..."
            }
        }
    ]
}


@pytest.fixture
def semantic_tool():
    """Create SemanticScholarTool instance"""
    return SemanticScholarTool()


@pytest.fixture
def semantic_tool_with_key():
    """Create SemanticScholarTool with API key"""
    return SemanticScholarTool(api_key="test_api_key")


class TestSemanticScholarToolInitialization:
    """Test tool initialization"""

    def test_init_without_key(self, semantic_tool):
        """Test initialization without API key"""
        assert semantic_tool.name == "semantic_scholar"
        assert semantic_tool.domain == "cross_disciplinary"
        assert semantic_tool.api_key is None
        assert semantic_tool.requests_per_second == 10

    def test_init_with_key(self, semantic_tool_with_key):
        """Test initialization with API key"""
        assert semantic_tool_with_key.api_key == "test_api_key"
        assert semantic_tool_with_key.requests_per_second == 100

    def test_tool_properties(self, semantic_tool):
        """Test tool properties"""
        assert semantic_tool.name == "semantic_scholar"
        assert semantic_tool.description
        assert "citation" in semantic_tool.description.lower()


class TestSemanticScholarPaperParsing:
    """Test paper data parsing"""

    def test_parse_paper_complete(self, semantic_tool):
        """Test parsing paper with all fields"""
        paper = semantic_tool._parse_paper(SAMPLE_PAPER_RESPONSE)

        assert isinstance(paper, SemanticScholarPaper)
        assert paper.paper_id == "649def34f8be52c8b66281af98ae884c09aef38b"
        assert paper.title == "Attention Is All You Need"
        assert paper.abstract == "The dominant sequence transduction models..."
        assert len(paper.authors) == 2
        assert "Ashish Vaswani" in paper.authors
        assert paper.year == 2017
        assert paper.venue == "NeurIPS"
        assert paper.doi == "10.48550/arXiv.1706.03762"
        assert paper.pmid is None
        assert paper.citation_count == 50000
        assert paper.reference_count == 35
        assert paper.is_open_access is True

    def test_parse_paper_minimal(self, semantic_tool):
        """Test parsing paper with minimal fields"""
        minimal_data = {
            "paperId": "test123",
            "title": "Test Paper"
        }

        paper = semantic_tool._parse_paper(minimal_data)

        assert paper.paper_id == "test123"
        assert paper.title == "Test Paper"
        assert paper.authors == []
        assert paper.year is None
        assert paper.citation_count == 0

    def test_parse_paper_with_pmid(self, semantic_tool):
        """Test parsing paper with PMID"""
        data = {
            **SAMPLE_PAPER_RESPONSE,
            "externalIds": {
                "DOI": "10.1038/nature12345",
                "PubMed": "29234567"
            }
        }

        paper = semantic_tool._parse_paper(data)

        assert paper.doi == "10.1038/nature12345"
        assert paper.pmid == "29234567"


@pytest.mark.asyncio
class TestSemanticScholarSearch:
    """Test paper search functionality"""

    @patch("httpx.AsyncClient")
    async def test_search_papers_success(self, mock_client_class, semantic_tool):
        """Test successful paper search"""
        # Setup mock - json() should be a coroutine
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_SEARCH_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute
        papers = await semantic_tool.search_papers("transformers", limit=10)

        # Verify
        assert len(papers) == 1
        assert papers[0].title == "Attention Is All You Need"
        assert papers[0].year == 2017

    @patch("httpx.AsyncClient")
    async def test_search_papers_with_year_filter(self, mock_client_class, semantic_tool):
        """Test search with year filtering"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_SEARCH_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute with year filter
        papers = await semantic_tool.search_papers(
            "machine learning",
            limit=10,
            year_min=2015,
            year_max=2020
        )

        # Verify
        assert len(papers) == 1
        # Check that params included year range
        call_args = mock_client.get.call_args
        assert "year" in call_args.kwargs["params"]

    @patch("httpx.AsyncClient")
    async def test_search_papers_empty_results(self, mock_client_class, semantic_tool):
        """Test search with no results"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"data": []})
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute
        papers = await semantic_tool.search_papers("nonexistent query")

        # Verify
        assert papers == []


@pytest.mark.asyncio
class TestSemanticScholarGetPaper:
    """Test get_paper functionality"""

    @patch("httpx.AsyncClient")
    async def test_get_paper_by_id(self, mock_client_class, semantic_tool):
        """Test fetching paper by Semantic Scholar ID"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_PAPER_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute
        paper = await semantic_tool.get_paper("649def34f8be52c8b66281af98ae884c09aef38b")

        # Verify
        assert paper.title == "Attention Is All You Need"
        assert paper.year == 2017

    @patch("httpx.AsyncClient")
    async def test_get_paper_by_doi(self, mock_client_class, semantic_tool):
        """Test fetching paper by DOI"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_PAPER_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute
        paper = await semantic_tool.get_paper("DOI:10.48550/arXiv.1706.03762")

        # Verify
        assert paper.doi == "10.48550/arXiv.1706.03762"


@pytest.mark.asyncio
class TestSemanticScholarCitations:
    """Test citation network fetching"""

    @patch("httpx.AsyncClient")
    async def test_get_citations(self, mock_client_class, semantic_tool):
        """Test fetching papers citing a paper"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_CITATIONS_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute
        citations = await semantic_tool.get_citations("649def34f8be52c8b66281af98ae884c09aef38b")

        # Verify
        assert len(citations) == 1
        assert citations[0].title == "BERT: Pre-training of Deep Bidirectional Transformers"
        assert citations[0].year == 2018

    @patch("httpx.AsyncClient")
    async def test_get_references(self, mock_client_class, semantic_tool):
        """Test fetching papers referenced by a paper"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_REFERENCES_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute
        references = await semantic_tool.get_references("649def34f8be52c8b66281af98ae884c09aef38b")

        # Verify
        assert len(references) == 1
        assert references[0].title == "Long Short-Term Memory"
        assert references[0].year == 1997


@pytest.mark.asyncio
class TestSemanticScholarExecute:
    """Test execute method (main tool interface)"""

    @patch("httpx.AsyncClient")
    async def test_execute_success(self, mock_client_class, semantic_tool):
        """Test execute method with successful search"""
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value=SAMPLE_SEARCH_RESPONSE)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_client_class.return_value = mock_client

        # Execute
        result = await semantic_tool.execute("transformers", max_results=10)

        # Verify
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert len(result.data) == 1
        assert result.metadata["source"] == "semantic_scholar"
        assert result.metadata["num_results"] == 1


@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting"""

    async def test_rate_limit_enforcement(self, semantic_tool):
        """Test that rate limiting adds delays"""
        import time

        # Make multiple rapid calls
        semantic_tool.last_request_time = time.time()

        start = time.time()
        await semantic_tool._rate_limit()
        elapsed = time.time() - start

        # Should have waited at least min_request_interval
        assert elapsed >= semantic_tool.min_request_interval


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
