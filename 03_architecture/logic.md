# AI Co-Scientist System Logic & Flow

This document describes the control flow, supervisor logic, and agent orchestration of Google's AI co-scientist multi-agent system.

---

## 1. System Overview

The AI co-scientist is a **compound multi-agent system** built on Gemini 2.0 that mirrors the scientific method through iterative hypothesis generation, debate, and evolution.

### Four Key Components

| Component | Purpose |
|-----------|---------|
| **Natural Language Interface** | Scientists define goals, provide feedback, and guide the system |
| **Asynchronous Task Framework** | Enables flexible test-time compute scaling |
| **Specialized Agents** | Six agents handle distinct aspects of scientific reasoning |
| **Context Memory** | Persistent state for long-horizon reasoning and recovery |

---

## 2. High-Level Information Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              SCIENTIST INPUT                                  │
│  • Research goal (natural language)                                          │
│  • Constraints & preferences                                                  │
│  • Prior publications (optional)                                             │
│  • Feedback & own hypotheses                                                 │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         RESEARCH PLAN CONFIGURATION                          │
│  • Parse goal → evaluation criteria                                          │
│  • Set novelty requirements                                                  │
│  • Configure domain constraints                                              │
│  • Enable tools (web search, AlphaFold, etc.)                               │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            SUPERVISOR AGENT                                  │
│  • Creates & manages task queue                                              │
│  • Assigns agents to worker processes                                        │
│  • Allocates resources based on statistics                                   │
│  • Determines terminal state                                                 │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              ┌─────────┐      ┌─────────┐      ┌─────────┐
              │ Worker  │      │ Worker  │      │ Worker  │
              │   1     │      │   2     │      │   N     │
              └────┬────┘      └────┬────┘      └────┬────┘
                   │                │                │
                   └────────────────┴────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SPECIALIZED AGENTS                                   │
│                                                                              │
│   ┌────────────┐    ┌────────────┐    ┌────────────┐                        │
│   │ Generation │───▶│ Reflection │───▶│  Ranking   │                        │
│   │   Agent    │    │   Agent    │    │   Agent    │                        │
│   └────────────┘    └────────────┘    └─────┬──────┘                        │
│         ▲                  ▲                │                                │
│         │                  │                ▼                                │
│   ┌─────┴──────┐    ┌──────┴─────┐    Tournament                            │
│   │ Evolution  │◀───│Meta-review │◀───  State                               │
│   │   Agent    │    │   Agent    │                                          │
│   └────────────┘    └────────────┘                                          │
│                           ▲                                                  │
│                     ┌─────┴──────┐                                          │
│                     │ Proximity  │                                          │
│                     │   Agent    │                                          │
│                     └────────────┘                                          │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CONTEXT MEMORY                                     │
│  • Tournament state & Elo ratings                                            │
│  • Proximity graph                                                           │
│  • Meta-review critiques                                                     │
│  • System statistics                                                         │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SCIENTIST OUTPUT                                   │
│  • Research overview                                                         │
│  • Ranked hypotheses with Elo scores                                         │
│  • Experimental protocols                                                    │
│  • Suggested collaborators                                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The Supervisor Agent

The **Supervisor** is the central orchestrator that manages the entire system's execution.

