# AI Co-Scientist: Multi-Agent Scientific Hypothesis Generation System

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.2+-61DAFB.svg)](https://reactjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready implementation of **Google's AI Co-Scientist system** - a multi-agent AI framework designed to augment scientific discovery through collaborative hypothesis generation, debate-based evaluation, and iterative refinement.

> **Reference:** Based on Google's AI Co-Scientist paper (2024) - See [01_Paper/01_google_co-scientist.pdf](01_Paper/01_google_co-scientist.pdf)

---

## 🎯 Project Status

**Current Phase:** Phase 6 Complete ✅ | **Code Lines:** ~20,680 Python | **Test Files:** 28

| Phase | Status | Components | Documentation |
|-------|--------|-----------|---------------|
| **Phase 1** | ✅ Complete | Config, LLM clients, Generation agent | [Phase1/](03_architecture/Phase1/) |
| **Phase 2** | ✅ Complete | Reflection, Ranking, Elo tournament, LangGraph workflow | [Phase2/](03_architecture/Phase2/) |
| **Phase 3** | ✅ Complete | Evolution, Proximity clustering, Meta-review, Web search | [Phase3/](03_architecture/Phase3/) |
| **Phase 4** | ✅ Complete | PostgreSQL, Redis, Supervisor, Safety, FastAPI | [Phase4/](03_architecture/Phase4/) |
| **Phase 5** | ✅ Complete | Vector storage, Literature tools, Observability, Frontend (React) | [Phase5/](03_architecture/Phase5/) |
| **Phase 6** | ✅ Complete | Multi-source citations, Observation review, Diversity sampling | [phase6_overview.md](03_architecture/phase6_overview.md) |

### 🚀 Latest Features (Phase 6)

- ✅ **Semantic Scholar Integration** - Citation graph expansion with academic search
- ✅ **Multi-Source Citation Merging** - Deduplicate papers from PubMed, Semantic Scholar, local PDFs
- ✅ **Observation Review Agent** - Validate hypotheses against literature observations
- ✅ **Generation Literature Expansion** - Direct literature integration in hypothesis generation
- ✅ **Diversity Sampling** - Cluster-aware hypothesis selection for diverse perspectives
- ✅ **Proximity-Aware Tournament Pairing** - Intelligent matchmaking for better evaluation
- ✅ **Production Hardening** - Timeout protection, retry logic, memory cleanup

---

## 🏗️ System Architecture

### Workflow Diagram

![AI Co-Scientist Workflow](docs/workflow-diagram.svg)

### Multi-Agent Ecosystem (10 Specialized Agents)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT                             │
│  • Dynamic task queue with weighted agent selection             │
│  • Terminal condition detection (budget, convergence, quality)  │
│  • Checkpoint/resume capability with timeout protection         │
│  • Memory cleanup and health monitoring                         │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
│  GENERATION    │  │   REFLECTION    │  │    RANKING      │
│                │  │                 │  │                 │
│ • Literature   │  │ • Initial       │  │ • Elo-based     │
│   expansion    │  │   review        │  │   tournament    │
│ • Citation     │  │ • Full review   │  │ • Multi-turn    │
│   graph search │  │   w/ search     │  │   debates       │
│ • Simulated    │  │ • Deep          │  │ • Proximity-    │
│   debate       │  │   verification  │  │   aware pairing │
│ • 4 generation │  │ • 6 review      │  │ • Win/loss      │
│   methods      │  │   types         │  │   tracking      │
└────────────────┘  └─────────────────┘  └─────────────────┘

┌────────────────┐  ┌─────────────────┐  ┌────────────────┐
│   EVOLUTION    │  │   PROXIMITY     │  │  META-REVIEW   │
│                │  │                 │  │                │
│ • Grounding    │  │ • Similarity    │  │ • Pattern      │
│ • Coherence    │  │   clustering    │  │   analysis     │
│ • Feasibility  │  │ • De-duplication│  │ • Research     │
│ • Inspiration  │  │ • Graph analysis│  │   overview     │
│ • Combination  │  │ • Theme         │  │ • Diversity    │
│ • Simplify     │  │   extraction    │  │   sampling     │
│ • Out-of-box   │  │ • Tournament    │  │ • Agent        │
│ (7 strategies) │  │   pairing       │  │   feedback     │
└────────────────┘  └─────────────────┘  └────────────────┘

┌────────────────┐  ┌─────────────────┐
│ OBSERVATION    │  │     SAFETY      │
│ REVIEW         │  │                 │
│                │  │ • Budget        │
│ • Extract      │  │   enforcement   │
│   observations │  │ • Ethics        │
│ • Validate vs  │  │   review        │
│   hypotheses   │  │ • Constraint    │
│ • Literature   │  │   validation    │
│   grounding    │  │ • Timeout       │
└────────────────┘  └─────────────────┘
```

### Data Flow Architecture

```
Research Goal (User Input)
    │
    ▼
┌──────────────────────────────────────┐
│  Supervisor Orchestration            │
│  ┌────────────────────────────────┐  │
│  │ Generation → Reflection        │  │
│  │      ↓            ↓            │  │
│  │ Proximity ← Ranking            │  │
│  │      ↓            ↓            │  │
│  │ Observation ← Evolution        │  │
│  │      ↓            ↓            │  │
│  │        Meta-review             │  │
│  └────────────────────────────────┘  │
│                                      │
│  Storage Layer (PostgreSQL/Redis)    │
│  Vector Store (ChromaDB)             │
│  Literature Tools (PubMed, S2)       │
└──────────────────────────────────────┘
    │
    ▼
Ranked Hypotheses + Research Overview
    │
    ▼
REST API (FastAPI) + Frontend (React)
```

---

## 📦 Installation

### Prerequisites

- **Python 3.11+** (Conda recommended)
- **Node.js 20+** (for frontend development)
- **PostgreSQL** (optional, for production storage)
- **Redis** (optional, for caching)

### Quick Start

```bash
# 1. Clone repository
git clone <repository-url>
cd ai-coscientist

# 2. Create Conda environment
conda env create -f 03_architecture/environment.yml
conda activate coscientist

# 3. Install additional dependencies
pip install -r requirements-api.txt

# 4. Configure API keys
cp 03_architecture/.env.example 03_architecture/.env
# Edit .env with your API keys (see Configuration section)

# 5. (Optional) Run tests
python 05_tests/phase1_test.py
python 05_tests/phase4_supervisor_test.py
python 05_tests/phase6_multi_source_merging_integration_test.py

# 6. Start API server
cd src/api
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 7. (Optional) Start frontend
cd frontend
npm install
npm run dev
```

**API Documentation:** http://localhost:8000/docs
**Frontend Dashboard:** http://localhost:5173

---

## ⚙️ Configuration

### Required API Keys

Edit [03_architecture/.env](03_architecture/.env.example):

```bash
# LLM Providers (at least one required)
GOOGLE_API_KEY=your-google-api-key        # https://aistudio.google.com/apikey
OPENAI_API_KEY=your-openai-api-key        # https://platform.openai.com/api-keys

# Web Search (required for literature exploration)
TAVILY_API_KEY=your-tavily-api-key        # https://tavily.com/

# Observability (optional but recommended)
LANGCHAIN_API_KEY=your-langsmith-key      # https://smith.langchain.com/
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ai-coscientist
```

### Model Configuration

**Switch LLM Provider:**
```bash
# Use Google Gemini (default, recommended)
LLM_PROVIDER=google

# Or use OpenAI
LLM_PROVIDER=openai
```

**Customize Models per Agent:**
```bash
# Google Gemini Models (recommended configuration)
GOOGLE_GENERATION_MODEL=gemini-3-pro-preview     # Best quality ($2/$12 per 1M tokens)
GOOGLE_REFLECTION_MODEL=gemini-2.5-flash         # Balanced ($0.30/$2.50)
GOOGLE_RANKING_MODEL=gemini-3-flash-preview      # Fast ($0.50/$3.00)
GOOGLE_EVOLUTION_MODEL=gemini-3-pro-preview      # Best quality
GOOGLE_META_REVIEW_MODEL=gemini-3-pro-preview    # Best quality
GOOGLE_SUPERVISOR_MODEL=gemini-3-flash-preview   # Fast

# OpenAI Models (alternative configuration)
OPENAI_GENERATION_MODEL=gpt-5.1          # $1.25/$10 per 1M tokens
OPENAI_REFLECTION_MODEL=gpt-5-mini       # $0.25/$2.00
OPENAI_RANKING_MODEL=gpt-5-mini          # $0.25/$2.00
OPENAI_EVOLUTION_MODEL=gpt-5.1           # $1.25/$10
OPENAI_META_REVIEW_MODEL=gpt-5           # $1.25/$10
OPENAI_SUPERVISOR_MODEL=gpt-5-nano       # $0.05/$0.40
```

### Storage Backend

```bash
# Development (in-memory, no setup needed)
STORAGE_BACKEND=memory

# Production (requires PostgreSQL + Redis)
STORAGE_BACKEND=cached
DATABASE_URL=postgresql://user:password@localhost:5432/coscientist
REDIS_URL=redis://localhost:6379
```

### Budget Control

```bash
BUDGET_LIMIT_AUD=50.0          # Maximum spend in AUD
USD_TO_AUD_RATE=1.55           # Update periodically
```

### Advanced Configuration

```bash
# Timeouts and Retry
LLM_TIMEOUT_SECONDS=300                    # 5 min per LLM call
LLM_MAX_RETRIES=3                          # Total attempts = 4
SUPERVISOR_MAX_EXECUTION_SECONDS=7200      # 2 hour workflow limit

# Memory Management
TASK_CLEANUP_INTERVAL_HOURS=1              # Cleanup frequency
TASK_MAX_AGE_HOURS=24                      # Remove old tasks after 24h
CHAT_HISTORY_MAX_MESSAGES=1000             # Per-goal message limit

# Phase 6 Features
PROXIMITY_AWARE_PAIRING=true               # Enable smart tournament pairing
DIVERSITY_SAMPLING_ENABLED=true            # Enable diversity sampling
CITATION_SOURCE_PRIORITY=["local","pubmed","semantic_scholar"]
```

---

## 🚀 Usage

### 1. REST API

#### Submit Research Goal

```bash
curl -X POST http://localhost:8000/goals \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Develop novel hypotheses for treating Alzheimer'\''s disease using FDA-approved drugs",
    "constraints": ["Must use FDA-approved compounds only"],
    "preferences": ["Focus on blood-brain barrier penetration"],
    "config": {
      "max_iterations": 10,
      "enable_evolution": true
    }
  }'
