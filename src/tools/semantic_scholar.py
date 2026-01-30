"""
Semantic Scholar API Tool

Provides access to citation networks via Semantic Scholar API.
Supports searching papers, fetching metadata, and building citation graphs.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

import httpx
from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolResult
from src.utils.errors import CoScientistError
import structlog

logger = structlog.get_logger()


class SemanticScholarPaper(BaseModel):
    """Represents a paper from Semantic Scholar"""

    paper_id: str = Field(..., description="Semantic Scholar paper ID")
    title: str = Field("", description="Paper title")
    abstract: Optional[str] = Field(None, description="Paper abstract")
    authors: List[str] = Field(default_factory=list, description="Author names")
    year: Optional[int] = Field(None, description="Publication year")
    venue: str = Field("", description="Publication venue/journal")
    doi: Optional[str] = Field(None, description="DOI identifier")
    pmid: Optional[str] = Field(None, description="PubMed ID")
    citation_count: int = Field(0, description="Number of citations")
    reference_count: int = Field(0, description="Number of references")
    is_open_access: bool = Field(False, description="Open access status")
    url: str = Field("", description="Semantic Scholar URL")


class SemanticScholarTool(BaseTool):
    """
    Semantic Scholar citation network tool.

    Provides access to Semantic Scholar's API for building citation networks,
    searching papers across all disciplines, and fetching paper metadata.

    Rate Limits:
        - Free tier: 5,000 requests per 5-minute window (~17 req/sec)
        - With API key: Higher limits available

    API Documentation: https://api.semanticscholar.org/api-docs/
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Semantic Scholar tool.

        Args:
            api_key: Optional API key for higher rate limits
        """
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"

        # Rate limiting
        self.requests_per_second = 100 if self.api_key else 10  # Conservative limits
        self.min_request_interval = 1.0 / self.requests_per_second
        self.last_request_time = 0.0

        # Default fields to fetch
        self.default_fields = [
            "paperId",
            "title",
            "abstract",
            "authors",
            "year",
            "venue",
            "externalIds",
            "citationCount",
            "referenceCount",
            "isOpenAccess",
            "url"
        ]

    @property
    def name(self) -> str:
        return "semantic_scholar"

    @property
    def description(self) -> str:
        return "Search academic papers and build citation networks via Semantic Scholar"

    @property
    def domain(self) -> str:
        return "cross_disciplinary"

    async def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with optional API key"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _parse_paper(self, data: Dict[str, Any]) -> SemanticScholarPaper:
        """Parse API response into SemanticScholarPaper"""
        try:
            # Extract author names
            authors = []
            if "authors" in data and data["authors"]:
                authors = [
                    author.get("name", "")
                    for author in data["authors"]
                    if author.get("name")
                ]

            # Extract external IDs
            external_ids = data.get("externalIds", {}) or {}
            doi = external_ids.get("DOI")
            pmid = external_ids.get("PubMed")

            return SemanticScholarPaper(
                paper_id=data.get("paperId", ""),
                title=data.get("title", ""),
                abstract=data.get("abstract"),
                authors=authors,
                year=data.get("year"),
                venue=data.get("venue", ""),
                doi=doi,
                pmid=pmid,
                citation_count=data.get("citationCount", 0),
                reference_count=data.get("referenceCount", 0),
                is_open_access=data.get("isOpenAccess", False),
                url=data.get("url", "")
            )

        except Exception as e:
            logger.warning("Failed to parse paper", error=str(e), data=data)
            raise CoScientistError(f"Failed to parse paper: {e}")

    async def search_papers(
        self,
        query: str,
        limit: int = 10,
        fields: Optional[List[str]] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None
    ) -> List[SemanticScholarPaper]:
        """
        Search for papers matching query.

        Args:
            query: Search query
            limit: Maximum number of results (default 10, max 100)
            fields: Fields to retrieve (uses defaults if None)
            year_min: Minimum publication year
            year_max: Maximum publication year

        Returns:
            List of SemanticScholarPaper objects
        """
        await self._rate_limit()

        fields_str = ",".join(fields or self.default_fields)
        params = {
            "query": query,
            "limit": min(limit, 100),  # API max is 100
            "fields": fields_str
        }

        if year_min:
            params["year"] = f"{year_min}-"
        if year_max:
            if "year" in params:
                params["year"] = f"{year_min}-{year_max}"
            else:
                params["year"] = f"-{year_max}"

        url = f"{self.base_url}/paper/search"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

            papers = []
            for paper_data in data.get("data", []):
                try:
                    paper = self._parse_paper(paper_data)
                    papers.append(paper)
                except CoScientistError:
                    continue  # Skip papers that fail to parse

            logger.info(
                "Semantic Scholar search completed",
                query=query[:100],
                num_results=len(papers)
            )

            return papers

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise CoScientistError("Semantic Scholar rate limit exceeded")
            raise CoScientistError(f"Semantic Scholar search failed: {e}")
        except httpx.RequestError as e:
            raise CoScientistError(f"Semantic Scholar request failed: {e}")

    async def get_paper(
        self,
        paper_id: str,
        fields: Optional[List[str]] = None
    ) -> SemanticScholarPaper:
        """
        Fetch paper metadata by ID.

        Args:
            paper_id: Semantic Scholar paper ID, DOI, or PMID
                     Examples: "649def34f8be52c8b66281af98ae884c09aef38b"
                              "DOI:10.1038/nature12345"
                              "PMID:29234567"
            fields: Fields to retrieve (uses defaults if None)

        Returns:
            SemanticScholarPaper object
        """
        await self._rate_limit()

        fields_str = ",".join(fields or self.default_fields)
        url = f"{self.base_url}/paper/{paper_id}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={"fields": fields_str},
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

            paper = self._parse_paper(data)

            logger.info(
                "Fetched paper from Semantic Scholar",
                paper_id=paper_id,
                title=paper.title[:100]
            )

            return paper

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise CoScientistError(f"Paper not found: {paper_id}")
            if e.response.status_code == 429:
                raise CoScientistError("Semantic Scholar rate limit exceeded")
            raise CoScientistError(f"Failed to fetch paper: {e}")
        except httpx.RequestError as e:
            raise CoScientistError(f"Semantic Scholar request failed: {e}")

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
        fields: Optional[List[str]] = None
    ) -> List[SemanticScholarPaper]:
        """
        Get papers CITING this paper (forward expansion).

        Args:
            paper_id: Semantic Scholar paper ID, DOI, or PMID
            limit: Maximum number of citations to fetch (max 1000)
            offset: Offset for pagination
            fields: Fields to retrieve (uses defaults if None)

        Returns:
            List of papers that cite the given paper
        """
        await self._rate_limit()

        fields_str = ",".join(fields or self.default_fields)
        url = f"{self.base_url}/paper/{paper_id}/citations"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={
                        "fields": fields_str,
                        "limit": min(limit, 1000),
                        "offset": offset
                    },
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

            papers = []
            for citation_data in data.get("data", []):
                try:
                    # Citations come wrapped in {"citingPaper": {...}}
                    paper_data = citation_data.get("citingPaper", {})
                    if paper_data:
                        paper = self._parse_paper(paper_data)
                        papers.append(paper)
                except CoScientistError:
                    continue

            logger.info(
                "Fetched citations from Semantic Scholar",
                paper_id=paper_id,
                num_citations=len(papers)
            )

            return papers

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise CoScientistError(f"Paper not found: {paper_id}")
            if e.response.status_code == 429:
                raise CoScientistError("Semantic Scholar rate limit exceeded")
            raise CoScientistError(f"Failed to fetch citations: {e}")
        except httpx.RequestError as e:
            raise CoScientistError(f"Semantic Scholar request failed: {e}")

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0,
        fields: Optional[List[str]] = None
    ) -> List[SemanticScholarPaper]:
        """
        Get papers REFERENCED by this paper (backward expansion).

        Args:
            paper_id: Semantic Scholar paper ID, DOI, or PMID
            limit: Maximum number of references to fetch (max 1000)
            offset: Offset for pagination
            fields: Fields to retrieve (uses defaults if None)

        Returns:
            List of papers referenced by the given paper
        """
        await self._rate_limit()

        fields_str = ",".join(fields or self.default_fields)
        url = f"{self.base_url}/paper/{paper_id}/references"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={
                        "fields": fields_str,
                        "limit": min(limit, 1000),
                        "offset": offset
                    },
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()

            papers = []
            for reference_data in data.get("data", []):
                try:
                    # References come wrapped in {"citedPaper": {...}}
                    paper_data = reference_data.get("citedPaper", {})
                    if paper_data:
                        paper = self._parse_paper(paper_data)
                        papers.append(paper)
                except CoScientistError:
                    continue

            logger.info(
                "Fetched references from Semantic Scholar",
                paper_id=paper_id,
                num_references=len(papers)
            )

            return papers

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise CoScientistError(f"Paper not found: {paper_id}")
            if e.response.status_code == 429:
                raise CoScientistError("Semantic Scholar rate limit exceeded")
            raise CoScientistError(f"Failed to fetch references: {e}")
        except httpx.RequestError as e:
            raise CoScientistError(f"Semantic Scholar request failed: {e}")

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Search Semantic Scholar for papers matching query.

        Args:
            query: Search query
            **kwargs: Optional parameters:
                - max_results: Maximum number of results (default 10)
                - year_min: Minimum publication year
                - year_max: Maximum publication year

        Returns:
            ToolResult with list of SemanticScholarPaper objects
        """
        max_results = kwargs.get("max_results", 10)
        year_min = kwargs.get("year_min")
        year_max = kwargs.get("year_max")

        logger.info(
            "Executing Semantic Scholar search",
            query=query[:100],
            max_results=max_results
        )

        try:
            papers = await self.search_papers(
                query=query,
                limit=max_results,
                year_min=year_min,
                year_max=year_max
            )

            return ToolResult.success_result(
                data=[paper.model_dump() for paper in papers],
                metadata={
                    "query": query,
                    "num_results": len(papers),
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "semantic_scholar"
                }
            )

        except CoScientistError as e:
            logger.error("Semantic Scholar search failed", error=str(e))
            return ToolResult.error_result(
                error=str(e),
                metadata={
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error("Unexpected error in Semantic Scholar search", error=str(e))
            return ToolResult.error_result(
                error=f"Unexpected error: {e}",
                metadata={
                    "query": query,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )


# Auto-register the tool
def register_semantic_scholar_tool():
    """Register Semantic Scholar tool in the global registry"""
    from src.tools.registry import registry
    try:
        semantic_tool = SemanticScholarTool()
        registry.register(semantic_tool)
        logger.info("Semantic Scholar tool auto-registered")
    except Exception as e:
        logger.warning("Failed to auto-register Semantic Scholar tool", error=str(e))
