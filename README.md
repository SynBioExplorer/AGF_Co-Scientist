# AI Co-Scientist: Multi-Agent Scientific Hypothesis Generation System

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready implementation of **Google's AI Co-Scientist system** - a multi-agent AI framework designed to augment scientific discovery through collaborative hypothesis generation, debate-based evaluation, and iterative refinement.

> **Reference:** Based on Google's AI Co-Scientist paper (2024) - See [01_Paper/01_google_co-scientist.pdf](01_Paper/01_google_co-scientist.pdf)

---

## 🎯 Project Status

| Phase | Status | Components |
|-------|--------|-----------|
| **Phase 1** | ✅ Complete | Config, LLM clients, Generation agent |
| **Phase 2** | ✅ Complete | Reflection, Ranking, Elo tournament, LangGraph workflow |
| **Phase 3** | ✅ Complete | Evolution, Proximity clustering, Meta-review, Web search |
| **Phase 4** | ✅ Complete | PostgreSQL, Redis, Supervisor, Safety, FastAPI |
| **Phase 5** | 🚧 Partial | Vector storage, Literature tools, Observability (in progress) |

**Current Capabilities:**
- ✅ 8 specialized agents with supervisor orchestration
- ✅ Elo-based tournament ranking (1200 initial rating)
- ✅ Multi-turn scientific debates
- ✅ 7 hypothesis evolution strategies
- ✅ Proximity-based clustering and deduplication
- ✅ Meta-review synthesis and research overviews
- ✅ Web search integration (Tavily)
- ✅ Robust JSON parsing with error recovery
- ✅ Cost tracking with budget enforcement
- ✅ Provider switching (Google Gemini ⟷ OpenAI)
- ✅ Production storage (PostgreSQL + Redis)
- ✅ REST API with chat endpoint
- ✅ Literature processing (PDF parsing, citation extraction)
- ✅ Vector storage with embeddings
- ✅ PubMed tool integration via MCP
- ✅ LangSmith observability and tracing

---

## 🏗️ Architecture Overview

### Multi-Agent System

```
┌─────────────────────────────────────────────────────────────────┐
│                      SUPERVISOR AGENT                           │
│  • Dynamic task queue with weighted agent selection             │
│  • Terminal condition detection (budget, convergence, quality)  │
│  • Checkpoint/resume capability                                 │
│  • Statistics tracking for weight adaptation                    │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
│  GENERATION    │  │   REFLECTION    │  │    RANKING      │
│                │  │                 │  │                 │
│ • Literature   │  │ • Initial       │  │ • Elo-based     │
│   exploration  │  │   review        │  │   tournament    │
│ • Simulated    │  │ • Full review   │  │ • Multi-turn    │
│   debate       │  │   w/ search     │  │   debates       │
│ • Iterative    │  │ • Deep          │  │ • Win/loss      │
│   assumptions  │  │   verification  │  │   tracking      │
└────────────────┘  └─────────────────┘  └─────────────────┘

┌────────────────┐  ┌─────────────────┐  ┌────────────────┐
│   EVOLUTION    │  │   PROXIMITY     │  │  META-REVIEW   │
│                │  │                 │  │                │
│ • Grounding    │  │ • Similarity    │  │ • Pattern      │
│ • Coherence    │  │   clustering    │  │   analysis     │
│ • Feasibility  │  │ • De-duplication│  │ • Research     │
│ • Inspiration  │  │ • Graph analysis│  │   overview     │
│ • Combination  │  │ • Theme         │  │ • Agent        │
│ • Simplify     │  │   extraction    │  │   feedback     │
│ • Out-of-box   │  │                 │  │                │
└────────────────┘  └─────────────────┘  └────────────────┘

┌────────────────┐
│     SAFETY     │
│                │
│ • Budget       │
│   enforcement  │
│ • Ethics       │
│   review       │
│ • Constraint   │
│   validation   │
└────────────────┘
```

### Data Flow

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
│  │ Evolution → Meta-review        │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
    │
    ▼
Ranked Hypotheses + Research Overview
```

---

## 📦 Installation

### Prerequisites

- Python 3.11+
- Conda (recommended) or virtualenv
- PostgreSQL (optional, for production storage)
- Redis (optional, for caching)

### Quick Start

```bash
# 1. Clone repository
cd /path/to/ai-coscientist

# 2. Create Conda environment
conda env create -f 03_architecture/environment.yml
conda activate coscientist

# 3. Configure API keys
cp 03_architecture/.env.example 03_architecture/.env
# Edit .env with your API keys (see Configuration section)

# 4. Run tests (optional)
python 05_tests/phase1_test.py
python 05_tests/phase2_test.py
python 05_tests/phase3_test.py
python 05_tests/phase4_supervisor_test.py

# 5. Start API server
cd src/api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**API Documentation:** http://localhost:8000/docs

---

## ⚙️ Configuration

### Required API Keys

