#!/usr/bin/env python3
"""Test storage implementations for AI Co-Scientist.

This module tests both InMemoryStorage and PostgreSQLStorage
to ensure they correctly implement the BaseStorage interface.

Run with:
    # Test in-memory only (no database required)
    pytest test_storage.py -v -k "memory"

    # Test PostgreSQL (requires running database)
    pytest test_storage.py -v -k "postgres"

    # Test all
    pytest test_storage.py -v
"""

import pytest
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root and architecture to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_Architecture"))

from schemas import (
    ResearchGoal,
    Hypothesis,
    HypothesisStatus,
    GenerationMethod,
    Review,
    ReviewType,
    TournamentMatch,
    ExperimentalProtocol,
    Citation,
    ProximityGraph,
    ProximityEdge,
    HypothesisCluster,
    AgentTask,
    AgentType,
)

from src.storage.memory import InMemoryStorage
from src.storage.base import BaseStorage
from src.utils.ids import generate_hypothesis_id, generate_review_id, generate_match_id


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def research_goal():
    """Create a sample research goal."""
    return ResearchGoal(
        id="goal_test_123",
        description="Identify novel drug targets for acute myeloid leukemia",
        constraints=["Focus on FDA-approved compounds", "Avoid known toxicity issues"],
        preferences=["Prioritize oral bioavailability", "Target proteins with existing structures"],
        prior_publications=["10.1038/nature12345", "10.1016/j.cell.2023.01.001"],
        laboratory_context="Academic research lab with access to cell culture and CRISPR screening",
    )


@pytest.fixture
def hypothesis(research_goal):
    """Create a sample hypothesis."""
    return Hypothesis(
        id=generate_hypothesis_id(),
        research_goal_id=research_goal.id,
        title="NPM1 as a Therapeutic Target in AML",
        summary="NPM1 mutations create a unique therapeutic vulnerability",
        hypothesis_statement="Targeting mutant NPM1 localization will selectively kill AML cells",
        rationale="NPM1 mutations are present in 30% of AML cases and cause cytoplasmic mislocalization",
        mechanism="Disrupting NPM1-CRM1 interaction traps mutant NPM1 in nucleus, triggering apoptosis",
        experimental_protocol=ExperimentalProtocol(
            objective="Validate NPM1 as a drug target",
            methodology="Use CRISPR to knockout CRM1 binding domain in NPM1",
            expected_outcomes=["Reduced cell viability in NPM1-mutant lines", "No effect in wildtype"],
            controls=["Wildtype NPM1 cells", "Non-targeting CRISPR"],
            materials=["OCI-AML3 cells", "CRISPR reagents"],
            success_criteria="50% reduction in viability in mutant vs wildtype",
        ),
        literature_citations=[
            Citation(title="NPM1 mutations in AML", relevance="Establishes mutation frequency"),
            Citation(title="CRM1 in nuclear export", relevance="Describes export mechanism"),
        ],
        status=HypothesisStatus.GENERATED,
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1200.0,
    )


@pytest.fixture
def review(hypothesis):
    """Create a sample review."""
    return Review(
        id=generate_review_id(),
        hypothesis_id=hypothesis.id,
        review_type=ReviewType.INITIAL,
        correctness_score=0.85,
        quality_score=0.80,
        novelty_score=0.70,
        testability_score=0.90,
        safety_score=0.95,
        strengths=["Well-grounded in literature", "Clear mechanism"],
        weaknesses=["Limited novelty", "Complex experimental design"],
        suggestions=["Simplify initial experiments", "Add more controls"],
        passed=True,
        rationale="Hypothesis is scientifically sound with good experimental design",
    )


@pytest.fixture
def match(hypothesis):
    """Create a sample tournament match."""
    return TournamentMatch(
        id=generate_match_id(),
        hypothesis_a_id=hypothesis.id,
        hypothesis_b_id="hyp_competitor_456",
        winner_id=hypothesis.id,
        decision_rationale="Hypothesis A has stronger experimental design and literature support",
        comparison_criteria=["novelty", "testability", "feasibility"],
        elo_change_a=16.0,
        elo_change_b=-16.0,
    )


# ============================================================================
# In-Memory Storage Tests
# ============================================================================

