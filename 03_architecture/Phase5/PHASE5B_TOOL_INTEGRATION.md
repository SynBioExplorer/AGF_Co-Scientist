# Phase 5B: Literature Tool Integration

## Overview

Integrate literature research tools for hypothesis generation, focusing on PubMed for biomedical literature search.

**Dependencies:** Phase 4 complete
**Primary Tool:** PubMed (NCBI E-utilities API)

## Motivation

From the Google paper (Section 3.5):
> "Web search and retrieval are primary tools... the co-scientist agents utilize domain-specific tools, such as open databases, to constrain searches and generate hypotheses."

## Scope

### In Scope (MVP)
- **PubMed** - Biomedical literature search via NCBI E-utilities
- Tool registry pattern for extensibility
- Integration with Generation agent

### Deferred
- DrugBank (requires paid API)
- ChEMBL (compound database)
- AlphaFold (protein structures)
- ClinicalTrials.gov
- UniProt

## Architecture

```
src/tools/
├── __init__.py
├── base.py           # Abstract tool interface
├── registry.py       # Tool registry
└── pubmed.py         # PubMed implementation
```

## Tool Interface

All tools implement a common interface:

```python
class BaseTool(ABC):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    async def execute(self, query: str, **kwargs) -> ToolResult: ...
```

## PubMed Tool

### Capabilities
- Search biomedical literature by keywords
- Return article metadata (title, abstract, authors, journal, DOI)
- Filter by date range
- Sort by relevance or date

### API Details
- **Endpoint:** NCBI E-utilities (https://eutils.ncbi.nlm.nih.gov/entrez/eutils)
- **Rate Limit:** 3 requests/second (10/second with API key)
- **Authentication:** Optional API key for higher rate limits
- **Response Format:** XML (parsed to structured data)

### Example Usage

```python
from src.tools.pubmed import PubMedTool

tool = PubMedTool(api_key="optional-ncbi-key")
result = await tool.execute("CRISPR gene editing cancer", max_results=10)

# Result contains:
# - pmid: PubMed ID
# - title: Article title
# - abstract: Article abstract
# - authors: List of author names
# - journal: Journal name
# - year: Publication year
# - doi: Digital Object Identifier
```

## Tool Registry

The registry manages tool discovery and domain-based selection:

```python
from src.tools.registry import registry

# Register tools
registry.register(PubMedTool())

# Get tool by name
pubmed = registry.get("pubmed")

# Get tools for a domain
tools = registry.get_tools_for_domain("biomedical")
```

### Domain Mapping

| Domain | Tools |
|--------|-------|
| `biomedical` | pubmed |
| `drug_discovery` | pubmed (+ drugbank, chembl when added) |
| `protein_research` | pubmed (+ alphafold, uniprot when added) |
| `general` | pubmed |

## Agent Integration

The Generation agent uses tools to gather context:

1. Detect research domain from goal description
2. Select relevant tools from registry
3. Execute tools to gather literature context
4. Include results in hypothesis generation prompt

### Domain Detection

Keywords trigger domain selection:
- `drug`, `therapeutic`, `treatment` → `drug_discovery`
- `protein`, `structure`, `enzyme` → `protein_research`
- Default → `general`

## Environment Variables

```bash
# Optional: Increases rate limit from 3 to 10 requests/second
PUBMED_API_KEY=your-ncbi-api-key

# Tool configuration
TOOL_TIMEOUT_SECONDS=30
TOOL_MAX_RESULTS=10
```

## API Endpoints

### New Backend Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tools/pubmed/search` | GET | Search PubMed directly |

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | Search query |
| `max_results` | int | 10 | Maximum results to return |

## Success Criteria

- [ ] PubMed search returning relevant articles
- [ ] Tool registry with domain-based selection
- [ ] Generation agent using tool context
- [ ] API endpoint for direct PubMed search
- [ ] Rate limiting respected
- [ ] Error handling for API failures

## Future Extensions

When needed, additional tools can be added following the same pattern:

| Tool | Purpose | API |
|------|---------|-----|
| DrugBank | Drug information | Paid API |
| ChEMBL | Compound data | Free API |
| AlphaFold | Protein structures | Free API |
| ClinicalTrials | Trial information | Free API |
| Semantic Scholar | Academic papers | Free API |
