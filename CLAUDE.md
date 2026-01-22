# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

The goal of this project is to **re-build and replicate Google's AI co-scientist system** - a multi-agent AI system designed to augment scientific discovery through collaborative hypothesis generation.

## Project Overview

This repository contains academic papers and reference materials documenting Google's AI co-scientist system architecture, prompts, and validation studies.

**Primary Reference Document:** `01_Paper/01_google_co-scientist.pdf`

> **Important:** Only read `01_google_co-scientist.pdf` for understanding the system architecture. The other PDFs in `01_Paper/` are supplementary materials (prompts, references, validation examples) and should NOT be read to avoid contaminating the context window with lengthy content.

## Repository Structure

- `01_Paper/` - Academic papers and documentation

  - `01_google_co-scientist.pdf` - Main paper describing the AI co-scientist system
  - `02_Prompts.pdf` - Agent prompts and example
  - `04_References.pdf` - Bibliography and references
  - `05_drug_repurposing.pdf` - Drug repurposing validation examples
  - `06_alphafold_integration.pdf` - AlphaFold tool integration details
  - `07_Conclusion_and_ethical.pdf` - conclusion and ethical implication
  - `08_introduction.pdf` - cover page with authors
  - 
- `02_Prompts/` - Individual prompts for the subagents in txt format

  - `01_Generation_Agent_Hypothesis_After_Literature_Review.txt`
  - `02_Generation_Agent_Hypothesis_After_Scientific_Debate.txt`
  - `03_Reflection_Agent_Generating_Observations.txt`
  - `04_Ranking_Agent_Hypothesis_Comparison_Tournament.txt`
  - `05_Ranking_Agent_Hypothesis_Comparison_Scientific_Debate.txt`
  - `06_Evolution_Agent_Hypothesis_Feasibility_Improvement.txt`
  - `07_Evolution_Agent_Hypothesis_Out_of_the_Box_Thinking.txt`
  - `08_Meta_Review_Agent_Meta_Review_Generation.txt`

- `03_Architecture/` - System architecture and data schemas

  - `schemas.py` - Pydantic data models defining all system data structures
  - `logic.md` - System flow, supervisor logic, and agent orchestration documentation
  - `environment.yml` - Conda environment with all dependencies
  - `.env.example` - Environment variables template (API keys, model config, budget)

- `04_Scripts/` - Utility scripts and tools

  - `cost_tracker.py` - Token usage and cost tracking with budget limits

## AI Co-scientist System Architecture

The system uses six specialized agents orchestrated by a Supervisor agent:

1. **Generation Agent** - Creates initial hypotheses via literature exploration and simulated scientific debates
2. **Reflection Agent** - Performs reviews (initial, full, deep verification, observation, simulation, tournament)
3. **Ranking Agent** - Runs Elo-based tournaments for hypothesis evaluation via pairwise comparisons
4. **Evolution Agent** - Refines hypotheses through grounding, simplification, combination, and out-of-box thinking
5. **Proximity Agent** - Builds similarity graphs for hypothesis clustering and de-duplication
6. **Meta-review Agent** - Synthesizes feedback patterns and generates research overviews

## Key Concepts

- **Generate, Debate, Evolve** - Core approach inspired by the scientific method
- **Test-time compute scaling** - Quality improves with more computational resources
- **Scientist-in-the-loop** - Designed for human expert collaboration, not autonomous operation
- **Elo rating** - Auto-evaluation metric for hypothesis ranking (concordant with accuracy on GPQA benchmark)

## System Logic (`03_Architecture/logic.md`)

The logic document describes the control flow and orchestration of the multi-agent system:

### Supervisor Agent Responsibilities

1. **Parse Research Goal** - Extract constraints, preferences, generate ResearchPlanConfiguration
2. **Initialize Task Queue** - Create initial Generation tasks, set agent weights
3. **Continuous Execution Loop**:
   - Assign agents to worker processes based on weights
   - Execute tasks asynchronously
   - Periodically compute statistics (hypothesis counts, tournament progress, agent effectiveness)
   - Adjust resource allocation based on effectiveness
   - Write state to Context Memory
   - Check terminal conditions (convergence, budget, quality threshold)
4. **Generate Research Overview** - Trigger Meta-review agent for final synthesis

### Self-Improving Loop (No Backpropagation)

```
Generate → Review → Tournament → Win/Loss Patterns → Meta-review → Feedback to Prompts → Generate...
```

The system improves via **in-context learning**: Meta-review feedback is appended to agent prompts in subsequent iterations, leveraging Gemini 2.0's long-context reasoning.

### Task Scheduling Priorities

- **Reflection**: Prioritize hypotheses without reviews
- **Ranking**: Pair similar hypotheses (from Proximity graph), newer hypotheses, top-ranked hypotheses
- **Evolution**: Focus on top-ranked hypotheses for refinement

### Terminal State Detection