```

**Response:**
```json
{
  "goal_id": "goal_abc123",
  "status": "processing",
  "progress": {
    "hypotheses_generated": 0,
    "matches_completed": 0
  },
  "current_iteration": 0,
  "max_iterations": 10
}
```

#### Check Progress

```bash
curl http://localhost:8000/goals/goal_abc123
```

#### Get Top Hypotheses

```bash
# Get top-ranked hypotheses (sorted by Elo rating)
curl "http://localhost:8000/goals/goal_abc123/hypotheses?page=1&page_size=10&sort_by=elo"
```

#### Chat with System

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the top 3 hypotheses and why?",
    "research_goal_id": "goal_abc123"
  }'
```

#### Search Literature (PubMed)

```bash
curl -X POST http://localhost:8000/api/v1/tools/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "CRISPR gene editing cancer",
    "max_results": 10
  }'
```

#### Upload Documents

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Content-Type: multipart/form-data" \
  -F "file=@paper.pdf" \
  -F "research_goal_id=goal_abc123"
```

### 2. Python SDK Usage

```python
from src.agents.supervisor import SupervisorAgent
from src.storage.factory import create_storage
from schemas import ResearchGoal
from src.utils.ids import generate_id

# Initialize storage
storage = create_storage()

# Create research goal
goal = ResearchGoal(
    id=generate_id("goal"),
    description="Develop hypotheses for cancer immunotherapy using checkpoint inhibitors",
    constraints=["Focus on T-cell activation", "FDA-approved drugs preferred"],
    preferences=["Novel mechanisms", "Combination therapies"]
)

