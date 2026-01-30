"""
Test suite for STOR-H4: Database Indexes for Performance

This test verifies that:
1. Index creation migration runs successfully
2. Indexes are idempotent (can run multiple times)
3. Key indexes are created correctly
4. Query performance is improved with indexes

Usage:
    pytest 05_tests/test_stor_h4_indexes.py -v
"""

import pytest
import time
from datetime import datetime

from src.storage.postgres import PostgreSQLStorage
from src.storage.memory import MemoryStorage

# Import schemas
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "03_architecture"))

from schemas import (
    ResearchGoal,
    Hypothesis,
    HypothesisStatus,
    GenerationMethod,
    Review,
    ReviewType,
    AgentTask,
    AgentType,
)


@pytest.fixture
async def postgres_storage():
    """Fixture providing connected PostgreSQL storage."""
    storage = PostgreSQLStorage()
    try:
        await storage.connect()
        yield storage
    except Exception as e:
        # If PostgreSQL is not available, skip tests
        pytest.skip(f"PostgreSQL not available: {e}")
    finally:
        await storage.disconnect()


@pytest.fixture
async def clean_postgres(postgres_storage):
    """Fixture providing clean PostgreSQL storage."""
    await postgres_storage.clear_all()
    yield postgres_storage
    await postgres_storage.clear_all()


class TestIndexCreation:
    """Test index creation functionality."""

    @pytest.mark.asyncio
    async def test_create_indexes_succeeds(self, postgres_storage):
        """Test that create_indexes() runs without errors."""
        await postgres_storage.create_indexes()
        # Should not raise any exceptions

    @pytest.mark.asyncio
    async def test_create_indexes_idempotent(self, postgres_storage):
        """Test that create_indexes() can be called multiple times."""
        # First call
        await postgres_storage.create_indexes()

        # Second call should not raise errors
        await postgres_storage.create_indexes()

        # Third call for good measure
        await postgres_storage.create_indexes()

    @pytest.mark.asyncio
    async def test_key_indexes_exist(self, postgres_storage):
        """Test that key indexes from migration 001 are created."""
        await postgres_storage.create_indexes()

        # Check for critical indexes
        expected_indexes = [
            'idx_hypotheses_goal_status',
            'idx_hypotheses_goal_elo',
            'idx_agent_tasks_queue',
            'idx_reviews_hypothesis_type',
            'idx_proximity_edges_goal_id',
            'idx_context_memory_goal_updated',
        ]

        async with postgres_storage._acquire_connection() as conn:
            for index_name in expected_indexes:
                result = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE schemaname = 'public' AND indexname = $1
                    )
                    """,
                    index_name
                )
                assert result, f"Index {index_name} should exist after migration"

    @pytest.mark.asyncio
    async def test_analyze_index_usage_function_exists(self, postgres_storage):
        """Test that the analyze_index_usage() function is created."""
        await postgres_storage.create_indexes()

        async with postgres_storage._acquire_connection() as conn:
            # Check function exists
            result = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc
                    WHERE proname = 'analyze_index_usage'
                )
                """
            )
            assert result, "analyze_index_usage() function should exist"

            # Try calling the function
            stats = await conn.fetch("SELECT * FROM analyze_index_usage() LIMIT 5")
            # Should return results (or empty set if no index usage yet)
            assert isinstance(stats, list)


