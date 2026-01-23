# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 Project Status: Phase 4 Complete ✅

**Current State:** Production-ready AI Co-Scientist system with full storage abstraction, supervisor orchestration, safety mechanisms, and REST API.

| Phase | Status | Summary | Documentation |
|-------|--------|---------|---------------|
| **Phase 1** | ✅ Complete | Foundation (config, LLM clients, Generation agent) | [03_architecture/Phase1/](03_architecture/Phase1/) |
| **Phase 2** | ✅ Complete | Core Pipeline (Reflection, Ranking, workflow) | [03_architecture/Phase2/](03_architecture/Phase2/) |
| **Phase 3** | ✅ Complete | Advanced Features (Evolution, Proximity, Meta-review) | [03_architecture/Phase3/](03_architecture/Phase3/) |
| **Phase 4** | ✅ Complete | Production Infrastructure (Database, Supervisor, Safety, API) | [03_architecture/Phase4/](03_architecture/Phase4/) |
| **Phase 5** | ⏳ Planned | Deployment & Advanced Features (Vector, Tools, Frontend) | [03_architecture/Phase5/](03_architecture/Phase5/) |

---

## Project Goal

Re-build and replicate **Google's AI co-scientist system** - a multi-agent AI system designed to augment scientific discovery through collaborative hypothesis generation.

**Primary Reference:** `01_Paper/01_google_co-scientist.pdf`

> **Note:** Only read `01_google_co-scientist.pdf` for system architecture. Other PDFs in `01_Paper/` are supplementary materials.

---

## System Capabilities

- 8 specialized agents (Generation, Reflection, Ranking, Evolution, Proximity, Meta-review, Supervisor, Safety)
- Elo-based tournament ranking (1200 initial rating per Google paper)
- Multi-turn scientific debates
- Hypothesis evolution with 7 strategies
- Proximity-based clustering and deduplication
- Meta-review synthesis and research overviews
- Web search integration (Tavily)
- Robust JSON parsing with error recovery
- Cost tracking with budget enforcement ($50 AUD default)
- Provider switching (Google Gemini ⟷ OpenAI)
- Storage abstraction (Memory, PostgreSQL, Redis caching)
- Supervisor orchestration with dynamic weighting
- Checkpoint/resume for workflow persistence
- FastAPI REST interface with chat endpoint

---

## Repository Structure

```
├── 01_Paper/           # Google co-scientist paper and supplements
├── 02_Prompts/         # Agent prompt templates (.txt)
├── 03_architecture/    # Schemas, logic, environment, phase documentation
│   ├── Phase1/         # Foundation components docs
│   ├── Phase2/         # Core pipeline docs
│   ├── Phase3/         # Advanced features docs
│   ├── Phase4/         # Production infrastructure docs
│   ├── Phase5/         # Deployment planning docs
│   ├── schemas.py      # Pydantic data models
│   ├── logic.md        # System flow documentation
│   └── environment.yml # Conda environment
├── 04_Scripts/         # Utility scripts (cost_tracker.py)
├── 05_tests/           # Integration tests per phase
│   ├── phase1_test.py
│   ├── phase2_test.py
│   ├── phase3_test.py
│   ├── phase4_storage_test.py
│   ├── phase4_checkpoint_test.py
│   ├── phase4_safety_test.py
│   ├── phase4_api_test.py
│   └── phase4_supervisor_test.py
└── src/                # Source code implementation
    ├── agents/         # All agent implementations
    ├── api/            # FastAPI backend
    ├── graphs/         # LangGraph workflows
    ├── llm/            # LLM client abstraction
    ├── prompts/        # Prompt loading
    ├── storage/        # Storage implementations
    ├── supervisor/     # Task queue and statistics
    ├── tournament/     # Elo rating system
    └── utils/          # Utilities
```

---

## Quick Start

