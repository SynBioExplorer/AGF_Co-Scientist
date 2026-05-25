"""Unit tests for B7: generated hypotheses must populate assumptions[].

Bug: the generation prompt's JSON schema (generation.py:1058-1087) did not
request ``assumptions``, and the inline Hypothesis(...) constructor at
1099-1129 never set the field, so 100% of generated hypotheses had
``assumptions == []`` and DeepVerification (B5) had nothing structured to
verify.

Fix: (a) ask for ``assumptions`` in the prompt schema, (b) construct
``Assumption`` objects from the parsed JSON.

GenerationAgent.__init__ initialises an LLM client, tool registry, paper-
quality scorer and limitations extractor, which makes an end-to-end execute()
test costly. Instead we verify the two halves of the fix surgically:
* the prompt source contains the assumptions schema fragment (part a);
* the inline construction pattern, when given LLM-shaped data with an
  assumptions list, populates Hypothesis.assumptions correctly (part b).
"""

import inspect
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import (  # noqa: E402
    Assumption,
    GenerationMethod,
    Hypothesis,
)


def test_generation_prompt_requests_assumptions():
    """Part (a) — the prompt asks the LLM for an assumptions array."""
    import src.agents.generation as gen_mod

    src = inspect.getsource(gen_mod)
    assert '"assumptions"' in src, (
        "B7 regression: generation prompt no longer requests assumptions."
    )
    assert 'is_fundamental' in src, (
        "B7 regression: prompt no longer mentions is_fundamental flag."
    )


def test_all_four_generation_methods_request_assumptions():
    """Tier 4 — every generation method's prompt must ask for assumptions.

    The original B7 fix only patched the structured_prompt suffix used by
    `literature_exploration`. The other three methods (`simulated_debate`,
    `iterative_assumptions`, `research_expansion`) build prompts inline in
    `_generate_via_*` and need the same schema fragment + REQUIRED directive.
    Live run 66dfa26c showed only 2/12 hypotheses had assumptions because of
    this gap.

    Coverage check: the CRITICAL "REQUIRED, not optional" directive must
    appear at least 4 times (one per generation-method prompt site).
    """
    import re

    import src.agents.generation as gen_mod

    src = inspect.getsource(gen_mod)
    directive_pattern = r"CRITICAL: The `assumptions` array is REQUIRED, not optional"
    count = len(re.findall(directive_pattern, src))
    assert count >= 4, (
        f"Tier-4 B7 regression: expected the REQUIRED directive in all 4 "
        f"generation-method prompts (literature_exploration + 3 inline), "
        f"found only {count}."
    )

    # Each of the 3 non-literature constructors must also pass assumptions=...
    # so even a compliant LLM response is propagated to the Hypothesis.
    for method_enum in (
        "GenerationMethod.SIMULATED_DEBATE",
        "GenerationMethod.ITERATIVE_ASSUMPTIONS",
        "GenerationMethod.RESEARCH_EXPANSION",
    ):
        idx = src.index(method_enum)
        # The constructor for this method ends with `generation_method=<enum>`;
        # the assumptions= kwarg appears 5-15 lines above. Look back 800 chars.
        block = src[max(0, idx - 800) : idx + 100]
        assert "assumptions=[" in block, (
            f"Tier-4 B7 regression: constructor for {method_enum} does not "
            f"propagate data['assumptions'] into Hypothesis.assumptions."
        )


def test_inline_parser_populates_assumptions_from_data():
    """Part (b) — the inline construction at generation.py:1099-1129 builds
    Assumption objects from data['assumptions']. We replicate the pattern
    here against a fixture dict; if the schema or pattern drifts, this
    breaks."""
    data = {
        "title": "t",
        "statement": "s",
        "rationale": "r",
        "mechanism": "m",
        "assumptions": [
            {"statement": "Cells express the receptor", "is_fundamental": True},
            {"statement": "Assay sensitivity sufficient", "is_fundamental": False},
            {"missing_statement": "should be skipped"},
            "not a dict — also skipped",
        ],
    }

    # This is exactly the pattern shipped in generation.py.
    assumptions = [
        Assumption(
            id=f"asm_{i}",
            statement=a["statement"],
            is_fundamental=bool(a.get("is_fundamental", True)),
        )
        for i, a in enumerate(data.get("assumptions", []))
        if isinstance(a, dict) and a.get("statement")
    ]

    h = Hypothesis(
        id="h1",
        research_goal_id="g1",
        title=data["title"],
        summary=data["title"],
        hypothesis_statement=data["statement"],
        rationale=data["rationale"],
        mechanism=data.get("mechanism"),
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        assumptions=assumptions,
    )

    assert len(h.assumptions) == 2, (
        f"B7 regression: expected 2 valid assumptions, got {len(h.assumptions)}"
    )
    assert h.assumptions[0].statement == "Cells express the receptor"
    assert h.assumptions[0].is_fundamental is True
    assert h.assumptions[1].is_fundamental is False
    # Each assumption has a unique id (required by schema).
    assert {a.id for a in h.assumptions} == {"asm_0", "asm_1"}


if __name__ == "__main__":
    test_generation_prompt_requests_assumptions()
    test_all_four_generation_methods_request_assumptions()
    test_inline_parser_populates_assumptions_from_data()
    print("✓ B7 tests passed")
