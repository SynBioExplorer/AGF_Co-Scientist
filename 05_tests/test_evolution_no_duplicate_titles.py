"""Unit tests for B9: evolved hypotheses must not silently inherit the
parent's title.

Bug: ``title=data.get("title", hypothesis.title)`` at evolution.py:172 fell
back to the parent's title when the LLM omitted ``title``. Combined with B1
(now fixed) this produced exact-duplicate leaderboard entries (R5 had 4).

Fix: synthesize ``f"{parent_title} [evolved: {strategy}]"`` when the title
is missing, equal to the parent's, or already present in ``existing_titles``
(threaded from the supervisor). On further collision, append ``#2``, ``#3`` …
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import (  # noqa: E402
    EvolutionStrategy,
    GenerationMethod,
    Hypothesis,
)

import src.agents.evolution as evolution_mod  # noqa: E402
from src.agents.evolution import EvolutionAgent  # noqa: E402


def _parent(elo: float = 1500.0, title: str = "Parent hypothesis") -> Hypothesis:
    return Hypothesis(
        id="hyp_parent",
        research_goal_id="goal_001",
        title=title,
        summary="s",
        hypothesis_statement="s",
        rationale="r",
        mechanism="m",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=elo,
    )


def _evolution_response(title=None) -> str:
    body = {
        "statement": "Evolved statement.",
        "summary": "Summary",
        "rationale": "r",
        "mechanism": "m",
        "experimental_protocol": {
            "objective": "o",
            "methodology": "m",
            "controls": ["c"],
            "expected_outcomes": ["o"],
            "success_criteria": "ok",
        },
        "citations": [],
    }
    if title is not None:
        body["title"] = title
    return json.dumps(body)


def _make_agent() -> EvolutionAgent:
    with patch("src.agents.evolution.get_llm_client", return_value=MagicMock()):
        return EvolutionAgent()


def test_missing_title_is_synthesized_not_inherited():
    """LLM omits title → synthetic title with [evolved: <strategy>] suffix."""
    agent = _make_agent()
    parent = _parent(title="Parent A")
    response = _evolution_response(title=None)

    evolved = agent._parse_evolution_response(
        response, parent, EvolutionStrategy.FEASIBILITY
    )

    assert evolved.title != parent.title, (
        f"B9 regression: evolved silently inherited parent's title '{parent.title}'."
    )
    assert "[evolved: feasibility]" in evolved.title


def test_parent_title_match_is_synthesized():
    """LLM returns the parent's title verbatim → synthesize instead."""
    agent = _make_agent()
    parent = _parent(title="Parent A")
    response = _evolution_response(title="Parent A")  # collision

    evolved = agent._parse_evolution_response(
        response, parent, EvolutionStrategy.COHERENCE
    )

    assert evolved.title != "Parent A"
    assert "[evolved: coherence]" in evolved.title


def test_existing_title_collision_appends_suffix():
    """Synthesized title that's already in existing_titles → '#2', '#3' …"""
    agent = _make_agent()
    parent = _parent(title="Parent B")
    response = _evolution_response(title=None)
    # The synthetic title is already in the pool.
    existing = {"Parent B [evolved: feasibility]"}

    evolved = agent._parse_evolution_response(
        response, parent, EvolutionStrategy.FEASIBILITY, existing_titles=existing
    )

    assert evolved.title == "Parent B [evolved: feasibility] #2"


def test_valid_distinct_title_is_kept():
    """LLM returns a unique title → use it unchanged."""
    agent = _make_agent()
    parent = _parent(title="Parent C")
    response = _evolution_response(title="A genuinely different idea")

    evolved = agent._parse_evolution_response(
        response, parent, EvolutionStrategy.FEASIBILITY
    )

    assert evolved.title == "A genuinely different idea"


if __name__ == "__main__":
    test_missing_title_is_synthesized_not_inherited()
    test_parent_title_match_is_synthesized()
    test_existing_title_collision_appends_suffix()
    test_valid_distinct_title_is_kept()
    print("✓ B9 tests passed")
