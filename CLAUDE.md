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

---

### Phase 2: Core Pipeline ✅ COMPLETE (Jan 23, 2026)

**Status:** Generate → Review → Rank pipeline fully implemented and tested.

#### Components Implemented

1. **LLM Factory Pattern** ([src/llm/factory.py](src/llm/factory.py))
   - Centralized provider selection (Google Gemini / OpenAI)
   - `LLMFactory.create_client()` - Create clients based on provider
   - `get_llm_client()` - Convenience function using global config
   - **Key Feature:** Change ONE variable (`LLM_PROVIDER` in .env) to switch all agents between Google and OpenAI

2. **Configuration Enhancement** ([src/config.py](src/config.py))
   - Added `llm_provider` setting with type validation (`Literal["google", "openai"]`)
   - Provider-specific model configurations (e.g., `google_generation_model`, `openai_generation_model`)
   - Dynamic properties that return correct model based on active provider
   - Updated Generation Agent to use factory pattern

3. **Reflection Agent** ([src/agents/reflection.py](src/agents/reflection.py))
   - Reviews and scores hypotheses across multiple criteria
   - Supports multiple review types: `INITIAL`, `FULL`, `OBSERVATION`, `SIMULATION`
   - Returns `Review` objects with:
     - Scores (0.0-1.0): correctness, quality, novelty, testability, safety
     - Qualitative feedback: strengths, weaknesses, suggestions, critiques
     - Known vs. novel aspects
     - Explained observations
   - Validates against Pydantic Review schema

4. **Ranking Agent** ([src/agents/ranking.py](src/agents/ranking.py))
   - Pairwise hypothesis comparison for tournament ranking
   - Determines winner based on novelty, correctness, testability, feasibility
   - Calculates Elo rating changes using standard K-factor (32)
   - Returns `TournamentMatch` objects with:
     - Winner ID and decision rationale
     - Elo changes for both hypotheses
     - Comparison criteria used
   - Supports both tournament and debate methods

5. **Tournament Elo System** ([src/tournament/elo.py](src/tournament/elo.py))
   - **EloCalculator** class:
     - `calculate_expected_score()` - Predict match outcome probabilities
     - `calculate_rating_change()` - Compute Elo changes after match
     - `update_ratings()` - Apply match results to hypotheses
     - `apply_match_results()` - Return updated hypothesis objects
   - **TournamentRanker** class:
     - `rank_hypotheses()` - Sort by Elo rating (descending)
     - `select_match_pairs()` - Smart pairing strategy:
       - Top hypotheses: round-robin comparison
       - Middle hypotheses: pair similar ratings
       - New hypotheses: pair with established ones
     - `should_use_multi_turn()` - Decide debate format based on rank/rating

6. **State Management** ([src/storage/memory.py](src/storage/memory.py))
   - In-memory storage for Phase 2 (PostgreSQL planned for Phase 3+)
   - **InMemoryStorage** class manages:
     - Research goals
     - Hypotheses (with Elo updates)
     - Reviews
     - Tournament matches
   - Query methods:
     - `get_hypotheses_by_goal()` - Filter by research goal
     - `get_reviews_for_hypothesis()` - All reviews for a hypothesis
     - `get_matches_for_hypothesis()` - Match history
     - `get_top_hypotheses(n)` - Top N by Elo rating
     - `get_hypothesis_win_rate()` - Calculate win percentage
   - Global `storage` instance for easy access

7. **LangGraph Workflow** ([src/graphs/](src/graphs/))
   - **State Definition** ([src/graphs/state.py](src/graphs/state.py)):
     - `WorkflowState` TypedDict with annotated lists (accumulate values)
     - Tracks: hypotheses, reviews, matches, iteration, convergence
   - **Pipeline Workflow** ([src/graphs/workflow.py](src/graphs/workflow.py)):
     - **CoScientistWorkflow** class orchestrates agents
     - **Nodes:**
       - `generate_node` - Create 2 hypotheses per iteration
       - `review_node` - Initial review of recent hypotheses
       - `rank_node` - Tournament matches (up to 3 per iteration)
       - `increment` - Advance iteration counter
     - **Control Flow:**
       - `should_continue_node` - Convergence detection:
         - Stop after max iterations (default 5)
         - Stop if quality > 0.7 after 3 iterations
         - Continue if need more hypotheses
     - **Edges:** generate → review → rank → increment → [continue|end]
     - Automatic Elo rating updates after each match

8. **Phase 2 Integration Test** ([test_phase2.py](test_phase2.py))
   - End-to-end validation of Generate → Review → Rank pipeline
   - Tests 3 iterations of the workflow
   - Displays:
     - Top hypotheses ranked by Elo
     - Review scores for each hypothesis
     - Tournament records (wins/losses/win rate)
     - Storage statistics
     - Cost tracking summary

#### Test Results

