# Agent Task 2: Enable Multi-Turn Debate

## Objective

Enable the fully-implemented multi-turn debate feature in the ranking agent to allow adversarial refinement of hypothesis comparisons.

---

## Problem Statement

Multi-turn debate is **fully implemented** but **explicitly disabled**:
- 3-turn debate logic exists at [src/agents/ranking.py:169-224](src/agents/ranking.py#L169-L224)
- A heuristic to decide when to use debate exists at [src/tournament/elo.py:201-235](src/tournament/elo.py#L201-L235)
- But `multi_turn=False` is hardcoded everywhere

---

## Evidence

### Implementation Exists

**[src/agents/ranking.py:29-36](src/agents/ranking.py#L29-L36) - Method signature:**
```python
def execute(
    self,
    hypothesis_a: Hypothesis,
    hypothesis_b: Hypothesis,
    method: str = "tournament",
    multi_turn: bool = False,  # <-- Defaults to False
    goal: str = ""
) -> TournamentMatch:
```

**[src/agents/ranking.py:99-104](src/agents/ranking.py#L99-L104) - Conditional logic:**
```python
if multi_turn:
    debate_turns = self._run_multi_turn_debate(
        hypothesis_a,
        hypothesis_b,
        num_turns=3
    )
```

**[src/agents/ranking.py:169-224](src/agents/ranking.py#L169-L224) - Full implementation:**
```python
def _run_multi_turn_debate(
    self,
    hypothesis_a: Hypothesis,
    hypothesis_b: Hypothesis,
    num_turns: int = 3
) -> List[DebateTurn]:
    """Run multi-turn adversarial debate between hypotheses"""
    # ... complete 3-turn debate with counterpoints
```

### But It's Disabled

**[src/graphs/workflow.py:112-118](src/graphs/workflow.py#L112-L118):**
```python
match = self.ranking_agent.execute(
    hypothesis_a=hyp_a,
    hypothesis_b=hyp_b,
    method="tournament",
    multi_turn=False,  # <-- HARDCODED FALSE
    goal=state["research_goal"].description
)
```

**[src/agents/supervisor.py:628-636](src/agents/supervisor.py#L628-L636):**
```python
match = await asyncio.to_thread(
    agent.execute,
    hypothesis_a=h_a,
    hypothesis_b=h_b,
    # multi_turn is NEVER passed - defaults to False
    goal=research_goal.description,
)
```

### Unused Decision Heuristic

**[src/tournament/elo.py:201-235](src/tournament/elo.py#L201-L235):**
```python
def should_use_multi_turn(
    self,
    hypothesis_a: Hypothesis,
    hypothesis_b: Hypothesis,
    top_n: int = 10,
    all_hypotheses: list[Hypothesis] = None
) -> bool:
    """Determine if match should use multi-turn debate

    Multi-turn debates are used for:
    - Matches between top-ranked hypotheses
    - Close rating comparisons (within 100 points)
    """
```

---

## Files to Modify

| File | Action |
|------|--------|
| [src/graphs/workflow.py](src/graphs/workflow.py) | Enable multi_turn or use heuristic |
| [src/agents/supervisor.py](src/agents/supervisor.py) | Pass multi_turn=True when calling ranking |

---

## Implementation Options

### Option A: Simple Enable (Always On)

**[src/graphs/workflow.py:116](src/graphs/workflow.py#L116):**
```python
# Change from:
multi_turn=False,
# To:
multi_turn=True,
```

**[src/agents/supervisor.py:628-636](src/agents/supervisor.py#L628-L636):**
```python
match = await asyncio.to_thread(
    agent.execute,
    hypothesis_a=h_a,
    hypothesis_b=h_b,
    multi_turn=True,  # ADD THIS
    goal=research_goal.description,
)
```

### Option B: Smart Enable (Use Heuristic)

**[src/graphs/workflow.py](src/graphs/workflow.py) - before the execute call:**
```python
# Import at top
from src.tournament.elo import EloTournament

# In rank_node method, before execute():
use_multi_turn = self.tournament_manager.should_use_multi_turn(
    hyp_a,
    hyp_b,
    all_hypotheses=state.get("hypotheses", [])
)

match = self.ranking_agent.execute(
    hypothesis_a=hyp_a,
    hypothesis_b=hyp_b,
    method="tournament",
    multi_turn=use_multi_turn,  # DYNAMIC
    goal=state["research_goal"].description
)
```

### Option C: Configurable Enable

Add to workflow configuration:
```python
# In WorkflowConfigRequest or similar
enable_multi_turn_debate: bool = True
```

Pass through to execution:
```python
multi_turn=config.enable_multi_turn_debate,
```

---

## Recommended Approach

**Start with Option A** (simple enable) to verify the feature works, then migrate to **Option B** (heuristic-based) for production to avoid unnecessary compute on obvious matches.

---

## Implementation Steps

### Step 1: Enable in Workflow

Edit [src/graphs/workflow.py:116](src/graphs/workflow.py#L116):
```python
multi_turn=True,
```

### Step 2: Enable in Supervisor (if using)

Edit [src/agents/supervisor.py:628-636](src/agents/supervisor.py#L628-L636):
```python
match = await asyncio.to_thread(
    agent.execute,
    hypothesis_a=h_a,
    hypothesis_b=h_b,
    multi_turn=True,
    goal=research_goal.description,
    preferences=research_goal.preferences
)
```

### Step 3: (Optional) Integrate Heuristic

If using Option B, ensure `EloTournament` instance is available and call `should_use_multi_turn()` before each ranking.

---

## Verification

1. **Unit test for debate:**
   ```python
   # Add to 05_tests/phase2_test.py or create new test
   def test_multi_turn_debate_enabled():
       ranking_agent = RankingAgent()
       match = ranking_agent.execute(
           hypothesis_a=hyp_a,
           hypothesis_b=hyp_b,
           multi_turn=True,
           goal="Test goal"
       )
       assert match.debate_turns is not None
       assert len(match.debate_turns) == 3
   ```

2. **Check logs for debate turns:**
   ```bash
   # After running a goal, look for debate-related output
   grep -i "debate" logs/*.log
   ```

3. **Verify TournamentMatch contains debate_turns:**
   - The `TournamentMatch` schema at [03_architecture/schemas.py](03_architecture/schemas.py) should have `debate_turns: List[DebateTurn]`

---

## Performance Considerations

Multi-turn debate increases:
- **LLM calls**: 3 additional calls per match (for 3 debate turns)
- **Latency**: Each match takes ~3x longer
- **Cost**: More tokens processed

**Mitigation**: Use Option B (heuristic) to only run debates on:
- Top-ranked hypotheses
- Close rating comparisons (within 100 Elo points)

---

## Success Criteria

- [ ] `multi_turn=True` is passed to ranking agent
- [ ] `TournamentMatch` objects contain populated `debate_turns`
- [ ] Debate turns show adversarial arguments with counterpoints
- [ ] Existing ranking tests still pass
- [ ] (Optional) Heuristic selectively enables debate for important matches