# Store goal
storage.add_research_goal(goal)

# Run supervisor workflow
supervisor = SupervisorAgent(storage)
result = supervisor.execute(
    research_goal=goal,
    max_iterations=20
)

# Get top hypotheses
top_hypotheses = storage.get_top_hypotheses(n=5)
for h in top_hypotheses:
    print(f"{h.title} (Elo: {h.elo_rating})")
    print(f"  Method: {h.generation_method}")
    print(f"  Citations: {len(h.literature_citations)}")
```

### 3. Frontend Dashboard

The React-based frontend provides:

- **Settings Panel** - Configure API keys, models, parameters
- **Chat Interface** - Conversational interaction with the system
- **Hypothesis Browser** - Browse, filter, and sort hypotheses
- **Detail View** - Deep dive into hypothesis rationale, experiments, citations
- **Dashboard** - Real-time statistics and Elo rating charts
- **Literature Page** - Upload PDFs, search PubMed, view citation graphs

```bash
# Start frontend (development)
cd frontend
npm run dev

# Build for production
npm run build
```

---

## 📊 Data Schemas

All **31 Pydantic models** defined in [03_architecture/schemas.py](03_architecture/schemas.py):

### Core Models
- **ResearchGoal** - User's research objective with constraints
- **ResearchPlanConfiguration** - Parsed system configuration
- **Hypothesis** - Generated scientific hypothesis (27 fields)
- **ExperimentalProtocol** - Proposed validation experiments
- **Citation** - Literature references
- **Assumption** - Decomposed hypothesis components

### Review Models
- **Review** - Reflection agent assessment
- **DeepVerificationReview** - Assumption-level validation

### Tournament Models
- **TournamentMatch** - Pairwise hypothesis comparison
- **DebateTurn** - Multi-turn debate arguments
- **TournamentState** - Current rankings and statistics

### Proximity Models
- **ProximityEdge** - Similarity between hypotheses
- **ProximityGraph** - Clustering structure
- **HypothesisCluster** - Grouped similar hypotheses

### Meta-Review Models
- **MetaReviewCritique** - Pattern analysis across debates
- **ResearchDirection** - Suggested research paths
- **ResearchOverview** - Comprehensive synthesis
- **ResearchContact** - Suggested domain experts

### Observation Models (Phase 6)
- **Observation** - Extracted from literature papers
- **ObservationExplanation** - Hypothesis vs observation match
- **ObservationReviewScore** - Aggregate validation score

### System Models
- **AgentTask** - Supervisor task queue items
- **SystemStatistics** - Performance metrics
- **ContextMemory** - Persistent system state
- **ScientistFeedback** - Human expert feedback
- **ChatMessage** - Chat interface messages

### Enums
- **HypothesisStatus** (7 states)
- **ReviewType** (6 types)
- **EvolutionStrategy** (7 strategies)
- **GenerationMethod** (4 methods)
- **AgentType** (9 agents)
- **ObservationType** (6 types)

---

## 🧪 Testing

### Test Suite Overview (28 Test Files)

```bash
# Phase 1-4: Core System Tests
python 05_tests/phase1_test.py                    # Foundation
python 05_tests/phase2_test.py                    # Core pipeline
python 05_tests/phase3_test.py                    # Advanced features
python 05_tests/phase4_supervisor_test.py         # Supervisor orchestration
python 05_tests/phase4_storage_test.py            # Database operations
python 05_tests/phase4_checkpoint_test.py         # State persistence
python 05_tests/phase4_safety_test.py             # Safety agent
python 05_tests/phase4_api_test.py                # API endpoints