The system terminates when:
1. Elo ratings converge (top hypotheses stabilize)
2. Compute budget exhausted
3. Quality threshold met
4. Scientist manually stops

## Data Schemas (`03_Architecture/schemas.py`)

The schemas file defines 27 Pydantic models representing all data structures in the system:

### Enumerations

| Enum | Purpose |
|------|---------|
| `HypothesisStatus` | Pipeline states: generated, initial_review, full_review, in_tournament, evolved, archived |
| `ReviewType` | Review types: initial, full, deep_verification, observation, simulation, tournament |
| `EvolutionStrategy` | Strategies: grounding, coherence, feasibility, inspiration, combination, simplification, out_of_box |
| `AgentType` | All 7 agent types (supervisor, generation, reflection, ranking, proximity, evolution, meta_review) |
| `GenerationMethod` | Methods: literature_exploration, simulated_debate, iterative_assumptions, research_expansion |

### Core Models

| Model | Description |
|-------|-------------|
| `ResearchGoal` | Scientist's input with description, constraints, preferences, prior publications |
| `ResearchPlanConfiguration` | Parsed config with evaluation criteria, domain constraints, enabled tools |
| `Hypothesis` | Main output: title, statement, rationale, mechanism, experimental protocol, citations, Elo rating |
| `Assumption` | Decomposed assumptions with sub-assumptions for deep verification |
| `Citation` | Literature reference with DOI, relevance explanation |
| `ExperimentalProtocol` | Proposed experiments with methodology, controls, success criteria |

### Review Models

| Model | Description |
|-------|-------------|
| `Review` | Base review with scores (correctness, quality, novelty, testability, safety) and qualitative feedback |
| `DeepVerificationReview` | Extended review for assumption decomposition and invalidation tracking |

### Tournament Models

| Model | Description |
|-------|-------------|
| `TournamentMatch` | Pairwise comparison with debate turns and Elo changes |
| `DebateTurn` | Single debate turn with arguments and counterpoints |
| `TournamentState` | Overall state with Elo ratings, match history, win/loss patterns |

### Proximity Graph Models

| Model | Description |
|-------|-------------|
| `ProximityEdge` | Similarity edge between two hypotheses |
| `ProximityGraph` | Full graph with edges and clusters |
| `HypothesisCluster` | Cluster of similar hypotheses with common themes |

### Meta-Review & Overview Models

| Model | Description |
|-------|-------------|
| `MetaReviewCritique` | Synthesized feedback with recurring patterns and agent-specific feedback |
| `ResearchDirection` | Potential research direction with suggested experiments |
| `ResearchContact` | Suggested domain expert for collaboration |
| `ResearchOverview` | Comprehensive overview with directions, top hypotheses, contacts |

### System State Models

| Model | Description |
|-------|-------------|
| `AgentTask` | Task queue item with priority, parameters, status |
| `SystemStatistics` | Supervisor metrics: hypothesis counts, tournament progress, agent effectiveness |
| `ContextMemory` | Persistent state across iterations (tournament, graph, reviews, scientist feedback) |

### Scientist Interaction Models

| Model | Description |
|-------|-------------|
| `ScientistFeedback` | Feedback on hypotheses or goal refinements |
| `ChatMessage` | Message in scientist-system chat interface |

## Validated Biomedical Applications

1. **Drug Repurposing (AML)** - Identified candidates like KIRA6 showing IC50 as low as 13 nM
2. **Novel Target Discovery (Liver Fibrosis)** - Proposed epigenetic targets validated in human hepatic organoids
3. **Antimicrobial Resistance (cf-PICIs)** - Independently recapitulated unpublished experimental findings

## Technology Stack

| Component | Tool |
|-----------|------|
| Agent Framework | LangGraph |
| LLM Provider | Google Gemini (primary), Anthropic Claude (optional) |
| Data Validation | Pydantic |
| Web Search | Tavily API |
| Vector Storage | ChromaDB (prototype) / pgvector (production) |
| Database | PostgreSQL + Redis |
| Backend API | FastAPI |

## Environment Setup

```bash
# Create conda environment
conda env create -f 03_Architecture/environment.yml
conda activate coscientist

# Configure API keys
cp 03_Architecture/.env.example 03_Architecture/.env
# Edit .env with your API keys
```

## Cost Tracking

The system includes a cost tracker (`04_Scripts/cost_tracker.py`) with:
- Hard budget limit (default: $50 AUD)
- Per-agent token and cost tracking
- Persistent storage across sessions
- `BudgetExceededError` when limit reached

```python
from cost_tracker import get_tracker

tracker = get_tracker(budget_aud=50.0)
tracker.check_budget()  # Raises if over budget
tracker.add_usage("generation", "gemini-3-pro-preview", input_tokens, output_tokens)
tracker.print_summary()
```

## Working with This Repository

When analyzing or extending this research:

