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
| **Phase 4** | PostgreSQL, Redis, Supervisor, Safety, FastAPI + Fixes | [03_architecture/Phase4/](03_architecture/Phase4/) |
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

## Phase 4 Fixes (Post-Implementation)

Three critical issues were identified and fixed to align the implementation with the Google paper:

| Fix | Issue | Solution | Docs |
|-----|-------|----------|------|
| Supervisor Integration | API bypassed SupervisorAgent, using simplified workflow | API now uses SupervisorAgent for dynamic orchestration | [PHASE4_FIX_SUPERVISOR_INTEGRATION.md](03_architecture/Phase4/PHASE4_FIX_SUPERVISOR_INTEGRATION.md) |
| Multi-Turn Debate | Debate was implemented but hardcoded to disabled | Enabled `multi_turn=True` in workflow and supervisor | [PHASE4_FIX_MULTI_TURN_DEBATE.md](03_architecture/Phase4/PHASE4_FIX_MULTI_TURN_DEBATE.md) |
| Evolution Strategies | Only FEASIBILITY strategy was used (hardcoded) | Dynamic selection from all 7 strategies based on context | [PHASE4_FIX_EVOLUTION_STRATEGIES.md](03_architecture/Phase4/PHASE4_FIX_EVOLUTION_STRATEGIES.md) |

---

## Session History: Paper-Feature-Complete Overhaul (April 2026)

The system was heavily overhauled across ~15 commits to close paper feature gaps, fix latent pipeline bugs, and harden the tournament. The system is now **feature-complete vs the Google paper** (all 4 generation methods, all review types, all 7 evolution strategies) with several extensions beyond the paper.

### How the system actually runs

**Entry point:** `/tmp/run_coscientist.py` (CLI) or `src/api/main.py` (FastAPI).

The CLI script:
1. `load_dotenv('03_architecture/.env')` BEFORE any src imports (critical - LangSmith checks env vars at import time)
2. Builds a `ResearchGoal` with `description`, `constraints`, `preferences`
3. `SupervisorAgent(async_storage).execute(goal, max_iterations=20)`
4. Dumps JSON to `data/runs/run_<timestamp>.json` + generates interactive HTML report via `src/utils/html_report.py`

**Execution flow per iteration (supervisor.py `_execute_iteration`):**
- Phase 1 (parallel): GENERATION + PROXIMITY
- Phase 2 (parallel): REFLECTION + OBSERVATION_REVIEW
- Phase 3 (parallel): RANKING + EVOLUTION
- Phase 4: META_REVIEW (also generates research overview in-iteration)

Termination: convergence >= 0.85 OR quality threshold met OR max iterations OR time limit OR budget exceeded. Blocked until every hypothesis has at least 1 tournament match.

### Generation methods (all 4 paper methods now implemented)

| Method | Weight | Implementation |
|--------|--------|----------------|
| LITERATURE_EXPLORATION | 30% | `_generate_via_literature` via `02_Prompts/01_*.txt` |
| SIMULATED_DEBATE | 30% | `_generate_via_debate` - 3 expert personas, 3 turns + synthesis |
| RESEARCH_EXPANSION | 25% | `_generate_via_expansion` - uses research_overview to target gaps |
| ITERATIVE_ASSUMPTIONS | 15% | `_generate_via_iterative_assumptions` - identify untested assumptions + reasoning chain |

Random weighted selection per generation task (`supervisor.py:621`).

### Review types (all paper types)

| Type | Purpose |
|------|---------|
| INITIAL | Quick pass/fail screen |
| FULL | Stricter review with citation verification, assumption probing, **biochemical compatibility check** (cofactor, substrate, environment, host, binding-domain) |
| DEEP_VERIFICATION | Decomposes hypothesis into assumptions, classifies fundamental vs non-fundamental |
| OBSERVATION | Validates hypothesis against literature observations (separate `ObservationReviewAgent`) |

### Tournament (paper Section 3.3.3 + extensions)

- Elo-based (K=32, initial 1200)
- Multi-turn debate runs BEFORE winner decision; transcript fed to decision prompt
- **Newcomer pairing tier (30% of budget)**: unmatched hypotheses paired against top-50%
- Within-cluster, cross-cluster, elite tiers (from proximity graph)
- Cross-iteration pair exclusion via `self._used_match_pairs`
- Cannot terminate while any hypothesis has 0 matches

### Session improvements (bugs fixed + features added)

