"""Unit tests for B3: time-aware drain phase.

Before this fix, the termination guard (supervisor.py:1333-1358) correctly
blocks termination whenever any hypothesis has zero matches, but because
B2 (evolved excluded) + B16 (generation outpaces ranking) made the pool
uncoverable, the guard was never satisfiable and runs only ended via
max_iterations or external kill.

Fix: in _execute_iteration, once elapsed > drain_phase_start_fraction *
max_execution_time_seconds, switch to a RANKING-only schedule with all 12
task slots so unmatched hypotheses get covered quickly. Cap at
drain_max_iterations to prevent stalls.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import AgentType, ResearchGoal  # noqa: E402


def _make_supervisor(elapsed_seconds: float, max_seconds: float = 1000.0):
    """Build a SupervisorAgent in a drain-aware state.

    elapsed_seconds — how long ago the workflow 'started'.
    max_seconds     — the time budget (drain triggers above 85%).
    """
    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):
        from src.agents.supervisor import SupervisorAgent

        mock_storage = MagicMock()
        mock_storage.get_hypotheses_by_goal = AsyncMock(return_value=[])
        mock_storage.get_all_reviews = AsyncMock(return_value=[])
        mock_storage.get_all_matches = AsyncMock(return_value=[])
        mock_storage.get_proximity_graph = AsyncMock(return_value=None)

        agent = SupervisorAgent(storage=mock_storage)
        agent._workflow_started_at = datetime.now() - timedelta(seconds=elapsed_seconds)
        agent._max_execution_time_seconds = max_seconds
        agent._drain_iterations = 0
        agent.iteration = 5
        # Stub task creation so we just observe what agent types get scheduled.
        agent._create_task_for_agent = AsyncMock(return_value=None)
        # Skip the post-phase full-review queueing (it touches storage methods
        # not relevant to drain behavior).
        agent._queue_full_reviews_for_top_initial = AsyncMock(return_value=None)
        return agent


def test_drain_activates_above_threshold_and_schedules_only_ranking():
    """Above the 85% threshold, only RANKING is scheduled."""
    # 900s elapsed / 1000s budget = 0.90 → in drain.
    agent = _make_supervisor(elapsed_seconds=900.0, max_seconds=1000.0)
    goal = ResearchGoal(id="goal_001", description="test goal")

    asyncio.run(agent._execute_iteration(goal))

    # Every _create_task_for_agent call must be RANKING.
    called_agent_types = {
        call.args[0] for call in agent._create_task_for_agent.call_args_list
    }
    assert called_agent_types == {AgentType.RANKING}, (
        f"B3 regression: drain should schedule only RANKING; got {called_agent_types}"
    )
    # And drain_iterations incremented.
    assert agent._drain_iterations == 1


def test_below_threshold_schedules_normal_phases():
    """Below the 85% threshold, drain is NOT active."""
    # 100s elapsed / 1000s budget = 0.10 → no drain.
    agent = _make_supervisor(elapsed_seconds=100.0, max_seconds=1000.0)
    goal = ResearchGoal(id="goal_001", description="test goal")
    # Avoid proximity-graph storage call below the drain branch.
    agent.storage.get_hypotheses_by_goal = AsyncMock(return_value=[])

    asyncio.run(agent._execute_iteration(goal))

    called_agent_types = {
        call.args[0] for call in agent._create_task_for_agent.call_args_list
    }
    # Should request multiple agent types (at minimum GENERATION + RANKING).
    assert AgentType.GENERATION in called_agent_types, (
        f"Normal phases should include GENERATION; got {called_agent_types}"
    )
    assert AgentType.RANKING in called_agent_types
    # Drain iterations did NOT advance.
    assert agent._drain_iterations == 0


def test_drain_cap_returns_early_after_max_iterations():
    """Once drain_iterations exceeds the cap, _execute_iteration returns early
    without scheduling anything."""
    from src.config import settings

    agent = _make_supervisor(elapsed_seconds=900.0, max_seconds=1000.0)
    # Simulate having already used all drain iterations.
    agent._drain_iterations = settings.drain_max_iterations
    goal = ResearchGoal(id="goal_001", description="test goal")

    asyncio.run(agent._execute_iteration(goal))

    # Nothing should have been scheduled — early return.
    assert agent._create_task_for_agent.call_count == 0, (
        f"B3 regression: drain cap exceeded should skip scheduling; "
        f"got {agent._create_task_for_agent.call_count} calls"
    )


if __name__ == "__main__":
    test_drain_activates_above_threshold_and_schedules_only_ranking()
    test_below_threshold_schedules_normal_phases()
    test_drain_cap_returns_early_after_max_iterations()
    print("✓ B3 drain tests passed")
