"""Unit tests for B16: rebalance weights toward ranking; pool-size cap.

Before this fix the supervisor scheduled ~3 GENERATION + ~2 RANKING tasks per
iteration (weights 0.25 / 0.20 × tasks_per_iteration=12), producing 40-55
hypotheses but only 21-29 matches — 55-62% of hypotheses never reviewed.

Fix:
  (a) ``_initialize_weights``: GENERATION 0.25→0.15, RANKING 0.20→0.30 so
      each iteration creates more matches than hypotheses.
  (b) Pool-size cap in the GENERATION branch of ``_create_task_for_agent``:
      once the pool reaches ``settings.generation_pool_cap`` (default 40),
      no more GENERATION tasks are queued, regardless of weight.

(B3 drain phase and B16 weight final tuning are scheduled for post-live-run
empirical adjustment per the plan; this test verifies the static change.)
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import (  # noqa: E402
    AgentType,
    GenerationMethod,
    Hypothesis,
    ResearchGoal,
)


def _hyp(hid: str) -> Hypothesis:
    return Hypothesis(
        id=hid,
        research_goal_id="goal_001",
        title=hid,
        summary="s",
        hypothesis_statement="s",
        rationale="r",
        mechanism="m",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
    )


def test_initial_weights_favour_ranking_over_generation():
    """B16(a) — RANKING weight must exceed GENERATION weight after rebalance."""
    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):
        from src.agents.supervisor import SupervisorAgent

        agent = SupervisorAgent(storage=MagicMock())

    weights = agent.agent_weights
    assert weights[AgentType.RANKING] > weights[AgentType.GENERATION], (
        f"B16 regression: RANKING ({weights[AgentType.RANKING]}) should exceed "
        f"GENERATION ({weights[AgentType.GENERATION]})."
    )
    # Sums to ~1.0 (allow small floating point slack)
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected ~1.0"
    # tasks_per_iteration = 12; ranking must produce at least 3 tasks per iter.
    tasks_per_iteration = 12
    ranking_tasks = max(1, int(weights[AgentType.RANKING] * tasks_per_iteration))
    generation_tasks = max(1, int(weights[AgentType.GENERATION] * tasks_per_iteration))
    assert ranking_tasks >= generation_tasks, (
        f"B16 regression: per-iter ranking={ranking_tasks} should be >= "
        f"generation={generation_tasks}"
    )


def test_generation_pool_cap_blocks_new_generation():
    """B16(b) — when the pool reaches the cap, no new GENERATION task is queued."""
    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):
        from src.agents.supervisor import SupervisorAgent
        from src.config import settings

        # Synthesize a pool at the cap size.
        full_pool = [_hyp(f"h{i}") for i in range(settings.generation_pool_cap)]

        mock_storage = MagicMock()
        mock_storage.get_hypotheses_by_goal = AsyncMock(return_value=full_pool)

        agent = SupervisorAgent(storage=mock_storage)
        goal = ResearchGoal(id="goal_001", description="test goal")
        task = asyncio.run(
            agent._create_task_for_agent(AgentType.GENERATION, goal)
        )

    assert task is None, (
        f"B16 regression: GENERATION should be blocked at cap, "
        f"got task={task}"
    )


def test_generation_below_cap_still_runs():
    """B16(b) — below the cap, GENERATION still produces a task."""
    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):
        from src.agents.supervisor import SupervisorAgent

        small_pool = [_hyp(f"h{i}") for i in range(5)]

        mock_storage = MagicMock()
        mock_storage.get_hypotheses_by_goal = AsyncMock(return_value=small_pool)

        agent = SupervisorAgent(storage=mock_storage)
        goal = ResearchGoal(id="goal_001", description="test goal")
        task = asyncio.run(
            agent._create_task_for_agent(AgentType.GENERATION, goal)
        )

    assert task is not None
    assert task.agent_type == AgentType.GENERATION


if __name__ == "__main__":
    test_initial_weights_favour_ranking_over_generation()
    test_generation_pool_cap_blocks_new_generation()
    test_generation_below_cap_still_runs()
    print("✓ B16 tests passed")