```bash
# Setup environment
conda env create -f 03_architecture/environment.yml
conda activate coscientist

# Configure API keys
cp 03_architecture/.env.example 03_architecture/.env
# Edit .env with your API keys (GOOGLE_API_KEY, OPENAI_API_KEY, TAVILY_API_KEY)

# Run tests
python 05_tests/phase1_test.py  # Foundation
python 05_tests/phase2_test.py  # Core pipeline
python 05_tests/phase3_test.py  # Advanced features
python 05_tests/phase4_supervisor_test.py  # Phase 4 supervisor

# Start API server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Phase Documentation

### Phase 1: Foundation
**Documentation:** [03_architecture/Phase1/README_PHASE1.md](03_architecture/Phase1/README_PHASE1.md)

| Component | Description | Doc |
|-----------|-------------|-----|
| Configuration | Pydantic settings, env loading | [PHASE1_CONFIG.md](03_architecture/Phase1/PHASE1_CONFIG.md) |
| Utilities | IDs, logging, errors | [PHASE1_UTILITIES.md](03_architecture/Phase1/PHASE1_UTILITIES.md) |
| LLM Clients | Google/OpenAI abstraction | [PHASE1_LLM_CLIENTS.md](03_architecture/Phase1/PHASE1_LLM_CLIENTS.md) |
| Prompts | Template loading | [PHASE1_PROMPTS.md](03_architecture/Phase1/PHASE1_PROMPTS.md) |
| Generation Agent | First working agent | [PHASE1_GENERATION_AGENT.md](03_architecture/Phase1/PHASE1_GENERATION_AGENT.md) |

### Phase 2: Core Pipeline
**Documentation:** [03_architecture/Phase2/README_PHASE2.md](03_architecture/Phase2/README_PHASE2.md)

| Component | Description | Doc |
|-----------|-------------|-----|
| LLM Factory | Provider switching pattern | [PHASE2_LLM_FACTORY.md](03_architecture/Phase2/PHASE2_LLM_FACTORY.md) |
| Reflection Agent | Hypothesis review & scoring | [PHASE2_REFLECTION_AGENT.md](03_architecture/Phase2/PHASE2_REFLECTION_AGENT.md) |
| Ranking Agent | Tournament comparisons | [PHASE2_RANKING_AGENT.md](03_architecture/Phase2/PHASE2_RANKING_AGENT.md) |
| Elo System | Rating calculations | [PHASE2_ELO_SYSTEM.md](03_architecture/Phase2/PHASE2_ELO_SYSTEM.md) |
| Storage | In-memory state | [PHASE2_STORAGE.md](03_architecture/Phase2/PHASE2_STORAGE.md) |
| Workflow | LangGraph orchestration | [PHASE2_WORKFLOW.md](03_architecture/Phase2/PHASE2_WORKFLOW.md) |

### Phase 3: Advanced Features
**Documentation:** [03_architecture/Phase3/README_PHASE3.md](03_architecture/Phase3/README_PHASE3.md)

| Component | Description | Doc |
|-----------|-------------|-----|
| Evolution Agent | 7 refinement strategies | [PHASE3_EVOLUTION_AGENT.md](03_architecture/Phase3/PHASE3_EVOLUTION_AGENT.md) |
| Proximity Agent | Similarity clustering | [PHASE3_PROXIMITY_AGENT.md](03_architecture/Phase3/PHASE3_PROXIMITY_AGENT.md) |
| Meta-review Agent | Feedback synthesis | [PHASE3_META_REVIEW_AGENT.md](03_architecture/Phase3/PHASE3_META_REVIEW_AGENT.md) |
| Web Search | Tavily integration | [PHASE3_WEB_SEARCH.md](03_architecture/Phase3/PHASE3_WEB_SEARCH.md) |
| JSON Parser | Robust LLM parsing | [PHASE3_JSON_PARSER.md](03_architecture/Phase3/PHASE3_JSON_PARSER.md) |
| Bug Fixes | Critical fixes applied | [PHASE3_BUG_FIXES.md](03_architecture/Phase3/PHASE3_BUG_FIXES.md) |

### Phase 4: Production Infrastructure
**Documentation:** [03_architecture/Phase4/README_PHASE4.md](03_architecture/Phase4/README_PHASE4.md)

| Component | Description | Doc |
|-----------|-------------|-----|
| Database | PostgreSQL + Redis | [PHASE4_AGENT_DATABASE.md](03_architecture/Phase4/PHASE4_AGENT_DATABASE.md) |
| Supervisor | Task orchestration | [PHASE4_AGENT_SUPERVISOR.md](03_architecture/Phase4/PHASE4_AGENT_SUPERVISOR.md) |
| Safety | Goal/hypothesis review | [PHASE4_AGENT_SAFETY.md](03_architecture/Phase4/PHASE4_AGENT_SAFETY.md) |
| API | FastAPI backend | [PHASE4_AGENT_API.md](03_architecture/Phase4/PHASE4_AGENT_API.md) |
| Parallel Workflow | Git worktrees guide | [PHASE4_PARALLEL_WORKFLOW.md](03_architecture/Phase4/PHASE4_PARALLEL_WORKFLOW.md) |

### Phase 5: Deployment & Advanced (Planned)
**Documentation:** [03_architecture/Phase5/README_PHASE5.md](03_architecture/Phase5/README_PHASE5.md)

| Component | Description | Doc |
|-----------|-------------|-----|
| 5A Vector Storage | ChromaDB/pgvector | [PHASE5A_VECTOR_STORAGE.md](03_architecture/Phase5/PHASE5A_VECTOR_STORAGE.md) |
| 5B Tool Integration | AlphaFold, PubMed, DrugBank | [PHASE5B_TOOL_INTEGRATION.md](03_architecture/Phase5/PHASE5B_TOOL_INTEGRATION.md) |
| 5C Literature | PDF parsing, citations | [PHASE5C_LITERATURE_PROCESSING.md](03_architecture/Phase5/PHASE5C_LITERATURE_PROCESSING.md) |
| 5D Frontend | React dashboard | [PHASE5D_FRONTEND_DASHBOARD.md](03_architecture/Phase5/PHASE5D_FRONTEND_DASHBOARD.md) |
| 5E Authentication | OAuth2/JWT, RBAC | [PHASE5E_AUTHENTICATION.md](03_architecture/Phase5/PHASE5E_AUTHENTICATION.md) |
| 5F Observability | Prometheus, Grafana | [PHASE5F_OBSERVABILITY.md](03_architecture/Phase5/PHASE5F_OBSERVABILITY.md) |
| 5G Deployment | Docker, AWS ECS | [PHASE5G_DEPLOYMENT.md](03_architecture/Phase5/PHASE5G_DEPLOYMENT.md) |

---

## Key Concepts

- **Generate, Debate, Evolve** - Core approach inspired by the scientific method
- **Test-time compute scaling** - Quality improves with more computational resources
- **Scientist-in-the-loop** - Designed for human expert collaboration
- **Elo rating (1200)** - Auto-evaluation metric matching Google paper specification
- **Self-improving loop** - Meta-review feedback appended to prompts (in-context learning)

---

## Technology Stack

| Component | Tool |
|-----------|------|
| Agent Framework | LangGraph |
| LLM Provider | Google Gemini (primary), OpenAI (alternative) |
| Data Validation | Pydantic |
| Web Search | Tavily API |
| Database | PostgreSQL + Redis |
| Backend API | FastAPI |
| Vector Storage | ChromaDB / pgvector (Phase 5) |

---

## Configuration

Edit `03_architecture/.env`:

```bash
# LLM Provider (change ONE variable to switch all agents)
LLM_PROVIDER=google  # or "openai"

