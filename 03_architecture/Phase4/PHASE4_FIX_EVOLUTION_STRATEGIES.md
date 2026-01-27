# Agent Task 3: Enable Dynamic Evolution Strategies

## Objective

Replace hardcoded `FEASIBILITY` evolution strategy with dynamic strategy selection using all 7 available strategies based on hypothesis characteristics.

---

## Problem Statement

The system defines **7 evolution strategies** per the Google Co-Scientist paper, but only `FEASIBILITY` is ever used:
- All strategies are defined in [03_architecture/schemas.py:47-56](03_architecture/schemas.py#L47-L56)
- The evolution agent supports all strategies at [src/agents/evolution.py:55-71](src/agents/evolution.py#L55-L71)
- But callers hardcode `FEASIBILITY` everywhere

---

## Evidence

### All 7 Strategies Defined

**[03_architecture/schemas.py:47-56](03_architecture/schemas.py#L47-L56):**
```python
class EvolutionStrategy(str, Enum):
    """Strategies used by the Evolution agent to refine hypotheses."""

    GROUNDING = "grounding"              # Enhance with literature support
    COHERENCE = "coherence"              # Improve logical consistency
    FEASIBILITY = "feasibility"          # Make more practical/testable
    INSPIRATION = "inspiration"          # Create new hypothesis inspired by existing
    COMBINATION = "combination"          # Merge best aspects of multiple hypotheses
    SIMPLIFICATION = "simplification"    # Simplify for easier verification
    OUT_OF_BOX = "out_of_box"            # Divergent thinking, explore novel directions
```

### Agent Supports All Strategies

**[src/agents/evolution.py:55-71](src/agents/evolution.py#L55-L71):**
```python
# Strategy grouping logic - routes to appropriate prompts
if strategy in [EvolutionStrategy.GROUNDING, EvolutionStrategy.COHERENCE,
                EvolutionStrategy.FEASIBILITY, EvolutionStrategy.SIMPLIFICATION]:
    # Use feasibility improvement prompt
    prompt = prompt_manager.format_evolution_prompt(
        hypothesis=self._format_hypothesis(hypothesis),
        strategy="feasibility",
        ...
    )
else:
    # Use out-of-box thinking prompt (INSPIRATION, COMBINATION, OUT_OF_BOX)
    prompt = prompt_manager.format_evolution_prompt(
        hypothesis=self._format_hypothesis(hypothesis),
        strategy="out_of_box",
        ...
    )
```

### But Hardcoded to FEASIBILITY

**[src/graphs/workflow.py:198](src/graphs/workflow.py#L198):**
```python
evolved = self.evolution_agent.execute(
    hypothesis=hypothesis,
    strategy=EvolutionStrategy.FEASIBILITY,  # <-- HARDCODED
    reviews=reviews
)
```

**[src/agents/supervisor.py:508](src/agents/supervisor.py#L508):**
```python
return AgentTask(
    # ...
    parameters={
        "hypothesis_id": top[0].id,
        "strategy": EvolutionStrategy.FEASIBILITY.value,  # <-- HARDCODED
    },
    # ...
)
```

---

## Files to Modify

| File | Action |
|------|--------|
| [src/graphs/workflow.py](src/graphs/workflow.py) | Add strategy selection logic |
| [src/agents/supervisor.py](src/agents/supervisor.py) | Add strategy selection logic |
| (Optional) [src/utils/strategy_selector.py](src/utils/strategy_selector.py) | Create reusable selector |

---

## Implementation Options

### Option A: Random Selection (Simplest)

```python
import random
from schemas import EvolutionStrategy

strategy = random.choice(list(EvolutionStrategy))
```

### Option B: Review-Based Selection (Recommended)

Select strategy based on weaknesses identified in reviews:

```python
from typing import List, Optional
from schemas import EvolutionStrategy, Review

def select_evolution_strategy(reviews: Optional[List[Review]] = None) -> EvolutionStrategy:
    """Select evolution strategy based on review feedback"""

    if not reviews:
        # No reviews - use random exploratory strategy
        return random.choice([
            EvolutionStrategy.OUT_OF_BOX,
            EvolutionStrategy.INSPIRATION
        ])

    # Analyze review content for weaknesses
    review_text = " ".join(r.content.lower() for r in reviews if r.content)

    # Map weaknesses to strategies
    if any(kw in review_text for kw in ["evidence", "literature", "citation", "support", "references"]):
        return EvolutionStrategy.GROUNDING

    if any(kw in review_text for kw in ["logic", "inconsistent", "contradiction", "coherent"]):
        return EvolutionStrategy.COHERENCE

    if any(kw in review_text for kw in ["practical", "feasible", "testable", "experiment"]):
        return EvolutionStrategy.FEASIBILITY

    if any(kw in review_text for kw in ["complex", "complicated", "simplify", "unclear"]):
        return EvolutionStrategy.SIMPLIFICATION

    if any(kw in review_text for kw in ["novel", "obvious", "incremental", "boring", "known"]):
        return EvolutionStrategy.OUT_OF_BOX

    if any(kw in review_text for kw in ["combine", "merge", "aspects", "elements"]):
        return EvolutionStrategy.COMBINATION

    # Default: random selection for diversity
    return random.choice(list(EvolutionStrategy))
```

### Option C: Round-Robin (Ensures Diversity)

```python
class StrategyRotator:
    def __init__(self):
        self.strategies = list(EvolutionStrategy)
        self.index = 0

    def next(self) -> EvolutionStrategy:
        strategy = self.strategies[self.index]
        self.index = (self.index + 1) % len(self.strategies)
        return strategy

# Usage
rotator = StrategyRotator()
strategy = rotator.next()
```

### Option D: Weighted Random (Bias Toward Useful)

```python
import random

STRATEGY_WEIGHTS = {
    EvolutionStrategy.GROUNDING: 0.20,      # Literature support
    EvolutionStrategy.COHERENCE: 0.15,      # Logic fixes
    EvolutionStrategy.FEASIBILITY: 0.25,    # Still important
    EvolutionStrategy.SIMPLIFICATION: 0.10, # Occasional
    EvolutionStrategy.OUT_OF_BOX: 0.15,     # Novelty
    EvolutionStrategy.INSPIRATION: 0.10,    # New ideas
    EvolutionStrategy.COMBINATION: 0.05,    # Rare
}

def weighted_strategy_selection() -> EvolutionStrategy:
    return random.choices(
        list(STRATEGY_WEIGHTS.keys()),
        weights=list(STRATEGY_WEIGHTS.values())
    )[0]
```

---

## Recommended Approach

**Use Option B (Review-Based Selection)** for intelligent selection, with **Option D (Weighted Random)** as fallback when reviews don't indicate clear weaknesses.

---

## Implementation Steps

### Step 1: Create Strategy Selector Utility

Create [src/utils/strategy_selector.py](src/utils/strategy_selector.py):

```python
"""Dynamic evolution strategy selection"""

import random
from typing import List, Optional
from schemas import EvolutionStrategy, Review


def select_evolution_strategy(
    reviews: Optional[List[Review]] = None,
    hypothesis_count: int = 0
) -> EvolutionStrategy:
    """
    Select evolution strategy based on context.

    Args:
        reviews: Review feedback for the hypothesis
        hypothesis_count: Total hypotheses generated so far

    Returns:
        Selected EvolutionStrategy
    """
    # Early iterations: favor divergent thinking
    if hypothesis_count < 5:
        return random.choice([
            EvolutionStrategy.OUT_OF_BOX,
            EvolutionStrategy.INSPIRATION
        ])

    # With reviews: analyze for weaknesses
    if reviews:
        review_text = " ".join(r.content.lower() for r in reviews if r.content)

        if "evidence" in review_text or "literature" in review_text:
            return EvolutionStrategy.GROUNDING
        if "logic" in review_text or "inconsistent" in review_text:
            return EvolutionStrategy.COHERENCE
        if "complex" in review_text:
            return EvolutionStrategy.SIMPLIFICATION
        if "novel" in review_text or "obvious" in review_text:
            return EvolutionStrategy.OUT_OF_BOX

    # Default: weighted random
    weights = {
        EvolutionStrategy.GROUNDING: 0.20,
        EvolutionStrategy.COHERENCE: 0.15,
        EvolutionStrategy.FEASIBILITY: 0.25,
        EvolutionStrategy.SIMPLIFICATION: 0.10,
        EvolutionStrategy.OUT_OF_BOX: 0.15,
        EvolutionStrategy.INSPIRATION: 0.10,
        EvolutionStrategy.COMBINATION: 0.05,
    }
    return random.choices(list(weights.keys()), weights=list(weights.values()))[0]
```

### Step 2: Update Workflow

Edit [src/graphs/workflow.py:198](src/graphs/workflow.py#L198):

```python
from src.utils.strategy_selector import select_evolution_strategy

# In evolve_node method:
def evolve_node(self, state: WorkflowState) -> Dict[str, Any]:
    # ... existing code to get hypothesis and reviews ...

    # Dynamic strategy selection
    strategy = select_evolution_strategy(
        reviews=reviews,
        hypothesis_count=len(state.get("hypotheses", []))
    )

    evolved = self.evolution_agent.execute(
        hypothesis=hypothesis,
        strategy=strategy,  # DYNAMIC
        reviews=reviews
    )
```

### Step 3: Update Supervisor

Edit [src/agents/supervisor.py:508](src/agents/supervisor.py#L508):

```python
from src.utils.strategy_selector import select_evolution_strategy

# In _create_task_for_agent method:
elif agent_type == AgentType.EVOLUTION:
    top = await self.storage.get_top_hypotheses(n=1, goal_id=goal_id)
    if top:
        # Get reviews for this hypothesis
        reviews = await self.storage.get_reviews_for_hypothesis(top[0].id)
        all_hypotheses = await self.storage.get_hypotheses(goal_id=goal_id)

        # Dynamic strategy selection
        strategy = select_evolution_strategy(
            reviews=reviews,
            hypothesis_count=len(all_hypotheses)
        )

        return AgentTask(
            id=generate_task_id(),
            agent_type=AgentType.EVOLUTION,
            task_type="evolve_hypothesis",
            priority=6,
            parameters={
                "hypothesis_id": top[0].id,
                "strategy": strategy.value,  # DYNAMIC
            },
            status="pending"
        )
```

---

## Verification

1. **Unit test for strategy selector:**
   ```python
   # 05_tests/test_strategy_selector.py
   from src.utils.strategy_selector import select_evolution_strategy
   from schemas import EvolutionStrategy, Review

   def test_grounding_selected_for_evidence_feedback():
       reviews = [Review(content="Needs more literature evidence")]
       strategy = select_evolution_strategy(reviews=reviews)
       assert strategy == EvolutionStrategy.GROUNDING

   def test_out_of_box_for_novelty_feedback():
       reviews = [Review(content="This is too obvious")]
       strategy = select_evolution_strategy(reviews=reviews)
       assert strategy == EvolutionStrategy.OUT_OF_BOX

   def test_all_strategies_can_be_selected():
       strategies_seen = set()
       for _ in range(1000):
           s = select_evolution_strategy(reviews=None, hypothesis_count=10)
           strategies_seen.add(s)
       assert len(strategies_seen) == len(EvolutionStrategy)
   ```

2. **Integration test:**
   ```bash
   # Run workflow and check logs for diverse strategies
   python 05_tests/phase3_test.py
   grep -i "strategy" logs/*.log | sort | uniq -c
   # Should show multiple different strategies used
   ```

3. **Verify evolved hypotheses track strategy:**
   - Check `Hypothesis.evolution_strategy` field is set correctly

---

## Success Criteria

- [ ] Strategy selector utility created and tested
- [ ] Workflow uses dynamic strategy selection
- [ ] Supervisor uses dynamic strategy selection
- [ ] All 7 strategies are used across multiple runs
- [ ] Strategy selection responds to review feedback
- [ ] Existing evolution tests pass
- [ ] Evolved hypotheses have varied `evolution_strategy` values