"""Unit test for B13: system_statistics.agent_weights must reflect the
supervisor's LIVE weights, not a hardcoded default dict.

Bug (CONFIRMED): statistics.compute_statistics() hardcoded
{GENERATION: 0.4, REFLECTION: 0.2, RANKING: 0.2, EVOLUTION: 0.1,
PROXIMITY: 0.05, META_REVIEW: 0.05} — disagreeing with
_initialize_weights and omitting OBSERVATION_REVIEW entirely. The run
JSON therefore could not show whether dynamic weighting did anything.

Fix: accept ``agent_weights`` kwarg; serialize whatever the supervisor
passes (its live dict).
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import AgentType  # noqa: E402
from src.supervisor.statistics import SupervisorStatistics  # noqa: E402


def _mock_storage():
    s = MagicMock()
    s.get_hypotheses_by_goal = AsyncMock(return_value=[])
    s.get_match_count = AsyncMock(return_value=0)
    s.get_top_hypotheses = AsyncMock(return_value=[])
    s.get_all_reviews = AsyncMock(return_value=[])
    return s


def test_compute_statistics_reports_live_supervisor_weights():
    """B13 — passing the supervisor's live weights dict makes them appear
    verbatim in SystemStatistics.agent_weights (serialized to enum .value)."""
    live_weights = {
        AgentType.GENERATION: 0.15,
        AgentType.REFLECTION: 0.25,
        AgentType.RANKING: 0.30,
        AgentType.EVOLUTION: 0.13,
        AgentType.OBSERVATION_REVIEW: 0.08,
        AgentType.PROXIMITY: 0.05,
        AgentType.META_REVIEW: 0.04,
    }

    stats_engine = SupervisorStatistics(_mock_storage())
    stats = asyncio.run(
        stats_engine.compute_statistics("goal_001", agent_weights=live_weights)
    )

    assert stats.agent_weights == {
        AgentType.GENERATION.value: 0.15,
        AgentType.REFLECTION.value: 0.25,
        AgentType.RANKING.value: 0.30,
        AgentType.EVOLUTION.value: 0.13,
        AgentType.OBSERVATION_REVIEW.value: 0.08,
        AgentType.PROXIMITY.value: 0.05,
        AgentType.META_REVIEW.value: 0.04,
    }, "B13 regression: reported weights diverged from live weights."

    # The previously-missing key now appears.
    assert AgentType.OBSERVATION_REVIEW.value in stats.agent_weights


def test_compute_statistics_omits_weights_when_not_supplied():
    """Legacy callers pass no weights → empty dict (better than lying)."""
    stats_engine = SupervisorStatistics(_mock_storage())
    stats = asyncio.run(stats_engine.compute_statistics("goal_001"))

    assert stats.agent_weights == {}


if __name__ == "__main__":
    test_compute_statistics_reports_live_supervisor_weights()
    test_compute_statistics_omits_weights_when_not_supplied()
    print("✓ B13 tests passed")
