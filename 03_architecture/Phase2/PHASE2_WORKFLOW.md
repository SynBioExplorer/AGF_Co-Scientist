# Phase 2: LangGraph Workflow

## Overview

LangGraph-based workflow orchestration implementing the Generate → Review → Rank pipeline with state accumulation and convergence detection.

**Files:** `src/graphs/state.py`, `src/graphs/workflow.py`
**Status:** ✅ Complete

## Workflow State

```python
# src/graphs/state.py

from typing import TypedDict, List, Annotated
import operator
from schemas import Hypothesis, Review, TournamentMatch

class WorkflowState(TypedDict):
    """State passed between workflow nodes"""

    # Input
    research_goal_id: str

    # Accumulated outputs (append-only)
    hypotheses: Annotated[List[Hypothesis], operator.add]
    reviews: Annotated[List[Review], operator.add]
    matches: Annotated[List[TournamentMatch], operator.add]

    # Control flow
    iteration: int
    max_iterations: int
    converged: bool

    # Quality tracking
    average_quality: float
```

The `Annotated[List[T], operator.add]` pattern ensures lists accumulate across nodes rather than overwriting.

## Workflow Implementation

```python
# src/graphs/workflow.py

from langgraph.graph import StateGraph, END
from src.graphs.state import WorkflowState
from src.agents.generation import GenerationAgent
from src.agents.reflection import ReflectionAgent
from src.agents.ranking import RankingAgent
from src.storage.memory import storage
from src.llm.factory import get_llm_client
from schemas import ResearchGoal
import structlog

logger = structlog.get_logger()

class CoScientistWorkflow:
    """LangGraph workflow for hypothesis pipeline"""

    def __init__(self):
        self.generation_agent = GenerationAgent(
            get_llm_client(agent_name="generation")
        )
        self.reflection_agent = ReflectionAgent(
            get_llm_client(agent_name="reflection")
        )
        self.ranking_agent = RankingAgent(
            get_llm_client(agent_name="ranking")
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow"""
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("generate", self.generate_node)
        graph.add_node("review", self.review_node)
        graph.add_node("rank", self.rank_node)
        graph.add_node("increment", self.increment_node)

        # Add edges
        graph.set_entry_point("generate")
        graph.add_edge("generate", "review")
        graph.add_edge("review", "rank")
        graph.add_edge("rank", "increment")

        # Conditional edge for looping
        graph.add_conditional_edges(
            "increment",
            self.should_continue,
            {
                "continue": "generate",
                "end": END
            }
        )

        return graph.compile()

    async def generate_node(self, state: WorkflowState) -> dict:
        """Generate new hypotheses"""
        logger.info(f"Generate node - Iteration {state['iteration']}")

        goal = storage.get_research_goal(state['research_goal_id'])
        new_hypotheses = []

        # Generate 2 hypotheses per iteration
        for _ in range(2):
            hypothesis = await self.generation_agent.execute(goal)
            storage.add_hypothesis(hypothesis)
            new_hypotheses.append(hypothesis)

        return {"hypotheses": new_hypotheses}

    async def review_node(self, state: WorkflowState) -> dict:
        """Review recent hypotheses"""
        logger.info(f"Review node - {len(state['hypotheses'])} hypotheses")

        goal = storage.get_research_goal(state['research_goal_id'])
        new_reviews = []

        # Review hypotheses from this iteration
        recent_hypotheses = state['hypotheses'][-2:]  # Last 2

        for hypothesis in recent_hypotheses:
            review = await self.reflection_agent.execute(
                hypothesis=hypothesis,
                research_goal=goal
            )
            storage.add_review(review)
            new_reviews.append(review)

        # Calculate average quality
        avg_quality = sum(r.quality_score for r in new_reviews) / len(new_reviews)

        return {
            "reviews": new_reviews,
            "average_quality": avg_quality
        }

    async def rank_node(self, state: WorkflowState) -> dict:
        """Run tournament matches"""
        logger.info(f"Rank node - {len(state['hypotheses'])} hypotheses")

        goal = storage.get_research_goal(state['research_goal_id'])
        new_matches = []

        # Get hypotheses and their reviews
        hypotheses = state['hypotheses']
        if len(hypotheses) < 2:
            return {"matches": []}

        # Run up to 3 matches per iteration
        from src.tournament.elo import TournamentRanker
        ranker = TournamentRanker()
        pairs = ranker.select_match_pairs(hypotheses, max_pairs=3)

        for hyp_a, hyp_b in pairs:
            # Get reviews
            reviews_a = storage.get_reviews_for_hypothesis(hyp_a.id)
            reviews_b = storage.get_reviews_for_hypothesis(hyp_b.id)

            if not reviews_a or not reviews_b:
                continue

            # Run match
            match = await self.ranking_agent.execute(
                hypothesis_a=hyp_a,
                hypothesis_b=hyp_b,
                review_a=reviews_a[0],
                review_b=reviews_b[0],
                research_goal=goal
            )
            storage.add_match(match)
            new_matches.append(match)

            # Update Elo ratings
            hyp_a.elo_rating += match.elo_change_a
            hyp_b.elo_rating += match.elo_change_b
            storage.update_hypothesis(hyp_a)
            storage.update_hypothesis(hyp_b)

        return {"matches": new_matches}

    def increment_node(self, state: WorkflowState) -> dict:
        """Increment iteration counter"""
        return {"iteration": state['iteration'] + 1}

    def should_continue(self, state: WorkflowState) -> str:
        """Determine if workflow should continue"""

        # Check max iterations
        if state['iteration'] >= state['max_iterations']:
            logger.info("Max iterations reached")
            return "end"

        # Check quality threshold (after min iterations)
        if state['iteration'] >= 3:
            if state['average_quality'] > 0.7:
                logger.info("Quality threshold met")
                return "end"

        # Check minimum hypotheses
        if len(state['hypotheses']) < 4:
            return "continue"

        return "continue"

    async def run(
        self,
        research_goal: ResearchGoal,
        max_iterations: int = 5
    ) -> WorkflowState:
        """Run the workflow

        Args:
            research_goal: Research goal to work on
            max_iterations: Maximum iterations

        Returns:
            Final workflow state
        """
        # Store goal
        storage.add_research_goal(research_goal)

        # Initial state
        initial_state = {
            "research_goal_id": research_goal.id,
            "hypotheses": [],
            "reviews": [],
            "matches": [],
            "iteration": 0,
            "max_iterations": max_iterations,
            "converged": False,
            "average_quality": 0.0
        }

        # Run graph
        final_state = await self.graph.ainvoke(initial_state)

        logger.info(
            "Workflow completed",
            iterations=final_state['iteration'],
            hypotheses=len(final_state['hypotheses']),
            matches=len(final_state['matches'])
        )

        return final_state
```