# Phase 5: Literature & Observability
python 05_tests/phase5a_vector.py                 # Vector storage (ChromaDB)
python 05_tests/phase5b_tools.py                  # PubMed integration
python 05_tests/phase5c_literature.py             # PDF processing
python 05_tests/phase5f_tracing.py                # LangSmith observability

# Phase 6: Advanced Features
python 05_tests/phase6_semantic_scholar_tool_test.py
python 05_tests/phase6_generation_literature_expansion_test.py
python 05_tests/phase6_observation_review_test.py
python 05_tests/phase6_multi_source_merging_integration_test.py
python 05_tests/phase6_diversity_sampling_test.py
python 05_tests/phase6_proximity_pairing_test.py
python 05_tests/phase6_graph_expander_test.py

# Production Hardening
python 05_tests/test_production_hardening.py      # Timeout, retry, memory
python 05_tests/test_supervisor_time_limit.py     # Workflow timeout
python 05_tests/test_source_merger.py             # Citation merging
python 05_tests/test_citation_cache.py            # Cache layer

# Run all tests
python -m pytest 05_tests/ -v
```

---

## 📁 Repository Structure

```
.
├── 01_Paper/                  # Google co-scientist paper and supplements (11 files)
├── 02_Prompts/                # Agent prompt templates (10 .txt files)
│   ├── 01_Generation_Agent_Hypothesis_After_Literature_Review.txt
│   ├── 02_Generation_Agent_Hypothesis_After_Scientific_Debate.txt
│   ├── 03_Observation_Review_Agent.txt
│   ├── 04_Ranking_Agent_Hypothesis_Comparison_Tournament.txt
│   └── ... (6 more prompts)
├── 03_architecture/           # Schemas, environment, phase docs (98 .md files)
│   ├── schemas.py             # 31 Pydantic data models (891 lines)
│   ├── environment.yml        # Conda environment
│   ├── .env.example           # Configuration template
│   ├── logic.md               # System flow documentation
│   ├── Phase1/                # Foundation docs (6 files)
│   ├── Phase2/                # Core pipeline docs (7 files)
│   ├── Phase3/                # Advanced features docs (7 files)
│   ├── Phase4/                # Production infrastructure docs (10 files)
│   ├── Phase5/                # Deployment and features docs (17 files)
│   ├── phase6_overview.md     # Phase 6 master index
│   ├── phase6_semantic_scholar_citation_graph.md
│   ├── phase6_generation_literature_expansion.md
│   ├── phase6_observation_review.md
│   ├── phase6_multi_source_citation_merging.md
│   ├── phase6_diversity_sampling.md
│   ├── phase6_diversity_sampling_ux.md
│   └── phase6_proximity_aware_tournament_pairing.md
├── 04_Scripts/                # Utility scripts
│   └── cost_tracker.py        # Cost monitoring and reporting
├── 05_tests/                  # Integration tests (28 test files)
│   ├── phase1_test.py
│   ├── phase4_supervisor_test.py
│   ├── phase6_multi_source_merging_integration_test.py
│   └── ... (25 more tests)
├── docs/                      # Documentation assets
│   └── workflow-diagram.svg   # System workflow diagram
├── frontend/                  # React frontend dashboard
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── chat/          # Chat interface
│   │   │   ├── hypotheses/    # Hypothesis browser
│   │   │   ├── settings/      # Settings panel
│   │   │   ├── layout/        # Layout components
│   │   │   └── common/        # Shared components
│   │   ├── services/          # API client
│   │   ├── store/             # Zustand state management
│   │   ├── types/             # TypeScript types
│   │   └── constants/         # Model configurations
│   ├── package.json
│   └── vite.config.ts
└── src/                       # Source code (20,680 lines Python)
    ├── agents/                # 10 specialized agents
    │   ├── base.py            # Abstract base agent
    │   ├── generation.py      # Hypothesis generation (4 methods, 19K lines)
    │   ├── reflection.py      # Review and validation
    │   ├── ranking.py         # Elo tournament
    │   ├── evolution.py       # Hypothesis refinement (7 strategies)
    │   ├── proximity.py       # Similarity clustering
    │   ├── meta_review.py     # Pattern synthesis
    │   ├── observation_review.py  # Literature validation (Phase 6)
    │   ├── safety.py          # Budget and ethics
    │   └── supervisor.py      # Orchestration (44K lines)
    ├── api/                   # FastAPI backend
    │   ├── main.py            # Main API server (26K lines)
    │   ├── background.py      # Background task management (21K lines)
    │   ├── chat.py            # Chat endpoint (13K lines)
    │   ├── documents.py       # Document upload (10K lines)
    │   ├── tools.py           # Tool integration endpoints
    │   ├── models.py          # API request/response models
    │   └── settings.py        # API configuration
    ├── embeddings/            # Embedding clients
    │   ├── base.py            # Abstract embedding interface
    │   ├── google.py          # Google text-embedding-004
    │   └── openai.py          # OpenAI text-embedding-3-small
    ├── graphs/                # LangGraph workflows
    │   └── workflow.py        # Multi-agent workflow graph
    ├── llm/                   # LLM client abstraction
    │   ├── base.py            # Abstract LLM interface
    │   ├── google.py          # Google Gemini client
    │   ├── openai.py          # OpenAI GPT client
    │   └── factory.py         # LLM provider factory
    ├── literature/            # PDF processing, citation extraction
    │   ├── pdf_parser.py      # PyMuPDF-based parser
    │   ├── chunker.py         # Text chunking with overlap
    │   ├── citation_extractor.py  # Author-year & numeric citations
    │   ├── citation_graph.py  # Graph analysis and statistics
    │   ├── graph_expander.py  # Citation graph BFS expansion (Phase 6)
    │   ├── source_merger.py   # Multi-source deduplication (Phase 6)
    │   └── repository.py      # Vector-backed literature store
    ├── observability/         # LangSmith tracing
    │   └── tracing.py         # Tracing utilities and decorators
    ├── storage/               # Storage backends
    │   ├── base.py            # Abstract storage interface (25K lines)
    │   ├── memory.py          # In-memory storage (35K lines)
    │   ├── postgres.py        # PostgreSQL backend (71K lines)
    │   ├── cache.py           # Redis caching layer (31K lines)
    │   ├── vector.py          # ChromaDB vector store (17K lines)
    │   ├── vector_factory.py  # Vector store factory
    │   ├── async_adapter.py   # Async storage adapter (26K lines)
    │   └── factory.py         # Storage factory
    ├── supervisor/            # Task queue, statistics, checkpointing
    │   ├── task_queue.py      # Priority task queue
    │   ├── statistics.py      # System statistics computation
    │   └── checkpoint.py      # State persistence
    ├── tools/                 # External tools
    │   ├── base.py            # Abstract tool interface
    │   ├── pubmed.py          # PubMed MCP integration
    │   ├── semantic_scholar.py # Semantic Scholar API (Phase 6)
    │   └── registry.py        # Tool registry
    ├── tournament/            # Elo rating system
    │   └── elo.py             # Elo calculation (1200 initial rating)
    ├── utils/                 # Utilities
    │   ├── logging_config.py  # Structured logging (structlog)
    │   ├── json_parser.py     # Robust JSON parsing with error recovery
    │   ├── web_search.py      # Tavily search integration
    │   ├── ids.py             # ID generation utilities
    │   ├── errors.py          # Custom exception types
    │   ├── retry.py           # Retry logic with exponential backoff
    │   └── strategy_selector.py  # Evolution strategy selection (Phase 6)
    └── config.py              # Global settings (Pydantic BaseSettings)
