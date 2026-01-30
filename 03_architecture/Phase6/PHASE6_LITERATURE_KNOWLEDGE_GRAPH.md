# Phase 6: Active Literature Knowledge Graph

**Status:** 📋 Planned
**Date:** 2026-01-30
**Duration:** 4 weeks (4 phases)

---

## Overview

Transform the literature system from **passive storage** to an **active, self-expanding knowledge graph** that automatically discovers foundational papers through citation snowballing.

### Vision

Implement "Observation Review" from the Google Co-Scientist paper - validate hypotheses against long-tail observations found in automatically discovered literature.

### Current vs Target State

| Aspect | Current (Passive) | Target (Active) |
|--------|-------------------|-----------------|
| **Citation Graph** | Stores relationships manually | Grows automatically via snowballing |
| **Literature Search** | Tavily web search (text) | Multi-source structured tools (PubMed MCP + Semantic Scholar) |
| **GenerationAgent** | Direct Tavily import | Tool registry with fallback |
| **Citation Validation** | LLM-generated, unvalidated | Validated against expanded graph |
| **Hypothesis Grounding** | Citations formatted as text | Citations linked to observation evidence |

---

## Problem Statement

### Current Limitations

1. **GenerationAgent bypasses PubMed tool**
   - Uses Tavily directly (`src/agents/generation.py:59-85`)
   - Results are unstructured text strings
   - No citation validation or enrichment

2. **Citation graph doesn't grow**
   - `CitationGraph` class exists but is manually populated
   - No automated discovery of foundational papers
   - Missing "cited by" and "references" networks

3. **PubMed MCP limitations**
   - `find_related_articles` returns similarity, NOT citations
   - Cannot build "cited by" or "references" networks
   - Limited to biomedical domain

4. **No observation-based validation**
   - Hypotheses lack grounding in specific experimental observations
   - No systematic review of whether hypotheses explain literature findings

### What the Google Paper Describes

**"Observation Review"** - The system doesn't just search literature, it:
1. Identifies specific "long-tail observations" in papers (experiments, datasets, results)
2. Checks if each hypothesis explains these observations
3. Scores hypotheses based on explanatory power

**Citation Snowballing** - Starting from high-relevance papers:
1. Fetch "references" (backward - foundational work)
2. Fetch "cited by" (forward - building on this work)
3. Recursively expand to discover key papers keyword search misses

---

## Solution Architecture

### Component A: Semantic Scholar Tool

**Why Semantic Scholar?**
- ✅ Provides true citation networks ("cited by" + "references")
- ✅ Cross-disciplinary coverage (200M+ papers)
- ✅ Free tier: 5,000 requests/5min (no API key needed)
- ✅ Citation counts and influence metrics
- ❌ No full text (but PubMed MCP provides this for PMC articles)

**Implementation:**

```python
# src/tools/semantic_scholar.py

class SemanticScholarTool(BaseTool):
    """Citation network expansion via Semantic Scholar API"""

    @property
    def name(self) -> str:
        return "semantic_scholar"

    @property
    def domain(self) -> str:
        return "cross_disciplinary"

    async def search_papers(
        self,
        query: str,
        limit: int = 10,
        fields: list[str] = None
    ) -> list[dict]:
        """Search for papers matching query"""

    async def get_paper(
        self,
        paper_id: str,  # DOI, PMID, or S2 paper ID
        fields: list[str] = None
    ) -> dict:
        """Fetch paper metadata"""

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """Get papers CITING this paper (forward expansion)"""

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """Get papers REFERENCED by this paper (backward expansion)"""

    async def get_author_papers(
        self,
        author_id: str,
        limit: int = 100
    ) -> list[dict]:
        """Get papers by specific author"""
```

**API Endpoints:**
- Search: `GET /paper/search?query={query}`
- Paper: `GET /paper/{paperId}`
- Citations: `GET /paper/{paperId}/citations`
- References: `GET /paper/{paperId}/references`

**Rate Limiting:**
- Free tier: 5,000 requests per 5-minute window
- Strategy: Cache responses (24h TTL), batch requests, exponential backoff

---

### Component B: Citation Graph Expander

**Purpose:** Automatically expand citation graphs by recursively fetching neighbors

