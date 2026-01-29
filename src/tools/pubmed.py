"""PubMed literature search tool using NCBI E-utilities API"""

import asyncio
import time
import xml.etree.ElementTree as ET
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolResult
from src.config import settings
from src.utils.errors import CoScientistError
import structlog

if TYPE_CHECKING:
    import aiohttp

logger = structlog.get_logger()


class PubMedArticle(BaseModel):
    """Represents a PubMed article"""

    pmid: str = Field(..., description="PubMed ID")
    title: str = Field(..., description="Article title")
    abstract: str = Field("", description="Article abstract")
    authors: List[str] = Field(default_factory=list, description="List of author names")
    journal: str = Field("", description="Journal name")
    year: int = Field(0, description="Publication year")
    doi: str = Field("", description="DOI identifier")


class PubMedTool(BaseTool):
    """
    PubMed literature search tool using NCBI E-utilities API.

    This tool provides access to PubMed's biomedical literature database
    using the NCBI E-utilities API. It supports searching and retrieving
    article metadata including titles, abstracts, and author information.

    Rate Limits:
        - Without API key: 3 requests/second
        - With API key: 10 requests/second
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize PubMed tool.

        Args:
            api_key: Optional NCBI API key for higher rate limits
        """
        self.api_key = api_key or getattr(settings, 'pubmed_api_key', None)
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

        # Rate limiting
        self.requests_per_second = 10 if self.api_key else 3
        self.min_request_interval = 1.0 / self.requests_per_second
        self.last_request_time = 0.0

    @property
    def name(self) -> str:
        return "pubmed"

    @property
    def description(self) -> str:
        return "Search PubMed for biomedical literature articles"

    @property
    def domain(self) -> str:
        return "biomedical"

    async def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    async def _esearch(self, query: str, max_results: int) -> List[str]:
        """
        Search PubMed for articles matching the query.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of PubMed IDs
        """
        import aiohttp

        await self._rate_limit()

        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'xml',
            'sort': 'relevance',
        }

        if self.api_key:
            params['api_key'] = self.api_key

        url = f"{self.base_url}/esearch.fcgi"

        try:
            timeout = aiohttp.ClientTimeout(total=getattr(settings, 'tool_timeout_seconds', 30))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    xml_data = await response.text()

            # Parse XML response
            root = ET.fromstring(xml_data)
            id_list = root.find('.//IdList')

            if id_list is None:
                return []

            pmids = [id_elem.text for id_elem in id_list.findall('Id') if id_elem.text]

            logger.info(
                "PubMed search completed",
                query=query[:100],
                num_results=len(pmids)
            )

            return pmids

        except aiohttp.ClientError as e:
            raise CoScientistError(f"PubMed search failed: {e}")
        except ET.ParseError as e:
            raise CoScientistError(f"Failed to parse PubMed XML response: {e}")

    async def _efetch(self, pmids: List[str]) -> List[PubMedArticle]:
        """
        Fetch detailed article information for given PubMed IDs.

        Args:
            pmids: List of PubMed IDs

        Returns:
            List of PubMedArticle objects
        """
        import aiohttp

        if not pmids:
            return []

        await self._rate_limit()

        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': 'xml',
            'rettype': 'abstract',
        }

        if self.api_key:
            params['api_key'] = self.api_key

        url = f"{self.base_url}/efetch.fcgi"

        try:
            timeout = aiohttp.ClientTimeout(total=getattr(settings, 'tool_timeout_seconds', 30))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    xml_data = await response.text()

            # Parse XML response
            root = ET.fromstring(xml_data)
            articles = []

            for article_elem in root.findall('.//PubmedArticle'):
                try:
                    article = self._parse_article(article_elem)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.warning("Failed to parse article", error=str(e))
                    continue

            logger.info("PubMed fetch completed", num_articles=len(articles))

            return articles

        except aiohttp.ClientError as e:
            raise CoScientistError(f"PubMed fetch failed: {e}")
        except ET.ParseError as e:
            raise CoScientistError(f"Failed to parse PubMed XML response: {e}")

    def _parse_article(self, article_elem: ET.Element) -> Optional[PubMedArticle]:
        """Parse a single PubMed article from XML"""
        try:
            medline_citation = article_elem.find('.//MedlineCitation')
            if medline_citation is None:
                return None

            # Get PMID
            pmid_elem = medline_citation.find('.//PMID')
            if pmid_elem is None or not pmid_elem.text:
                return None
            pmid = pmid_elem.text

            # Get article details
            article = medline_citation.find('.//Article')
            if article is None:
                return None

            # Title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None and title_elem.text else ""

            # Abstract
            abstract_elem = article.find('.//AbstractText')
            abstract = abstract_elem.text if abstract_elem is not None and abstract_elem.text else ""

            # Authors
            authors = []
            author_list = article.find('.//AuthorList')
            if author_list is not None:
                for author_elem in author_list.findall('.//Author'):
                    last_name = author_elem.find('.//LastName')
                    fore_name = author_elem.find('.//ForeName')
                    if last_name is not None and last_name.text:
                        name = last_name.text
                        if fore_name is not None and fore_name.text:
                            name = f"{fore_name.text} {name}"
                        authors.append(name)

            # Journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None and journal_elem.text else ""

            # Year
            year = 0
            pub_date = article.find('.//PubDate/Year')
            if pub_date is not None and pub_date.text:
                try:
                    year = int(pub_date.text)
                except ValueError:
                    pass

            # DOI
            doi = ""
            article_id_list = article_elem.find('.//PubmedData/ArticleIdList')
            if article_id_list is not None:
                for article_id in article_id_list.findall('.//ArticleId'):
                    if article_id.get('IdType') == 'doi' and article_id.text:
                        doi = article_id.text
                        break

            return PubMedArticle(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                year=year,
                doi=doi,
            )

        except Exception as e:
            logger.warning("Error parsing article", error=str(e))
            return None

    async def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Search PubMed for articles matching the query.

        Args:
            query: Search query
            **kwargs: Optional parameters:
                - max_results: Maximum number of results (default from settings or 10)

        Returns:
            ToolResult with list of PubMedArticle objects
        """
        max_results = kwargs.get(
            'max_results',
            getattr(settings, 'tool_max_results', 10)
        )

        logger.info(
            "Executing PubMed search",
            query=query[:100],
            max_results=max_results
        )

        try:
            # Search for articles
            pmids = await self._esearch(query, max_results)

            if not pmids:
                return ToolResult.success_result(
                    data=[],
                    metadata={
                        'query': query,
                        'num_results': 0,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                )

            # Fetch article details
            articles = await self._efetch(pmids)

            return ToolResult.success_result(
                data=[article.model_dump() for article in articles],
                metadata={
                    'query': query,
                    'num_results': len(articles),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )

        except CoScientistError as e:
            logger.error("PubMed search failed", error=str(e))
            return ToolResult.error_result(
                error=str(e),
                metadata={
                    'query': query,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error("Unexpected error in PubMed search", error=str(e))
            return ToolResult.error_result(
                error=f"Unexpected error: {e}",
                metadata={
                    'query': query,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )


# Auto-register the tool (only if registry is being used)
def register_pubmed_tool():
    """Register PubMed tool in the global registry"""
    from src.tools.registry import registry
    try:
        pubmed_tool = PubMedTool()
        registry.register(pubmed_tool)
        logger.info("PubMed tool auto-registered")
    except Exception as e:
        logger.warning("Failed to auto-register PubMed tool", error=str(e))