### Responsibilities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SUPERVISOR AGENT LOOP                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. PARSE RESEARCH GOAL                                                     │
│     └──▶ Extract constraints, preferences, evaluation criteria             │
│     └──▶ Generate ResearchPlanConfiguration                                │
│                                                                             │
│  2. INITIALIZE TASK QUEUE                                                   │
│     └──▶ Create initial Generation tasks                                   │
│     └──▶ Set initial agent weights                                         │
│                                                                             │
│  3. CONTINUOUS EXECUTION LOOP                                               │
│     │                                                                       │
│     ├──▶ Assign agents to worker processes based on weights                │
│     │                                                                       │
│     ├──▶ Execute tasks asynchronously                                      │
│     │                                                                       │
│     ├──▶ PERIODICALLY COMPUTE STATISTICS:                                  │
│     │    • Hypotheses generated / pending review                           │
│     │    • Tournament progress & convergence                               │
│     │    • Agent effectiveness rates                                       │
│     │    • Generation method success rates                                 │
│     │                                                                       │
│     ├──▶ ADJUST RESOURCE ALLOCATION:                                       │
│     │    • Weight agents based on effectiveness                            │
│     │    • Prioritize promising directions                                 │
│     │                                                                       │
│     ├──▶ WRITE STATE TO CONTEXT MEMORY                                     │
│     │    • Enables recovery from failures                                  │
│     │    • Provides feedback for next iteration                            │
│     │                                                                       │
│     └──▶ CHECK TERMINAL CONDITIONS:                                        │
│          • Tournament convergence reached?                                 │
│          • Compute budget exhausted?                                       │
│          • Quality threshold met?                                          │
│                                                                             │
│  4. GENERATE RESEARCH OVERVIEW                                              │
│     └──▶ Trigger Meta-review agent to synthesize outputs                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Weight Allocation Logic

The Supervisor dynamically adjusts agent weights based on effectiveness:

```python
# Pseudocode for weight allocation
def compute_agent_weights(statistics):
    weights = {}

    # Generation vs Evolution balance
    if statistics.generation_success_rate > 0.5:
        weights['generation'] = 0.4
    else:
        weights['generation'] = 0.2

    # Prioritize evolution if top hypotheses need refinement
    if statistics.evolution_improvement_rate > 0.3:
        weights['evolution'] = 0.3

    # Always maintain review capacity
    weights['reflection'] = 0.2

    # Ranking depends on pending comparisons
    weights['ranking'] = min(0.2, pending_comparisons / 100)

    # Meta-review triggers periodically
    weights['meta_review'] = 0.05 if iteration % 10 == 0 else 0.0

    return normalize(weights)
```

---

## 4. Specialized Agent Details

### 4.1 Generation Agent

**Purpose:** Create initial hypotheses from the research goal.

| Method | Description |
|--------|-------------|
| **Literature Exploration** | Web search → read articles → synthesize → generate hypothesis |
| **Simulated Scientific Debate** | Self-play multi-turn debate leading to refined hypothesis |
| **Iterative Assumptions** | Identify testable intermediate assumptions via reasoning hops |
| **Research Expansion** | Review existing hypotheses + meta-review feedback → explore gaps |

```
Input:  Research goal + Meta-review feedback (optional)
Output: New Hypothesis with citations and experimental protocol
```

---

### 4.2 Reflection Agent

**Purpose:** Review and validate hypotheses like a scientific peer reviewer.

| Review Type | Tools | Purpose |
|-------------|-------|---------|
| **Initial** | None | Quick filter for obvious flaws |
| **Full** | Web search | Comprehensive literature-grounded review |
| **Deep Verification** | Web search | Decompose into assumptions, verify each |
| **Observation** | Web search | Can hypothesis explain existing phenomena? |
| **Simulation** | None | Step-wise simulation of mechanism |
| **Tournament** | Tournament state | Adapt reviews based on win/loss patterns |

```
Input:  Hypothesis + Review type
Output: Review with scores (correctness, novelty, quality, safety) + pass/fail
```

---

### 4.3 Ranking Agent

**Purpose:** Evaluate and rank hypotheses via Elo-based tournament.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ELO TOURNAMENT FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  NEW HYPOTHESIS ENTERS ──▶ Initial Elo = 1200                              │
│                                                                             │
│  MATCH SELECTION PRIORITY:                                                  │
│    1. Similar hypotheses (from Proximity graph)                            │
│    2. Newer hypotheses                                                      │
│    3. Top-ranked hypotheses                                                 │
│                                                                             │
│  COMPARISON METHODS:                                                        │
│    • Top-ranked: Multi-turn scientific debate                              │
│    • Lower-ranked: Single-turn pairwise comparison                         │
│                                                                             │
│  EVALUATION CRITERIA:                                                       │
│    • Novelty                                                                │
│    • Correctness                                                            │
│    • Testability                                                            │
│                                                                             │
│  OUTPUT:                                                                    │
│    • Winner/loser decision with rationale                                  │
│    • Elo rating updates                                                    │
│    • Win/loss patterns → Meta-review agent                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 4.4 Proximity Agent

