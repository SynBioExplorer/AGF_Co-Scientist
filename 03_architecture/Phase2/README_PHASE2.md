# Phase 2: Core Pipeline

## Overview

Phase 2 implements the core Generate → Review → Rank pipeline, adding the Reflection Agent, Ranking Agent, Elo tournament system, in-memory storage, and LangGraph workflow orchestration.

**Status:** ✅ COMPLETE (Jan 23, 2026)
**Dependencies:** Phase 1 complete
**Estimated Duration:** 1 week

## Components

| Component | Description | Documentation |
|-----------|-------------|---------------|
| LLM Factory | Provider switching pattern | [PHASE2_LLM_FACTORY.md](./PHASE2_LLM_FACTORY.md) |
| Reflection Agent | Hypothesis review & scoring | [PHASE2_REFLECTION_AGENT.md](./PHASE2_REFLECTION_AGENT.md) |
| Ranking Agent | Tournament pairwise comparison | [PHASE2_RANKING_AGENT.md](./PHASE2_RANKING_AGENT.md) |
| Elo System | Tournament rating calculations | [PHASE2_ELO_SYSTEM.md](./PHASE2_ELO_SYSTEM.md) |
| Storage | In-memory state management | [PHASE2_STORAGE.md](./PHASE2_STORAGE.md) |
| Workflow | LangGraph orchestration | [PHASE2_WORKFLOW.md](./PHASE2_WORKFLOW.md) |

## Architecture

```
src/
├── llm/
│   └── factory.py              # LLM provider factory
├── agents/
│   ├── reflection.py           # Reflection agent
│   └── ranking.py              # Ranking agent
├── tournament/
│   ├── __init__.py
│   └── elo.py                  # Elo calculator & tournament ranker
├── storage/
│   ├── __init__.py
│   └── memory.py               # In-memory storage
└── graphs/
    ├── __init__.py
    ├── state.py                # Workflow state definition
    └── workflow.py             # LangGraph pipeline
```

## Pipeline Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Generate   │ -> │   Review    │ -> │    Rank     │
│ (2 hypos)   │    │ (scores)    │    │ (Elo tour) │
└─────────────┘    └─────────────┘    └─────────────┘
       │                                     │
       └─────────── Iterate ─────────────────┘
```

## Key Features

### Provider Switching
Change ONE variable to switch all agents:
```bash
LLM_PROVIDER=openai  # or "google"
```

### Elo Tournament
- Initial rating: 1200 (per Google paper)
- K-factor: 32
- Pairwise comparisons with winner determination

### LangGraph Workflow
- State accumulation with `Annotated[List[T], operator.add]`
- Convergence detection
- Quality-based stopping criteria

## Test Results

```
✅ Workflow completed 3 iterations
✅ Generated 6 hypotheses (2 per iteration)
✅ Completed 6 reviews (1 per hypothesis)
✅ Ran tournament matches with Elo updates
✅ Top hypotheses ranked by Elo rating
```

## Key Learnings

1. **Prompt Variables:** Ranking prompt requires specific names (`hypothesis 1`, not `hypothesis_1`)
2. **LangGraph State:** Use `Annotated[List[T], operator.add]` to accumulate
3. **Provider Flexibility:** Factory pattern enables one-line provider switching
4. **Elo Convergence:** Tournament naturally ranks; quality threshold prevents waste

## Quick Start

```bash
# Run Phase 2 test
python test_phase2.py
```

## Success Criteria

- [x] LLM factory switches providers via config
- [x] Reflection Agent reviews with multi-criteria scores
- [x] Ranking Agent conducts pairwise comparisons
- [x] Elo system calculates rating changes
- [x] Storage persists hypotheses, reviews, matches
- [x] Workflow executes multiple iterations
- [x] Convergence detection stops appropriately