```python
# src/literature/graph_expander.py

class ExpansionStrategy(str, Enum):
    """Citation graph expansion directions"""
    BACKWARD = "backward"      # Follow references (earlier foundational work)
    FORWARD = "forward"        # Follow citations (later work building on this)
    BIDIRECTIONAL = "bidirectional"  # Both directions

class CitationGraphExpander:
    """Automatically expand citation graphs by fetching neighbors"""

    def __init__(
        self,
        graph: CitationGraph,
        tools: dict[str, BaseTool]  # {"semantic_scholar": ..., "pubmed": ...}
    ):
        self.graph = graph
        self.tools = tools
        self.cache = {}  # In-memory cache for session

    async def expand_from_paper(
        self,
        paper_id: str,  # DOI or PMID
        strategy: ExpansionStrategy = ExpansionStrategy.BACKWARD,
        max_depth: int = 1,  # USER DECISION: depth=1
        min_relevance: float = 0.5
    ) -> list[CitationNode]:
        """
        Expand graph from a seed paper.

        Args:
            paper_id: DOI or PMID of seed paper
            strategy: Which direction to expand
            max_depth: How many hops to follow (1 = immediate neighbors only)
            min_relevance: Prune papers below this relevance score

        Returns:
            List of newly discovered papers

        Algorithm:
            1. Fetch paper via Semantic Scholar
            2. If strategy includes BACKWARD: fetch references
            3. If strategy includes FORWARD: fetch citations
            4. For each neighbor: calculate relevance score
            5. If depth < max_depth: recursively expand high-relevance neighbors
            6. Add all to CitationGraph
            7. Return list of new papers
        """

    async def expand_from_results(
        self,
        search_results: list[dict],  # PubMed or Semantic Scholar results
        depth: int = 1
    ) -> CitationGraph:
        """
        Expand graph from multiple seed papers.

        Args:
            search_results: List of papers from search
            depth: Expansion depth

        Returns:
            Expanded citation graph

        Workflow:
            1. For each search result: extract DOI/PMID
            2. Expand each seed paper (depth=1)
            3. Merge all subgraphs
            4. Deduplicate by DOI/PMID
            5. Return unified graph
        """

    async def snowball_from_hypothesis(
        self,
        hypothesis: Hypothesis,
        max_papers: int = 50  # Limit total papers in graph
    ) -> CitationGraph:
        """
        Start from hypothesis citations, expand to build evidence graph.

        Args:
            hypothesis: Hypothesis with literature_citations
            max_papers: Maximum papers in graph

        Workflow:
            1. Extract DOIs from hypothesis.literature_citations
            2. For each paper: fetch citations + references (depth=1)
            3. Rank all papers by relevance to hypothesis
            4. Keep top max_papers
            5. Return subgraph of most relevant papers
        """

    def _calculate_relevance(
        self,
        paper: dict,
        research_goal: ResearchGoal
    ) -> float:
        """
        Score paper relevance to research goal.

        Factors:
            - Title similarity (embeddings)
            - Abstract similarity
            - Citation count (influence)
            - Recency (exponential decay)
            - Keyword overlap

        Returns: 0.0-1.0 score
        """

    def _deduplicate_papers(
        self,
        papers: list[dict]
    ) -> list[dict]:
        """
        Remove duplicate papers by DOI/PMID.

        Priority: DOI > PMID > S2 paper ID
        """
```

---

### Component C: Enhanced GenerationAgent

**Refactor to use tool registry with Tavily fallback**