**Purpose:** Compute similarity between hypotheses for clustering and match-making.

```
Input:  All hypotheses in tournament
Output: ProximityGraph with:
        • Similarity scores between hypothesis pairs
        • Clusters of related hypotheses
        • Representative hypothesis per cluster
```

**Uses:**
- Help Ranking agent pair similar hypotheses for meaningful comparisons
- Enable scientists to explore related ideas
- Support de-duplication

---

### 4.5 Evolution Agent

**Purpose:** Continuously refine and improve top-ranked hypotheses.

| Strategy | Description |
|----------|-------------|
| **Grounding** | Add literature support, fill reasoning gaps |
| **Coherence** | Fix logical inconsistencies |
| **Feasibility** | Make more practical and testable |
| **Inspiration** | Create new hypothesis inspired by existing ones |
| **Combination** | Merge best aspects of multiple hypotheses |
| **Simplification** | Simplify for easier verification |
| **Out-of-Box** | Divergent thinking, explore unconventional directions |

**Key Design:** Evolution creates NEW hypotheses rather than modifying existing ones. This protects top-ranked hypotheses from flawed improvements since each new hypothesis must compete in the tournament.

---

### 4.6 Meta-Review Agent

**Purpose:** Enable self-improvement through feedback synthesis.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      META-REVIEW AGENT FUNCTIONS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. PATTERN SYNTHESIS                                                       │
│     • Analyze all reviews and tournament debates                           │
│     • Identify recurring strengths in winning hypotheses                   │
│     • Identify recurring weaknesses in losing hypotheses                   │
│     • Generate meta-review critique                                        │
│                                                                             │
│  2. FEEDBACK PROPAGATION                                                    │
│     • Append feedback to Generation agent prompts                          │
│     • Append feedback to Reflection agent prompts                          │
│     • Append feedback to Evolution agent prompts                           │
│     └──▶ This is IN-CONTEXT LEARNING (no backpropagation!)                │
│                                                                             │
│  3. RESEARCH OVERVIEW GENERATION                                            │
│     • Synthesize top-ranked hypotheses                                     │
│     • Outline research directions                                          │
│     • Suggest experiments and collaborators                                │
│     • Format to specification (e.g., NIH Specific Aims)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. The Self-Improving Loop

The key innovation is a **self-improving loop** without any fine-tuning or reinforcement learning:

```
                    ┌──────────────────────────────────────┐
                    │                                      │
                    ▼                                      │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  Generate   │───▶│   Review    │───▶│  Tournament │     │
│ Hypotheses  │    │ Hypotheses  │    │   Matches   │     │
└─────────────┘    └─────────────┘    └──────┬──────┘     │
                                             │            │
                                             ▼            │
                                      ┌─────────────┐     │
                                      │ Win/Loss    │     │
                                      │ Patterns    │     │
                                      └──────┬──────┘     │
                                             │            │
                                             ▼            │
                                      ┌─────────────┐     │
                                      │ Meta-review │     │
                                      │ Synthesis   │     │
                                      └──────┬──────┘     │
                                             │            │
                                             ▼            │
                                      ┌─────────────┐     │
                                      │  Feedback   │─────┘
                                      │ to Prompts  │
                                      └─────────────┘
```

**How it works:**
1. Tournament matches reveal what makes hypotheses win or lose
2. Meta-review agent synthesizes patterns from all debates
3. Feedback is **appended to agent prompts** in the next iteration
4. Agents improve via Gemini 2.0's long-context reasoning
5. Quality scales with more test-time compute

