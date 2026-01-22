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

## Working with This Repository

When analyzing or extending this research:

- The system is model-agnostic and built on Gemini 2.0 but portable to other LLMs
- Hypotheses must be grounded in prior literature, not standalone ideas
- Safety mechanisms include goal/hypothesis safety reviews and adversarial testing
- All outputs require human expert validation before experimental pursuit
