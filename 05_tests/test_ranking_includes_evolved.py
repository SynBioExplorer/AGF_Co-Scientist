"""Unit test for B2: Evolved hypotheses must be tournament-eligible.

Bug at src/agents/supervisor.py:776-779 (CONFIRMED): the RANKING-branch
tournament pool filters to hypotheses with at least one Review row, deliberately
excluding unreviewed Elo-1200 defaults. But evolved hypotheses are generated
late and rarely reviewed before run end, so 0/17-20 of them per run enter any
match. Combined with B1 (now fixed), the leaderboard becomes unrepresentative.

Fix: broaden the predicate to admit hypotheses with non-empty
parent_hypothesis_ids — they always carry lineage, and with B1 they enter at
1200 like any newcomer.
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
    Review,
    ReviewType,
)


def _make_hypothesis(hid: str, parent_ids=None) -> Hypothesis:
    return Hypothesis(
        id=hid,
        research_goal_id="goal_001",
        title=f"Hypothesis {hid}",
        summary="summary",
        hypothesis_statement="statement",
        rationale="rationale",
        mechanism="mechanism",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        parent_hypothesis_ids=parent_ids or [],
    )


def _make_review(rid: str, hyp_id: str) -> Review:
    return Review(
        id=rid,
        hypothesis_id=hyp_id,
        review_type=ReviewType.INITIAL,
        passed=True,
        rationale="passed",
    )


def test_evolved_hypothesis_enters_tournament_pool():
    """B2 — RANKING-branch pool must include evolved hypotheses with non-empty
    parent_hypothesis_ids, even when they have no reviews yet."""

    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):

        from src.agents.supervisor import SupervisorAgent

        # One reviewed parent + one evolved (unreviewed) child.
        parent = _make_hypothesis("hyp_parent", parent_ids=None)
        evolved = _make_hypothesis("hyp_evolved", parent_ids=["hyp_parent"])
        review = _make_review("rev_001", "hyp_parent")

        mock_storage = MagicMock()
        mock_storage.get_hypotheses_by_goal = AsyncMock(return_value=[parent, evolved])
        mock_storage.get_all_reviews = AsyncMock(return_value=[review])
        mock_storage.get_all_matches = AsyncMock(return_value=[])
        mock_storage.get_proximity_graph = AsyncMock(return_value=None)

        agent = SupervisorAgent(storage=mock_storage)
        goal = ResearchGoal(id="goal_001", description="test goal")

        task = asyncio.run(
            agent._create_task_for_agent(AgentType.RANKING, goal)
        )

    # With the fix, both parent (reviewed) and evolved (lineage) are in the pool
    # of size 2 → a tournament match task is created.
    # Without the fix, pool = {parent} only → len(reviewed) < 2 → task is None.
    assert task is not None, (
        "B2 regression: evolved hypothesis was filtered out, pool size < 2, "
        "no RANKING task created."
    )
    assert task.agent_type == AgentType.RANKING
    matched_ids = {
        task.parameters.get("hypothesis_a_id"),
        task.parameters.get("hypothesis_b_id"),
    }
    assert "hyp_evolved" in matched_ids, (
        f"B2 regression: evolved hypothesis not in match pair. "
        f"matched_ids={matched_ids}"
    )


if __name__ == "__main__":
    test_evolved_hypothesis_enters_tournament_pool()
    print("✓ B2 test passed: evolved hypotheses enter the tournament pool")