---

## 6. Default Evaluation Criteria

All hypotheses are evaluated against these criteria:

| Criterion | Description |
|-----------|-------------|
| **Alignment** | Precisely matches research goals, preferences, and constraints |
| **Plausibility** | Free of obvious flaws; contradictions with literature must be justified |
| **Novelty** | Goes beyond existing knowledge; not just synthesis of known information |
| **Testability** | Amenable to empirical validation within specified constraints |
| **Safety** | Does not enable unsafe, unethical, or harmful research |

---

## 7. Task Scheduling & Prioritization

### Task Queue Management

```python
# Pseudocode for task scheduling
class TaskQueue:
    def get_next_tasks(self, agent_weights, statistics):
        tasks = []

        # Sample agents based on weights
        for agent_type, weight in agent_weights.items():
            num_tasks = int(weight * available_workers)

            if agent_type == 'generation':
                tasks.extend(create_generation_tasks(num_tasks))

            elif agent_type == 'reflection':
                # Prioritize hypotheses without reviews
                pending = get_hypotheses_pending_review()
                tasks.extend(create_review_tasks(pending[:num_tasks]))

            elif agent_type == 'ranking':
                # Prioritize: similar pairs, newer, top-ranked
                matches = select_tournament_matches(
                    proximity_graph=self.proximity_graph,
                    prioritize_new=True,
                    prioritize_top=True
                )
                tasks.extend(create_ranking_tasks(matches[:num_tasks]))

            elif agent_type == 'evolution':
                # Evolve top-ranked hypotheses
                top_hypotheses = get_top_ranked(k=10)
                tasks.extend(create_evolution_tasks(top_hypotheses))

        return tasks
```

### Terminal State Detection

The system terminates when:
1. **Convergence:** Elo ratings stabilize (top hypotheses stop changing)
2. **Budget:** Compute budget exhausted
3. **Quality:** Top hypothesis meets quality threshold
4. **User:** Scientist manually stops the system

---

## 8. Scientist-in-the-Loop Interactions

The system is designed for collaboration, not automation:

| Interaction | Effect |
|-------------|--------|
| **Refine goal** | Updates ResearchPlanConfiguration, may restart |
| **Provide review** | Added as scientist review, influences tournament |
| **Submit hypothesis** | Enters tournament alongside AI-generated ones |
| **Chat/discuss** | Guides exploration directions |
| **Request focus** | Restricts to specific literature or directions |

---

## 9. Tool Integration

Agents can use external tools via API:

| Tool | Used By | Purpose |
|------|---------|---------|
| **Web Search** | Generation, Reflection | Literature retrieval |
| **AlphaFold** | Generation, Reflection | Protein structure prediction |
| **Domain DBs** | Generation | Constrained search (e.g., FDA drugs) |
| **Private Repo** | All | Scientist-provided publications |

---

## 10. Relationship to schemas.py

This logic document corresponds to the data structures in `schemas.py`:

| Logic Component | Schema Classes |
|-----------------|----------------|
| Research Goal Parsing | `ResearchGoal` → `ResearchPlanConfiguration` |
| Hypothesis Flow | `Hypothesis`, `HypothesisStatus` |
| Review System | `Review`, `DeepVerificationReview`, `ReviewType` |
| Tournament | `TournamentState`, `TournamentMatch`, `DebateTurn` |
| Proximity | `ProximityGraph`, `ProximityEdge`, `HypothesisCluster` |
| Evolution | `EvolutionStrategy` (enum) |
| Meta-review | `MetaReviewCritique`, `ResearchOverview` |
| System State | `ContextMemory`, `SystemStatistics`, `AgentTask` |
| Scientist Input | `ScientistFeedback`, `ChatMessage` |

---

## References

- Google AI Co-Scientist Paper (2024)
- See `02_Prompts/` for actual agent prompts
- See `schemas.py` for data structure definitions
