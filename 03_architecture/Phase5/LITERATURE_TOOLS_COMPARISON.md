# Literature Tools Comparison for AI Co-Scientist

**Date:** 2026-01-29
**Purpose:** Evaluate literature search options for hypothesis generation and research

---

## Available Options

### 1. PubMed (Currently Implemented)

**What it is:** NIH's database of biomedical and life sciences literature

**Your Implementation:**
- Custom tool in `src/tools/pubmed.py` using aiohttp
- Basic search and article retrieval
- Rate limiting built-in

**PubMed MCP Server (Available):**
- `mcp__claude_ai_PubMed__search_articles` - Advanced search
- `mcp__claude_ai_PubMed__get_article_metadata` - Full metadata
- `mcp__claude_ai_PubMed__find_related_articles` - Citation network
- `mcp__claude_ai_PubMed__get_full_text_article` - Full text from PMC
- `mcp__claude_ai_PubMed__convert_article_ids` - PMID/DOI conversion
- `mcp__claude_ai_PubMed__get_copyright_status` - License info

**Pros:**
- ✅ Free, no API key required (higher limits with key)
- ✅ Comprehensive biomedical/life sciences coverage
- ✅ MCP already integrated in your environment
- ✅ Full text available for PMC articles
- ✅ Citation network analysis

**Cons:**
- ❌ Limited to biomedical sciences
- ❌ No cross-disciplinary coverage

**Recommendation:** **Use PubMed MCP** - more features than custom implementation

---

### 2. Semantic Scholar

**What it is:** AI-powered academic search engine by Allen Institute

**API Features:**
- Search 200M+ papers across all disciplines
- Citation network (citing/cited papers)
- Author information and h-index
- Paper influence metrics
- Recommendation API
- Free tier: 5,000 requests/5min

**Pros:**
- ✅ Cross-disciplinary (not just biomedical)
- ✅ AI-powered relevance ranking
- ✅ Rich citation network
- ✅ Influence metrics (highly cited papers)
- ✅ Free tier generous

**Cons:**
- ❌ Requires API key
- ❌ Not as comprehensive for clinical trials as PubMed
- ❌ No MCP server available (would need custom integration)

**Integration Effort:** Medium - needs custom tool implementation

---

### 3. OpenAlex

**What it is:** Open catalog of scholarly papers, authors, institutions

**API Features:**
- 250M+ works across all disciplines
- Completely free, no API key required
- Citation network
- Open access status
- Institution and funder information
- Author disambiguation

**Pros:**
- ✅ Completely free, unlimited use
- ✅ Cross-disciplinary coverage
- ✅ Open data philosophy
- ✅ Good for tracking open access papers
- ✅ RESTful API, easy to integrate

**Cons:**
- ❌ Less biomedical focus than PubMed
- ❌ No full text access
- ❌ No MCP server available

**Integration Effort:** Medium - needs custom tool implementation

---

### 4. PaperQA2

**What it is:** LLM-powered question answering over scientific papers

**Features:**
- RAG-based QA over PDFs
- Citation-backed answers
- Multi-document synthesis
- Integration with Semantic Scholar, Crossref
- Local PDF collection indexing

**Pros:**
- ✅ Designed for scientific QA
- ✅ Citations for every claim
- ✅ Works with your private PDF collection
- ✅ Integrates with multiple sources

**Cons:**
- ❌ Heavier dependency (requires setup)
- ❌ More complex than simple search APIs
- ❌ Adds another LLM layer (cost)
- ❌ Overlap with your Phase 5C literature processing

**Integration Effort:** High - substantial library, may duplicate functionality

---

## Recommendation Matrix

### For Your AI Co-Scientist System

| Use Case | Best Tool | Why |
|----------|-----------|-----|
| **Biomedical hypothesis generation** | PubMed MCP | Most comprehensive biomedical coverage, already integrated |
| **Cross-disciplinary research** | Semantic Scholar | AI-powered relevance, all fields |
| **Budget-conscious scaling** | OpenAlex | Free unlimited, broad coverage |
| **Private PDF QA** | Your Phase 5C implementation | Already built, designed for this |
| **Citation network analysis** | PubMed MCP | Built-in citation tools |

---

## Proposed Multi-Tool Strategy