class TestIndexPerformance:
    """Test that indexes improve query performance."""

    @pytest.mark.asyncio
    async def test_hypothesis_filtering_performance(self, clean_postgres):
        """Test that filtering hypotheses by goal + status is fast with indexes."""
        storage = clean_postgres
        await storage.create_indexes()

        # Create test data
        goal = ResearchGoal(
            id="test_goal_perf",
            description="Performance test goal"
        )
        await storage.add_research_goal(goal)

        # Create 100 hypotheses
        for i in range(100):
            hyp = Hypothesis(
                id=f"hyp_{i}",
                research_goal_id=goal.id,
                title=f"Test Hypothesis {i}",
                summary="Test summary",
                hypothesis_statement="Test statement",
                rationale="Test rationale",
                generation_method=GenerationMethod.LITERATURE_EXPLORATION,
                status=HypothesisStatus.IN_TOURNAMENT if i % 2 == 0 else HypothesisStatus.GENERATED,
            )
            await storage.add_hypothesis(hyp)

        # Measure query time
        start = time.time()
        results = await storage.get_hypotheses_by_goal(
            goal.id,
            status=HypothesisStatus.IN_TOURNAMENT
        )
        elapsed = time.time() - start

        # Should be fast (< 50ms for 100 hypotheses)
        assert len(results) == 50
        assert elapsed < 0.05, f"Query took {elapsed*1000:.1f}ms (expected < 50ms)"

    @pytest.mark.asyncio
    async def test_top_hypotheses_performance(self, clean_postgres):
        """Test that getting top hypotheses by Elo is fast with indexes."""
        storage = clean_postgres
        await storage.create_indexes()

        # Create test data
        goal = ResearchGoal(
            id="test_goal_elo",
            description="Elo test goal"
        )
        await storage.add_research_goal(goal)

        # Create 100 hypotheses with varying Elo ratings
        for i in range(100):
            hyp = Hypothesis(
                id=f"hyp_elo_{i}",
                research_goal_id=goal.id,
                title=f"Test Hypothesis {i}",
                summary="Test summary",
                hypothesis_statement="Test statement",
                rationale="Test rationale",
                generation_method=GenerationMethod.LITERATURE_EXPLORATION,
                elo_rating=1200.0 + (i * 10),  # Ratings from 1200 to 2190
            )
            await storage.add_hypothesis(hyp)

        # Measure query time
        start = time.time()
        results = await storage.get_top_hypotheses(n=10, goal_id=goal.id)
        elapsed = time.time() - start

        # Verify results
        assert len(results) == 10
        assert results[0].elo_rating > results[-1].elo_rating  # Sorted descending

        # Should be fast (< 50ms for 100 hypotheses)
        assert elapsed < 0.05, f"Query took {elapsed*1000:.1f}ms (expected < 50ms)"

    @pytest.mark.asyncio
    async def test_task_queue_performance(self, clean_postgres):
        """Test that task queue operations are fast with indexes."""
        storage = clean_postgres
        await storage.create_indexes()

        # Create 100 pending tasks
        for i in range(100):
            task = AgentTask(
                id=f"task_{i}",
                agent_type=AgentType.GENERATION,
                task_type="generate_hypothesis",
                priority=i % 10 + 1,  # Priorities 1-10
                status="pending"
            )
            await storage.add_task(task)

        # Measure query time
        start = time.time()
        tasks = await storage.get_pending_tasks(
            agent_type=AgentType.GENERATION,
            limit=10
        )
        elapsed = time.time() - start

        # Verify results
        assert len(tasks) == 10
        assert tasks[0].priority >= tasks[-1].priority  # Sorted by priority desc

        # Should be fast (< 50ms for 100 tasks)
        assert elapsed < 0.05, f"Query took {elapsed*1000:.1f}ms (expected < 50ms)"


class TestIndexMonitoring:
    """Test index monitoring and analysis functions."""

    @pytest.mark.asyncio
    async def test_index_usage_tracking(self, postgres_storage):
        """Test that we can track index usage statistics."""
        await postgres_storage.create_indexes()

        async with postgres_storage._acquire_connection() as conn:
            # Get index statistics
            stats = await conn.fetch(
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                  AND indexname LIKE 'idx_%'
                ORDER BY indexname
                """
            )

            # Should have multiple indexes
            assert len(stats) > 0, "Should have indexes to monitor"

            # Check structure
            for stat in stats:
                assert 'tablename' in stat
                assert 'indexname' in stat
                assert 'idx_scan' in stat

    @pytest.mark.asyncio
    async def test_analyze_index_usage_function(self, postgres_storage):
        """Test the custom analyze_index_usage() function."""
        await postgres_storage.create_indexes()

        async with postgres_storage._acquire_connection() as conn:
            result = await conn.fetch(
                "SELECT * FROM analyze_index_usage() LIMIT 10"
            )

            # Should return results
            assert isinstance(result, list)

            # If there are results, check structure
            if result:
                assert 'tablename' in result[0]
                assert 'indexname' in result[0]
                assert 'idx_scan' in result[0]


@pytest.mark.asyncio
async def test_migration_script_existence():
    """Test that migration SQL file exists and is readable."""
    migration_file = Path(__file__).parent.parent / "src" / "storage" / "migrations" / "001_add_indexes.sql"

    assert migration_file.exists(), "Migration SQL file should exist"
    assert migration_file.is_file(), "Migration SQL should be a file"

    # Read file to ensure it's valid
    content = migration_file.read_text()
    assert len(content) > 1000, "Migration file should have substantial content"
    assert "CREATE INDEX" in content, "Should contain CREATE INDEX statements"
    assert "CONCURRENTLY" in content, "Should use CONCURRENTLY for safety"
    assert "IF NOT EXISTS" in content, "Should use IF NOT EXISTS for idempotency"


@pytest.mark.asyncio
async def test_migration_documentation_exists():
    """Test that migration documentation exists."""
    readme = Path(__file__).parent.parent / "src" / "storage" / "migrations" / "README.md"

    assert readme.exists(), "Migration README should exist"
    content = readme.read_text()
    assert "001_add_indexes.sql" in content, "Should document migration 001"
    assert "Performance Impact" in content, "Should document performance impact"


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v", "-s"])