- The system is model-agnostic and built on Gemini 2.0 but portable to other LLMs
- Hypotheses must be grounded in prior literature, not standalone ideas
- Safety mechanisms include goal/hypothesis safety reviews and adversarial testing
- All outputs require human expert validation before experimental pursuit

---

## Implementation Progress

### Phase 1: Foundation ✅ COMPLETE (Jan 22, 2026)

**Status:** All components implemented and tested successfully.

#### Components Implemented

1. **Project Structure**
   - Created organized `src/` directory with modular structure
   - Proper Python package hierarchy with `__init__.py` files

2. **Configuration Module** ([src/config.py](src/config.py))
   - Pydantic-based settings management
   - Loads from `03_architecture/.env`
   - Type-safe configuration for API keys, models, budget, paths

3. **Utility Modules** ([src/utils/](src/utils/))
   - `ids.py` - Unique ID generation for hypotheses, reviews, matches, tasks
   - `logging_config.py` - Structured JSON logging via structlog
   - `errors.py` - Custom exception hierarchy (CoScientistError, BudgetExceededError, etc.)

4. **Prompt Manager** ([src/prompts/loader.py](src/prompts/loader.py))
   - Loads agent prompts from `02_Prompts/*.txt`
   - Template formatting with research goals and preferences
   - Supports all 6 agent types with method variants
   - In-memory caching for performance

5. **LLM Client Infrastructure** ([src/llm/](src/llm/))
   - `base.py` - Abstract base client with sync/async interface
   - `google.py` - Google Gemini client with cost tracking integration
   - `openai.py` - OpenAI GPT client with cost tracking integration
   - Handles structured/unstructured responses (text blocks, JSON)
   - Token estimation and budget enforcement

6. **Agent Infrastructure** ([src/agents/](src/agents/))
   - `base.py` - Abstract base agent with logging
   - `generation.py` - **Generation Agent** (fully functional)
     - Literature exploration method
     - Structured JSON output parsing
     - Validates against Pydantic schemas (Hypothesis, ExperimentalProtocol, Citation)
     - Initial Elo rating assignment (1500.0)

7. **Integration Test** ([test_phase1.py](test_phase1.py))
   - End-to-end validation of all Phase 1 components
   - Tests configuration, ID generation, prompt loading, agent execution, cost tracking

#### Test Results

```
✅ Configuration loaded successfully
✅ ID generation working
✅ Prompts loading from files
✅ Generation Agent created complete hypothesis:
   - Title: "Repurposing Disulfiram as a Selective NPL4-Targeting Agent..."
   - Complete with: statement, rationale, mechanism, experimental protocol, citations
   - Initial Elo rating: 1500.0
✅ Cost tracking recorded usage: 1,307 input / 2,679 output tokens
```

#### Budget Status

- **Budget:** $50.00 AUD
- **Spent:** $0.05 AUD (0.1%)
- **Remaining:** $49.95 AUD
- **API Calls:** 5 (Google Gemini 3 Pro Preview)

#### Key Learnings

1. **Gemini Response Handling:** Response content can be a list of content blocks (dicts with 'text' field), not just strings. Implemented flexible parsing in `google.py`.

2. **Schema Alignment:** LLM output JSON must match Pydantic schema field names exactly:
   - Hypothesis requires: `research_goal_id`, `summary`, `hypothesis_statement`
   - ExperimentalProtocol requires: `objective`, `controls` (list), `expected_outcomes` (list)
   - Citation requires: `title`, `relevance`

3. **Prompt Engineering:** Providing schema examples in JSON format improves structured output consistency.

#### Dependencies Installed

- `structlog` - Structured logging
- `langchain-google-genai` - Google Gemini integration
- `langchain-openai` - OpenAI integration
- Plus transitive deps: `google-genai`, `langchain-core`, `langsmith`, `tiktoken`, etc.

#### Files Created

```
src/
├── __init__.py
├── config.py                  # Settings management
├── utils/
│   ├── __init__.py
│   ├── ids.py                 # ID generation
│   ├── logging_config.py      # Structured logging
│   └── errors.py              # Custom exceptions
├── prompts/
│   ├── __init__.py
│   └── loader.py              # Prompt loading/formatting
├── llm/
│   ├── __init__.py
│   ├── base.py                # Abstract LLM client
│   ├── google.py              # Gemini client
│   └── openai.py              # OpenAI client
└── agents/
    ├── __init__.py
    ├── base.py                # Abstract agent
    └── generation.py          # Generation agent

test_phase1.py                 # Integration test
```

#### Next Steps: Phase 2

Phase 2 will implement the core pipeline (Generate → Review → Rank):

1. **Reflection Agent** - Review and score hypotheses
2. **Ranking Agent** - Pairwise comparisons with Elo updates
3. **Tournament System** - Elo rating calculator and match pairing
4. **LangGraph Supervisor** - Orchestrate agent workflow
5. **State Management** - In-memory state storage
6. **Integration Test** - End-to-end pipeline validation