**Pipeline bugs fixed:**
- Task queue double-free (get_next_task was deleting tasks before update_task_status could find them)
- Tasks created via `_create_task_for_agent` fallback never registered in queue
- Evolution silently dropped `parent_hypothesis_ids` due to schema mismatch
- `generate_research_overview` failed every call due to `tracing_v2_enabled` (async context manager) called from sync code - fixed by making `trace_run` a no-op passthrough
- Research overview never generated during iterations (only at run end) - now fires after each meta-review
- Evolution got stuck on single parent (10x evolved) - added top-5 selection with 3-parent cooldown
- Tournament monoculture (4 unique winners across 24 matches) - added newcomer pairing tier
- Early termination before late-arriving hypotheses could compete

**Quality improvements:**
- `ResearchGoal.constraints` now flows through all prompts (was defined in schema but never injected)
- Biochemical compatibility checklist added to FULL review
- Existing titles passed to generation for deduplication
- Semantic theme-saturation warning (keyword-based, fires when any theme >40% of pool)
- Phased milestones with go/no-go criteria required in all generation prompts
- Materials, limitations, estimated_timeline required in protocol
- Citations required (including in iterative_assumptions path)
- Evolution generates new summary instead of inheriting parent's (was causing label/content mismatch)
- Evolution retries once on truncated JSON from Gemini

**Infrastructure:**
- LangSmith tracing: EU endpoint (`eu.api.smith.langchain.com`), PAT token, project `AGF-co-scientist`
- LLM clients read API keys from `os.environ` first, settings fallback (for per-request API middleware)
- Interactive HTML report (`src/utils/html_report.py`) - self-contained with Plotly, filterable cards
- Safety threshold default 0.0 (disabled)

**Paper features completed:**
- Iterative assumptions generation method (was a stub enum)
- Observation review as a separate agent class (paper describes it as a review subtype)

### Extensions beyond the paper

1. Citation graph expansion (PubMed + Semantic Scholar merger, backward traversal)
2. Paper quality scoring (recency, citations, journal tier, retraction filtering)
3. Refutation search (actively seeks contradictory evidence, checks retraction status)
4. Biochemical compatibility validation in FULL review
5. Cost tracking with AUD budget enforcement
6. Safety agent as separate gatekeeper
7. Existing-title deduplication across all generation methods
8. Evolution parent rotation
9. Newcomer tournament pairing
10. Interactive HTML report generation

### Open improvement opportunities

**High-impact (next session):**
- Elo K-factor tuning (currently 32, paper doesn't specify)
- Proximity agent is O(n²) LLM calls - wire embedding client or use batched call
- Simulation review (`ReviewType.SIMULATION`) - mentioned in paper but not implemented
- Scientist-in-the-loop mid-run feedback injection

**Medium-impact:**
- Research contacts from citation graph (paper describes this, our meta_review mentions contacts but doesn't link to real authors)
- Richer embeddings for proximity (currently LLM similarity scoring is slow and approximate)
- Per-hypothesis cost accounting (currently global budget only)

**Systematic quality issues observed in grant panel reviews:**
- LLM generates creative ideas but **routinely stacks 5+ unvalidated modules** (feasibility scores 3-5/10 across every run)
- Recurring biochemical errors: Wza topology confusion, PhaB cofactor specificity, VHb as O2 consumer (not carrier), CBD binding non-cellulose EPS
- Phased milestones now required but LLM may treat as optional - monitor next run
- Thematic monoculture can shift to new cluster each run (buoyancy in run 4). Keyword-based detection may need expansion

### Running the system

```bash
# 1. Activate env
conda activate coscientist

# 2. Launch CLI run in background
cd "Google co-scientist"
python /tmp/run_coscientist.py > /tmp/coscientist-run.log 2>&1 &

# 3. Monitor
tail -f /tmp/coscientist-run.log
grep "iteration_complete" /tmp/coscientist-run.log

# 4. View results
open data/runs/run_<timestamp>.html
```

Typical run: 20 iterations × ~10 min = 2-3 hours, 40-60 hypotheses, $2-5 USD in Gemini costs.

**Monitoring during run:**
- `grep -c "task_execution_failed"` - should stay 0
- `grep -oE "method=[a-z_]+" | sort | uniq -c` - all 4 methods firing
- `grep "research_overview_generated"` - should appear by iteration 3
- `grep "MUST propose something"` - theme saturation warning firing
- Traces: https://eu.smith.langchain.com (`AGF-co-scientist` project)

## Notes

- All hypotheses require human expert validation
- Cost tracking enforces budget limits ($50 AUD default)