Edit `03_architecture/.env`:

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
# Google Gemini Models
GOOGLE_GENERATION_MODEL=gemini-3-pro-preview     # Best quality
GOOGLE_REFLECTION_MODEL=gemini-2.5-flash         # Balanced
GOOGLE_RANKING_MODEL=gemini-3-flash-preview      # Fast

# OpenAI Models
OPENAI_GENERATION_MODEL=gpt-5.1
OPENAI_REFLECTION_MODEL=gpt-5-mini
OPENAI_RANKING_MODEL=gpt-5-nano
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

---

## 🚀 Usage

### API Endpoints

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

#### Get Hypotheses

```bash
# Get top-ranked hypotheses
curl "http://localhost:8000/goals/goal_abc123/hypotheses?page=1&page_size=10&sort_by=elo"
```

#### Chat with System

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the top 3 hypotheses for treating Alzheimer'\''s?",
    "research_goal_id": "goal_abc123"
  }'
```

#### Search Literature (PubMed)

```bash
curl -X POST http://localhost:8000/api/v1/tools/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "CRISPR gene editing",
    "max_results": 10
  }'
```

### Python SDK Usage

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
    description="Develop hypotheses for cancer immunotherapy",
    constraints=["Focus on T-cell activation"],
    preferences=["Novel mechanisms preferred"]
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
```

---

## 📊 Data Schemas

All 27 Pydantic models defined in [03_architecture/schemas.py](03_architecture/schemas.py):

### Core Models
- **ResearchGoal** - User's research objective with constraints
- **Hypothesis** - Generated scientific hypothesis with supporting evidence
- **ExperimentalProtocol** - Proposed validation experiments
- **Citation** - Literature references

### Review Models
- **Review** - Reflection agent assessment
- **DeepVerificationReview** - Assumption-level validation
- **Assumption** - Decomposed hypothesis components

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

### System Models
- **AgentTask** - Supervisor task queue items
- **SystemStatistics** - Performance metrics
- **ContextMemory** - Persistent system state

---

## 🧪 Testing

```bash
# Phase-specific tests
python 05_tests/phase1_test.py          # Foundation
python 05_tests/phase2_test.py          # Core pipeline
python 05_tests/phase3_test.py          # Advanced features
python 05_tests/phase4_supervisor_test.py  # Supervisor orchestration
python 05_tests/test_vector.py          # Vector storage
python 05_tests/test_literature.py      # Literature processing
python 05_tests/test_tools.py           # Tool integration

# Run all tests
python -m pytest 05_tests/
```

---

## 📁 Repository Structure

```
.
├── 01_Paper/              # Google co-scientist paper and supplements
├── 02_Prompts/            # Agent prompt templates (.txt)
├── 03_architecture/       # Schemas, environment, phase docs
│   ├── schemas.py         # 27 Pydantic data models
│   ├── environment.yml    # Conda environment
│   ├── .env.example       # Configuration template
│   ├── Phase1/            # Foundation docs
│   ├── Phase2/            # Core pipeline docs
│   ├── Phase3/            # Advanced features docs
│   ├── Phase4/            # Production infrastructure docs
│   └── Phase5/            # Deployment and advanced features
├── 04_Scripts/            # Utility scripts
│   └── cost_tracker.py    # Cost monitoring
├── 05_tests/              # Integration tests
└── src/                   # Source code
    ├── agents/            # 8 specialized agents
    │   ├── generation.py  # Hypothesis generation (4 methods)
    │   ├── reflection.py  # Review and validation
    │   ├── ranking.py     # Elo tournament
    │   ├── evolution.py   # Hypothesis refinement (7 strategies)
    │   ├── proximity.py   # Similarity clustering
    │   ├── meta_review.py # Pattern synthesis
    │   ├── safety.py      # Budget and ethics
    │   └── supervisor.py  # Orchestration
    ├── api/               # FastAPI backend
    │   ├── main.py        # Main API server
    │   ├── chat.py        # Chat endpoint
    │   ├── tools.py       # Tool integration endpoints
    │   └── documents.py   # Document upload (planned)
    ├── embeddings/        # Embedding clients (Google, OpenAI)
    ├── graphs/            # LangGraph workflows
    ├── llm/               # LLM client abstraction
    ├── literature/        # PDF processing, citation extraction
    ├── observability/     # LangSmith tracing
    ├── storage/           # Storage backends (Memory, PostgreSQL, Redis)
    ├── supervisor/        # Task queue, statistics, checkpointing
    ├── tools/             # External tools (PubMed via MCP)
    ├── tournament/        # Elo rating system
    └── utils/             # Utilities (logging, JSON parsing, web search)
```

---

## 🔑 Key Features

### 1. Generate, Debate, Evolve Workflow

The system follows a scientific method-inspired approach:

1. **Generation** - Create diverse hypotheses using 4 methods:
   - Literature exploration (web search synthesis)
   - Simulated debate (self-play arguments)
   - Iterative assumptions (conditional reasoning)
   - Research expansion (explore unexplored areas)