```

---

## 🔑 Key Features

### 1. Generate, Debate, Evolve Workflow

The system follows a scientific method-inspired approach:

**Generation (4 Methods)**
1. **Literature Exploration** - Web/database search synthesis with citation graphs
2. **Simulated Debate** - Self-play scientific arguments
3. **Iterative Assumptions** - Conditional reasoning chains
4. **Research Expansion** - Explore unexplored areas in hypothesis space

**Debate (Multi-Turn Tournaments)**
- Elo-based ranking (1200 initial rating, matching Google paper)
- Pairwise comparisons with scientific arguments
- Adaptive debate depth (multi-turn for top-ranked hypotheses)
- Proximity-aware pairing (70% within-cluster, 20% cross-cluster)

**Evolve (7 Strategies)**
1. **Grounding** - Enhance literature support
2. **Coherence** - Improve logical consistency
3. **Feasibility** - Make more testable
4. **Inspiration** - Create variants inspired by existing
5. **Combination** - Merge best aspects
6. **Simplification** - Reduce complexity
7. **Out-of-box** - Divergent novel directions

### 2. Supervisor Orchestration

Dynamic task queue with weighted agent selection:

```python
# Agent weights adapt based on effectiveness
initial_weights = {
    "generation": 0.30,
    "reflection": 0.20,
    "ranking": 0.15,
    "evolution": 0.15,
    "proximity": 0.10,
    "meta_review": 0.10
}

