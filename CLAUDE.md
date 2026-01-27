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

| Phase | Summary | Docs |
|-------|---------|------|
| **Phase 1** | Config, LLM clients, Generation agent | [03_architecture/Phase1/](03_architecture/Phase1/) |
| **Phase 2** | Reflection, Ranking, Elo, LangGraph workflow | [03_architecture/Phase2/](03_architecture/Phase2/) |
| **Phase 3** | Evolution, Proximity, Meta-review, Tavily search | [03_architecture/Phase3/](03_architecture/Phase3/) |
| **Phase 4** | PostgreSQL, Redis, Supervisor, Safety, FastAPI | [03_architecture/Phase4/](03_architecture/Phase4/) |
| **Phase 5** | Vector storage, tools, frontend, auth, deployment | [03_architecture/Phase5/](03_architecture/Phase5/) |

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

## Notes

- All hypotheses require human expert validation
- Cost tracking enforces budget limits ($50 AUD default)

