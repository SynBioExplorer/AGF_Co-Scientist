"""Web search utilities using Tavily API"""

from typing import List, Dict, Optional
import requests
from src.config import settings
from src.utils.errors import CoScientistError
import structlog

logger = structlog.get_logger()


class TavilySearchClient:
    """Client for Tavily search API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.tavily_api_key
        if not self.api_key:
            raise CoScientistError("Tavily API key not configured")

        self.base_url = "https://api.tavily.com/search"

    def search(
        self,
        query: str,
        search_depth: str = "advanced",  # "basic" or "advanced"
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """Search using Tavily API

        Args:
            query: Search query
            search_depth: "basic" or "advanced" (advanced is more thorough)
            max_results: Maximum number of results to return
            include_domains: List of domains to include (e.g., ["pubmed.gov", "nature.com"])
            exclude_domains: List of domains to exclude

        Returns:
            List of search results with title, url, content
        """

        logger.info(
            "Tavily search",
            query=query[:100],
            depth=search_depth,
            max_results=max_results
        )

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": True,  # Get AI-generated answer
            "include_raw_content": False,  # Don't need full HTML
        }

        if include_domains:
            payload["include_domains"] = include_domains

        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()

            data = response.json()

            results = []
            for result in data.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0)
                })

            # Add AI answer if available
            if data.get("answer"):
                results.insert(0, {
                    "title": "AI Summary",
                    "url": "",
                    "content": data["answer"],
                    "score": 1.0
                })

            logger.info(
                "Tavily search completed",
                num_results=len(results)
            )

            return results

        except requests.exceptions.RequestException as e:
            raise CoScientistError(f"Tavily search failed: {e}")

    def search_scientific_literature(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, str]]:
        """Search scientific literature databases

        Args:
            query: Research query
            max_results: Maximum number of results

        Returns:
            List of scientific articles
        """

        # Focus on scientific domains
        include_domains = [
            "pubmed.ncbi.nlm.nih.gov",
            "nature.com",
            "science.org",
            "cell.com",
            "nejm.org",
            "thelancet.com",
            "nih.gov",
            "biorxiv.org",
            "arxiv.org"
        ]

        return self.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=include_domains
        )


# Global instance
def get_search_client() -> TavilySearchClient:
    """Get global Tavily search client"""
    return TavilySearchClient()