class TestInMemoryStorage:
    """Test InMemoryStorage implementation."""

    @pytest.fixture
    async def storage(self):
        """Create and connect storage."""
        storage = InMemoryStorage()
        await storage.connect()
        yield storage
        await storage.disconnect()

    @pytest.mark.asyncio
    async def test_connection(self, storage):
        """Test connect/disconnect and health check."""
        assert await storage.health_check() is True

    @pytest.mark.asyncio
    async def test_research_goal_crud(self, storage, research_goal):
        """Test research goal CRUD operations."""
        # Create
        result = await storage.add_research_goal(research_goal)
        assert result.id == research_goal.id

        # Read
        retrieved = await storage.get_research_goal(research_goal.id)
        assert retrieved is not None
        assert retrieved.description == research_goal.description

        # Update
        research_goal.description = "Updated description"
        await storage.update_research_goal(research_goal)
        updated = await storage.get_research_goal(research_goal.id)
        assert updated.description == "Updated description"

        # List
        all_goals = await storage.get_all_research_goals()
        assert len(all_goals) == 1

        # Delete
        deleted = await storage.delete_research_goal(research_goal.id)
        assert deleted is True
        assert await storage.get_research_goal(research_goal.id) is None

    @pytest.mark.asyncio
    async def test_hypothesis_crud(self, storage, research_goal, hypothesis):
        """Test hypothesis CRUD operations."""
        await storage.add_research_goal(research_goal)

        # Create
        result = await storage.add_hypothesis(hypothesis)
        assert result.id == hypothesis.id

        # Read
        retrieved = await storage.get_hypothesis(hypothesis.id)
        assert retrieved is not None
        assert retrieved.title == hypothesis.title
        assert retrieved.elo_rating == 1200.0

        # Update Elo
        hypothesis.elo_rating = 1250.0
        await storage.update_hypothesis(hypothesis)
        updated = await storage.get_hypothesis(hypothesis.id)
        assert updated.elo_rating == 1250.0

        # Get by goal
        by_goal = await storage.get_hypotheses_by_goal(research_goal.id)
        assert len(by_goal) == 1

        # Get top hypotheses
        top = await storage.get_top_hypotheses(n=5)
        assert len(top) == 1

        # Count
        count = await storage.get_hypothesis_count()
        assert count == 1

        # Delete
        deleted = await storage.delete_hypothesis(hypothesis.id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_review_operations(self, storage, research_goal, hypothesis, review):
        """Test review operations."""
        await storage.add_research_goal(research_goal)
        await storage.add_hypothesis(hypothesis)

        # Add review
        result = await storage.add_review(review)
        assert result.id == review.id

        # Get review
        retrieved = await storage.get_review(review.id)
        assert retrieved is not None
        assert retrieved.passed is True

        # Get reviews for hypothesis
        reviews = await storage.get_reviews_for_hypothesis(hypothesis.id)
        assert len(reviews) == 1

    @pytest.mark.asyncio
    async def test_match_operations(self, storage, research_goal, hypothesis, match):
        """Test tournament match operations."""
        await storage.add_research_goal(research_goal)
        await storage.add_hypothesis(hypothesis)

        # Add match
        result = await storage.add_match(match)
        assert result.id == match.id

        # Get match
        retrieved = await storage.get_match(match.id)
        assert retrieved is not None
        assert retrieved.winner_id == hypothesis.id

        # Get matches for hypothesis
        matches = await storage.get_matches_for_hypothesis(hypothesis.id)
        assert len(matches) == 1

        # Win rate
        win_rate = await storage.get_hypothesis_win_rate(hypothesis.id)
        assert win_rate == 1.0

    @pytest.mark.asyncio
    async def test_proximity_graph(self, storage, research_goal, hypothesis):
        """Test proximity graph operations."""
        await storage.add_research_goal(research_goal)
        await storage.add_hypothesis(hypothesis)

        # Create graph with edge
        edge = ProximityEdge(
            hypothesis_a_id=hypothesis.id,
            hypothesis_b_id="hyp_other_123",
            similarity_score=0.85,
            shared_concepts=["NPM1", "AML", "targeted therapy"],
        )
        cluster = HypothesisCluster(
            id="cluster_1",
            name="NPM1-focused hypotheses",
            hypothesis_ids=[hypothesis.id, "hyp_other_123"],
            common_themes=["NPM1 targeting"],
        )
        graph = ProximityGraph(
            research_goal_id=research_goal.id,
            edges=[edge],
            clusters=[cluster],
        )

        # Save graph
        result = await storage.save_proximity_graph(graph)
        assert result.research_goal_id == research_goal.id

        # Get graph
        retrieved = await storage.get_proximity_graph(research_goal.id)
        assert retrieved is not None
        assert len(retrieved.edges) == 1
        assert len(retrieved.clusters) == 1

        # Get similar hypotheses
        similar = await storage.get_similar_hypotheses(hypothesis.id, min_similarity=0.8)
        assert len(similar) == 1
        assert similar[0][0] == "hyp_other_123"
        assert similar[0][1] == 0.85

    @pytest.mark.asyncio
    async def test_task_operations(self, storage):
        """Test agent task operations."""
        task = AgentTask(
            id="task_test_1",
            agent_type=AgentType.GENERATION,
            task_type="generate_hypothesis",
            priority=5,
            parameters={"goal_id": "goal_123"},
            status="pending",
        )

        # Add task
        result = await storage.add_task(task)
        assert result.id == task.id

        # Get pending tasks
        pending = await storage.get_pending_tasks(AgentType.GENERATION)
        assert len(pending) == 1

        # Claim task
        claimed = await storage.claim_next_task(AgentType.GENERATION, "worker_1")
        assert claimed is not None
        assert claimed.status == "running"

        # Update status
        updated = await storage.update_task_status(task.id, "complete", {"result": "success"})
        assert updated.status == "complete"

    @pytest.mark.asyncio
    async def test_stats(self, storage, research_goal, hypothesis, review, match):
        """Test storage statistics."""
        await storage.add_research_goal(research_goal)
        await storage.add_hypothesis(hypothesis)
        await storage.add_review(review)
        await storage.add_match(match)

        stats = await storage.get_stats()
        assert stats["research_goals"] == 1
        assert stats["hypotheses"] == 1
        assert stats["reviews"] == 1
        assert stats["matches"] == 1

    @pytest.mark.asyncio
    async def test_clear_all(self, storage, research_goal, hypothesis):
        """Test clearing all data."""
        await storage.add_research_goal(research_goal)
        await storage.add_hypothesis(hypothesis)

        await storage.clear_all()

        stats = await storage.get_stats()
        assert stats["research_goals"] == 0
        assert stats["hypotheses"] == 0


# ============================================================================
# PostgreSQL Storage Tests (requires running database)
# ============================================================================

class TestPostgreSQLStorage:
    """Test PostgreSQLStorage implementation.

    These tests require a running PostgreSQL database with the schema applied.
    Skip these tests if no database is available.
    """

    @pytest.fixture
    async def storage(self):
        """Create and connect PostgreSQL storage."""
        try:
            from src.storage.postgres import PostgreSQLStorage
            from src.config import settings

            storage = PostgreSQLStorage(database_url=settings.database_url)
            await storage.connect()

            # Clear test data before each test
            await storage.clear_all()

            yield storage

            await storage.clear_all()
            await storage.disconnect()
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    @pytest.mark.asyncio
    async def test_connection(self, storage):
        """Test connect/disconnect and health check."""
        assert await storage.health_check() is True

    @pytest.mark.asyncio
    async def test_hypothesis_crud(self, storage, research_goal, hypothesis):
        """Test hypothesis CRUD operations in PostgreSQL."""
        await storage.add_research_goal(research_goal)

        # Create
        result = await storage.add_hypothesis(hypothesis)
        assert result.id == hypothesis.id

        # Read
        retrieved = await storage.get_hypothesis(hypothesis.id)
        assert retrieved is not None
        assert retrieved.title == hypothesis.title
        assert retrieved.elo_rating == 1200.0

        # Verify JSONB fields
        assert len(retrieved.literature_citations) == 2
        assert retrieved.experimental_protocol is not None

        # Update Elo
        hypothesis.elo_rating = 1250.0
        await storage.update_hypothesis(hypothesis)
        updated = await storage.get_hypothesis(hypothesis.id)
        assert updated.elo_rating == 1250.0

        # Top hypotheses
        top = await storage.get_top_hypotheses(n=5, goal_id=research_goal.id)
        assert len(top) == 1

    @pytest.mark.asyncio
    async def test_win_rate_calculation(self, storage, research_goal, hypothesis):
        """Test win rate calculation in PostgreSQL."""
        await storage.add_research_goal(research_goal)
        await storage.add_hypothesis(hypothesis)

        # Create a second hypothesis
        hypothesis2 = Hypothesis(
            id="hyp_competitor_456",
            research_goal_id=research_goal.id,
            title="Competitor Hypothesis",
            summary="Alternative approach",
            hypothesis_statement="Different target",
            rationale="Based on other evidence",
            status=HypothesisStatus.GENERATED,
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
            elo_rating=1200.0,
        )
        await storage.add_hypothesis(hypothesis2)

        # Create matches
        match1 = TournamentMatch(
            id="match_1",
            hypothesis_a_id=hypothesis.id,
            hypothesis_b_id=hypothesis2.id,
            winner_id=hypothesis.id,
            decision_rationale="A wins",
            elo_change_a=16.0,
            elo_change_b=-16.0,
        )
        match2 = TournamentMatch(
            id="match_2",
            hypothesis_a_id=hypothesis.id,
            hypothesis_b_id=hypothesis2.id,
            winner_id=hypothesis2.id,
            decision_rationale="B wins",
            elo_change_a=-16.0,
            elo_change_b=16.0,
        )

        await storage.add_match(match1)
        await storage.add_match(match2)

        # Check win rates
        win_rate_a = await storage.get_hypothesis_win_rate(hypothesis.id)
        assert win_rate_a == 0.5  # 1 win out of 2 matches

        win_rate_b = await storage.get_hypothesis_win_rate(hypothesis2.id)
        assert win_rate_b == 0.5


# ============================================================================
# Factory Tests
# ============================================================================

class TestStorageFactory:
    """Test storage factory functions."""

    def test_get_memory_storage(self):
        """Test creating in-memory storage."""
        from src.storage.factory import get_storage

        storage = get_storage(backend="memory")
        assert isinstance(storage, InMemoryStorage)

    def test_get_postgres_storage(self):
        """Test creating PostgreSQL storage."""
        from src.storage.factory import get_storage

        try:
            storage = get_storage(backend="postgres")
            assert storage is not None
        except ImportError:
            pytest.skip("asyncpg not installed")

    def test_invalid_backend(self):
        """Test invalid backend raises error."""
        from src.storage.factory import get_storage

        with pytest.raises(ValueError, match="Unknown storage backend"):
            get_storage(backend="invalid")


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

class TestBackwardCompatibility:
    """Test backward compatibility with Phase 1-3 code."""

    def test_sync_storage_instance(self):
        """Test global sync storage instance works."""
        from src.storage.memory import storage

        # Clear any existing data
        storage.clear_all()

        # Create research goal
        goal = ResearchGoal(
            id="compat_test_goal",
            description="Test goal for compatibility",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        # Verify retrieval
        retrieved = storage.get_research_goal("compat_test_goal")
        assert retrieved is not None
        assert retrieved.description == "Test goal for compatibility"

        # Clean up
        storage.clear_all()

    def test_sync_hypothesis_operations(self):
        """Test sync hypothesis operations."""
        from src.storage.memory import storage
        from schemas import GenerationMethod

        storage.clear_all()

        goal = ResearchGoal(
            id="compat_goal",
            description="Test",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        hyp = Hypothesis(
            id="compat_hyp",
            research_goal_id="compat_goal",
            title="Test Hypothesis",
            summary="Test summary",
            hypothesis_statement="Test statement",
            rationale="Test rationale",
            status=HypothesisStatus.GENERATED,
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
            elo_rating=1200.0,
        )
        storage.add_hypothesis(hyp)

        # Get all hypotheses
        all_hyps = storage.get_all_hypotheses()
        assert len(all_hyps) == 1

        # Get by goal
        by_goal = storage.get_hypotheses_by_goal("compat_goal")
        assert len(by_goal) == 1

        # Get top
        top = storage.get_top_hypotheses(n=5)
        assert len(top) == 1

        storage.clear_all()


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
