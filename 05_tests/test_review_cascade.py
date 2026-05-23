"""Unit tests for B5: deep_verification and observation reviews must fire.

DEEP_VERIFICATION bug (CONFIRMED): scheduling was gated on
``hyp.status == HypothesisStatus.FULL_REVIEW`` but the full-review result
handler advances status to IN_TOURNAMENT before the next supervisor pass,
so the gate was never satisfied. Fix: check the reviews directly (any
passing FULL review + no existing DEEP_VERIFICATION), status-independent.

OBSERVATION_REVIEW bug (CONFIRMED): single early-return per call meant
only 1 task per iteration regardless of pool size. Fix: queue up to
OBSERVATION_BATCH_CAP (3) per call via task_queue.
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
    HypothesisStatus,
    ResearchGoal,
    Review,
    ReviewType,
)


def _hyp(hid: str, status=HypothesisStatus.GENERATED) -> Hypothesis:
    return Hypothesis(
        id=hid,
        research_goal_id="goal_001",
        title=hid,
        summary="s",
        hypothesis_statement="s",
        rationale="r",
        mechanism="m",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        status=status,
    )


def _rev(rid: str, hyp_id: str, rtype: ReviewType, passed: bool = True) -> Review:
    return Review(
        id=rid,
        hypothesis_id=hyp_id,
        review_type=rtype,
        passed=passed,
        rationale="ok",
    )


def _make_supervisor_with_storage(mock_storage):
    with patch("src.agents.supervisor.get_llm_client", return_value=MagicMock()), \
         patch("src.agents.supervisor.get_tracker", return_value=MagicMock()), \
         patch("src.agents.supervisor.SafetyAgent", return_value=MagicMock()):
        from src.agents.supervisor import SupervisorAgent
        return SupervisorAgent(storage=mock_storage)


def test_deep_verification_fires_after_full_review_passes_even_when_status_advanced():
    """B5(a) — hypothesis with passing FULL review + IN_TOURNAMENT status
    (post-advance) should still get scheduled for DEEP_VERIFICATION."""

    hyp = _hyp("h1", status=HypothesisStatus.IN_TOURNAMENT)  # post-advance status
    full_review = _rev("r1", "h1", ReviewType.FULL, passed=True)

    mock_storage = MagicMock()
    # No hypotheses need initial review (so we fall through to deep-verification logic).
    mock_storage.get_hypotheses_needing_review = AsyncMock(return_value=[])
    # Top hypothesis (require_reviews=True still includes it because it has a Review).
    mock_storage.get_top_hypotheses = AsyncMock(return_value=[hyp])
    mock_storage.get_reviews_for_hypothesis = AsyncMock(return_value=[full_review])

    agent = _make_supervisor_with_storage(mock_storage)
    goal = ResearchGoal(id="goal_001", description="test")

    task = asyncio.run(
        agent._create_task_for_agent(AgentType.REFLECTION, goal)
    )

    assert task is not None, (
        "B5 regression: deep verification did not fire despite passing FULL review."
    )
    assert task.task_type == "deep_verification_review"
    assert task.parameters["review_type"] == ReviewType.DEEP_VERIFICATION.value
    assert task.parameters["hypothesis_id"] == "h1"


def test_reflection_skipped_if_all_review_types_done():
    """Already has DEEP_VERIFICATION *and* SIMULATION → no new REFLECTION
    task. (B6 added SIMULATION scheduling, so DEEP_VERIFICATION alone is
    no longer sufficient for an idle state.)"""
    hyp = _hyp("h1", status=HypothesisStatus.IN_TOURNAMENT)
    reviews = [
        _rev("r1", "h1", ReviewType.FULL, passed=True),
        _rev("r2", "h1", ReviewType.DEEP_VERIFICATION, passed=True),
        _rev("r3", "h1", ReviewType.SIMULATION, passed=True),
    ]
    mock_storage = MagicMock()
    mock_storage.get_hypotheses_needing_review = AsyncMock(return_value=[])
    mock_storage.get_top_hypotheses = AsyncMock(return_value=[hyp])
    mock_storage.get_reviews_for_hypothesis = AsyncMock(return_value=reviews)

    agent = _make_supervisor_with_storage(mock_storage)
    goal = ResearchGoal(id="goal_001", description="test")
    task = asyncio.run(agent._create_task_for_agent(AgentType.REFLECTION, goal))

    assert task is None


def test_observation_review_batches_multiple_per_call():
    """B5(b) — should queue up to 3 observation reviews per call (not just 1)."""
    eligible = [
        _hyp(f"h{i}", status=HypothesisStatus.IN_TOURNAMENT) for i in range(5)
    ]
    mock_storage = MagicMock()
    mock_storage.get_hypotheses_by_goal = AsyncMock(return_value=eligible)
    mock_storage.get_observation_review = AsyncMock(return_value=None)

    agent = _make_supervisor_with_storage(mock_storage)
    goal = ResearchGoal(id="goal_001", description="test")

    task = asyncio.run(
        agent._create_task_for_agent(AgentType.OBSERVATION_REVIEW, goal)
    )

    assert task is not None
    assert task.agent_type == AgentType.OBSERVATION_REVIEW
    # First task returned + 2 extra queued = 3 total scheduled (the cap).
    pending = agent.task_queue.get_pending_count(AgentType.OBSERVATION_REVIEW)
    # Excludes the returned `task` (the caller is the one that registers it).
    assert pending == 2, (
        f"B5 regression: expected 2 extra queued observation reviews "
        f"(cap=3, minus the returned one); got {pending}"
    )


if __name__ == "__main__":
    test_deep_verification_fires_after_full_review_passes_even_when_status_advanced()
    test_deep_verification_skipped_if_already_done()
    test_observation_review_batches_multiple_per_call()
    print("✓ B5 tests passed")