## Workflow Diagram

```
                    ┌─────────────────┐
                    │   Entry Point   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
            ┌──────▶│    Generate     │ (2 hypotheses)
            │       └────────┬────────┘
            │                │
            │                ▼
            │       ┌─────────────────┐
            │       │     Review      │ (score each)
            │       └────────┬────────┘
            │                │
            │                ▼
            │       ┌─────────────────┐
            │       │      Rank       │ (tournament)
            │       └────────┬────────┘
            │                │
            │                ▼
            │       ┌─────────────────┐
            │       │   Increment     │ (iteration++)
            │       └────────┬────────┘
            │                │
            │                ▼
            │       ┌─────────────────┐
            │       │ Should Continue?│
            │       └───┬─────────┬───┘
            │           │         │
            │   continue│         │end
            │           │         │
            └───────────┘         ▼
                           ┌───────────┐
                           │    END    │
                           └───────────┘
```

## Convergence Detection

Workflow terminates when:

1. **Max iterations reached** - Default 5
2. **Quality threshold met** - Average quality > 0.7 after 3+ iterations
3. **Manual stop** - External termination

```python
def should_continue(self, state: WorkflowState) -> str:
    if state['iteration'] >= state['max_iterations']:
        return "end"

    if state['iteration'] >= 3 and state['average_quality'] > 0.7:
        return "end"

    return "continue"
```

## Usage

```python
from src.graphs.workflow import CoScientistWorkflow
from schemas import ResearchGoal

# Create workflow
workflow = CoScientistWorkflow()

# Define goal
goal = ResearchGoal(
    id="goal_001",
    description="Identify drug repurposing candidates for AML",
    constraints=["FDA-approved only"],
    preferences=["Testability"]
)

# Run workflow
final_state = await workflow.run(goal, max_iterations=3)

# Inspect results
print(f"Generated {len(final_state['hypotheses'])} hypotheses")
print(f"Ran {len(final_state['matches'])} tournament matches")

# Get top hypotheses
top_hypotheses = storage.get_top_hypotheses(n=3, goal_id=goal.id)
for hyp in top_hypotheses:
    print(f"  {hyp.title}: Elo {hyp.elo_rating:.0f}")
```

## State Accumulation

Using `Annotated[List[T], operator.add]`:

```python
# Node returns
return {"hypotheses": [new_hyp]}  # Adds to list

# State accumulates
# Iteration 1: hypotheses = [hyp1, hyp2]
# Iteration 2: hypotheses = [hyp1, hyp2, hyp3, hyp4]
# Iteration 3: hypotheses = [hyp1, hyp2, hyp3, hyp4, hyp5, hyp6]
```

## Testing

```python
@pytest.mark.asyncio
async def test_workflow_execution():
    """Test workflow runs to completion"""
    workflow = CoScientistWorkflow()

    goal = ResearchGoal(
        id="test",
        description="Test goal",
        constraints=[],
        preferences=[]
    )

    final_state = await workflow.run(goal, max_iterations=2)

    assert final_state['iteration'] == 2
    assert len(final_state['hypotheses']) >= 4  # 2 per iteration
    assert len(final_state['reviews']) >= 4

@pytest.mark.asyncio
async def test_convergence():
    """Test early convergence"""
    # With high quality hypotheses, should stop before max_iterations
    ...
```