# Terminal conditions
- Budget exhausted (cost tracking with AUD limits)
- Tournament convergence (stable rankings over iterations)
- Quality threshold (top hypothesis Elo > target)
- Max iterations reached
- Time limit exceeded (2 hours default)
```

### 3. Multi-Source Literature Integration (Phase 6)

Unified citation management across sources:

**Sources:**
- **Local PDFs** - Private repository with priority
- **PubMed** - Biomedical literature (MCP server)
- **Semantic Scholar** - Academic search with citation graphs

**Features:**
- **Deduplication** - DOI, PMID, title fuzzy matching
- **Priority Merging** - Local > PubMed > Semantic Scholar
- **Caching** - Redis cache (24h papers, 7d metadata)
- **Citation Graph Expansion** - BFS exploration with depth limits
- **Parallel Processing** - Concurrent expansion (5 workers default)

```python
from src.literature.source_merger import CitationSourceMerger

merger = CitationSourceMerger(
    local_repo=local_pdf_repository,
    pubmed_tool=pubmed_search_tool,
    semantic_scholar_tool=s2_search_tool
)

# Search across all sources with deduplication
papers = await merger.search_multi_source(
    query="CRISPR gene editing",
    max_results=50,
    enable_expansion=True
)
```

### 4. Observation Review (Phase 6)

Validate hypotheses against concrete literature observations:

```python
from src.agents.observation_review import ObservationReviewAgent

agent = ObservationReviewAgent(storage)

# Extract observations from papers
observations = agent.extract_observations(
    papers=literature_papers,
    research_goal=goal,
    max_observations=20
)

# Score hypothesis against observations
score = agent.review_hypothesis(
    hypothesis=hypothesis,
    observations=observations
)

