# Phase 3: Web Search Integration

## Overview

Tavily API integration for scientific literature search, enabling hypothesis generation grounded in current research.

**File:** `src/utils/web_search.py`
**Status:** ✅ Complete

## TavilySearchClient

```python
import requests
from typing import List, Dict, Optional

class TavilySearchClient:
    """Client for Tavily web search API"""

    SCIENTIFIC_DOMAINS = [
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

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tavily.com/search"

    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        max_results: int = 5
    ) -> List[Dict]:
        """Execute web search

        Args:
            query: Search query
            search_depth: "basic" or "advanced"
            include_domains: Limit to these domains
            exclude_domains: Exclude these domains
            max_results: Maximum results to return

        Returns:
            List of search results with title, url, content
        """
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": True
        }

        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        response = requests.post(self.base_url, json=payload)
        response.raise_for_status()

        data = response.json()
        return data.get("results", [])

    async def search_scientific_literature(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """Search scientific databases specifically

        Args:
            query: Scientific search query
            max_results: Maximum results

        Returns:
            Results from scientific domains only
        """
        return await self.search(
            query=query,
            search_depth="advanced",
            include_domains=self.SCIENTIFIC_DOMAINS,
            max_results=max_results
        )
```

## Scientific Domains

The client focuses on peer-reviewed sources:

| Domain | Type |
|--------|------|
| pubmed.ncbi.nlm.nih.gov | Medical literature |
| nature.com | General science |
| science.org | General science |
| cell.com | Life sciences |
| nejm.org | Medical journals |
| thelancet.com | Medical journals |
| nih.gov | Government research |
| biorxiv.org | Preprints (biology) |
| arxiv.org | Preprints (general) |

## Integration with Generation Agent

```python
# In src/agents/generation.py

async def execute(
    self,
    research_goal: ResearchGoal,
    method: GenerationMethod = GenerationMethod.LITERATURE_EXPLORATION,
    articles_with_reasoning: str = "",
    use_web_search: bool = False  # New parameter
) -> Hypothesis:
    # Optionally search for literature
    if use_web_search and not articles_with_reasoning:
        articles_with_reasoning = await self._search_literature(
            research_goal.description
        )

    # Continue with hypothesis generation...

async def _search_literature(self, query: str) -> str:
    """Search for relevant literature via web search"""
    from src.utils.web_search import TavilySearchClient
    from src.config import settings

    if not settings.tavily_api_key:
        return "No literature search configured."

    client = TavilySearchClient(settings.tavily_api_key)
    results = await client.search_scientific_literature(query)

    # Format results for prompt context
    formatted = []
    for i, result in enumerate(results[:5], 1):
        formatted.append(
            f"[{i}] {result.get('title', 'Unknown')}\n"
            f"    {result.get('content', '')[:200]}..."
        )

    return "\n\n".join(formatted)
```

## Configuration

Add Tavily API key to `.env`:

```bash
# 03_architecture/.env
TAVILY_API_KEY=your-tavily-api-key
```

## Usage

```python
from src.utils.web_search import TavilySearchClient
from src.config import settings

# Direct usage
client = TavilySearchClient(settings.tavily_api_key)

# General search
results = await client.search("AML drug targets")

# Scientific-focused search
results = await client.search_scientific_literature(
    "IRE1α inhibitors acute myeloid leukemia"
)

for result in results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Content: {result['content'][:100]}...")
    print()

# Via Generation Agent
from src.agents.generation import GenerationAgent
from src.llm.factory import get_llm_client

agent = GenerationAgent(get_llm_client())
hypothesis = await agent.execute(
    research_goal=goal,
    use_web_search=True  # Enable literature search
)
```

## Search Depth Options

| Depth | Speed | Quality | Cost |
|-------|-------|---------|------|
| basic | Fast | Good | Lower |
| advanced | Slower | Better | Higher |

For scientific literature, `advanced` depth is recommended.

## Result Format

```json
{
    "title": "IRE1α in AML pathogenesis - PubMed",
    "url": "https://pubmed.ncbi.nlm.nih.gov/...",
    "content": "The unfolded protein response (UPR) pathway...",
    "score": 0.95
}
```

## Testing

```python
@pytest.mark.asyncio
async def test_web_search():
    """Test Tavily search integration"""
    from src.config import settings

    if not settings.tavily_api_key:
        pytest.skip("No Tavily API key configured")

    client = TavilySearchClient(settings.tavily_api_key)
    results = await client.search_scientific_literature(
        "cancer drug repurposing"
    )

    assert len(results) > 0
    assert "title" in results[0]
    assert "url" in results[0]
```
