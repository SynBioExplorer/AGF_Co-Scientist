"""Unit tests for B4: get_top_hypotheses must

(a) support a ``require_reviews: bool = False`` filter that, when True, restricts
    the result to hypotheses with at least one Review row; and
(b) (bonus, missed by the report) ACTUALLY sort by ``elo_rating`` descending in
    the memory/sqlite/async_adapter backends — currently they return insertion
    order and silently mis-order the leaderboard whenever those backends are
    used in tests / dev.

Postgres already sorts via SQL ``ORDER BY elo_rating DESC`` (postgres.py:500-503);
its require_reviews branch is verified by inspection (cannot run unit tests
against a live database here).
"""

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

from schemas import (  # noqa: E402
    GenerationMethod,
    Hypothesis,
    Review,
    ReviewType,
)
from src.storage.async_adapter import AsyncStorageAdapter  # noqa: E402


def _hyp(hid: str, elo: float) -> Hypothesis:
    return Hypothesis(
        id=hid,
        research_goal_id="goal_001",
        title=hid,
        summary="s",
        hypothesis_statement="s",
        rationale="r",
        mechanism="m",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=elo,
    )


def _rev(rid: str, hyp_id: str) -> Review:
    return Review(
        id=rid,
        hypothesis_id=hyp_id,
        review_type=ReviewType.INITIAL,
        passed=True,
        rationale="ok",
    )


def test_get_top_hypotheses_sorts_by_elo_descending():
    """Bonus B4 fix: in-memory backends now sort by Elo desc instead of
    returning insertion order."""
    async def _run():
        storage = AsyncStorageAdapter()
        # Insert deliberately out of Elo order.
        await storage.add_hypothesis(_hyp("a", 1200.0))
        await storage.add_hypothesis(_hyp("b", 1700.0))
        await storage.add_hypothesis(_hyp("c", 1500.0))

        top = await storage.get_top_hypotheses(n=10, goal_id="goal_001")
        elos = [h.elo_rating for h in top]
        assert elos == sorted(elos, reverse=True), (
            f"B4-bonus regression: get_top_hypotheses not sorted by Elo desc; "
            f"got {elos}"
        )
        # First element should be the 1700-Elo hyp.
        assert top[0].id == "b"

    asyncio.run(_run())


def test_get_top_hypotheses_require_reviews_filters_unreviewed():
    """B4 — require_reviews=True restricts to hypotheses with ≥1 review,
    keeping unreviewed Elo-1200 evolved newcomers out of the leaderboard."""
    async def _run():
        storage = AsyncStorageAdapter()
        await storage.add_hypothesis(_hyp("a", 1700.0))  # unreviewed
        await storage.add_hypothesis(_hyp("b", 1500.0))  # reviewed
        await storage.add_hypothesis(_hyp("c", 1200.0))  # reviewed
        await storage.add_review(_rev("r1", "b"))
        await storage.add_review(_rev("r2", "c"))

        top = await storage.get_top_hypotheses(
            n=10, goal_id="goal_001", require_reviews=True
        )
        ids = [h.id for h in top]
        assert "a" not in ids, (
            "B4 regression: unreviewed hyp 'a' leaked into the top list."
        )
        assert set(ids) == {"b", "c"}, f"Unexpected ids: {ids}"
        # Sort order: 1500 (b) before 1200 (c).
        assert top[0].id == "b"


    asyncio.run(_run())


if __name__ == "__main__":
    test_get_top_hypotheses_sorts_by_elo_descending()
    test_get_top_hypotheses_require_reviews_filters_unreviewed()
    print("✓ B4 tests passed")