```python
# src/agents/generation.py (MODIFIED)

class GenerationAgent:
    """Generate hypotheses with literature grounding"""

    def __init__(self, llm_client, storage, tool_registry=None):
        self.llm_client = llm_client
        self.storage = storage
        self.prompt_manager = PromptManager()

        # NEW: Use tool registry instead of direct Tavily import
        self.tool_registry = tool_registry or get_tool_registry()
        self.graph_expander = None  # Initialized when needed

    async def execute(
        self,
        research_goal: ResearchGoal,
        method: GenerationMethod = GenerationMethod.LITERATURE_EXPLORATION,
        use_literature_expansion: bool = True  # NEW parameter
    ) -> Hypothesis:
        """
        Generate hypothesis with automated citation expansion.

        Workflow:
            BEFORE generating hypothesis:
            1. Search literature (PubMed MCP + Semantic Scholar)
            2. Build initial citation graph from top results
            3. Expand graph via snowballing (depth=1)
            4. Format expanded graph as context for LLM

            GENERATE:
            5. LLM generates hypothesis with citations

            AFTER generating hypothesis:
            6. Validate LLM-generated citations exist in graph
            7. If missing: fetch via Semantic Scholar
            8. Return hypothesis with validated + expanded citations
        """

        # NEW: Try literature tools first, fallback to Tavily
        search_results, citation_graph = await self._search_literature(
            research_goal,
            use_expansion=use_literature_expansion
        )

        # Format literature context for LLM
        literature_context = self._format_literature_context(
            search_results,
            citation_graph
        )

        # Generate hypothesis (existing logic)
        prompt = self.prompt_manager.format_generation_prompt(
            goal=research_goal.description,
            preferences=research_goal.preferences,
            method=method.value,
            literature_context=literature_context  # NEW: structured context
        )

        response = await self.llm_client.invoke(prompt)
        hypothesis_data = parse_llm_json(response)

        # Create hypothesis
        hypothesis = Hypothesis(**hypothesis_data)

        # NEW: Validate and expand citations
        if use_literature_expansion and citation_graph:
            hypothesis = await self._validate_citations(
                hypothesis,
                citation_graph
            )

        return hypothesis

    async def _search_literature(
        self,
        research_goal: ResearchGoal,
        use_expansion: bool = True
    ) -> tuple[list[dict], CitationGraph]:
        """
        Try literature tools first, fallback to Tavily.

        Returns:
            (search_results, citation_graph)
        """
        try:
            # Primary: Structured literature tools
            pubmed_tool = self.tool_registry.get("pubmed_mcp")
            semantic_tool = self.tool_registry.get("semantic_scholar")

            if not pubmed_tool or not semantic_tool:
                raise ValueError("Literature tools not available")

            # Search both sources
            pubmed_results = await self._search_pubmed(
                research_goal,
                pubmed_tool
            )
            semantic_results = await self._search_semantic_scholar(
                research_goal,
                semantic_tool
            )

            all_results = pubmed_results + semantic_results

            # Build citation graph if expansion enabled
            if use_expansion:
                if not self.graph_expander:
                    self.graph_expander = CitationGraphExpander(
                        graph=CitationGraph(),
                        tools={
                            "semantic_scholar": semantic_tool,
                            "pubmed": pubmed_tool
                        }
                    )

                citation_graph = await self.graph_expander.expand_from_results(
                    all_results,
                    depth=1  # USER DECISION: depth=1 for speed
                )
            else:
                citation_graph = CitationGraph()

            logger.info(
                "Literature search complete",
                num_results=len(all_results),
                graph_nodes=len(citation_graph.nodes)
            )

            return (all_results, citation_graph)

        except Exception as e:
            # USER DECISION: Keep Tavily as fallback
            logger.warning(
                f"Literature tools failed: {e}, falling back to Tavily"
            )

            # Fallback: Tavily web search (existing logic)
            tavily_results = await self._search_tavily(research_goal)
            empty_graph = CitationGraph()

            return (tavily_results, empty_graph)

    async def _validate_citations(
        self,
        hypothesis: Hypothesis,
        citation_graph: CitationGraph
    ) -> Hypothesis:
        """
        Validate LLM-generated citations against citation graph.

        Args:
            hypothesis: Hypothesis with literature_citations
            citation_graph: Expanded citation graph

        Returns:
            Hypothesis with validated citations

        Logic:
            1. For each citation in hypothesis.literature_citations:
                a. Check if DOI exists in citation_graph
                b. If missing: fetch via Semantic Scholar
                c. Add to citation_graph
            2. Update hypothesis.literature_citations with validated metadata
            3. Return updated hypothesis
        """

    def _format_literature_context(
        self,
        results: list[dict],
        citation_graph: CitationGraph
    ) -> str:
        """
        Format search results and citation graph for LLM prompt.

        Structure:
            ## Literature Analysis

            Found {N} papers on this topic. Citation network analysis:

            ### Top Papers by Citation Count:
            1. Paper A (PMID: 12345, DOI: 10.xxx, Citations: 142)
               - Title: ...
               - Key finding: ...
               - Foundational work: Cites Papers C, D (seminal 2015 study)

            2. Paper B (PMID: 67890, DOI: 10.yyy, Citations: 89)
               - Title: ...
               - Key finding: ...
               - Building on: Cited by 23 recent papers (2023-2024)

            ### Citation Network Insights:
            - Most cited foundational paper: Paper C (2015, 500+ citations)
            - Recent work building on this: 45 papers in last 2 years
            - Key research groups: [Author X et al., Author Y et al.]
        """
```

---

### Component D: Observation Review Agent

**Purpose:** Implement "Observation Review" from Google paper