2. **Debate** - Multi-turn tournaments between top hypotheses:
   - Elo-based ranking (1200 initial rating)
   - Pairwise comparisons with scientific arguments
   - Adaptive debate depth (multi-turn for top-ranked)

3. **Evolve** - Refine hypotheses using 7 strategies:
   - **Grounding** - Enhance literature support
   - **Coherence** - Improve logical consistency
   - **Feasibility** - Make more testable
   - **Inspiration** - Create variants inspired by existing
   - **Combination** - Merge best aspects
   - **Simplification** - Reduce complexity
   - **Out-of-box** - Divergent novel directions

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
- Budget exhausted (cost tracking)
- Tournament convergence (stable rankings)
- Quality threshold (top hypothesis Elo > target)
- Max iterations reached
```

### 3. Proximity-Based Clustering

Semantic similarity analysis for deduplication:

```python
# Cosine similarity on hypothesis embeddings
similarity_threshold = 0.85  # Configurable

# Clusters enable:
- De-duplication (merge similar hypotheses)
- Theme extraction (common concepts)
- Efficient exploration (avoid redundant generation)
```

### 4. Literature Integration

Multiple search and processing capabilities:

- **Tavily Web Search** - Real-time literature exploration
- **PubMed Integration** - Biomedical literature via MCP server
- **PDF Processing** - Extract text, citations, metadata
- **Citation Graph** - Analyze reference networks
- **Vector RAG** - Semantic search over documents

### 5. Cost Tracking & Budget Enforcement

Real-time cost monitoring across all LLM calls:

```python
# Automatic tracking per request
{
  "model": "gemini-3-pro-preview",
  "input_tokens": 1500,
  "output_tokens": 800,
  "cost_usd": 0.012,
  "cost_aud": 0.019
}

# System stops when budget exceeded
if total_cost_aud >= BUDGET_LIMIT_AUD:
    raise BudgetExceededError()
```

### 6. Phase 5 Features (Partial)

Recently added capabilities:

- ✅ **Vector Storage** - ChromaDB with Google/OpenAI embeddings
- ✅ **Literature Processing** - PDF parsing, chunking, citation extraction
- ✅ **Tool Integration** - PubMed search via MCP server
- ✅ **Observability** - LangSmith tracing for debugging
- 🚧 **Frontend Dashboard** - React UI (planned)

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

### Phase Documentation

| Phase | Focus | Documentation |
|-------|-------|---------------|
| **Phase 1** | Foundation | [03_architecture/Phase1/](03_architecture/Phase1/) |
| **Phase 2** | Core Pipeline | [03_architecture/Phase2/](03_architecture/Phase2/) |
| **Phase 3** | Advanced Features | [03_architecture/Phase3/](03_architecture/Phase3/) |
| **Phase 4** | Production | [03_architecture/Phase4/](03_architecture/Phase4/) |
| **Phase 5** | Deployment | [03_architecture/Phase5/](03_architecture/Phase5/) |

### Key Documents

- [03_architecture/schemas.py](03_architecture/schemas.py) - All data models
- [03_architecture/logic.md](03_architecture/logic.md) - System flow
- [CLAUDE.md](CLAUDE.md) - Developer guide for Claude Code
- [01_Paper/01_google_co-scientist.pdf](01_Paper/01_google_co-scientist.pdf) - Original paper

---

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Agent Framework** | LangGraph 0.2+ |
| **LLM Providers** | Google Gemini, OpenAI GPT |
| **Data Validation** | Pydantic 2.0+ |
| **Web Search** | Tavily API |
| **Database** | PostgreSQL + SQLAlchemy |
| **Caching** | Redis |
| **Vector Storage** | ChromaDB |
| **Embeddings** | Google Gemini, OpenAI text-embedding |
| **Backend API** | FastAPI + Uvicorn |
| **Literature** | PyMuPDF, PubMed MCP |
| **Observability** | LangSmith |
| **Scientific Computing** | NumPy, scikit-learn, NetworkX |

---

## 🤝 Contributing

This is a research implementation based on the Google AI Co-Scientist paper. Contributions welcome:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Guidelines:**
- Add tests for new features
- Update documentation
- Follow existing code style
- Test with both Google and OpenAI providers

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **Google DeepMind** - Original AI Co-Scientist paper and architecture
- **Anthropic** - Claude LLM integration
- **LangChain** - LangGraph agent framework
- **Tavily** - Web search API

---

## 📧 Contact

For questions or collaboration:
- Open an issue on GitHub
- Check [CLAUDE.md](CLAUDE.md) for developer guidance

---

## ⚠️ Important Notes

1. **Human Expert Validation Required** - All hypotheses require review by domain experts before experimental pursuit
2. **Budget Monitoring** - Always set `BUDGET_LIMIT_AUD` to prevent unexpected costs
3. **API Keys** - Never commit `.env` file with real API keys
4. **Storage** - Use `memory` backend for development, `cached` for production
5. **Observability** - Enable LangSmith tracing for debugging complex workflows

---

**Status:** Production-ready for research use | Phase 5 features in development

**Last Updated:** January 2026
