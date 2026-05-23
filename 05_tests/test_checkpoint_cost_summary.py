"""Unit test for B14: cost summary must be persisted into the run JSON.

Before this fix, the supervisor only called ``cost_tracker.print_summary()``
(console output, not persisted), and the cost data was lost after the run.
The fix adds an optional ``cost_summary`` parameter to ``_save_checkpoint``
that lands in ``ContextMemory.cost_summary`` (new schema field).

B11/B12 (final-iteration stats + iteration_count consistency) are addressed
by the same finalization block; they require an end-to-end run to verify and
are covered by the live verification run (Tier 2/3 verification step).
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import (  # noqa: E402
    AgentType,
    ContextMemory,
    SystemStatistics,
)


def _make_stats() -> SystemStatistics:
    return SystemStatistics(
        research_goal_id="goal_001",
        total_hypotheses=3,
        hypotheses_pending_review=1,
        hypotheses_in_tournament=2,
        hypotheses_archived=0,
        tournament_matches_completed=4,
        tournament_convergence_score=0.5,
        generation_success_rate=0.7,
        evolution_improvement_rate=0.2,
        method_effectiveness={},
        agent_weights={AgentType.GENERATION.value: 0.25},
        computed_at=datetime.now(),
    )


def test_save_checkpoint_persists_cost_summary():
    """B14 — _save_checkpoint must propagate cost_summary into ContextMemory."""
    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):

        from src.agents.supervisor import SupervisorAgent

        mock_storage = MagicMock()
        mock_storage.get_hypotheses_by_goal = AsyncMock(return_value=[])
        mock_storage.get_tournament_state = AsyncMock(return_value=None)
        mock_storage.get_proximity_graph = AsyncMock(return_value=None)
        mock_storage.get_meta_review = AsyncMock(return_value=None)
        mock_storage.get_research_overview = AsyncMock(return_value=None)
        mock_storage.save_checkpoint = AsyncMock()

        agent = SupervisorAgent(storage=mock_storage)
        agent.iteration = 5  # simulate post-loop state

        cost_summary = {
            "total_cost_usd": 1.23,
            "total_tokens": 4567,
            "per_agent": {"generation": 0.45, "reflection": 0.31},
        }

        asyncio.run(agent._save_checkpoint(
            "goal_001", _make_stats(), cost_summary=cost_summary,
        ))

    # Assert save_checkpoint was called once with a ContextMemory carrying
    # the cost_summary intact.
    assert mock_storage.save_checkpoint.call_count == 1
    saved = mock_storage.save_checkpoint.call_args.args[0]
    assert isinstance(saved, ContextMemory)
    assert saved.cost_summary == cost_summary, (
        f"B14 regression: cost_summary not persisted; saved={saved.cost_summary}"
    )
    # B12 sanity: iteration_count reflects the supervisor's current iteration.
    assert saved.iteration_count == 5


def test_save_checkpoint_default_cost_summary_is_none():
    """Backward compatibility — per-iteration saves omit cost_summary."""
    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):

        from src.agents.supervisor import SupervisorAgent

        mock_storage = MagicMock()
        mock_storage.get_hypotheses_by_goal = AsyncMock(return_value=[])
        mock_storage.get_tournament_state = AsyncMock(return_value=None)
        mock_storage.get_proximity_graph = AsyncMock(return_value=None)
        mock_storage.get_meta_review = AsyncMock(return_value=None)
        mock_storage.get_research_overview = AsyncMock(return_value=None)
        mock_storage.save_checkpoint = AsyncMock()

        agent = SupervisorAgent(storage=mock_storage)
        asyncio.run(agent._save_checkpoint("goal_001", _make_stats()))

    saved = mock_storage.save_checkpoint.call_args.args[0]
    assert saved.cost_summary is None


if __name__ == "__main__":
    test_save_checkpoint_persists_cost_summary()
    test_save_checkpoint_default_cost_summary_is_none()
    print("✓ B14 tests passed")