```python
# src/agents/observation_review.py (NEW)

class ObservationType(str, Enum):
    """Types of observations from papers"""
    EXPERIMENTAL = "experimental"  # Specific experiment/protocol
    DATASET = "dataset"            # Dataset characteristics
    RESULT = "result"              # Quantitative result
    MECHANISM = "mechanism"        # Proposed mechanism

class Observation(BaseModel):
    """A specific observation from a scientific paper"""
    id: str = Field(default_factory=lambda: generate_id("obs"))
    paper_id: str  # DOI or PMID
    paper_title: str
    text: str  # The observation text
    type: ObservationType
    context: str  # Surrounding sentences for context
    relevance_score: float = 0.0

class ObservationReviewScore(BaseModel):
    """Score for how well hypothesis explains observations"""
    hypothesis_id: str
    observations: list[Observation]
    explanation_scores: list[float]  # Per observation (0-1)
    overall_score: float  # Aggregate score
    reasoning: str  # LLM explanation of fit

class ObservationReviewAgent:
    """
    Implements "Observation Review" from Google paper.

    Given a hypothesis + citation graph:
    1. Extract "long-tail observations" from papers
    2. Check if hypothesis explains these observations
    3. Score hypothesis based on explanatory power
    """

    def __init__(self, llm_client, prompt_manager):
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager

    async def extract_observations(
        self,
        papers: list[dict],  # Papers from citation graph
        observation_type: ObservationType = ObservationType.EXPERIMENTAL,
        max_per_paper: int = 3
    ) -> list[Observation]:
        """
        Extract key observations from paper abstracts/full text.

        Args:
            papers: List of papers (with abstracts or full text)
            observation_type: Type of observations to extract
            max_per_paper: Max observations per paper

        Returns:
            List of Observation objects

        Process:
            1. For each paper:
                a. Prompt LLM: "Extract {observation_type} observations from this abstract"
                b. Parse response into Observation objects
                c. Add paper metadata
            2. Filter: Remove duplicates
            3. Return all observations
        """

    async def score_hypothesis_fit(
        self,
        hypothesis: Hypothesis,
        observations: list[Observation]
    ) -> ObservationReviewScore:
        """
        Prompt LLM: "Does this hypothesis explain observation X?"

        Args:
            hypothesis: Hypothesis to evaluate
            observations: List of observations from papers

        Returns:
            ObservationReviewScore with per-observation + aggregate scores

        Process:
            1. For each observation:
                a. Prompt: "Does hypothesis '{hypothesis.title}' explain observation '{obs.text}'?"
                b. LLM responds: {explanation: str, score: 0-1}
                c. Store per-observation score
            2. Aggregate: overall_score = mean(explanation_scores)
            3. Return ObservationReviewScore
        """

    async def review_hypothesis(
        self,
        hypothesis: Hypothesis,
        citation_graph: CitationGraph,
        num_observations: int = 20
    ) -> ObservationReviewScore:
        """
        Full observation review workflow.

        Args:
            hypothesis: Hypothesis to review
            citation_graph: Citation graph with papers
            num_observations: Target number of observations

        Workflow:
            1. Get top papers from citation graph (by citation count)
            2. Extract observations (target: num_observations total)
            3. Score hypothesis fit to observations
            4. Return ObservationReviewScore
        """
```

---

### Component E: Multi-Source Citation Merging

**Purpose:** Combine PubMed MCP + Semantic Scholar + local PDFs without duplicates

```python
# src/literature/source_merger.py (NEW)

class CitationSourceMerger:
    """Merge citations from multiple sources without duplicates"""

    def __init__(self):
        self.id_map = {}  # Map DOI/PMID to canonical ID

    def merge_papers(
        self,
        papers: list[dict],
        sources: list[str]  # ["pubmed", "semantic_scholar", "local"]
    ) -> list[dict]:
        """
        Merge papers from multiple sources.

        Deduplication priority: DOI > PMID > S2 paper ID

        Metadata priority:
            - For biomedical: prefer PubMed metadata
            - For citations: prefer Semantic Scholar counts
            - For full text: prefer local PDFs

        Args:
            papers: List of papers from various sources
            sources: Source names (for metadata priority)

        Returns:
            Deduplicated list with merged metadata
        """

    def merge_citation_graphs(
        self,
        graphs: list[CitationGraph]
    ) -> CitationGraph:
        """
        Merge multiple citation graphs.

        Process:
            1. Combine all nodes (deduplicate by DOI/PMID)
            2. Combine all edges (deduplicate by source+target)
            3. Recalculate citation counts
            4. Return unified graph
        """
```

---

### Component F: Citation Graph Caching

**Purpose:** Reduce redundant API calls by caching citation graphs

