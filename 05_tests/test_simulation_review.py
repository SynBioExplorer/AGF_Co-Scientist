"""Unit tests for B6: SIMULATION review type implemented + scheduled.

Bug (CONFIRMED): ``ReviewType.SIMULATION`` existed in the schema enum but
the dispatch in reflection.py:417-434 had no branch for it — it silently
fell through to ``_create_initial_review_prompt``. And the supervisor never
scheduled it anywhere, so the bug was latent.

Fix:
  (a) Explicit dispatch — SIMULATION routes to a new
      ``_create_simulation_review_prompt``; unknown types now raise.
  (b) Schedule SIMULATION reviews in the REFLECTION branch of
      ``_create_task_for_agent`` for top hypotheses with a passing FULL
      review and no existing SIMULATION review.
"""

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import (  # noqa: E402
    GenerationMethod,
    Hypothesis,
    ReviewType,
)


def _hyp() -> Hypothesis:
    return Hypothesis(
        id="h1",
        research_goal_id="g1",
        title="t",
        summary="s",
        hypothesis_statement="The cell expresses receptor X.",
        rationale="r",
        mechanism="receptor X binds ligand Y, triggering pathway Z",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
    )


def test_simulation_prompt_helper_exists_and_mentions_simulation_fields():
    """B6(a) — _create_simulation_review_prompt produces a SIMULATION prompt
    that asks for simulation_steps and potential_failures."""
    with patch("src.agents.reflection.get_llm_client", return_value=MagicMock()):
        from src.agents.reflection import ReflectionAgent

        agent = ReflectionAgent()
        prompt = agent._create_simulation_review_prompt(_hyp())

    assert "simulation_steps" in prompt
    assert "potential_failures" in prompt
    # Step-by-step framing should be present.
    assert "step by step" in prompt.lower() or "step-by-step" in prompt.lower()


def test_dispatch_explicit_branches_and_raises_on_unknown():
    """B6(a) — reflection source has an explicit elif for SIMULATION and
    raises on unknown types instead of silently degrading."""
    import src.agents.reflection as ref_mod
    src = inspect.getsource(ref_mod)

    assert "elif review_type == ReviewType.SIMULATION" in src, (
        "B6 regression: SIMULATION dispatch branch missing."
    )
    assert "elif review_type == ReviewType.INITIAL" in src, (
        "B6 regression: INITIAL should be explicit, not catch-all."
    )
    assert "unknown review_type" in src, (
        "B6 regression: dispatch should raise on unknown review types."
    )


def test_review_construction_populates_simulation_fields():
    """B6(a) — Review() call propagates simulation_steps and
    potential_failures from the LLM response data."""
    import src.agents.reflection as ref_mod
    src = inspect.getsource(ref_mod)

    assert 'simulation_steps=data.get("simulation_steps", [])' in src
    assert 'potential_failures=data.get("potential_failures", [])' in src


def test_supervisor_schedules_simulation_reviews():
    """B6(b) — REFLECTION branch of _create_task_for_agent enqueues a
    SIMULATION review for top hypotheses with passing FULL + no SIMULATION."""
    import src.agents.supervisor as sup_mod
    src = inspect.getsource(sup_mod)

    assert '"simulation_review"' in src, (
        "B6 regression: supervisor doesn't schedule simulation_review tasks."
    )
    assert "ReviewType.SIMULATION.value" in src


if __name__ == "__main__":
    test_simulation_prompt_helper_exists_and_mentions_simulation_fields()
    test_dispatch_explicit_branches_and_raises_on_unknown()
    test_review_construction_populates_simulation_fields()
    test_supervisor_schedules_simulation_reviews()
    print("✓ B6 tests passed")
