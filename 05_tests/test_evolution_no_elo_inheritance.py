"""Unit test for B1: Evolution must not inherit parent's Elo rating.

Per the Google paper ("each new hypothesis must also compete in the tournament"),
evolved hypotheses must enter at the schema default (1200.0) and earn their
rating through match outcomes. The bug at evolution.py:184 (CONFIRMED) copies the
parent's Elo onto every evolved child, poisoning the leaderboard with unearned
ratings.

This test asserts the evolved hypothesis starts at the schema default. With the
unfixed code it fails (evolved.elo_rating == parent.elo_rating); with the fix
(delete the elo_rating= kwarg in _parse_evolution_response) it passes because
the default at schemas.py:210-212 applies.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Match the import pattern used by 05_tests/test_supervisor_time_limit_unit.py,
# plus 04_Scripts/ for `cost_tracker` (imported transitively by src.llm.google).
_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import (  # noqa: E402
    EvolutionStrategy,
    GenerationMethod,
    Hypothesis,
)

# Pre-import the module so that mock.patch's dotted-path lookup can resolve
# `src.agents.evolution.get_llm_client` (without this, `mock.patch` calls
# `getattr(src, 'agents')` before the submodule has been loaded).
import src.agents.evolution as evolution_mod  # noqa: E402
from src.agents.evolution import EvolutionAgent  # noqa: E402


def _make_parent_hypothesis(elo: float = 1500.0) -> Hypothesis:
    """Build a minimal valid parent hypothesis with a non-default Elo."""
    return Hypothesis(
        id="hyp_parent_001",
        research_goal_id="goal_001",
        title="Parent hypothesis title",
        summary="Parent summary text",
        hypothesis_statement="Parent statement that motivates evolution.",
        rationale="Parent rationale.",
        mechanism="Parent mechanism.",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=elo,
    )


def _evolution_response_json() -> str:
    """A well-formed evolution response. Note: never contains an elo_rating field
    (the LLM prompt does not request one)."""
    return json.dumps({
        "title": "Evolved hypothesis title",
        "statement": "Evolved statement addressing feasibility concerns.",
        "summary": "Evolved summary",
        "rationale": "Refined rationale.",
        "mechanism": "Refined mechanism.",
        "experimental_protocol": {
            "objective": "Test the evolved hypothesis",
            "methodology": "Standard assay",
            "controls": ["positive control"],
            "expected_outcomes": ["improved feasibility"],
            "success_criteria": "p < 0.05",
        },
        "citations": [],
        "evolution_rationale": "Tightened the proposed mechanism for feasibility.",
    })


def test_evolved_hypothesis_does_not_inherit_parent_elo():
    """The keystone (B1) — evolved hypotheses start at schema default 1200.0."""
    with patch.object(evolution_mod, "get_llm_client", return_value=MagicMock()):
        agent = EvolutionAgent()

    parent = _make_parent_hypothesis(elo=1500.0)
    response = _evolution_response_json()

    evolved = agent._parse_evolution_response(
        response, parent, EvolutionStrategy.FEASIBILITY
    )

    # Primary assertion: evolved hypotheses must NOT inherit the parent's Elo.
    # Schema default at 03_architecture/schemas.py:210-212 is 1200.0.
    assert evolved.elo_rating == 1200.0, (
        f"B1 regression: evolved hypothesis got elo_rating={evolved.elo_rating} "
        f"(parent was {parent.elo_rating}); expected schema default 1200.0."
    )

    # Sanity: lineage and generation method are preserved.
    assert evolved.parent_hypothesis_ids == [parent.id]
    assert evolved.generation_method == parent.generation_method


if __name__ == "__main__":
    test_evolved_hypothesis_does_not_inherit_parent_elo()
    print("✓ B1 test passed: evolved hypotheses do not inherit parent Elo")