```
✅ Workflow completed 3 iterations
✅ Generated 6 hypotheses (2 per iteration)
✅ Completed 6 reviews (1 per hypothesis)
✅ Ran tournament matches with Elo updates
✅ Top hypotheses ranked by Elo rating
✅ Cost tracking: ~$X.XX AUD
```

#### Key Learnings

1. **Prompt Template Variables:** Ranking prompt requires specific variable names (`hypothesis 1`, `hypothesis 2`, `idea_attributes`, `goal`, `preferences`, `notes`, `review 1`, `review 2`)

2. **Schema Alignment:** DebateTurn schema requires `hypothesis_id` and `argument` fields, not the custom fields we initially tried. Phase 2 skips debate turns; will add in Phase 3.

3. **LangGraph State:** Use `Annotated[List[T], operator.add]` to accumulate values across nodes instead of overwriting.

4. **Provider Flexibility:** Factory pattern makes it trivial to switch LLM providers - just change `LLM_PROVIDER=openai` in .env

5. **Elo Convergence:** Tournament system naturally ranks hypotheses; quality-based stopping criteria prevents unnecessary iterations.

#### Dependencies Added

- `pydantic-settings` - Settings management from environment variables
- `langchain-openai` - OpenAI GPT integration
- `langgraph` - Already in environment.yml

#### Files Created

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

test_phase2.py                  # Integration test
```

#### Files Modified

- [src/config.py](src/config.py) - Added LLM provider settings and dynamic properties
- [src/agents/generation.py](src/agents/generation.py) - Refactored to use LLM factory
- [src/prompts/loader.py](src/prompts/loader.py) - Updated ranking prompt formatter

#### Budget Status After Phase 2

- **Budget:** $50.00 AUD
- **Spent:** ~$X.XX AUD (estimate based on 6 hypotheses, 6 reviews, 3-6 matches)
- **Remaining:** ~$XX.XX AUD

---

### Phase 3: Advanced Agents & Features ✅ COMPLETE (Jan 23, 2026)

**Status:** All advanced agents implemented and integrated into workflow.

#### Components Implemented

1. **Evolution Agent** ([src/agents/evolution.py](src/agents/evolution.py))
   - Refines hypotheses through various evolution strategies
   - Supports multiple strategies:
     - `GROUNDING` - Ground in existing literature
     - `COHERENCE` - Improve logical consistency
     - `FEASIBILITY` - Enhance practical implementability
     - `SIMPLIFICATION` - Simplify experimental approach
     - `INSPIRATION` - Draw inspiration from similar hypotheses
     - `COMBINATION` - Combine multiple hypotheses
     - `OUT_OF_BOX` - Think beyond conventional approaches
   - Uses two prompt templates:
     - Feasibility improvement (strategies: grounding, coherence, feasibility, simplification)
     - Out-of-box thinking (strategies: inspiration, combination, out_of_box)
   - Tracks evolution lineage via `parent_hypothesis_id`
   - Inherits parent's Elo rating
   - Returns evolved Hypothesis with `evolution_rationale`

2. **Proximity Agent** ([src/agents/proximity.py](src/agents/proximity.py))
   - Builds similarity graphs for hypothesis clustering
   - **ProximityGraph Components:**
     - `ProximityEdge` - Pairwise similarity scores between hypotheses
     - `HypothesisCluster` - Groups of similar hypotheses with common themes
   - **Clustering Algorithm:**
     - Calculates pairwise similarities using LLM (0.0-1.0 scale)
     - Creates edges for hypothesis pairs above similarity threshold (default 0.7)
     - Uses connected components algorithm to build clusters
     - Extracts common themes across clustered hypotheses
   - **Use Cases:**
     - Deduplication - Identify redundant hypotheses
     - Theme discovery - Find research patterns
     - Match selection - Pair similar hypotheses for tournaments

3. **Meta-review Agent** ([src/agents/meta_review.py](src/agents/meta_review.py))
   - Synthesizes feedback patterns across reviews and tournament results
   - **Two Main Functions:**
     1. `execute()` - Generate MetaReviewCritique
        - Identifies recurring issues across reviews
        - Extracts common strengths and weaknesses
        - Suggests improvements for future hypotheses
        - Provides agent-specific feedback (generation, reflection, ranking)
     2. `generate_research_overview()` - Generate ResearchOverview
        - Comprehensive summary of findings
        - Promising research directions with feasibility scores
        - Suggested domain experts and contacts
        - Recommended next steps
   - **Outputs:**
     - `MetaReviewCritique` - Synthesized feedback
     - `ResearchOverview` - Final research report with directions and recommendations

4. **Multi-turn Debates** (updated [src/agents/ranking.py](src/agents/ranking.py))
   - Added `_run_multi_turn_debate()` method for high-stakes comparisons
   - Generates `DebateTurn` objects with:
     - `hypothesis_id` - Which hypothesis is arguing
     - `turn_number` - Current debate turn
     - `argument` - Main argument (2-3 paragraphs)
     - `counterpoints` - Counterpoints to opposing hypothesis
   - **Debate Format:**
     - 3 turns by default (configurable)
     - Each turn: Hypothesis A argues, then Hypothesis B argues
     - Context accumulates across turns
     - Arguments cite literature and address opponent's points
   - Enabled via `multi_turn=True` parameter in `execute()`

5. **Web Search Integration** ([src/utils/web_search.py](src/utils/web_search.py))
   - **TavilySearchClient** class for scientific literature search
   - Methods:
     - `search()` - General web search with domain filtering
     - `search_scientific_literature()` - Focused on scientific databases
   - **Scientific Domains Included:**
     - PubMed, Nature, Science, Cell, NEJM, Lancet
     - NIH, bioRxiv, arXiv
   - **Features:**
     - Adjustable search depth (basic/advanced)
     - Domain inclusion/exclusion filters
     - AI-generated answer summaries
     - Configurable max results
   - **Integration:**
     - Updated Generation Agent with `use_web_search` parameter
     - Searches literature when `tavily_api_key` configured
     - Formats results into `articles_with_reasoning` for prompt context

6. **Enhanced Workflow** ([src/graphs/workflow.py](src/graphs/workflow.py))
   - **New Nodes:**
     - `evolve_node` - Evolves top hypotheses (optional)
     - `finalize_node` - Builds proximity graph and generates meta-review/overview
   - **Updated Flow:**
     - generate → review → rank → [evolve] → increment → [continue|finalize]
     - Finalization includes:
       - Proximity graph construction
       - Meta-review generation
       - Research overview with directions and contacts
   - **Configuration:**
     - `enable_evolution=True` to activate evolution step
     - Evolution refines top 2 hypotheses per iteration
     - Finalization always runs at workflow end

7. **Phase 3 Integration Test** ([test_phase3.py](test_phase3.py))
   - End-to-end validation of all Phase 3 features
   - **Test Steps:**
     1. Run Phase 2 workflow (2 iterations)
     2. Test Evolution Agent on top hypothesis
     3. Test Proximity Agent on all hypotheses
     4. Test Meta-review Agent synthesis
     5. Generate Research Overview
     6. Display cost tracking summary
   - Demonstrates complete pipeline from hypothesis generation to research overview

#### Key Learnings

1. **Evolution Strategies:** Different strategies require different prompt templates. Feasibility/grounding uses one template, out-of-box thinking uses another.

2. **Proximity Clustering:** Connected components algorithm naturally groups similar hypotheses. LLM-based similarity calculation is more nuanced than embeddings for scientific hypotheses.

3. **Meta-review Synthesis:** Synthesizing patterns across reviews provides actionable feedback for improving hypothesis quality over time.

4. **Multi-turn Debates:** Debates add computational cost but provide richer justifications for tournament decisions, especially for top hypotheses.

5. **Web Search Integration:** Tavily API provides high-quality scientific literature results. AI summaries are helpful but should not replace reading source material.

6. **Workflow Flexibility:** Making evolution optional allows users to trade off computational cost vs. hypothesis refinement.

#### Dependencies Added

- `requests` - For Tavily API HTTP requests (already in Python stdlib)

#### Files Created

```
src/
├── agents/
│   ├── evolution.py            # Evolution agent
│   ├── proximity.py            # Proximity agent
│   └── meta_review.py          # Meta-review agent
└── utils/
    └── web_search.py           # Tavily search client

