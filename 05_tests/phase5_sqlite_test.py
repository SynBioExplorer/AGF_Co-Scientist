#!/usr/bin/env python3
"""Tests for the Phase A SQLite storage backend."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Set the data-dir override BEFORE importing anything that resolves it.
_TMP = tempfile.mkdtemp(prefix="agf_phase5_sqlite_")
os.environ["AGF_DATA_DIR"] = _TMP
os.environ.setdefault("GOOGLE_API_KEY", "dummy")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "03_architecture"))

from schemas import (  # noqa: E402
    AgentTask,
    AgentType,
    Citation,
    ExperimentalProtocol,
    GenerationMethod,
    Hypothesis,
    HypothesisStatus,
    ResearchGoal,
    Review,
    ReviewType,
    TournamentMatch,
)
from src.storage import create_storage  # noqa: E402
from src.storage.sqlite_store import SQLiteStorage  # noqa: E402
from src.utils.ids import (  # noqa: E402
    generate_hypothesis_id,
    generate_id,
    generate_match_id,
    generate_review_id,
)


def _goal() -> ResearchGoal:
    return ResearchGoal(
        id="goal_sqlite_test",
        description="Test goal for SQLite backend",
        constraints=["constraint a"],
        preferences=["pref a"],
    )


def _hypothesis(goal_id: str) -> Hypothesis:
    return Hypothesis(
        id=generate_hypothesis_id(),
        research_goal_id=goal_id,
        title="Test hypothesis",
        summary="A summary",
        hypothesis_statement="A claim",
        rationale="Because reasons",
        mechanism="Mechanism",
        experimental_protocol=ExperimentalProtocol(
            objective="o", methodology="m", expected_outcomes=["x"],
            controls=["c"], materials=["mat"], success_criteria="ok",
        ),
        literature_citations=[Citation(title="A", relevance="x")],
        status=HypothesisStatus.GENERATED,
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1234.0,
    )


def _review(hyp_id: str) -> Review:
    return Review(
        id=generate_review_id(),
        hypothesis_id=hyp_id,
        review_type=ReviewType.INITIAL,
        correctness_score=0.8,
        quality_score=0.7,
        novelty_score=0.6,
        testability_score=0.9,
        safety_score=0.95,
        strengths=["s"],
        weaknesses=["w"],
        suggestions=["q"],
        passed=True,
        rationale="r",
    )


class TestSQLiteStorage(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.tmp = Path(tempfile.mkdtemp(prefix="agf_phase5_sqlite_run_"))
        self.db_path = self.tmp / "coscientist.db"
        self.store = SQLiteStorage(db_path=self.db_path)
        self.loop.run_until_complete(self.store.connect())

    def tearDown(self):
        self.loop.run_until_complete(self.store.disconnect())
        self.loop.close()

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    # ------------------------------------------------------------------

    def test_factory_creates_sqlite(self):
        st = create_storage("sqlite", database_url=str(self.db_path))
        self.assertIsInstance(st, SQLiteStorage)

    def test_db_file_created(self):
        self.assertTrue(self.db_path.exists())

    def test_health(self):
        self.assertTrue(self._run(self.store.health_check()))

    def test_goal_crud(self):
        g = _goal()
        self._run(self.store.add_research_goal(g))
        loaded = self._run(self.store.get_research_goal(g.id))
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.description, g.description)

        g.description = "updated"
        self._run(self.store.update_research_goal(g))
        again = self._run(self.store.get_research_goal(g.id))
        self.assertEqual(again.description, "updated")

        all_goals = self._run(self.store.get_all_research_goals())
        self.assertEqual(len(all_goals), 1)

        self.assertTrue(self._run(self.store.delete_research_goal(g.id)))
        self.assertIsNone(self._run(self.store.get_research_goal(g.id)))

    def test_hypothesis_crud_and_ordering(self):
        g = _goal()
        self._run(self.store.add_research_goal(g))
        h_low = _hypothesis(g.id)
        h_low.elo_rating = 1000.0
        h_high = _hypothesis(g.id)
        h_high.elo_rating = 1800.0
        self._run(self.store.add_hypothesis(h_low))
        self._run(self.store.add_hypothesis(h_high))

        top = self._run(self.store.get_top_hypotheses(n=2))
        self.assertEqual(top[0].id, h_high.id)
        self.assertEqual(top[1].id, h_low.id)

        by_goal = self._run(self.store.get_hypotheses_by_goal(g.id))
        self.assertEqual(len(by_goal), 2)

        cnt = self._run(self.store.get_hypothesis_count(g.id))
        self.assertEqual(cnt, 2)

    def test_review_crud(self):
        g = _goal()
        self._run(self.store.add_research_goal(g))
        h = _hypothesis(g.id)
        self._run(self.store.add_hypothesis(h))

        r = _review(h.id)
        self._run(self.store.add_review(r))
        reviews = self._run(self.store.get_reviews_for_hypothesis(h.id))
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].id, r.id)

        all_reviews = self._run(self.store.get_all_reviews(goal_id=g.id))
        self.assertEqual(len(all_reviews), 1)

    def test_match_and_winrate(self):
        g = _goal()
        self._run(self.store.add_research_goal(g))
        h_a = _hypothesis(g.id)
        h_b = _hypothesis(g.id)
        self._run(self.store.add_hypothesis(h_a))
        self._run(self.store.add_hypothesis(h_b))

        m = TournamentMatch(
            id=generate_match_id(),
            hypothesis_a_id=h_a.id,
            hypothesis_b_id=h_b.id,
            winner_id=h_a.id,
            decision_rationale="A is better",
            comparison_criteria=["novelty"],
            elo_change_a=16.0,
            elo_change_b=-16.0,
        )
        self._run(self.store.add_match(m))
        self.assertEqual(self._run(self.store.get_match_count(g.id)), 1)
        wr = self._run(self.store.get_hypothesis_win_rate(h_a.id))
        self.assertEqual(wr, 1.0)

    def test_task_queue(self):
        t = AgentTask(
            id=generate_id("task"),
            agent_type=AgentType.GENERATION,
            task_type="generate_hypothesis",
            status="pending",
            priority=5,
            parameters={"foo": "bar"},
        )
        self._run(self.store.add_task(t))
        pending = self._run(self.store.get_pending_tasks(AgentType.GENERATION))
        self.assertEqual(len(pending), 1)
        claimed = self._run(self.store.claim_next_task(AgentType.GENERATION, "w1"))
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.status, "running")
        self.assertEqual(claimed.parameters.get("worker_id"), "w1")

        updated = self._run(self.store.update_task_status(t.id, "complete", {"ok": 1}))
        self.assertEqual(updated.status, "complete")
        self.assertEqual(updated.result, {"ok": 1})

    def test_clear_and_stats(self):
        g = _goal()
        self._run(self.store.add_research_goal(g))
        h = _hypothesis(g.id)
        self._run(self.store.add_hypothesis(h))
        stats = self._run(self.store.get_stats())
        self.assertEqual(stats["research_goals"], 1)
        self.assertEqual(stats["hypotheses"], 1)
        self._run(self.store.clear_all())
        stats2 = self._run(self.store.get_stats())
        self.assertEqual(stats2["research_goals"], 0)
        self.assertEqual(stats2["hypotheses"], 0)

    def test_cascade_delete(self):
        g = _goal()
        self._run(self.store.add_research_goal(g))
        h = _hypothesis(g.id)
        self._run(self.store.add_hypothesis(h))
        r = _review(h.id)
        self._run(self.store.add_review(r))
        self._run(self.store.delete_research_goal(g.id))
        self.assertIsNone(self._run(self.store.get_research_goal(g.id)))
        self.assertIsNone(self._run(self.store.get_hypothesis(h.id)))
        self.assertEqual(self._run(self.store.get_reviews_for_hypothesis(h.id)), [])

    def test_persistence_across_reconnect(self):
        g = _goal()
        self._run(self.store.add_research_goal(g))
        self._run(self.store.disconnect())
        new_store = SQLiteStorage(db_path=self.db_path)
        self._run(new_store.connect())
        try:
            self.assertIsNotNone(self._run(new_store.get_research_goal(g.id)))
        finally:
            self._run(new_store.disconnect())
        # Reconnect original so tearDown can run cleanly.
        self._run(self.store.connect())


if __name__ == "__main__":
    unittest.main()
