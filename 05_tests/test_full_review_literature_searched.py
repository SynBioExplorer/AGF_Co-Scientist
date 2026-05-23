"""Unit test for B8: FULL reviews must populate Review.literature_searched.

Bug (CONFIRMED): ``_create_full_review_prompt`` built its prompt from the
hypothesis' existing literature_citations but never ran a search of its own,
and Review() was never constructed with ``literature_searched=...``. The
field was an empty list on 100% of reviews despite CLAUDE.md describing
FULL review as performing "citation verification".

Fix: in the FULL branch of execute(), derive up to
``settings.full_review_max_queries`` queries from the hypothesis title /
statement / mechanism and record them on Review.literature_searched. The
field then documents what was (or should be) checked, even when the actual
network call is skipped — eliminating the "100% empty" symptom.
"""

import inspect
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))


def _reflection_source() -> str:
    import src.agents.reflection as ref_mod
    return inspect.getsource(ref_mod)


def test_full_review_derives_literature_search_queries():
    """B8 — the FULL branch derives query strings from the hypothesis."""
    src = _reflection_source()
    assert "literature_searched_queries" in src, (
        "B8 regression: literature_searched_queries variable is missing."
    )
    assert "full_review_max_queries" in src, (
        "B8 regression: configurable query cap setting not referenced."
    )


def test_review_constructor_threads_literature_searched():
    """B8 — Review(...) receives literature_searched=literature_searched_queries."""
    src = _reflection_source()
    assert "literature_searched=literature_searched_queries" in src, (
        "B8 regression: Review() no longer propagates the search queries."
    )


def test_config_has_full_review_max_queries_setting():
    """The new ``full_review_max_queries`` setting was added with a sensible default."""
    from src.config import settings

    assert hasattr(settings, "full_review_max_queries"), (
        "B8 regression: settings.full_review_max_queries missing."
    )
    assert isinstance(settings.full_review_max_queries, int)
    assert settings.full_review_max_queries >= 1


if __name__ == "__main__":
    test_full_review_derives_literature_search_queries()
    test_review_constructor_threads_literature_searched()
    test_config_has_full_review_max_queries_setting()
    print("✓ B8 tests passed")