```python
# src/storage/cache.py (NEW)

class CitationGraphCache:
    """Cache citation graphs per research goal"""

    def __init__(self, redis_client=None):
        self.redis = redis_client  # Optional Redis backend
        self.memory_cache = {}  # In-memory fallback

    async def get_graph(
        self,
        cache_key: str  # research_goal.id or paper DOI
    ) -> Optional[CitationGraph]:
        """
        Retrieve cached citation graph.

        TTL: 24 hours (citations don't change frequently)
        """

    async def set_graph(
        self,
        cache_key: str,
        graph: CitationGraph,
        ttl_seconds: int = 86400  # 24 hours
    ):
        """Store citation graph in cache"""

    def _serialize_graph(self, graph: CitationGraph) -> str:
        """Serialize graph to JSON"""

    def _deserialize_graph(self, json_str: str) -> CitationGraph:
        """Deserialize graph from JSON"""
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal:** Add Semantic Scholar tool and basic citation expansion

**Tasks:**
1. ✅ Implement `SemanticScholarTool` (`src/tools/semantic_scholar.py`)
   - API wrapper for search, get_paper, get_citations, get_references
   - Rate limiting (5K/5min)
   - Error handling and retries

2. ✅ Implement `CitationGraphExpander` (`src/literature/graph_expander.py`)
   - `expand_from_paper()` with depth=1
   - Relevance scoring
   - Deduplication logic

3. ✅ Register tool in registry (`src/tools/registry.py`)

4. ✅ Unit tests
   - `test_semantic_scholar_tool.py` - API calls, rate limiting
   - `test_graph_expander.py` - Expansion logic, deduplication

**Files Created:**
- `src/tools/semantic_scholar.py`
- `src/literature/graph_expander.py`
- `05_tests/test_semantic_scholar_tool.py`
- `05_tests/test_graph_expander.py`

**Files Modified:**
- `src/tools/registry.py` (register SemanticScholarTool)

**Success Criteria:**
- Can search Semantic Scholar API
- Can fetch paper + citations + references
- Can expand graph depth=1 from seed paper
- Unit tests pass

---

### Phase 2: GenerationAgent Integration (Week 2)

**Goal:** Make GenerationAgent use literature tools with Tavily fallback

**Tasks:**
1. ✅ Refactor `GenerationAgent` (`src/agents/generation.py`)
   - Replace direct Tavily import with tool registry
   - Add `use_literature_expansion` parameter
   - Implement `_search_literature()` with fallback logic
   - Implement `_validate_citations()`
   - Implement `_format_literature_context()`

2. ✅ Update workflow (`src/graphs/workflow.py`)
   - Set `use_literature_expansion=True` by default

3. ✅ Update prompt template (`02_Prompts/generation_prompt.txt`)
   - Add section for literature context
   - Include citation graph insights

4. ✅ Integration tests
   - `test_generation_with_expansion.py` - Full workflow
   - `test_tavily_fallback.py` - Verify fallback works

**Files Modified:**
- `src/agents/generation.py` (major refactor)
- `src/graphs/workflow.py` (enable expansion)
- `02_Prompts/generation_prompt.txt` (add literature section)

**Files Created:**
- `05_tests/test_generation_with_expansion.py`
- `05_tests/test_tavily_fallback.py`

**Success Criteria:**
- GenerationAgent uses tool registry
- Literature tools tried first, Tavily fallback works
- Generated hypotheses have validated citations
- Citation graph has 30-50 papers
- Integration tests pass

---

### Phase 3: Observation Review (Week 3)

**Goal:** Implement "Observation Review" scoring

**Tasks:**
1. ✅ Implement `ObservationReviewAgent` (`src/agents/observation_review.py`)
   - `extract_observations()` - Parse observations from papers
   - `score_hypothesis_fit()` - Check if hypothesis explains observations
   - `review_hypothesis()` - Full workflow

2. ✅ Create prompt template (`02_Prompts/observation_review_prompt.txt`)
   - Template for extracting observations
   - Template for scoring hypothesis fit

3. ✅ Update schemas (`03_architecture/schemas.py`)
   - Add `Observation` model
   - Add `ObservationReviewScore` model
   - Add `ObservationType` enum

4. ✅ Integrate with `RankingAgent` (`src/agents/ranking.py`)
   - Add observation review score to Elo calculation
   - Weight: 30% Elo debates, 20% observation review, 50% reflection

5. ✅ Add to Supervisor (`src/agents/supervisor.py`)
   - Add ObservationReviewAgent to task queue
   - Trigger after initial ranking

6. ✅ Tests
   - `test_observation_review.py` - Extraction and scoring
   - `test_observation_integration.py` - End-to-end with ranking

**Files Created:**
- `src/agents/observation_review.py`
- `02_Prompts/observation_review_prompt.txt`
- `05_tests/test_observation_review.py`
- `05_tests/test_observation_integration.py`

**Files Modified:**
- `03_architecture/schemas.py` (add Observation models)
- `src/agents/ranking.py` (integrate observation scores)
- `src/agents/supervisor.py` (add to task queue)

**Success Criteria:**
- Can extract observations from paper abstracts
- Can score hypothesis fit (0-1)
- Observation scores integrated into ranking
- End-to-end test passes

---

### Phase 4: Multi-Source Merging (Week 4)

**Goal:** Combine PubMed + Semantic Scholar + local PDFs

**Tasks:**
1. ✅ Implement `CitationSourceMerger` (`src/literature/source_merger.py`)
   - Deduplicate by DOI/PMID
   - Merge metadata with source priority
   - Merge citation graphs

2. ✅ Update `PrivateRepository` (`src/literature/repository.py`)
   - When indexing PDF: extract citations → add to graph
   - Search private repo FIRST before external APIs
   - Integrate with `CitationGraphExpander`

3. ✅ Implement `CitationGraphCache` (`src/storage/cache.py`)
   - Cache graphs by research goal ID
   - TTL: 24 hours
   - Redis backend (optional, fallback to memory)

4. ✅ Performance optimization
   - Async citation fetching
   - Batch requests where possible
   - Connection pooling

5. ✅ Tests
   - `test_source_merger.py` - Deduplication and merging
   - `test_private_repo_integration.py` - PDF citations → graph
   - `test_citation_cache.py` - Caching logic
   - `test_performance.py` - <5 seconds for depth=1 expansion

**Files Created:**
- `src/literature/source_merger.py`
- `src/storage/cache.py`
- `05_tests/test_source_merger.py`
- `05_tests/test_citation_cache.py`
- `05_tests/test_performance.py`

**Files Modified:**
- `src/literature/repository.py` (citation graph integration)
- `05_tests/test_private_repo_integration.py`

**Success Criteria:**
- PubMed + Semantic Scholar + local PDFs merged without duplicates
- Private repository citations feed into graph
- Citation graphs cached (24h TTL)
- Performance: <5 seconds for depth=1 expansion

---

## Data Models (Schema Updates)

**File:** `03_architecture/schemas.py`

### New Models

```python
class ObservationType(str, Enum):
    """Types of observations from papers"""
    EXPERIMENTAL = "experimental"
    DATASET = "dataset"
    RESULT = "result"
    MECHANISM = "mechanism"