# Output: ObservationReviewScore
# - overall_score (0.0-1.0)
# - observations_explained_count
# - strengths, weaknesses, summary
```

### 5. Diversity Sampling (Phase 6)

Cluster-aware hypothesis selection for diverse perspectives:

```python
from src.agents.meta_review import MetaReviewAgent

agent = MetaReviewAgent(storage)

# Sample diverse hypotheses from clusters
diverse_hypotheses = agent.sample_diverse_hypotheses(
    n=10,
    min_elo=1200.0,
    strategy="balanced"  # or "quality", "exploratory"
)

# Returns hypotheses covering different clusters
# Ensures overview represents full hypothesis space
```

### 6. Production Hardening

**Timeout Protection:**
- Per-LLM call: 5 minutes (configurable)
- Per-iteration: 10 minutes
- Total workflow: 2 hours (prevents infinite loops)

**Retry Logic:**
- Exponential backoff (1s, 2s, 4s, 8s...)
- Max delay cap: 30 seconds
- Default retries: 3 (4 total attempts)

**Memory Cleanup:**
- Periodic task cleanup (every 1 hour)
- Remove completed tasks after 24 hours
- Chat history pruning (1000 messages/goal, 7 days max)
- Health check monitoring for deadlocks

**Error Recovery:**
- Robust JSON parsing with fallback
- Graceful degradation on API failures
- Checkpoint/resume for long workflows

### 7. Cost Tracking & Budget Enforcement

Real-time cost monitoring across all LLM calls:

```python
# Automatic tracking per request
{
  "model": "gemini-3-pro-preview",
  "input_tokens": 1500,
  "output_tokens": 800,
  "cost_usd": 0.012,
  "cost_aud": 0.019  # Converted at configured rate
}

# System stops when budget exceeded
if total_cost_aud >= BUDGET_LIMIT_AUD:
    raise BudgetExceededError()

# Track costs by agent, method, model
python 04_Scripts/cost_tracker.py --breakdown
```

### 8. Observability with LangSmith

End-to-end tracing of multi-agent workflows:

```bash
# Enable in .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-key
LANGCHAIN_PROJECT=ai-coscientist

