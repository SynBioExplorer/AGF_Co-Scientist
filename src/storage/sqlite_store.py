"""SQLite storage backend.

Implements :class:`BaseStorage` using ``aiosqlite`` against a single file
DB stored under :func:`src.utils.paths.get_app_data_dir`. Designed for
zero-setup desktop use; not intended for high concurrency.

Storage strategy
----------------

We persist each Pydantic model as a JSON blob in a per-type table,
keyed by the model's ``id``. A handful of additional columns are
extracted to support common query paths (filter by ``research_goal_id``,
filter by status, order by ``elo_rating`` or ``created_at``).

Schema is created on first ``connect()`` -- no migrations.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import aiosqlite  # type: ignore
except ImportError:  # pragma: no cover
    aiosqlite = None  # type: ignore

import structlog

sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import (  # noqa: E402
    AgentTask,
    AgentType,
    ChatMessage,
    ContextMemory,
    Hypothesis,
    HypothesisCluster,
    HypothesisStatus,
    MetaReviewCritique,
    ObservationReviewScore,
    ProximityEdge,
    ProximityGraph,
    ResearchGoal,
    ResearchOverview,
    Review,
    ReviewType,
    ScientistFeedback,
    SystemStatistics,
    TournamentMatch,
    TournamentState,
)

from src.storage.base import BaseStorage

logger = structlog.get_logger()


def _dt_str(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _dumps(model: Any) -> str:
    """Serialize a Pydantic model to JSON."""
    return model.model_dump_json()


def _loads(raw: str, cls):
    return cls.model_validate_json(raw)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS research_goals (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS hypotheses (
    id TEXT PRIMARY KEY,
    research_goal_id TEXT,
    status TEXT,
    elo_rating REAL,
    created_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hyp_goal ON hypotheses(research_goal_id);
CREATE INDEX IF NOT EXISTS idx_hyp_elo ON hypotheses(elo_rating DESC);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    review_type TEXT,
    created_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rev_hyp ON reviews(hypothesis_id);

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    hypothesis_a_id TEXT,
    hypothesis_b_id TEXT,
    winner_id TEXT,
    created_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_match_a ON matches(hypothesis_a_id);
CREATE INDEX IF NOT EXISTS idx_match_b ON matches(hypothesis_b_id);

CREATE TABLE IF NOT EXISTS tournament_states (
    goal_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proximity_graphs (
    goal_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proximity_edges (
    goal_id TEXT,
    edge_index INTEGER,
    data TEXT NOT NULL,
    PRIMARY KEY (goal_id, edge_index)
);

CREATE TABLE IF NOT EXISTS meta_reviews (
    id TEXT PRIMARY KEY,
    goal_id TEXT,
    created_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meta_goal ON meta_reviews(goal_id);

CREATE TABLE IF NOT EXISTS research_overviews (
    goal_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    agent_type TEXT,
    status TEXT,
    priority INTEGER,
    created_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status, agent_type);

CREATE TABLE IF NOT EXISTS statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id TEXT,
    computed_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stats_goal ON statistics(goal_id);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id TEXT,
    updated_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chk_goal ON checkpoints(goal_id);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    hypothesis_id TEXT,
    created_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fb_hyp ON feedback(hypothesis_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id TEXT,
    created_at TEXT,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_goal ON chat_messages(goal_id);

CREATE TABLE IF NOT EXISTS observation_reviews (
    hypothesis_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""


class SQLiteStorage(BaseStorage):
    """Single-file SQLite implementation of :class:`BaseStorage`."""

    def __init__(self, db_path: Optional[str | Path] = None):
        if aiosqlite is None:
            raise RuntimeError(
                "aiosqlite is not installed. Run: pip install aiosqlite"
            )
        if db_path is None:
            from src.utils.paths import get_sqlite_db_path

            db_path = get_sqlite_db_path()
        self.db_path = str(db_path)
        self._db: Optional[aiosqlite.Connection] = None
        # In-memory fallback for chat goal-id resolution -- the ChatMessage
        # schema doesn't carry a goal_id, but we need to scope chats.
        self._connected = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        if self._connected:
            return
        # Ensure parent directory exists.
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        # Auto-create tables.
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        self._connected = True
        logger.info("SQLiteStorage connected", db_path=self.db_path)

    async def disconnect(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
        self._connected = False

    async def health_check(self) -> bool:
        if not self._db:
            return False
        try:
            await self._db.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _require(self) -> "aiosqlite.Connection":
        if not self._db:
            raise RuntimeError("SQLiteStorage not connected")
        return self._db

    # ------------------------------------------------------------------
    # Research Goals
    # ------------------------------------------------------------------

    async def add_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO research_goals (id, data, created_at) VALUES (?, ?, ?)",
            (goal.id, _dumps(goal), _dt_str(getattr(goal, "created_at", None))),
        )
        await db.commit()
        return goal

    async def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM research_goals WHERE id = ?", (goal_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return _loads(row["data"], ResearchGoal)

    async def get_all_research_goals(self) -> List[ResearchGoal]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM research_goals ORDER BY created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], ResearchGoal) for r in rows]

    async def update_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        return await self.add_research_goal(goal)

    async def delete_research_goal(self, goal_id: str) -> bool:
        db = self._require()
        async with db.execute(
            "SELECT id FROM research_goals WHERE id = ?", (goal_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False

        # Cascade: hypotheses, reviews, matches, etc.
        # Hypothesis IDs first so we can drop reviews / matches that touch them.
        async with db.execute(
            "SELECT id FROM hypotheses WHERE research_goal_id = ?", (goal_id,)
        ) as cur:
            hyp_ids = [r["id"] for r in await cur.fetchall()]

        await db.execute(
            "DELETE FROM hypotheses WHERE research_goal_id = ?", (goal_id,)
        )
        if hyp_ids:
            qs = ",".join("?" for _ in hyp_ids)
            await db.execute(
                f"DELETE FROM reviews WHERE hypothesis_id IN ({qs})", hyp_ids
            )
            await db.execute(
                f"DELETE FROM matches WHERE hypothesis_a_id IN ({qs}) "
                f"OR hypothesis_b_id IN ({qs})",
                hyp_ids + hyp_ids,
            )
            await db.execute(
                f"DELETE FROM observation_reviews WHERE hypothesis_id IN ({qs})",
                hyp_ids,
            )
            await db.execute(
                f"DELETE FROM feedback WHERE hypothesis_id IN ({qs})", hyp_ids
            )

        await db.execute("DELETE FROM tournament_states WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM proximity_graphs WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM proximity_edges WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM meta_reviews WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM research_overviews WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM statistics WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM checkpoints WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM chat_messages WHERE goal_id = ?", (goal_id,))
        await db.execute("DELETE FROM research_goals WHERE id = ?", (goal_id,))
        await db.commit()
        return True

    # ------------------------------------------------------------------
    # Hypotheses
    # ------------------------------------------------------------------

    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO hypotheses "
            "(id, research_goal_id, status, elo_rating, created_at, data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                hypothesis.id,
                hypothesis.research_goal_id,
                getattr(hypothesis.status, "value", str(hypothesis.status)),
                float(hypothesis.elo_rating or 1200.0),
                _dt_str(getattr(hypothesis, "created_at", None)),
                _dumps(hypothesis),
            ),
        )
        await db.commit()
        return hypothesis

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM hypotheses WHERE id = ?", (hypothesis_id,)
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], Hypothesis) if row else None

    async def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        hypothesis.updated_at = datetime.now()
        return await self.add_hypothesis(hypothesis)

    async def delete_hypothesis(self, hypothesis_id: str) -> bool:
        db = self._require()
        async with db.execute(
            "SELECT id FROM hypotheses WHERE id = ?", (hypothesis_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return False
        await db.execute("DELETE FROM hypotheses WHERE id = ?", (hypothesis_id,))
        await db.execute(
            "DELETE FROM reviews WHERE hypothesis_id = ?", (hypothesis_id,)
        )
        await db.commit()
        return True

    async def get_all_hypotheses(self) -> List[Hypothesis]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM hypotheses ORDER BY elo_rating DESC"
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], Hypothesis) for r in rows]

    async def get_hypotheses_by_goal(
        self, goal_id: str, status: Optional[HypothesisStatus] = None
    ) -> List[Hypothesis]:
        db = self._require()
        if status is not None:
            status_val = getattr(status, "value", str(status))
            async with db.execute(
                "SELECT data FROM hypotheses WHERE research_goal_id = ? AND status = ? "
                "ORDER BY elo_rating DESC",
                (goal_id, status_val),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT data FROM hypotheses WHERE research_goal_id = ? "
                "ORDER BY elo_rating DESC",
                (goal_id,),
            ) as cur:
                rows = await cur.fetchall()
        return [_loads(r["data"], Hypothesis) for r in rows]

    async def get_top_hypotheses(
        self, n: int = 10, goal_id: Optional[str] = None
    ) -> List[Hypothesis]:
        if goal_id:
            return (await self.get_hypotheses_by_goal(goal_id))[:n]
        return (await self.get_all_hypotheses())[:n]

    async def get_hypotheses_needing_review(
        self, goal_id: str, limit: int = 10
    ) -> List[Hypothesis]:
        hyps = await self.get_hypotheses_by_goal(goal_id, HypothesisStatus.GENERATED)
        result: List[Hypothesis] = []
        for h in hyps:
            reviews = await self.get_reviews_for_hypothesis(h.id)
            if not reviews:
                result.append(h)
                if len(result) >= limit:
                    break
        return result

    async def get_hypothesis_count(self, goal_id: Optional[str] = None) -> int:
        db = self._require()
        if goal_id:
            async with db.execute(
                "SELECT COUNT(*) AS c FROM hypotheses WHERE research_goal_id = ?",
                (goal_id,),
            ) as cur:
                row = await cur.fetchone()
        else:
            async with db.execute("SELECT COUNT(*) AS c FROM hypotheses") as cur:
                row = await cur.fetchone()
        return int(row["c"])

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    async def add_review(self, review: Review) -> Review:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO reviews "
            "(id, hypothesis_id, review_type, created_at, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                review.id,
                review.hypothesis_id,
                getattr(review.review_type, "value", str(review.review_type)),
                _dt_str(getattr(review, "created_at", None)),
                _dumps(review),
            ),
        )
        await db.commit()
        return review

    async def get_review(self, review_id: str) -> Optional[Review]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM reviews WHERE id = ?", (review_id,)
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], Review) if row else None

    async def get_reviews_for_hypothesis(
        self, hypothesis_id: str, review_type: Optional[ReviewType] = None
    ) -> List[Review]:
        db = self._require()
        if review_type:
            rt_val = getattr(review_type, "value", str(review_type))
            async with db.execute(
                "SELECT data FROM reviews WHERE hypothesis_id = ? AND review_type = ? "
                "ORDER BY created_at DESC",
                (hypothesis_id, rt_val),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT data FROM reviews WHERE hypothesis_id = ? "
                "ORDER BY created_at DESC",
                (hypothesis_id,),
            ) as cur:
                rows = await cur.fetchall()
        return [_loads(r["data"], Review) for r in rows]

    async def get_all_reviews(self, goal_id: Optional[str] = None) -> List[Review]:
        db = self._require()
        if goal_id:
            async with db.execute(
                "SELECT r.data FROM reviews r "
                "JOIN hypotheses h ON r.hypothesis_id = h.id "
                "WHERE h.research_goal_id = ?",
                (goal_id,),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute("SELECT data FROM reviews") as cur:
                rows = await cur.fetchall()
        return [_loads(r["data"], Review) for r in rows]

    # ------------------------------------------------------------------
    # Matches
    # ------------------------------------------------------------------

    async def add_match(self, match: TournamentMatch) -> TournamentMatch:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO matches "
            "(id, hypothesis_a_id, hypothesis_b_id, winner_id, created_at, data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                match.id,
                match.hypothesis_a_id,
                match.hypothesis_b_id,
                match.winner_id,
                _dt_str(getattr(match, "created_at", None)),
                _dumps(match),
            ),
        )
        await db.commit()
        return match

    async def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM matches WHERE id = ?", (match_id,)
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], TournamentMatch) if row else None

    async def get_matches_for_hypothesis(
        self, hypothesis_id: str
    ) -> List[TournamentMatch]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM matches "
            "WHERE hypothesis_a_id = ? OR hypothesis_b_id = ?",
            (hypothesis_id, hypothesis_id),
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], TournamentMatch) for r in rows]

    async def get_all_matches(
        self, goal_id: Optional[str] = None
    ) -> List[TournamentMatch]:
        db = self._require()
        if goal_id:
            async with db.execute(
                "SELECT m.data FROM matches m "
                "JOIN hypotheses h ON m.hypothesis_a_id = h.id "
                "WHERE h.research_goal_id = ?",
                (goal_id,),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute("SELECT data FROM matches") as cur:
                rows = await cur.fetchall()
        return [_loads(r["data"], TournamentMatch) for r in rows]

    async def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        matches = await self.get_matches_for_hypothesis(hypothesis_id)
        if not matches:
            return 0.0
        wins = sum(1 for m in matches if m.winner_id == hypothesis_id)
        return wins / len(matches)

    async def get_match_count(self, goal_id: Optional[str] = None) -> int:
        matches = await self.get_all_matches(goal_id)
        return len(matches)

    # ------------------------------------------------------------------
    # Tournament State
    # ------------------------------------------------------------------

    async def save_tournament_state(
        self, state: TournamentState
    ) -> TournamentState:
        db = self._require()
        state.updated_at = datetime.now()
        await db.execute(
            "INSERT OR REPLACE INTO tournament_states (goal_id, data) VALUES (?, ?)",
            (state.research_goal_id, _dumps(state)),
        )
        await db.commit()
        return state

    async def get_tournament_state(
        self, goal_id: str
    ) -> Optional[TournamentState]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM tournament_states WHERE goal_id = ?", (goal_id,)
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], TournamentState) if row else None

    # ------------------------------------------------------------------
    # Proximity Graph
    # ------------------------------------------------------------------

    async def save_proximity_graph(
        self, graph: ProximityGraph
    ) -> ProximityGraph:
        db = self._require()
        graph.updated_at = datetime.now()
        await db.execute(
            "INSERT OR REPLACE INTO proximity_graphs (goal_id, data) VALUES (?, ?)",
            (graph.research_goal_id, _dumps(graph)),
        )
        # Rewrite edges table for this goal.
        await db.execute(
            "DELETE FROM proximity_edges WHERE goal_id = ?",
            (graph.research_goal_id,),
        )
        for i, edge in enumerate(graph.edges):
            await db.execute(
                "INSERT INTO proximity_edges (goal_id, edge_index, data) VALUES (?, ?, ?)",
                (graph.research_goal_id, i, _dumps(edge)),
            )
        await db.commit()
        return graph

    async def get_proximity_graph(
        self, goal_id: str
    ) -> Optional[ProximityGraph]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM proximity_graphs WHERE goal_id = ?", (goal_id,)
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], ProximityGraph) if row else None

    async def add_proximity_edge(
        self, goal_id: str, edge: ProximityEdge
    ) -> ProximityEdge:
        db = self._require()
        async with db.execute(
            "SELECT COALESCE(MAX(edge_index), -1) + 1 AS next_idx "
            "FROM proximity_edges WHERE goal_id = ?",
            (goal_id,),
        ) as cur:
            row = await cur.fetchone()
        next_idx = int(row["next_idx"])
        await db.execute(
            "INSERT INTO proximity_edges (goal_id, edge_index, data) VALUES (?, ?, ?)",
            (goal_id, next_idx, _dumps(edge)),
        )

        # Keep the consolidated graph blob in sync if present.
        graph = await self.get_proximity_graph(goal_id)
        if graph:
            graph.edges.append(edge)
            graph.updated_at = datetime.now()
            await db.execute(
                "UPDATE proximity_graphs SET data = ? WHERE goal_id = ?",
                (_dumps(graph), goal_id),
            )
        await db.commit()
        return edge

    async def get_similar_hypotheses(
        self, hypothesis_id: str, min_similarity: float = 0.7
    ) -> List[tuple[str, float]]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM proximity_edges"
        ) as cur:
            rows = await cur.fetchall()
        result: list[tuple[str, float]] = []
        for r in rows:
            edge = _loads(r["data"], ProximityEdge)
            if edge.similarity_score < min_similarity:
                continue
            if edge.hypothesis_a_id == hypothesis_id:
                result.append((edge.hypothesis_b_id, edge.similarity_score))
            elif edge.hypothesis_b_id == hypothesis_id:
                result.append((edge.hypothesis_a_id, edge.similarity_score))
        return sorted(result, key=lambda x: x[1], reverse=True)

    # ------------------------------------------------------------------
    # Meta review / overview
    # ------------------------------------------------------------------

    async def save_meta_review(
        self, meta_review: MetaReviewCritique
    ) -> MetaReviewCritique:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO meta_reviews (id, goal_id, created_at, data) "
            "VALUES (?, ?, ?, ?)",
            (
                meta_review.id,
                meta_review.research_goal_id,
                _dt_str(getattr(meta_review, "created_at", None)),
                _dumps(meta_review),
            ),
        )
        await db.commit()
        return meta_review

    async def get_meta_review(
        self, goal_id: str
    ) -> Optional[MetaReviewCritique]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM meta_reviews WHERE goal_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (goal_id,),
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], MetaReviewCritique) if row else None

    async def get_all_meta_reviews(
        self, goal_id: str
    ) -> List[MetaReviewCritique]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM meta_reviews WHERE goal_id = ? "
            "ORDER BY created_at DESC",
            (goal_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], MetaReviewCritique) for r in rows]

    async def save_research_overview(
        self, overview: ResearchOverview
    ) -> ResearchOverview:
        db = self._require()
        overview.updated_at = datetime.now()
        await db.execute(
            "INSERT OR REPLACE INTO research_overviews (goal_id, data) "
            "VALUES (?, ?)",
            (overview.research_goal_id, _dumps(overview)),
        )
        await db.commit()
        return overview

    async def get_research_overview(
        self, goal_id: str
    ) -> Optional[ResearchOverview]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM research_overviews WHERE goal_id = ?", (goal_id,)
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], ResearchOverview) if row else None

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def add_task(self, task: AgentTask) -> AgentTask:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO tasks "
            "(id, agent_type, status, priority, created_at, data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                task.id,
                getattr(task.agent_type, "value", str(task.agent_type)),
                task.status,
                int(getattr(task, "priority", 0) or 0),
                _dt_str(getattr(task, "created_at", None)),
                _dumps(task),
            ),
        )
        await db.commit()
        return task

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM tasks WHERE id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], AgentTask) if row else None

    async def get_pending_tasks(
        self, agent_type: Optional[AgentType] = None, limit: int = 100
    ) -> List[AgentTask]:
        db = self._require()
        if agent_type:
            at_val = getattr(agent_type, "value", str(agent_type))
            async with db.execute(
                "SELECT data FROM tasks WHERE status = 'pending' AND agent_type = ? "
                "ORDER BY priority DESC, created_at ASC LIMIT ?",
                (at_val, limit),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT data FROM tasks WHERE status = 'pending' "
                "ORDER BY priority DESC, created_at ASC LIMIT ?",
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
        return [_loads(r["data"], AgentTask) for r in rows]

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> AgentTask:
        task = await self.get_task(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        task.status = status
        if result is not None:
            task.result = result
        now = datetime.now()
        if status == "running":
            task.started_at = now
        elif status in ("complete", "failed"):
            task.completed_at = now
        return await self.add_task(task)

    async def claim_next_task(
        self, agent_type: AgentType, worker_id: str
    ) -> Optional[AgentTask]:
        pending = await self.get_pending_tasks(agent_type, limit=1)
        if not pending:
            return None
        task = pending[0]
        task.status = "running"
        task.started_at = datetime.now()
        task.parameters = dict(task.parameters or {})
        task.parameters["worker_id"] = worker_id
        return await self.add_task(task)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def save_statistics(
        self, stats: SystemStatistics
    ) -> SystemStatistics:
        db = self._require()
        await db.execute(
            "INSERT INTO statistics (goal_id, computed_at, data) VALUES (?, ?, ?)",
            (
                stats.research_goal_id,
                _dt_str(getattr(stats, "computed_at", None)),
                _dumps(stats),
            ),
        )
        await db.commit()
        return stats

    async def get_latest_statistics(
        self, goal_id: str
    ) -> Optional[SystemStatistics]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM statistics WHERE goal_id = ? "
            "ORDER BY computed_at DESC LIMIT 1",
            (goal_id,),
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], SystemStatistics) if row else None

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    async def save_checkpoint(
        self, checkpoint: ContextMemory
    ) -> ContextMemory:
        db = self._require()
        checkpoint.updated_at = datetime.now()
        await db.execute(
            "INSERT INTO checkpoints (goal_id, updated_at, data) VALUES (?, ?, ?)",
            (
                checkpoint.research_goal_id,
                _dt_str(checkpoint.updated_at),
                _dumps(checkpoint),
            ),
        )
        await db.commit()
        return checkpoint

    async def get_latest_checkpoint(
        self, goal_id: str
    ) -> Optional[ContextMemory]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM checkpoints WHERE goal_id = ? "
            "ORDER BY updated_at DESC LIMIT 1",
            (goal_id,),
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], ContextMemory) if row else None

    async def get_all_checkpoints(
        self, goal_id: str
    ) -> List[ContextMemory]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM checkpoints WHERE goal_id = ? "
            "ORDER BY updated_at DESC",
            (goal_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], ContextMemory) for r in rows]

    # ------------------------------------------------------------------
    # Observation Reviews
    # ------------------------------------------------------------------

    async def add_observation_review(
        self, review: ObservationReviewScore
    ) -> ObservationReviewScore:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO observation_reviews (hypothesis_id, data) "
            "VALUES (?, ?)",
            (review.hypothesis_id, _dumps(review)),
        )
        await db.commit()
        return review

    async def get_observation_review(
        self, hypothesis_id: str
    ) -> Optional[ObservationReviewScore]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM observation_reviews WHERE hypothesis_id = ?",
            (hypothesis_id,),
        ) as cur:
            row = await cur.fetchone()
        return _loads(row["data"], ObservationReviewScore) if row else None

    async def get_observation_reviews_by_goal(
        self, goal_id: str
    ) -> List[ObservationReviewScore]:
        db = self._require()
        async with db.execute(
            "SELECT o.data FROM observation_reviews o "
            "JOIN hypotheses h ON o.hypothesis_id = h.id "
            "WHERE h.research_goal_id = ?",
            (goal_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], ObservationReviewScore) for r in rows]

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    async def add_feedback(
        self, feedback: ScientistFeedback
    ) -> ScientistFeedback:
        db = self._require()
        await db.execute(
            "INSERT OR REPLACE INTO feedback (id, hypothesis_id, created_at, data) "
            "VALUES (?, ?, ?, ?)",
            (
                feedback.id,
                feedback.hypothesis_id,
                _dt_str(getattr(feedback, "created_at", None)),
                _dumps(feedback),
            ),
        )
        await db.commit()
        return feedback

    async def get_feedback_for_hypothesis(
        self, hypothesis_id: str
    ) -> List[ScientistFeedback]:
        db = self._require()
        async with db.execute(
            "SELECT data FROM feedback WHERE hypothesis_id = ?", (hypothesis_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], ScientistFeedback) for r in rows]

    async def get_all_feedback(
        self, goal_id: str
    ) -> List[ScientistFeedback]:
        db = self._require()
        async with db.execute(
            "SELECT f.data FROM feedback f "
            "JOIN hypotheses h ON f.hypothesis_id = h.id "
            "WHERE h.research_goal_id = ?",
            (goal_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], ScientistFeedback) for r in rows]

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def add_chat_message(self, message: ChatMessage) -> ChatMessage:
        db = self._require()
        # ChatMessage doesn't carry a goal_id; we mimic the in-memory store
        # and use "default" as the scope key.
        await db.execute(
            "INSERT INTO chat_messages (goal_id, created_at, data) VALUES (?, ?, ?)",
            (
                "default",
                _dt_str(getattr(message, "created_at", None)),
                _dumps(message),
            ),
        )
        await db.commit()
        return message

    async def get_chat_history(
        self, goal_id: str, limit: int = 100
    ) -> List[ChatMessage]:
        db = self._require()
        # Same scope-key convention as add_chat_message.
        target = goal_id if goal_id else "default"
        async with db.execute(
            "SELECT data FROM chat_messages WHERE goal_id = ? OR goal_id = 'default' "
            "ORDER BY created_at ASC LIMIT ?",
            (target, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [_loads(r["data"], ChatMessage) for r in rows]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def clear_all(self, goal_id: Optional[str] = None) -> None:
        db = self._require()
        if goal_id:
            await self.delete_research_goal(goal_id)
            return
        tables = [
            "research_goals",
            "hypotheses",
            "reviews",
            "matches",
            "tournament_states",
            "proximity_graphs",
            "proximity_edges",
            "meta_reviews",
            "research_overviews",
            "tasks",
            "statistics",
            "checkpoints",
            "feedback",
            "chat_messages",
            "observation_reviews",
        ]
        for t in tables:
            await db.execute(f"DELETE FROM {t}")
        await db.commit()

    async def get_stats(self) -> Dict[str, int]:
        db = self._require()
        counts: Dict[str, int] = {}
        for table, alias in [
            ("research_goals", "research_goals"),
            ("hypotheses", "hypotheses"),
            ("reviews", "reviews"),
            ("matches", "matches"),
            ("tournament_states", "tournament_states"),
            ("proximity_graphs", "proximity_graphs"),
            ("meta_reviews", "meta_reviews"),
            ("research_overviews", "overviews"),
            ("tasks", "tasks"),
            ("checkpoints", "checkpoints"),
            ("feedback", "feedback"),
            ("observation_reviews", "observation_reviews"),
        ]:
            async with db.execute(f"SELECT COUNT(*) AS c FROM {table}") as cur:
                row = await cur.fetchone()
            counts[alias] = int(row["c"])
        return counts

    # Transactions: SQLite is autocommit-per-statement here; we keep these
    # as no-ops to satisfy the interface.
    async def begin_transaction(self) -> Any:
        return None

    async def commit_transaction(self, transaction: Any) -> None:
        if self._db:
            await self._db.commit()

    async def rollback_transaction(self, transaction: Any) -> None:
        if self._db:
            await self._db.rollback()