class Observation(BaseModel):
    """A specific observation from a scientific paper"""
    id: str = Field(default_factory=lambda: generate_id("obs"))
    paper_id: str  # DOI or PMID
    paper_title: str
    text: str
    type: ObservationType
    context: str
    relevance_score: float = 0.0

class ObservationReviewScore(BaseModel):
    """Score for how well hypothesis explains observations"""
    hypothesis_id: str
    observations: list[Observation]
    explanation_scores: list[float]
    overall_score: float
    reasoning: str

class ExpansionStrategy(str, Enum):
    """Citation graph expansion directions"""
    BACKWARD = "backward"
    FORWARD = "forward"
    BIDIRECTIONAL = "bidirectional"
```

### Modified Models

```python
class Hypothesis(BaseModel):
    """Hypothesis with enhanced citation tracking"""
    # ... existing fields ...

    # NEW: Store citation graph for this hypothesis
    citation_graph_cache_key: Optional[str] = None

    # NEW: Observation review score
    observation_review_score: Optional[ObservationReviewScore] = None
```

---

## Configuration Updates

**File:** `src/config.py`

```python
# Literature Tools
SEMANTIC_SCHOLAR_API_URL: str = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_RATE_LIMIT: int = 100  # requests/second (safe limit)

# Citation Expansion
CITATION_EXPANSION_DEPTH: int = 1  # USER DECISION: depth=1
CITATION_MAX_PAPERS: int = 50  # Max papers in graph
CITATION_MIN_RELEVANCE: float = 0.5  # Prune below this threshold

# Observation Review
OBSERVATION_REVIEW_ENABLED: bool = True
OBSERVATION_MAX_PER_PAPER: int = 3
OBSERVATION_TARGET_TOTAL: int = 20