### **Tier 1: Primary (Already Available)**
```python
# Use PubMed MCP for biomedical queries
- mcp__claude_ai_PubMed__search_articles()
- mcp__claude_ai_PubMed__get_article_metadata()
- mcp__claude_ai_PubMed__find_related_articles()
```

### **Tier 2: Add Semantic Scholar for Cross-Disciplinary**
```python
# Custom tool for broader research
class SemanticScholarTool(BaseTool):
    - search_papers()
    - get_paper_citations()
    - get_author_papers()
    - get_recommendations()
```

### **Tier 3: Optional - OpenAlex for Free Scaling**
```python
# Fallback for high-volume queries
class OpenAlexTool(BaseTool):
    - search_works()
    - get_work()
    - get_related_works()
```

---

## Implementation Priority

### **Immediate (Now)**
1. **Replace custom PubMed tool with MCP** - more features, better maintained
2. **Update Generation agent** to use MCP PubMed tools
3. **Test with real hypothesis generation**

### **Short-term (Next Sprint)**
1. **Add Semantic Scholar** - enables cross-disciplinary research
2. **Create tool selection logic** - PubMed for bio, S2 for cross-disciplinary
3. **Update prompts** to specify which tool for which query

### **Long-term (If Needed)**
1. **Add OpenAlex** - if scaling beyond free tiers
2. **Implement tool orchestration** - combine results from multiple sources
3. **Add caching layer** - reduce redundant API calls

---

## Code Changes Required

### 1. Update Tool Registry to Use PubMed MCP
```python
# src/tools/registry.py
class ToolRegistry:
    def register_mcp_tools(self):
        """Register MCP-provided tools"""
        self.register(PubMedMCPTool(
            name="pubmed_search",
            mcp_function="mcp__claude_ai_PubMed__search_articles"
        ))
```

### 2. Add Semantic Scholar Tool
```python
# src/tools/semantic_scholar.py
class SemanticScholarTool(BaseTool):
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.semanticscholar.org/graph/v1"

    async def search(self, query: str, limit: int = 10) -> List[Dict]:
        # Implement search
```

### 3. Update Generation Agent to Select Tool
```python
# src/agents/generation.py
class GenerationAgent:
    def select_literature_tool(self, goal: ResearchGoal) -> str:
        """Select appropriate tool based on research domain"""
        if self.is_biomedical(goal):
            return "pubmed_mcp"
        else:
            return "semantic_scholar"
```

---

## Environment Updates Needed

### Add to `environment.yml`
```yaml
# None needed for PubMed MCP (already integrated)

# For Semantic Scholar (if added)
- pip:
    - semanticscholar  # Official Python client
```

### Add to `.env`
```bash
# Optional: PubMed API key for higher rate limits
PUBMED_API_KEY=your_key_here

# Optional: Semantic Scholar API key
SEMANTIC_SCHOLAR_API_KEY=your_key_here  # Free tier: no key needed
```

---

## Decision Recommendation

### **Recommended Approach:**

1. **Immediate:** Switch from custom PubMed tool to PubMed MCP
   - Benefit: More features (full text, citations, metadata)
   - Effort: Low (MCP already integrated)
   - Risk: None

2. **Near-term:** Add Semantic Scholar as secondary tool
   - Benefit: Cross-disciplinary coverage
   - Effort: Medium (custom implementation)
   - Risk: Low (independent addition)

3. **Skip:** PaperQA2 for now
   - Reason: Overlaps with Phase 5C literature processing
   - Your implementation already does PDF QA
   - PaperQA2 adds complexity without clear benefit

4. **Optional:** Add OpenAlex if needed
   - When: If you exceed PubMed/S2 rate limits
   - Benefit: Free unlimited queries
   - Effort: Medium

---

## Next Steps

**Would you like me to:**

1. ✅ **Replace custom PubMed with MCP implementation?**
   - Update `src/tools/pubmed.py` to use MCP functions
   - Update tests to use MCP
   - Remove aiohttp dependency from tool tests

2. ✅ **Add Semantic Scholar tool?**
   - Implement `src/tools/semantic_scholar.py`
   - Add to tool registry
   - Create tests

3. ✅ **Update Generation agent to use multiple tools?**
   - Add tool selection logic
   - Update prompts to specify tool usage
   - Test with cross-disciplinary hypotheses

Let me know which direction you'd like to go!