# API Keys
GOOGLE_API_KEY=your-key
OPENAI_API_KEY=your-key
TAVILY_API_KEY=your-key

# Budget
BUDGET_AUD=50.0
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/goals` | POST | Submit research goal |
| `/goals/{id}` | GET | Get goal status |
| `/hypotheses` | GET | List hypotheses |
| `/hypotheses/{id}` | GET | Get hypothesis details |
| `/feedback` | POST | Submit scientist feedback |
| `/statistics/{goal_id}` | GET | Get goal statistics |
| `/chat` | POST | Chat with system |
| `/chat/{goal_id}/history` | GET | Get chat history |

---

## Data Schemas

All 27 Pydantic models defined in [03_architecture/schemas.py](03_architecture/schemas.py):

- **Core:** ResearchGoal, Hypothesis, ExperimentalProtocol, Citation
- **Reviews:** Review, DeepVerificationReview
- **Tournament:** TournamentMatch, DebateTurn, TournamentState
- **Proximity:** ProximityEdge, ProximityGraph, HypothesisCluster
- **Meta-review:** MetaReviewCritique, ResearchDirection, ResearchOverview
- **System:** AgentTask, SystemStatistics, ContextMemory
- **Interaction:** ScientistFeedback, ChatMessage

---

## Working with This Repository

- Hypotheses must be grounded in prior literature
- Safety mechanisms review all goals and hypotheses
- All outputs require human expert validation
- System is model-agnostic (portable to other LLMs)
- Cost tracking enforces budget limits

---

## Phase 4 Bug Fixes (Jan 2026)

Critical async/await and integration issues identified during code review and fixed:

### CRITICAL Fixes

| Issue | File | Fix |
|-------|------|-----|
| **CheckpointManager missing async/await** | [src/supervisor/checkpoint.py](src/supervisor/checkpoint.py) | Converted 5 methods to `async def`, added `await` to all storage calls |
| **SupervisorAgent blocking event loop** | [src/agents/supervisor.py](src/agents/supervisor.py) | Wrapped all 6 sync agent `execute()` calls with `asyncio.to_thread()` |

### HIGH Priority Fixes

| Issue | File | Fix |
|-------|------|-----|
| **API using sync storage** | [src/api/main.py](src/api/main.py) | Switched to `AsyncStorageAdapter`, added `await` to all storage calls |
| **SafetyAgent sync methods** | [src/agents/safety.py](src/agents/safety.py) | Converted to async interface, use `ainvoke()` for LLM calls |

### MEDIUM Priority Fixes

| Issue | File | Fix |
|-------|------|-----|
| **BackgroundTaskManager event loop** | [src/api/background.py](src/api/background.py) | Simplified to use `asyncio.get_running_loop()` |
| **Feedback not persisted** | [src/api/main.py](src/api/main.py) | Implemented `ScientistFeedback` storage in `/feedback` endpoint |
| **SyncInMemoryStorage missing method** | [src/storage/memory.py](src/storage/memory.py) | Added `get_all_reviews()` method for backward compatibility |
| **Evolution prompt missing parameters** | [src/prompts/loader.py](src/prompts/loader.py) | Added `goal` and `preferences` defaults to `format_evolution_prompt()` |

### Verification

All fixes verified with:
- `python test_supervisor.py` - **ALL TESTS PASSED**
- `python test_phase1.py` - **PASSED**
- `python test_phase3.py` - Workflow completes successfully (Evolution step may fail due to LLM JSON variability)

---

## Validated Applications (from Google paper)

1. **Drug Repurposing (AML)** - KIRA6 showing IC50 as low as 13 nM
2. **Novel Target Discovery (Liver Fibrosis)** - Epigenetic targets validated
3. **Antimicrobial Resistance (cf-PICIs)** - Recapitulated unpublished findings