# Caching
CITATION_GRAPH_CACHE_TTL: int = 86400  # 24 hours
```

**File:** `03_architecture/.env.example`

```bash
# Semantic Scholar (optional - no key needed for free tier)
# SEMANTIC_SCHOLAR_API_KEY=your-key-here  # For higher limits
```

---

## Testing Strategy

### Unit Tests

**Phase 1:**
- `test_semantic_scholar_tool.py` - API wrapper, rate limiting, error handling
- `test_graph_expander.py` - Expansion logic, deduplication, relevance scoring

**Phase 2:**
- `test_generation_refactor.py` - Tool registry integration
- `test_citation_validation.py` - Validate LLM citations

**Phase 3:**
- `test_observation_extraction.py` - Extract observations from papers
- `test_observation_scoring.py` - Score hypothesis fit

**Phase 4:**
- `test_source_merger.py` - Deduplication and metadata merging
- `test_citation_cache.py` - Caching logic

### Integration Tests

**Phase 2:**
- `test_generation_with_expansion.py` - Full generation workflow with citation graph
- `test_tavily_fallback.py` - Verify fallback when tools fail

**Phase 3:**
- `test_observation_integration.py` - Observation review + ranking integration

**Phase 4:**
- `test_multi_source_merge.py` - PubMed + Semantic Scholar + local PDFs
- `test_private_repo_integration.py` - PDF citations → citation graph

### End-to-End Test

```python
# 05_tests/test_literature_e2e.py

async def test_full_citation_snowball():
    """
    Full workflow test:
    1. Submit research goal
    2. GenerationAgent searches PubMed + Semantic Scholar
    3. Expand citation graph depth=1
    4. Verify graph has 30-50 papers
    5. Generate hypothesis
    6. Validate citations exist in graph
    7. ObservationReviewAgent scores hypothesis
    8. Verify observation score >0.7
    """
```

### Performance Benchmarks

```python
# 05_tests/test_performance.py

async def test_expansion_performance():
    """
    Benchmark citation graph expansion.

    Success criteria:
        - depth=1 expansion: <5 seconds
        - 10 seed papers → 30-50 total papers
        - <100 API calls total
        - Cache hit rate >80% on repeated calls
    """
```

---

## API Changes

**New endpoint:** `POST /api/v1/literature/expand`

```python
# src/api/literature.py (NEW)

@router.post("/expand")
async def expand_citation_graph(
    request: CitationExpansionRequest
) -> CitationExpansionResponse:
    """
    Expand citation graph from seed papers.

    Request:
        {
            "paper_ids": ["10.1038/nature12345", "PMID:67890"],
            "depth": 1,
            "strategy": "backward"
        }

    Response:
        {
            "graph": {
                "nodes": [...],
                "edges": [...]
            },
            "statistics": {
                "total_papers": 45,
                "expansion_time_seconds": 3.2,
                "api_calls": 47
            }
        }
    """