# Automatic tracing of:
- LLM calls (prompts, responses, latency)
- Agent executions (inputs, outputs, errors)
- Tool invocations (PubMed, Semantic Scholar, Tavily)
- LangGraph workflow steps
```

View traces at: https://smith.langchain.com/

---

## 🐛 Known Issues & Fixes

Three critical issues were identified post-Phase 4 and fixed:

| Issue | Problem | Solution | Documentation |
|-------|---------|----------|---------------|
| **Supervisor Integration** | API bypassed SupervisorAgent | Refactored to use supervisor orchestration | [PHASE4_FIX_SUPERVISOR_INTEGRATION.md](03_architecture/Phase4/PHASE4_FIX_SUPERVISOR_INTEGRATION.md) |
| **Multi-Turn Debate** | Debates hardcoded to disabled | Enabled `multi_turn=True` in workflow | [PHASE4_FIX_MULTI_TURN_DEBATE.md](03_architecture/Phase4/PHASE4_FIX_MULTI_TURN_DEBATE.md) |
| **Evolution Strategies** | Only FEASIBILITY strategy used | Dynamic selection from all 7 strategies | [PHASE4_FIX_EVOLUTION_STRATEGIES.md](03_architecture/Phase4/PHASE4_FIX_EVOLUTION_STRATEGIES.md) |

---

## 📚 Documentation

### Comprehensive Documentation (98+ Markdown Files)

| Category | Files | Location |
|----------|-------|----------|
| **Phase 1** | 6 docs | [03_architecture/Phase1/](03_architecture/Phase1/) - Config, LLM, Generation |
| **Phase 2** | 7 docs | [03_architecture/Phase2/](03_architecture/Phase2/) - Reflection, Ranking, Elo, Workflow |
| **Phase 3** | 7 docs | [03_architecture/Phase3/](03_architecture/Phase3/) - Evolution, Proximity, Meta-review |
| **Phase 4** | 10 docs | [03_architecture/Phase4/](03_architecture/Phase4/) - Database, Supervisor, Safety, API |
| **Phase 5** | 17 docs | [03_architecture/Phase5/](03_architecture/Phase5/) - Vector, Literature, Observability, Frontend |
| **Phase 6** | 8 docs | [03_architecture/](03_architecture/) - phase6_*.md (Multi-source, Observation, Diversity) |

### Key Documents

- **[schemas.py](03_architecture/schemas.py)** - All 31 data models (891 lines)
- **[logic.md](03_architecture/logic.md)** - System flow and decision logic
- **[CLAUDE.md](CLAUDE.md)** - Developer guide for Claude Code
- **[01_google_co-scientist.pdf](01_Paper/01_google_co-scientist.pdf)** - Original Google paper
- **[phase6_overview.md](03_architecture/phase6_overview.md)** - Phase 6 master index

---

## 🛠️ Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Agent Framework** | LangGraph | 0.2+ |
| **LLM Providers** | Google Gemini, OpenAI GPT | Latest |
| **Data Validation** | Pydantic | 2.0+ |
| **Web Search** | Tavily API | - |
| **Database** | PostgreSQL + SQLAlchemy | 2.0+ |
| **Caching** | Redis | Latest |
| **Vector Storage** | ChromaDB | Latest |
| **Embeddings** | Google text-embedding-004, OpenAI text-embedding-3-small | - |
| **Backend API** | FastAPI + Uvicorn | 0.109+ |
| **Frontend** | React + TypeScript + Vite | 19.2+ |
| **State Management** | Zustand | 5.0+ |
| **UI Components** | Tailwind CSS + Recharts | Latest |
| **Literature** | PyMuPDF, PubMed MCP, Semantic Scholar API | - |
| **Observability** | LangSmith (LangChain) | Latest |
| **Scientific Computing** | NumPy, scikit-learn, NetworkX, pandas | Latest |
| **HTTP Clients** | httpx, aiohttp, requests | Latest |
| **Logging** | structlog | 23.2+ |
| **Testing** | pytest, pytest-asyncio | Latest |

---

## 🤝 Contributing

This is a research implementation based on the Google AI Co-Scientist paper. Contributions welcome:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Guidelines:**
- Add tests for new features (see `05_tests/` for examples)
- Update documentation (phase docs + README)
- Follow existing code style (type hints, docstrings, structlog)
- Test with both Google and OpenAI providers
- Run full test suite before submitting

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **Google DeepMind** - Original AI Co-Scientist paper and architecture
- **Anthropic** - Claude LLM and Claude Code development environment
- **LangChain** - LangGraph agent framework and LangSmith observability
- **Tavily** - Web search API for literature exploration
- **Semantic Scholar** - Academic citation graph database
- **PubMed/NCBI** - Biomedical literature access

---

## 📧 Contact & Support

For questions, issues, or collaboration:

- **Issues:** Open an issue on GitHub
- **Documentation:** Check [CLAUDE.md](CLAUDE.md) for developer guidance
- **API Docs:** http://localhost:8000/docs (when running)
- **LangSmith Traces:** https://smith.langchain.com/ (debugging)

---

## ⚠️ Important Notes

1. **Human Expert Validation Required** - All hypotheses require review by domain experts before experimental pursuit
2. **Budget Monitoring** - Always set `BUDGET_LIMIT_AUD` to prevent unexpected costs (default: $50 AUD)
3. **API Keys** - Never commit `.env` file with real API keys to version control
4. **Storage** - Use `memory` backend for development, `cached` (PostgreSQL+Redis) for production
5. **Observability** - Enable LangSmith tracing for debugging complex multi-agent workflows
6. **Timeouts** - Default 2-hour workflow limit prevents runaway costs; adjust as needed
7. **Testing** - Run phase tests to verify setup before production use
8. **Literature Sources** - Configure citation source priority based on your access

---

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| **Start API** | `uvicorn src.api.main:app --reload --port 8000` |
| **Start Frontend** | `cd frontend && npm run dev` |
| **Run Tests** | `python -m pytest 05_tests/ -v` |
| **Check Costs** | `python 04_Scripts/cost_tracker.py --breakdown` |
| **View API Docs** | http://localhost:8000/docs |
| **View Traces** | https://smith.langchain.com/ |
| **Update Config** | Edit `03_architecture/.env` |
| **Add Hypothesis** | `POST /goals` → `GET /goals/{id}/hypotheses` |
| **Search Literature** | `POST /api/v1/tools/search` |
| **Upload Paper** | `POST /api/v1/documents/upload` |

---

**Project Status:** Production-Ready ✅ | **Last Updated:** 2026-01-30
**Codebase:** 20,680 lines Python + React TypeScript frontend
**Documentation:** 98 markdown files + 31 data models
**Test Coverage:** 28 integration tests across all phases
