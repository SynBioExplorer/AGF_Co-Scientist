"""PostgreSQL storage implementation for AI Co-Scientist.

This implementation provides persistent storage using PostgreSQL with:
- Async connection pooling via asyncpg
- JSONB for complex nested objects
- Prepared statements for performance
- Transaction support

Requires PostgreSQL 15+ with pg_trgm extension for text search.
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import asynccontextmanager
import sys
from pathlib import Path
import structlog

try:
    import asyncpg
except ImportError:
    asyncpg = None  # Will raise error on connect if not installed

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import (
    ResearchGoal,
    ResearchPlanConfiguration,
    Hypothesis,
    HypothesisStatus,
    GenerationMethod,
    Review,
    ReviewType,
    TournamentMatch,
    TournamentState,
    DebateTurn,
    ProximityGraph,
    ProximityEdge,
    HypothesisCluster,
    MetaReviewCritique,
    ResearchOverview,
    ResearchDirection,
    ResearchContact,
    Citation,
    ExperimentalProtocol,
    Assumption,
    AgentTask,
    AgentType,
    SystemStatistics,
    ContextMemory,
    ScientistFeedback,
    ChatMessage,
)

from src.storage.base import BaseStorage

logger = structlog.get_logger()


class PostgreSQLStorage(BaseStorage):
    """PostgreSQL-backed storage with connection pooling.

    Uses asyncpg for high-performance async database access.
    All complex objects (citations, experimental_protocol, etc.) are
    stored as JSONB for flexibility.
    """

    def __init__(self, database_url: Optional[str] = None):
        """Initialize PostgreSQL storage.

        Args:
            database_url: PostgreSQL connection URL.
                Format: postgresql://user:password@host:port/database
                If not provided, will use settings.database_url on connect.
        """
        self._database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Create connection pool with production-grade sizing."""
        if asyncpg is None:
            raise ImportError("asyncpg is required for PostgreSQL storage. Install with: pip install asyncpg")

        if self._database_url is None:
            from src.config import settings
            self._database_url = settings.database_url

        try:
            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=5,  # Increased from 2 to handle baseline load
                max_size=50,  # Increased from 10 to handle concurrent requests
                command_timeout=60,
                timeout=30.0,  # Added: pool acquisition timeout
            )
            pool_size = self._pool.get_size()
            logger.info(
                "PostgreSQL connection pool created",
                database=self._database_url.split("@")[-1],
                min_size=5,
                max_size=50,
                current_size=pool_size,
            )
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL", error=str(e))
            raise

    async def create_indexes(self) -> None:
        """Create performance indexes from migration 001_add_indexes.sql.

        This method is idempotent and can be safely called multiple times.
        It creates indexes with IF NOT EXISTS to avoid errors on re-runs.

        The indexes optimize common query patterns:
        - Filtered queries on research_goal_id, status, elo_rating
        - Top-N queries with ORDER BY + LIMIT
        - Foreign key lookups and JOINs
        - Task queue operations for Supervisor

        Expected performance improvements:
        - Filtered queries: 100-1000x faster
        - Top-N queries: 50-500x faster
        - Foreign key lookups: 10-100x faster

        Note:
            Uses CONCURRENTLY to avoid locking tables. Safe for production.
            See src/storage/migrations/001_add_indexes.sql for details.

        Raises:
            RuntimeError: If connection pool is not initialized.
        """
        import os
        from pathlib import Path

        migration_file = Path(__file__).parent / "migrations" / "001_add_indexes.sql"

        if not migration_file.exists():
            logger.error(
                "Migration file not found",
                path=str(migration_file)
            )
            raise FileNotFoundError(f"Migration file not found: {migration_file}")

        logger.info("Creating performance indexes from migration 001")

        # Read migration SQL
        migration_sql = migration_file.read_text()

        # Execute migration
        async with self._acquire_connection() as conn:
            try:
                # Split on semicolons and execute each statement
                # (asyncpg doesn't support multiple statements in one execute)
                statements = [s.strip() for s in migration_sql.split(';') if s.strip()]

                for i, statement in enumerate(statements, 1):
                    # Skip comments and empty statements
                    if not statement or statement.startswith('--'):
                        continue

                    try:
                        await conn.execute(statement)
                        logger.debug(
                            "Executed migration statement",
                            statement_num=i,
                            total=len(statements)
                        )
                    except Exception as stmt_error:
                        # Log but continue - some statements may fail if indexes exist
                        logger.warning(
                            "Migration statement failed (may be expected if index exists)",
                            statement_num=i,
                            error=str(stmt_error),
                            statement_preview=statement[:100]
                        )

                logger.info(
                    "Performance indexes created successfully",
                    statements_executed=len([s for s in statements if s and not s.startswith('--')])
                )

            except Exception as e:
                logger.error("Failed to create indexes", error=str(e))
                raise

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")

    async def health_check(self) -> bool:
        """Check database connectivity with timeout protection.

        Returns False if:
        - Pool is not initialized
        - Query times out (5 second limit)
        - Any database error occurs
        """
        import asyncio

        if not self._pool:
            return False

        try:
            # Add timeout to health check to prevent hanging
            # Use pool.acquire() directly to avoid the monitoring overhead
            async with asyncio.timeout(5.0):
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
            return True
        except asyncio.TimeoutError:
            logger.error("Health check timed out after 5 seconds")
            return False
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False

    def _check_pool_usage(self) -> None:
        """Log warning if pool usage exceeds 80% threshold."""
        if not self._pool:
            return

        current_size = self._pool.get_size()
        max_size = self._pool.get_max_size()
        usage_percent = (current_size / max_size) * 100

        if usage_percent >= 80:
            logger.warning(
                "Connection pool usage high",
                current_size=current_size,
                max_size=max_size,
                usage_percent=f"{usage_percent:.1f}%",
            )

    @asynccontextmanager
    async def _acquire_connection(self):
        """Acquire a connection from the pool with timeout and monitoring.

        Raises:
            asyncio.TimeoutError: If connection acquisition exceeds 30 seconds.
            RuntimeError: If pool is not initialized.
        """
        import asyncio

        if not self._pool:
            raise RuntimeError("Connection pool not initialized. Call connect() first.")

        # Check pool usage before acquiring
        self._check_pool_usage()

        try:
            # Acquire with timeout to prevent indefinite blocking
            async with asyncio.timeout(30.0):
                async with self._pool.acquire() as conn:
                    yield conn
        except asyncio.TimeoutError:
            current_size = self._pool.get_size()
            max_size = self._pool.get_max_size()
            logger.error(
                "Connection pool acquisition timeout",
                timeout_seconds=30.0,
                pool_size=current_size,
                max_size=max_size,
            )
            raise

    # =========================================================================
    # Research Goals
    # =========================================================================

    async def add_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Store a new research goal."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO research_goals (id, description, constraints, preferences,
                    prior_publications, laboratory_context, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                goal.id,
                goal.description,
                json.dumps(goal.constraints),
                json.dumps(goal.preferences),
                json.dumps(goal.prior_publications),
                goal.laboratory_context,
                goal.created_at,
            )
            logger.info("Research goal added", goal_id=goal.id)
        return goal

    async def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve a research goal by ID."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM research_goals WHERE id = $1",
                goal_id,
            )
            if not row:
                return None
            return self._row_to_research_goal(row)

    async def get_all_research_goals(self) -> List[ResearchGoal]:
        """Get all research goals."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM research_goals ORDER BY created_at DESC"
            )
            return [self._row_to_research_goal(row) for row in rows]

    async def update_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Update an existing research goal."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                UPDATE research_goals SET
                    description = $2,
                    constraints = $3,
                    preferences = $4,
                    prior_publications = $5,
                    laboratory_context = $6
                WHERE id = $1
                """,
                goal.id,
                goal.description,
                json.dumps(goal.constraints),
                json.dumps(goal.preferences),
                json.dumps(goal.prior_publications),
                goal.laboratory_context,
            )
            logger.info("Research goal updated", goal_id=goal.id)
        return goal

    async def delete_research_goal(self, goal_id: str) -> bool:
        """Delete a research goal (cascades to all related data)."""
        async with self._acquire_connection() as conn:
            result = await conn.execute(
                "DELETE FROM research_goals WHERE id = $1",
                goal_id,
            )
            deleted = result == "DELETE 1"
            if deleted:
                logger.info("Research goal deleted with cascade", goal_id=goal_id)
            return deleted

    def _row_to_research_goal(self, row: asyncpg.Record) -> ResearchGoal:
        """Convert database row to ResearchGoal."""
        return ResearchGoal(
            id=row["id"],
            description=row["description"],
            constraints=json.loads(row["constraints"]) if row["constraints"] else [],
            preferences=json.loads(row["preferences"]) if row["preferences"] else [],
            prior_publications=json.loads(row["prior_publications"]) if row["prior_publications"] else [],
            laboratory_context=row["laboratory_context"],
            created_at=row["created_at"],
        )

    # =========================================================================
    # Hypotheses
    # =========================================================================

    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Store a new hypothesis."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO hypotheses (
                    id, research_goal_id, title, summary, hypothesis_statement,
                    rationale, mechanism, experimental_protocol, literature_citations,
                    assumptions, category, status, generation_method,
                    parent_hypothesis_ids, elo_rating, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                """,
                hypothesis.id,
                hypothesis.research_goal_id,
                hypothesis.title,
                hypothesis.summary,
                hypothesis.hypothesis_statement,
                hypothesis.rationale,
                hypothesis.mechanism,
                json.dumps(hypothesis.experimental_protocol.model_dump()) if hypothesis.experimental_protocol else None,
                json.dumps([c.model_dump() for c in hypothesis.literature_citations]),
                json.dumps([a.model_dump() for a in hypothesis.assumptions]),
                hypothesis.category,
                hypothesis.status.value,
                hypothesis.generation_method.value,
                json.dumps(hypothesis.parent_hypothesis_ids),
                hypothesis.elo_rating,
                hypothesis.created_at,
                hypothesis.updated_at,
            )
            logger.info("Hypothesis added", hypothesis_id=hypothesis.id)
        return hypothesis

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve a hypothesis by ID."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM hypotheses WHERE id = $1",
                hypothesis_id,
            )
            if not row:
                return None
            return self._row_to_hypothesis(row)

    async def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Update an existing hypothesis."""
        hypothesis.updated_at = datetime.now()
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                UPDATE hypotheses SET
                    title = $2, summary = $3, hypothesis_statement = $4,
                    rationale = $5, mechanism = $6, experimental_protocol = $7,
                    literature_citations = $8, assumptions = $9, category = $10,
                    status = $11, elo_rating = $12, updated_at = $13
                WHERE id = $1
                """,
                hypothesis.id,
                hypothesis.title,
                hypothesis.summary,
                hypothesis.hypothesis_statement,
                hypothesis.rationale,
                hypothesis.mechanism,
                json.dumps(hypothesis.experimental_protocol.model_dump()) if hypothesis.experimental_protocol else None,
                json.dumps([c.model_dump() for c in hypothesis.literature_citations]),
                json.dumps([a.model_dump() for a in hypothesis.assumptions]),
                hypothesis.category,
                hypothesis.status.value,
                hypothesis.elo_rating,
                hypothesis.updated_at,
            )
            logger.debug("Hypothesis updated", hypothesis_id=hypothesis.id)
        return hypothesis

    async def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis (cascades to reviews and matches)."""
        async with self._acquire_connection() as conn:
            result = await conn.execute(
                "DELETE FROM hypotheses WHERE id = $1",
                hypothesis_id,
            )
            deleted = result == "DELETE 1"
            if deleted:
                logger.info("Hypothesis deleted", hypothesis_id=hypothesis_id)
            return deleted

    async def get_all_hypotheses(self) -> List[Hypothesis]:
        """Get all hypotheses sorted by Elo rating."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM hypotheses ORDER BY elo_rating DESC"
            )
            return [self._row_to_hypothesis(row) for row in rows]

    async def get_hypotheses_by_goal(
        self,
        goal_id: str,
        status: Optional[HypothesisStatus] = None
    ) -> List[Hypothesis]:
        """Get all hypotheses for a research goal."""
        async with self._acquire_connection() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM hypotheses
                    WHERE research_goal_id = $1 AND status = $2
                    ORDER BY elo_rating DESC
                    """,
                    goal_id,
                    status.value,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM hypotheses
                    WHERE research_goal_id = $1
                    ORDER BY elo_rating DESC
                    """,
                    goal_id,
                )
            return [self._row_to_hypothesis(row) for row in rows]

    async def get_top_hypotheses(
        self,
        n: int = 10,
        goal_id: Optional[str] = None
    ) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating."""
        async with self._acquire_connection() as conn:
            if goal_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM hypotheses
                    WHERE research_goal_id = $1
                    ORDER BY elo_rating DESC
                    LIMIT $2
                    """,
                    goal_id,
                    n,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM hypotheses ORDER BY elo_rating DESC LIMIT $1",
                    n,
                )
            return [self._row_to_hypothesis(row) for row in rows]

    async def get_hypotheses_needing_review(
        self,
        goal_id: str,
        limit: int = 10
    ) -> List[Hypothesis]:
        """Get hypotheses without reviews."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT h.* FROM hypotheses h
                LEFT JOIN reviews r ON h.id = r.hypothesis_id
                WHERE h.research_goal_id = $1 AND h.status = 'generated' AND r.id IS NULL
                ORDER BY h.created_at ASC
                LIMIT $2
                """,
                goal_id,
                limit,
            )
            return [self._row_to_hypothesis(row) for row in rows]

    async def get_hypothesis_count(self, goal_id: Optional[str] = None) -> int:
        """Get total count of hypotheses."""
        async with self._acquire_connection() as conn:
            if goal_id:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM hypotheses WHERE research_goal_id = $1",
                    goal_id,
                )
            else:
                count = await conn.fetchval("SELECT COUNT(*) FROM hypotheses")
            return count

    def _row_to_hypothesis(self, row: asyncpg.Record) -> Hypothesis:
        """Convert database row to Hypothesis."""
        citations = []
        if row["literature_citations"]:
            citations_data = json.loads(row["literature_citations"])
            citations = [Citation(**c) for c in citations_data]

        assumptions = []
        if row["assumptions"]:
            assumptions_data = json.loads(row["assumptions"])
            assumptions = [Assumption(**a) for a in assumptions_data]

        experimental_protocol = None
        if row["experimental_protocol"]:
            experimental_protocol = ExperimentalProtocol(**json.loads(row["experimental_protocol"]))

        parent_ids = []
        if row["parent_hypothesis_ids"]:
            parent_ids = json.loads(row["parent_hypothesis_ids"])

        return Hypothesis(
            id=row["id"],
            research_goal_id=row["research_goal_id"],
            title=row["title"],
            summary=row["summary"],
            hypothesis_statement=row["hypothesis_statement"],
            rationale=row["rationale"],
            mechanism=row["mechanism"],
            experimental_protocol=experimental_protocol,
            literature_citations=citations,
            assumptions=assumptions,
            category=row["category"],
            status=HypothesisStatus(row["status"]),
            generation_method=GenerationMethod(row["generation_method"]),
            parent_hypothesis_ids=parent_ids,
            elo_rating=row["elo_rating"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Reviews
    # =========================================================================

    async def add_review(self, review: Review) -> Review:
        """Store a new review."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO reviews (
                    id, hypothesis_id, review_type,
                    correctness_score, quality_score, novelty_score,
                    testability_score, safety_score,
                    strengths, weaknesses, suggestions, critiques,
                    known_aspects, novel_aspects, explained_observations,
                    simulation_steps, potential_failures,
                    passed, rationale, literature_searched, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                """,
                review.id,
                review.hypothesis_id,
                review.review_type.value,
                review.correctness_score,
                review.quality_score,
                review.novelty_score,
                review.testability_score,
                review.safety_score,
                json.dumps(review.strengths),
                json.dumps(review.weaknesses),
                json.dumps(review.suggestions),
                json.dumps(review.critiques),
                json.dumps(review.known_aspects),
                json.dumps(review.novel_aspects),
                json.dumps(review.explained_observations),
                json.dumps(review.simulation_steps),
                json.dumps(review.potential_failures),
                review.passed,
                review.rationale,
                json.dumps(review.literature_searched),
                review.created_at,
            )
            logger.info("Review added", review_id=review.id, hypothesis_id=review.hypothesis_id)
        return review

    async def get_review(self, review_id: str) -> Optional[Review]:
        """Retrieve a review by ID."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM reviews WHERE id = $1",
                review_id,
            )
            if not row:
                return None
            return self._row_to_review(row)

    async def get_reviews_for_hypothesis(
        self,
        hypothesis_id: str,
        review_type: Optional[ReviewType] = None
    ) -> List[Review]:
        """Get all reviews for a hypothesis."""
        async with self._acquire_connection() as conn:
            if review_type:
                rows = await conn.fetch(
                    """
                    SELECT * FROM reviews
                    WHERE hypothesis_id = $1 AND review_type = $2
                    ORDER BY created_at DESC
                    """,
                    hypothesis_id,
                    review_type.value,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM reviews
                    WHERE hypothesis_id = $1
                    ORDER BY created_at DESC
                    """,
                    hypothesis_id,
                )
            return [self._row_to_review(row) for row in rows]

    async def get_all_reviews(self, goal_id: Optional[str] = None) -> List[Review]:
        """Get all reviews."""
        async with self._acquire_connection() as conn:
            if goal_id:
                rows = await conn.fetch(
                    """
                    SELECT r.* FROM reviews r
                    JOIN hypotheses h ON r.hypothesis_id = h.id
                    WHERE h.research_goal_id = $1
                    ORDER BY r.created_at DESC
                    """,
                    goal_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM reviews ORDER BY created_at DESC"
                )
            return [self._row_to_review(row) for row in rows]

    def _row_to_review(self, row: asyncpg.Record) -> Review:
        """Convert database row to Review."""
        return Review(
            id=row["id"],
            hypothesis_id=row["hypothesis_id"],
            review_type=ReviewType(row["review_type"]),
            correctness_score=row["correctness_score"],
            quality_score=row["quality_score"],
            novelty_score=row["novelty_score"],
            testability_score=row["testability_score"],
            safety_score=row["safety_score"],
            strengths=json.loads(row["strengths"]) if row["strengths"] else [],
            weaknesses=json.loads(row["weaknesses"]) if row["weaknesses"] else [],
            suggestions=json.loads(row["suggestions"]) if row["suggestions"] else [],
            critiques=json.loads(row["critiques"]) if row["critiques"] else [],
            known_aspects=json.loads(row["known_aspects"]) if row["known_aspects"] else [],
            novel_aspects=json.loads(row["novel_aspects"]) if row["novel_aspects"] else [],
            explained_observations=json.loads(row["explained_observations"]) if row["explained_observations"] else [],
            simulation_steps=json.loads(row["simulation_steps"]) if row["simulation_steps"] else [],
            potential_failures=json.loads(row["potential_failures"]) if row["potential_failures"] else [],
            passed=row["passed"],
            rationale=row["rationale"],
            literature_searched=json.loads(row["literature_searched"]) if row["literature_searched"] else [],
            created_at=row["created_at"],
        )

    # =========================================================================
    # Tournament Matches
    # =========================================================================

    async def add_match(self, match: TournamentMatch) -> TournamentMatch:
        """Store a new tournament match."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO tournament_matches (
                    id, hypothesis_a_id, hypothesis_b_id, debate_turns, is_multi_turn,
                    winner_id, decision_rationale, comparison_criteria,
                    elo_change_a, elo_change_b, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                match.id,
                match.hypothesis_a_id,
                match.hypothesis_b_id,
                json.dumps([t.model_dump() for t in match.debate_turns]),
                match.is_multi_turn,
                match.winner_id,
                match.decision_rationale,
                json.dumps(match.comparison_criteria),
                match.elo_change_a,
                match.elo_change_b,
                match.created_at,
            )
            logger.info("Match added", match_id=match.id)
        return match

    async def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        """Retrieve a match by ID."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tournament_matches WHERE id = $1",
                match_id,
            )
            if not row:
                return None
            return self._row_to_match(row)

    async def get_matches_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[TournamentMatch]:
        """Get all matches involving a hypothesis."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM tournament_matches
                WHERE hypothesis_a_id = $1 OR hypothesis_b_id = $1
                ORDER BY created_at DESC
                """,
                hypothesis_id,
            )
            return [self._row_to_match(row) for row in rows]

    async def get_all_matches(self, goal_id: Optional[str] = None) -> List[TournamentMatch]:
        """Get all tournament matches."""
        async with self._acquire_connection() as conn:
            if goal_id:
                rows = await conn.fetch(
                    """
                    SELECT tm.* FROM tournament_matches tm
                    JOIN hypotheses h ON tm.hypothesis_a_id = h.id
                    WHERE h.research_goal_id = $1
                    ORDER BY tm.created_at DESC
                    """,
                    goal_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM tournament_matches ORDER BY created_at DESC"
                )
            return [self._row_to_match(row) for row in rows]

    async def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for a hypothesis."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN winner_id = $1 THEN 1 END) as wins
                FROM tournament_matches
                WHERE hypothesis_a_id = $1 OR hypothesis_b_id = $1
                """,
                hypothesis_id,
            )
            if row["total"] == 0:
                return 0.0
            return row["wins"] / row["total"]

    async def get_match_count(self, goal_id: Optional[str] = None) -> int:
        """Get total count of matches."""
        async with self._acquire_connection() as conn:
            if goal_id:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM tournament_matches tm
                    JOIN hypotheses h ON tm.hypothesis_a_id = h.id
                    WHERE h.research_goal_id = $1
                    """,
                    goal_id,
                )
            else:
                count = await conn.fetchval("SELECT COUNT(*) FROM tournament_matches")
            return count

    def _row_to_match(self, row: asyncpg.Record) -> TournamentMatch:
        """Convert database row to TournamentMatch."""
        debate_turns = []
        if row["debate_turns"]:
            turns_data = json.loads(row["debate_turns"])
            debate_turns = [DebateTurn(**t) for t in turns_data]

        return TournamentMatch(
            id=row["id"],
            hypothesis_a_id=row["hypothesis_a_id"],
            hypothesis_b_id=row["hypothesis_b_id"],
            debate_turns=debate_turns,
            is_multi_turn=row["is_multi_turn"],
            winner_id=row["winner_id"],
            decision_rationale=row["decision_rationale"],
            comparison_criteria=json.loads(row["comparison_criteria"]) if row["comparison_criteria"] else [],
            elo_change_a=row["elo_change_a"],
            elo_change_b=row["elo_change_b"],
            created_at=row["created_at"],
        )

    # =========================================================================
    # Tournament State
    # =========================================================================

    async def save_tournament_state(self, state: TournamentState) -> TournamentState:
        """Save tournament state."""
        state.updated_at = datetime.now()
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO tournament_states (
                    research_goal_id, hypotheses, elo_ratings, match_history,
                    total_matches, win_patterns, loss_patterns, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (research_goal_id) DO UPDATE SET
                    hypotheses = $2, elo_ratings = $3, match_history = $4,
                    total_matches = $5, win_patterns = $6, loss_patterns = $7, updated_at = $8
                """,
                state.research_goal_id,
                json.dumps(state.hypotheses),
                json.dumps(state.elo_ratings),
                json.dumps(state.match_history),
                state.total_matches,
                json.dumps(state.win_patterns),
                json.dumps(state.loss_patterns),
                state.updated_at,
            )
        return state

    async def get_tournament_state(self, goal_id: str) -> Optional[TournamentState]:
        """Get tournament state."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tournament_states WHERE research_goal_id = $1",
                goal_id,
            )
            if not row:
                return None
            return TournamentState(
                research_goal_id=row["research_goal_id"],
                hypotheses=json.loads(row["hypotheses"]) if row["hypotheses"] else [],
                elo_ratings=json.loads(row["elo_ratings"]) if row["elo_ratings"] else {},
                match_history=json.loads(row["match_history"]) if row["match_history"] else [],
                total_matches=row["total_matches"],
                win_patterns=json.loads(row["win_patterns"]) if row["win_patterns"] else [],
                loss_patterns=json.loads(row["loss_patterns"]) if row["loss_patterns"] else [],
                updated_at=row["updated_at"],
            )

    # =========================================================================
    # Proximity Graph
    # =========================================================================

    async def save_proximity_graph(self, graph: ProximityGraph) -> ProximityGraph:
        """Save proximity graph."""
        graph.updated_at = datetime.now()
        async with self._acquire_connection() as conn:
            async with conn.transaction():
                # Upsert graph metadata
                await conn.execute(
                    """
                    INSERT INTO proximity_graphs (research_goal_id, updated_at)
                    VALUES ($1, $2)
                    ON CONFLICT (research_goal_id) DO UPDATE SET updated_at = $2
                    """,
                    graph.research_goal_id,
                    graph.updated_at,
                )

                # Delete existing edges and clusters for this goal
                await conn.execute(
                    "DELETE FROM proximity_edges WHERE research_goal_id = $1",
                    graph.research_goal_id,
                )
                await conn.execute(
                    "DELETE FROM hypothesis_clusters WHERE research_goal_id = $1",
                    graph.research_goal_id,
                )

                # Insert new edges
                for edge in graph.edges:
                    await conn.execute(
                        """
                        INSERT INTO proximity_edges (
                            research_goal_id, hypothesis_a_id, hypothesis_b_id,
                            similarity_score, shared_concepts
                        ) VALUES ($1, $2, $3, $4, $5)
                        """,
                        graph.research_goal_id,
                        edge.hypothesis_a_id,
                        edge.hypothesis_b_id,
                        edge.similarity_score,
                        json.dumps(edge.shared_concepts),
                    )

                # Insert new clusters
                for cluster in graph.clusters:
                    await conn.execute(
                        """
                        INSERT INTO hypothesis_clusters (
                            id, research_goal_id, name, hypothesis_ids,
                            representative_id, common_themes
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        cluster.id,
                        graph.research_goal_id,
                        cluster.name,
                        json.dumps(cluster.hypothesis_ids),
                        cluster.representative_id,
                        json.dumps(cluster.common_themes),
                    )

        return graph

    async def get_proximity_graph(self, goal_id: str) -> Optional[ProximityGraph]:
        """Get proximity graph."""
        async with self._acquire_connection() as conn:
            # Check if graph exists
            graph_row = await conn.fetchrow(
                "SELECT * FROM proximity_graphs WHERE research_goal_id = $1",
                goal_id,
            )
            if not graph_row:
                return None

            # Get edges
            edge_rows = await conn.fetch(
                "SELECT * FROM proximity_edges WHERE research_goal_id = $1",
                goal_id,
            )
            edges = [
                ProximityEdge(
                    hypothesis_a_id=row["hypothesis_a_id"],
                    hypothesis_b_id=row["hypothesis_b_id"],
                    similarity_score=row["similarity_score"],
                    shared_concepts=json.loads(row["shared_concepts"]) if row["shared_concepts"] else [],
                )
                for row in edge_rows
            ]

            # Get clusters
            cluster_rows = await conn.fetch(
                "SELECT * FROM hypothesis_clusters WHERE research_goal_id = $1",
                goal_id,
            )
            clusters = [
                HypothesisCluster(
                    id=row["id"],
                    name=row["name"],
                    hypothesis_ids=json.loads(row["hypothesis_ids"]) if row["hypothesis_ids"] else [],
                    representative_id=row["representative_id"],
                    common_themes=json.loads(row["common_themes"]) if row["common_themes"] else [],
                )
                for row in cluster_rows
            ]

            return ProximityGraph(
                research_goal_id=goal_id,
                edges=edges,
                clusters=clusters,
                updated_at=graph_row["updated_at"],
            )

    async def add_proximity_edge(
        self,
        goal_id: str,
        edge: ProximityEdge
    ) -> ProximityEdge:
        """Add a single edge to the proximity graph."""
        async with self._acquire_connection() as conn:
            # Ensure graph exists
            await conn.execute(
                """
                INSERT INTO proximity_graphs (research_goal_id, updated_at)
                VALUES ($1, NOW())
                ON CONFLICT (research_goal_id) DO UPDATE SET updated_at = NOW()
                """,
                goal_id,
            )
            # Insert edge
            await conn.execute(
                """
                INSERT INTO proximity_edges (
                    research_goal_id, hypothesis_a_id, hypothesis_b_id,
                    similarity_score, shared_concepts
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (research_goal_id, hypothesis_a_id, hypothesis_b_id)
                DO UPDATE SET similarity_score = $4, shared_concepts = $5
                """,
                goal_id,
                edge.hypothesis_a_id,
                edge.hypothesis_b_id,
                edge.similarity_score,
                json.dumps(edge.shared_concepts),
            )
        return edge

    async def get_similar_hypotheses(
        self,
        hypothesis_id: str,
        min_similarity: float = 0.7
    ) -> List[tuple[str, float]]:
        """Get hypotheses similar to a given hypothesis."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    CASE WHEN hypothesis_a_id = $1 THEN hypothesis_b_id ELSE hypothesis_a_id END as similar_id,
                    similarity_score
                FROM proximity_edges
                WHERE (hypothesis_a_id = $1 OR hypothesis_b_id = $1)
                    AND similarity_score >= $2
                ORDER BY similarity_score DESC
                """,
                hypothesis_id,
                min_similarity,
            )
            return [(row["similar_id"], row["similarity_score"]) for row in rows]

    # =========================================================================
    # Meta-Review
    # =========================================================================

    async def save_meta_review(
        self,
        meta_review: MetaReviewCritique
    ) -> MetaReviewCritique:
        """Save meta-review critique."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO meta_reviews (
                    id, research_goal_id, recurring_strengths, recurring_weaknesses,
                    improvement_opportunities, generation_feedback, reflection_feedback,
                    evolution_feedback, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                meta_review.id,
                meta_review.research_goal_id,
                json.dumps(meta_review.recurring_strengths),
                json.dumps(meta_review.recurring_weaknesses),
                json.dumps(meta_review.improvement_opportunities),
                json.dumps(meta_review.generation_feedback),
                json.dumps(meta_review.reflection_feedback),
                json.dumps(meta_review.evolution_feedback),
                meta_review.created_at,
            )
        return meta_review

    async def get_meta_review(self, goal_id: str) -> Optional[MetaReviewCritique]:
        """Get latest meta-review."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM meta_reviews
                WHERE research_goal_id = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                goal_id,
            )
            if not row:
                return None
            return self._row_to_meta_review(row)

    async def get_all_meta_reviews(self, goal_id: str) -> List[MetaReviewCritique]:
        """Get all meta-reviews for a goal."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM meta_reviews
                WHERE research_goal_id = $1
                ORDER BY created_at DESC
                """,
                goal_id,
            )
            return [self._row_to_meta_review(row) for row in rows]

    def _row_to_meta_review(self, row: asyncpg.Record) -> MetaReviewCritique:
        """Convert database row to MetaReviewCritique."""
        return MetaReviewCritique(
            id=row["id"],
            research_goal_id=row["research_goal_id"],
            recurring_strengths=json.loads(row["recurring_strengths"]) if row["recurring_strengths"] else [],
            recurring_weaknesses=json.loads(row["recurring_weaknesses"]) if row["recurring_weaknesses"] else [],
            improvement_opportunities=json.loads(row["improvement_opportunities"]) if row["improvement_opportunities"] else [],
            generation_feedback=json.loads(row["generation_feedback"]) if row["generation_feedback"] else [],
            reflection_feedback=json.loads(row["reflection_feedback"]) if row["reflection_feedback"] else [],
            evolution_feedback=json.loads(row["evolution_feedback"]) if row["evolution_feedback"] else [],
            created_at=row["created_at"],
        )

    # =========================================================================
    # Research Overview
    # =========================================================================

    async def save_research_overview(
        self,
        overview: ResearchOverview
    ) -> ResearchOverview:
        """Save research overview."""
        overview.updated_at = datetime.now()
        async with self._acquire_connection() as conn:
            async with conn.transaction():
                # Upsert overview
                await conn.execute(
                    """
                    INSERT INTO research_overviews (
                        id, research_goal_id, executive_summary, current_knowledge_boundary,
                        top_hypotheses_summary, key_literature, output_format, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO UPDATE SET
                        executive_summary = $3, current_knowledge_boundary = $4,
                        top_hypotheses_summary = $5, key_literature = $6,
                        output_format = $7, updated_at = $9
                    """,
                    overview.id,
                    overview.research_goal_id,
                    overview.executive_summary,
                    overview.current_knowledge_boundary,
                    json.dumps(overview.top_hypotheses_summary),
                    json.dumps([c.model_dump() for c in overview.key_literature]),
                    overview.output_format,
                    overview.created_at,
                    overview.updated_at,
                )

                # Delete existing directions and contacts
                await conn.execute(
                    "DELETE FROM research_directions WHERE research_overview_id = $1",
                    overview.id,
                )
                await conn.execute(
                    "DELETE FROM research_contacts WHERE research_overview_id = $1",
                    overview.id,
                )

                # Insert directions
                for i, direction in enumerate(overview.research_directions):
                    await conn.execute(
                        """
                        INSERT INTO research_directions (
                            research_overview_id, name, description, justification,
                            suggested_experiments, example_topics, related_hypothesis_ids, display_order
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        overview.id,
                        direction.name,
                        direction.description,
                        direction.justification,
                        json.dumps(direction.suggested_experiments),
                        json.dumps(direction.example_topics),
                        json.dumps(direction.related_hypothesis_ids),
                        i,
                    )

                # Insert contacts
                for i, contact in enumerate(overview.suggested_contacts):
                    await conn.execute(
                        """
                        INSERT INTO research_contacts (
                            research_overview_id, name, affiliation, expertise,
                            relevance_reasoning, publications, display_order
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        overview.id,
                        contact.name,
                        contact.affiliation,
                        json.dumps(contact.expertise),
                        contact.relevance_reasoning,
                        json.dumps(contact.publications),
                        i,
                    )

        return overview

    async def get_research_overview(self, goal_id: str) -> Optional[ResearchOverview]:
        """Get research overview."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM research_overviews
                WHERE research_goal_id = $1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                goal_id,
            )
            if not row:
                return None

            # Get directions
            direction_rows = await conn.fetch(
                """
                SELECT * FROM research_directions
                WHERE research_overview_id = $1
                ORDER BY display_order
                """,
                row["id"],
            )
            directions = [
                ResearchDirection(
                    name=r["name"],
                    description=r["description"],
                    justification=r["justification"],
                    suggested_experiments=json.loads(r["suggested_experiments"]) if r["suggested_experiments"] else [],
                    example_topics=json.loads(r["example_topics"]) if r["example_topics"] else [],
                    related_hypothesis_ids=json.loads(r["related_hypothesis_ids"]) if r["related_hypothesis_ids"] else [],
                )
                for r in direction_rows
            ]

            # Get contacts
            contact_rows = await conn.fetch(
                """
                SELECT * FROM research_contacts
                WHERE research_overview_id = $1
                ORDER BY display_order
                """,
                row["id"],
            )
            contacts = [
                ResearchContact(
                    name=r["name"],
                    affiliation=r["affiliation"],
                    expertise=json.loads(r["expertise"]) if r["expertise"] else [],
                    relevance_reasoning=r["relevance_reasoning"],
                    publications=json.loads(r["publications"]) if r["publications"] else [],
                )
                for r in contact_rows
            ]

            return ResearchOverview(
                id=row["id"],
                research_goal_id=row["research_goal_id"],
                executive_summary=row["executive_summary"],
                current_knowledge_boundary=row["current_knowledge_boundary"],
                research_directions=directions,
                top_hypotheses_summary=json.loads(row["top_hypotheses_summary"]) if row["top_hypotheses_summary"] else [],
                suggested_contacts=contacts,
                key_literature=[Citation(**c) for c in json.loads(row["key_literature"])] if row["key_literature"] else [],
                output_format=row["output_format"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    # =========================================================================
    # Agent Tasks
    # =========================================================================

    async def add_task(self, task: AgentTask) -> AgentTask:
        """Add a task to the queue."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO agent_tasks (
                    id, agent_type, task_type, priority, parameters,
                    status, result, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                task.id,
                task.agent_type.value,
                task.task_type,
                task.priority,
                json.dumps(task.parameters),
                task.status,
                json.dumps(task.result) if task.result else None,
                task.created_at,
            )
            logger.debug("Task added", task_id=task.id, agent=task.agent_type)
        return task

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agent_tasks WHERE id = $1",
                task_id,
            )
            if not row:
                return None
            return self._row_to_task(row)

    async def get_pending_tasks(
        self,
        agent_type: Optional[AgentType] = None,
        limit: int = 100
    ) -> List[AgentTask]:
        """Get pending tasks."""
        async with self._acquire_connection() as conn:
            if agent_type:
                rows = await conn.fetch(
                    """
                    SELECT * FROM agent_tasks
                    WHERE status = 'pending' AND agent_type = $1
                    ORDER BY priority DESC, created_at ASC
                    LIMIT $2
                    """,
                    agent_type.value,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM agent_tasks
                    WHERE status = 'pending'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT $1
                    """,
                    limit,
                )
            return [self._row_to_task(row) for row in rows]

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> AgentTask:
        """Update task status."""
        async with self._acquire_connection() as conn:
            now = datetime.now()
            if status == "running":
                await conn.execute(
                    """
                    UPDATE agent_tasks SET status = $2, started_at = $3
                    WHERE id = $1
                    """,
                    task_id,
                    status,
                    now,
                )
            elif status in ("complete", "failed"):
                await conn.execute(
                    """
                    UPDATE agent_tasks SET status = $2, result = $3, completed_at = $4
                    WHERE id = $1
                    """,
                    task_id,
                    status,
                    json.dumps(result) if result else None,
                    now,
                )
            else:
                await conn.execute(
                    "UPDATE agent_tasks SET status = $2 WHERE id = $1",
                    task_id,
                    status,
                )
            return await self.get_task(task_id)

    async def claim_next_task(
        self,
        agent_type: AgentType,
        worker_id: str
    ) -> Optional[AgentTask]:
        """Atomically claim the next available task."""
        async with self._acquire_connection() as conn:
            # Use SELECT FOR UPDATE SKIP LOCKED for atomic claiming
            row = await conn.fetchrow(
                """
                UPDATE agent_tasks SET
                    status = 'running',
                    started_at = NOW(),
                    worker_id = $2
                WHERE id = (
                    SELECT id FROM agent_tasks
                    WHERE status = 'pending' AND agent_type = $1
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
                """,
                agent_type.value,
                worker_id,
            )
            if not row:
                return None
            return self._row_to_task(row)

    def _row_to_task(self, row: asyncpg.Record) -> AgentTask:
        """Convert database row to AgentTask."""
        return AgentTask(
            id=row["id"],
            agent_type=AgentType(row["agent_type"]),
            task_type=row["task_type"],
            priority=row["priority"],
            parameters=json.loads(row["parameters"]) if row["parameters"] else {},
            status=row["status"],
            result=json.loads(row["result"]) if row["result"] else None,
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    # =========================================================================
    # System Statistics
    # =========================================================================

    async def save_statistics(self, stats: SystemStatistics) -> SystemStatistics:
        """Save system statistics."""
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO system_statistics (
                    research_goal_id, total_hypotheses, hypotheses_pending_review,
                    hypotheses_in_tournament, hypotheses_archived,
                    tournament_matches_completed, tournament_convergence_score,
                    generation_success_rate, evolution_improvement_rate,
                    method_effectiveness, agent_weights, computed_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                stats.research_goal_id,
                stats.total_hypotheses,
                stats.hypotheses_pending_review,
                stats.hypotheses_in_tournament,
                stats.hypotheses_archived,
                stats.tournament_matches_completed,
                stats.tournament_convergence_score,
                stats.generation_success_rate,
                stats.evolution_improvement_rate,
                json.dumps(stats.method_effectiveness),
                json.dumps(stats.agent_weights),
                stats.computed_at,
            )
        return stats

    async def get_latest_statistics(self, goal_id: str) -> Optional[SystemStatistics]:
        """Get latest statistics."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM system_statistics
                WHERE research_goal_id = $1
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                goal_id,
            )
            if not row:
                return None
            return SystemStatistics(
                research_goal_id=row["research_goal_id"],
                total_hypotheses=row["total_hypotheses"],
                hypotheses_pending_review=row["hypotheses_pending_review"],
                hypotheses_in_tournament=row["hypotheses_in_tournament"],
                hypotheses_archived=row["hypotheses_archived"],
                tournament_matches_completed=row["tournament_matches_completed"],
                tournament_convergence_score=row["tournament_convergence_score"],
                generation_success_rate=row["generation_success_rate"],
                evolution_improvement_rate=row["evolution_improvement_rate"],
                method_effectiveness=json.loads(row["method_effectiveness"]) if row["method_effectiveness"] else {},
                agent_weights=json.loads(row["agent_weights"]) if row["agent_weights"] else {},
                computed_at=row["computed_at"],
            )

    # =========================================================================
    # Context Memory (Checkpoints)
    # =========================================================================

    async def save_checkpoint(self, checkpoint: ContextMemory) -> ContextMemory:
        """Save a checkpoint."""
        checkpoint.updated_at = datetime.now()
        async with self._acquire_connection() as conn:
            await conn.execute(
                """
                INSERT INTO context_memory (
                    research_goal_id, research_plan_config, tournament_state_snapshot,
                    proximity_graph_snapshot, latest_meta_review_id, latest_research_overview_id,
                    system_statistics_snapshot, hypothesis_ids, review_ids, iteration_count,
                    scientist_reviews, scientist_hypotheses, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                checkpoint.research_goal_id,
                json.dumps(checkpoint.research_plan_config.model_dump()) if checkpoint.research_plan_config else None,
                json.dumps(checkpoint.tournament_state.model_dump()) if checkpoint.tournament_state else None,
                json.dumps(checkpoint.proximity_graph.model_dump()) if checkpoint.proximity_graph else None,
                checkpoint.latest_meta_review.id if checkpoint.latest_meta_review else None,
                checkpoint.latest_research_overview.id if checkpoint.latest_research_overview else None,
                json.dumps(checkpoint.system_statistics.model_dump()) if checkpoint.system_statistics else None,
                json.dumps(checkpoint.hypothesis_ids),
                json.dumps(checkpoint.review_ids),
                checkpoint.iteration_count,
                json.dumps(checkpoint.scientist_reviews),
                json.dumps(checkpoint.scientist_hypotheses),
                checkpoint.created_at,
                checkpoint.updated_at,
            )
            logger.info("Checkpoint saved", goal_id=checkpoint.research_goal_id, iteration=checkpoint.iteration_count)
        return checkpoint

    async def get_latest_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Get latest checkpoint."""
        async with self._acquire_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM context_memory
                WHERE research_goal_id = $1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                goal_id,
            )
            if not row:
                return None
            return self._row_to_checkpoint(row)

    async def get_all_checkpoints(self, goal_id: str) -> List[ContextMemory]:
        """Get all checkpoints."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM context_memory
                WHERE research_goal_id = $1
                ORDER BY updated_at DESC
                """,
                goal_id,
            )
            return [self._row_to_checkpoint(row) for row in rows]

    def _row_to_checkpoint(self, row: asyncpg.Record) -> ContextMemory:
        """Convert database row to ContextMemory."""
        return ContextMemory(
            research_goal_id=row["research_goal_id"],
            research_plan_config=ResearchPlanConfiguration(**json.loads(row["research_plan_config"])) if row["research_plan_config"] else None,
            tournament_state=TournamentState(**json.loads(row["tournament_state_snapshot"])) if row["tournament_state_snapshot"] else None,
            proximity_graph=None,  # Would need to reconstruct from edges/clusters
            latest_meta_review=None,  # Would need to fetch by ID
            latest_research_overview=None,  # Would need to fetch by ID
            system_statistics=SystemStatistics(**json.loads(row["system_statistics_snapshot"])) if row["system_statistics_snapshot"] else None,
            hypothesis_ids=json.loads(row["hypothesis_ids"]) if row["hypothesis_ids"] else [],
            review_ids=json.loads(row["review_ids"]) if row["review_ids"] else [],
            iteration_count=row["iteration_count"],
            scientist_reviews=json.loads(row["scientist_reviews"]) if row["scientist_reviews"] else [],
            scientist_hypotheses=json.loads(row["scientist_hypotheses"]) if row["scientist_hypotheses"] else [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # =========================================================================
    # Scientist Feedback
    # =========================================================================

    async def add_feedback(self, feedback: ScientistFeedback) -> ScientistFeedback:
        """Store scientist feedback."""
        async with self._acquire_connection() as conn:
            # Get research_goal_id from hypothesis if available
            goal_id = None
            if feedback.hypothesis_id:
                hyp = await self.get_hypothesis(feedback.hypothesis_id)
                if hyp:
                    goal_id = hyp.research_goal_id

            await conn.execute(
                """
                INSERT INTO scientist_feedback (
                    id, research_goal_id, hypothesis_id, feedback_type, content, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                feedback.id,
                goal_id,
                feedback.hypothesis_id,
                feedback.feedback_type,
                feedback.content,
                feedback.created_at,
            )
        return feedback

    async def get_feedback_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[ScientistFeedback]:
        """Get feedback for a hypothesis."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM scientist_feedback
                WHERE hypothesis_id = $1
                ORDER BY created_at DESC
                """,
                hypothesis_id,
            )
            return [self._row_to_feedback(row) for row in rows]

    async def get_all_feedback(self, goal_id: str) -> List[ScientistFeedback]:
        """Get all feedback for a goal."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM scientist_feedback
                WHERE research_goal_id = $1
                ORDER BY created_at DESC
                """,
                goal_id,
            )
            return [self._row_to_feedback(row) for row in rows]

    def _row_to_feedback(self, row: asyncpg.Record) -> ScientistFeedback:
        """Convert database row to ScientistFeedback."""
        return ScientistFeedback(
            id=row["id"],
            hypothesis_id=row["hypothesis_id"],
            feedback_type=row["feedback_type"],
            content=row["content"],
            created_at=row["created_at"],
        )

    # =========================================================================
    # Chat Messages
    # =========================================================================

    async def add_chat_message(self, message: ChatMessage) -> ChatMessage:
        """Store a chat message."""
        async with self._acquire_connection() as conn:
            # Infer goal_id from hypothesis references
            goal_id = None
            if message.hypothesis_references:
                hyp = await self.get_hypothesis(message.hypothesis_references[0])
                if hyp:
                    goal_id = hyp.research_goal_id

            await conn.execute(
                """
                INSERT INTO chat_messages (
                    id, research_goal_id, role, content, hypothesis_references, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                message.id,
                goal_id,
                message.role,
                message.content,
                json.dumps(message.hypothesis_references),
                message.created_at,
            )
        return message

    async def get_chat_history(
        self,
        goal_id: str,
        limit: int = 100
    ) -> List[ChatMessage]:
        """Get chat history."""
        async with self._acquire_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM chat_messages
                WHERE research_goal_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                goal_id,
                limit,
            )
            return [
                ChatMessage(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    hypothesis_references=json.loads(row["hypothesis_references"]) if row["hypothesis_references"] else [],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def clear_all(self, goal_id: Optional[str] = None) -> None:
        """Clear all stored data."""
        async with self._acquire_connection() as conn:
            if goal_id:
                await conn.execute(
                    "DELETE FROM research_goals WHERE id = $1",
                    goal_id,
                )
                logger.info("Research goal and related data cleared", goal_id=goal_id)
            else:
                # Truncate all tables (respects foreign key order)
                await conn.execute("""
                    TRUNCATE TABLE chat_messages, scientist_feedback, context_memory,
                    system_statistics, agent_tasks, research_contacts, research_directions,
                    research_overviews, meta_reviews, hypothesis_clusters, proximity_edges,
                    proximity_graphs, tournament_states, tournament_matches, reviews,
                    hypotheses, research_plan_configurations, research_goals CASCADE
                """)
                logger.warning("All storage cleared")

    async def get_stats(self) -> Dict[str, int]:
        """Get storage statistics."""
        async with self._acquire_connection() as conn:
            stats = {}
            tables = [
                "research_goals", "hypotheses", "reviews", "tournament_matches",
                "proximity_edges", "hypothesis_clusters", "meta_reviews",
                "research_overviews", "agent_tasks", "context_memory",
                "scientist_feedback", "chat_messages"
            ]
            for table in tables:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                stats[table] = count
            return stats

    # =========================================================================
    # Transaction Support
    # =========================================================================

    @asynccontextmanager
    async def transaction(self):
        """Safe transaction context manager with automatic cleanup.

        Usage:
            async with storage.transaction() as conn:
                await conn.execute(...)
                await conn.execute(...)
            # Auto-commits on success, auto-rollbacks on exception

        This prevents connection leaks that occur when exceptions happen
        between begin_transaction() and commit/rollback calls.
        """
        conn = await self._pool.acquire()
        tx = conn.transaction()
        try:
            await tx.start()
            yield conn
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise
        finally:
            await self._pool.release(conn)

    async def begin_transaction(self) -> Any:
        """Begin a database transaction.

        .. deprecated::
            This method is deprecated and may be removed in a future version.
            Use the transaction() context manager instead to ensure proper
            cleanup and avoid connection leaks.

        WARNING: This method can leak connections if exceptions occur before
        commit/rollback is called. The context manager pattern is strongly
        recommended:

        Example (Recommended)::

            async with storage.transaction() as conn:
                # Your transactional code here
                await conn.execute("INSERT ...")

        Example (Deprecated)::

            # NOT RECOMMENDED - can leak connections!
            txn = await storage.begin_transaction()
            try:
                await txn["conn"].execute("INSERT ...")
                await storage.commit_transaction(txn)
            except:
                await storage.rollback_transaction(txn)
                raise

        Returns:
            Dict with 'conn' and 'transaction' keys.
        """
        logger.warning(
            "begin_transaction() is deprecated - use transaction() context manager instead",
            stack_info=False
        )
        conn = await self._pool.acquire()
        transaction = conn.transaction()
        await transaction.start()
        return {"conn": conn, "transaction": transaction}

    async def commit_transaction(self, transaction: Any) -> None:
        """Commit a transaction.

        .. deprecated::
            This method is deprecated. Use the transaction() context manager instead.

        Args:
            transaction: Dict returned by begin_transaction().

        Example (Recommended)::

            async with storage.transaction() as conn:
                await conn.execute("INSERT ...")
                # Auto-commits on success

        Example (Deprecated)::

            # NOT RECOMMENDED
            txn = await storage.begin_transaction()
            await storage.commit_transaction(txn)
        """
        logger.warning(
            "commit_transaction() is deprecated - use transaction() context manager instead",
            stack_info=False
        )
        conn = None
        try:
            if transaction is None:
                logger.error("commit_transaction called with None transaction")
                return
            if not isinstance(transaction, dict):
                logger.error("commit_transaction called with invalid transaction type")
                return
            if "transaction" not in transaction or "conn" not in transaction:
                logger.error("commit_transaction called with malformed transaction dict")
                return

            conn = transaction["conn"]
            await transaction["transaction"].commit()
        finally:
            # Defensive cleanup - ensure connection is released even if transaction is malformed
            if conn is not None:
                await self._pool.release(conn)
            elif transaction is not None and isinstance(transaction, dict) and "conn" in transaction:
                await self._pool.release(transaction["conn"])

    async def rollback_transaction(self, transaction: Any) -> None:
        """Rollback a transaction.

        .. deprecated::
            This method is deprecated. Use the transaction() context manager instead.

        Args:
            transaction: Dict returned by begin_transaction().

        Example (Recommended)::

            async with storage.transaction() as conn:
                await conn.execute("INSERT ...")
                # Auto-rollbacks on exception

        Example (Deprecated)::

            # NOT RECOMMENDED
            txn = await storage.begin_transaction()
            await storage.rollback_transaction(txn)
        """
        logger.warning(
            "rollback_transaction() is deprecated - use transaction() context manager instead",
            stack_info=False
        )
        conn = None
        try:
            if transaction is None:
                logger.error("rollback_transaction called with None transaction")
                return
            if not isinstance(transaction, dict):
                logger.error("rollback_transaction called with invalid transaction type")
                return
            if "transaction" not in transaction or "conn" not in transaction:
                logger.error("rollback_transaction called with malformed transaction dict")
                return

            conn = transaction["conn"]
            await transaction["transaction"].rollback()
        finally:
            # Defensive cleanup - ensure connection is released even if transaction is malformed
            if conn is not None:
                await self._pool.release(conn)
            elif transaction is not None and isinstance(transaction, dict) and "conn" in transaction:
                await self._pool.release(transaction["conn"])