```

---

## Documentation Updates

### Files to Update

1. **README.md**
   - Add Phase 6 to project status table
   - Update capabilities list with citation snowballing
   - Add Semantic Scholar to technology stack

2. **CLAUDE.md**
   - Add Phase 6 documentation reference
   - Update agent list with ObservationReviewAgent

3. **New Documentation:**
   - `03_architecture/Phase6/SEMANTIC_SCHOLAR_API.md` - API reference
   - `03_architecture/Phase6/CITATION_SNOWBALLING_GUIDE.md` - User guide
   - `03_architecture/Phase6/OBSERVATION_REVIEW_METHODOLOGY.md` - Algorithm details

---

## Risk Mitigation

### Risk 1: Semantic Scholar API Rate Limits

**Impact:** Citation expansion may fail if rate limit exceeded

**Mitigation:**
- Cache responses (24h TTL) - reduces redundant calls
- Batch requests where possible
- Exponential backoff on 429 errors
- Track usage per research goal
- Fallback to PubMed MCP if S2 unavailable

**Monitoring:**
- Log API call counts per session
- Alert if approaching limit (4K/5min)
- Dashboard showing daily usage

### Risk 2: Tavily Fallback Never Triggers

**Impact:** May not discover fallback bugs until production failure

**Testing:**
- Mock Semantic Scholar failures in unit tests
- Integration test with forced tool failures
- Verify Tavily called and generation continues
- Verify empty graph doesn't crash downstream agents

### Risk 3: Citation Graph Too Large (Memory)

**Impact:** OOM errors if graph grows too large

**Mitigation:**
- Limit depth=1 (USER DECISION - ~50 papers max)
- Prune low-relevance papers (threshold=0.5)
- Store only essential metadata in graph
- Persist to disk if >1000 papers
- Use Redis/PostgreSQL for large graphs

**Monitoring:**
- Track graph size per research goal
- Alert if >500 papers in memory
- Automatic pruning if threshold exceeded

### Risk 4: Slow Citation Expansion Blocks Generation

**Impact:** GenerationAgent takes too long, poor UX

**Mitigation:**
- Async expansion (non-blocking)
- Timeout after 30 seconds
- Return partial graph if timeout
- Cache commonly expanded papers
- Background expansion for low-priority tasks

**Performance targets:**
- depth=1 expansion: <5 seconds
- depth=2 expansion: <15 seconds
- Fallback to Tavily: <2 seconds

---

## Success Metrics

### Phase 1 Complete When:
- ✅ Semantic Scholar API wrapper functional
- ✅ Citation graph expands depth=1 from seed paper
- ✅ Unit tests pass (API calls, rate limiting, graph expansion)
- ✅ Can fetch 50+ papers from single seed

### Phase 2 Complete When:
- ✅ GenerationAgent uses tool registry (not direct imports)
- ✅ Literature tools tried first, Tavily fallback works
- ✅ Generated hypotheses have validated citations from graph
- ✅ Integration test passes: full generation workflow
- ✅ Citation graph has 30-50 papers per hypothesis

### Phase 3 Complete When:
- ✅ ObservationReviewAgent extracts observations from papers
- ✅ Hypotheses scored based on observation fit (0-1)
- ✅ Scores integrated into Supervisor orchestration
- ✅ End-to-end test passes: goal → generation → observation review
- ✅ Observation scores improve hypothesis ranking accuracy

### Phase 4 Complete When:
- ✅ PubMed + Semantic Scholar + local PDFs merged without duplicates
- ✅ Private repository citations feed into graph
- ✅ Citation graphs cached (24h TTL)
- ✅ Performance test passes: <5 seconds for depth=1 expansion
- ✅ Cache hit rate >80% on repeated calls

### Overall Success When:
- ✅ Generated hypotheses grounded in 30-50 validated citations
- ✅ Citation graphs discover foundational papers missed by keyword search
- ✅ Observation review scores improve ranking accuracy by 20%+
- ✅ System falls back gracefully to Tavily when tools fail
- ✅ All 4 phases fully tested and documented

---

## Timeline

**Total Duration:** 4 weeks (4 phases)

| Week | Phase | Deliverables |
|------|-------|--------------|
| **Week 1** | Foundation | Semantic Scholar tool, CitationGraphExpander, unit tests |
| **Week 2** | GenerationAgent | Refactored agent, tool registry integration, Tavily fallback, integration tests |
| **Week 3** | Observation Review | ObservationReviewAgent, ranking integration, supervisor orchestration |
| **Week 4** | Multi-Source | Citation merging, private repo integration, caching, performance optimization |

**Estimated Effort:** 120-160 hours (30-40 hours/week)

---

## Comparison to Google Paper

| Google Paper Feature | Phase 6 Implementation |
|---------------------|----------------------|
| **Citation Snowballing** | ✅ CitationGraphExpander with depth=1 backward/forward expansion |
| **Observation Review** | ✅ ObservationReviewAgent extracts observations + scores hypothesis fit |
| **Long-tail Observations** | ✅ Extract experimental/dataset/result observations from abstracts |
| **Multi-source Literature** | ✅ PubMed MCP + Semantic Scholar + local PDFs |
| **Automated Grounding** | ✅ Validate LLM citations against expanded graph |
| **Citation Network Analysis** | ✅ Co-citation, bibliographic coupling, influence metrics |

**Key Difference:** Google paper doesn't specify exact APIs. We chose Semantic Scholar for free citation network access.

---

## Next Steps

1. ✅ Get user approval for Phase 6 plan
2. ✅ Create implementation branch: `feature/phase6-literature-knowledge-graph`
3. ✅ Week 1: Implement Phase 1 (Semantic Scholar + CitationGraphExpander)
4. ✅ Week 2: Implement Phase 2 (GenerationAgent refactor)
5. ✅ Week 3: Implement Phase 3 (Observation Review)
6. ✅ Week 4: Implement Phase 4 (Multi-source merging)
7. ✅ Final testing and documentation
8. ✅ Merge to main

---

**Status:** 📋 Ready for implementation pending user approval
**Last Updated:** 2026-01-30