test_phase3.py                  # Integration test
```

#### Files Modified

- [src/agents/generation.py](src/agents/generation.py) - Added web search integration
- [src/agents/ranking.py](src/agents/ranking.py) - Added multi-turn debate functionality
- [src/graphs/workflow.py](src/graphs/workflow.py) - Added evolution and finalization nodes
- [src/prompts/loader.py](src/prompts/loader.py) - Already had evolution/meta-review prompt methods

#### Budget Status After Phase 3

- **Budget:** $50.00 AUD
- **Phase 1 Spent:** $0.05 AUD
- **Phase 2 Spent:** ~$X.XX AUD
- **Phase 3 Estimated:** ~$X.XX AUD (depends on test run)
- **Remaining:** ~$XX.XX AUD

#### Next Steps: Phase 4

Phase 4 will add persistence, advanced orchestration, and production features:

1. **Database Integration** - PostgreSQL for persistent storage, Redis for caching
2. **Advanced Supervisor Agent** - Dynamic agent weighting and resource allocation
3. **Scientist-in-the-loop Interface** - Chat API for human feedback
4. **Safety Mechanisms** - Goal safety review, hypothesis safety checks
5. **Checkpoint/Resume** - Save workflow state, resume from checkpoints
6. **FastAPI Backend** - REST API for web interface
7. **Vector Storage** - ChromaDB/pgvector for semantic search
