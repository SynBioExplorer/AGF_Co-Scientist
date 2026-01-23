#!/usr/bin/env python3
"""Test Phase 4: Supervisor Components

This test suite validates:
1. TaskQueue - Priority ordering, filtering, status updates
2. SupervisorStatistics - Convergence calculation, effectiveness metrics
3. AsyncStorageAdapter - Storage operations
4. SupervisorAgent - Orchestration loop (integration test)
"""

import sys
import asyncio
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.config import settings
from src.utils.logging_config import setup_logging
import structlog

# Import schemas
sys.path.append(str(settings.architecture_dir))
from schemas import (
    AgentTask,
    AgentType,
    ResearchGoal,
    Hypothesis,
    Review,
    ReviewType,
    TournamentMatch,
    HypothesisStatus,
    GenerationMethod,
)


def test_task_queue():
    """Test TaskQueue priority ordering and filtering."""
    from src.supervisor.task_queue import TaskQueue

    logger = structlog.get_logger()
    logger.info("=== Testing TaskQueue ===")

    queue = TaskQueue()

    # Test 1: Priority ordering
    logger.info("Test 1: Priority ordering")
    task_low = AgentTask(
        id="task_low",
        agent_type=AgentType.GENERATION,
        task_type="generate_hypothesis",
        priority=1,
        parameters={},
        status="pending"
    )
    task_high = AgentTask(
        id="task_high",
        agent_type=AgentType.GENERATION,
        task_type="generate_hypothesis",
        priority=10,
        parameters={},
        status="pending"
    )
    task_medium = AgentTask(
        id="task_medium",
        agent_type=AgentType.REFLECTION,
        task_type="review_hypothesis",
        priority=5,
        parameters={},
        status="pending"
    )

    queue.add_task(task_low)
    queue.add_task(task_high)
    queue.add_task(task_medium)

    # Should get high priority first
    next_task = queue.get_next_task()
    assert next_task.id == "task_high", f"Expected task_high, got {next_task.id}"
    logger.info("  - High priority task retrieved first")

    # Test 2: Filter by agent type
    logger.info("Test 2: Filter by agent type")
    queue.clear()
    queue.add_task(AgentTask(
        id="gen1", agent_type=AgentType.GENERATION, task_type="generate",
        priority=5, parameters={}, status="pending"
    ))
    queue.add_task(AgentTask(
        id="ref1", agent_type=AgentType.REFLECTION, task_type="review",
        priority=10, parameters={}, status="pending"
    ))

    # Get reflection task (should skip higher priority generation task)
    ref_task = queue.get_next_task(agent_type=AgentType.REFLECTION)
    assert ref_task.id == "ref1", f"Expected ref1, got {ref_task.id}"
    logger.info("  - Filtered by agent type correctly")

    # Test 3: Status tracking
    logger.info("Test 3: Status tracking")
    queue.clear()
    queue.add_task(AgentTask(
        id="status_test", agent_type=AgentType.GENERATION, task_type="generate",
        priority=5, parameters={}, status="pending"
    ))

    queue.update_task_status("status_test", "running")
    task = queue.get_task("status_test")
    assert task.status == "running", f"Expected running, got {task.status}"
    assert task.started_at is not None, "started_at should be set"
    logger.info("  - Status updated correctly")

    # Test 4: Statistics
    logger.info("Test 4: Queue statistics")
    queue.clear()
    for i in range(5):
        queue.add_task(AgentTask(
            id=f"stat_task_{i}",
            agent_type=AgentType.GENERATION if i % 2 == 0 else AgentType.REFLECTION,
            task_type="test",
            priority=i,
            parameters={},
            status="pending"
        ))

    stats = queue.get_statistics()
    assert stats["total"] == 5, f"Expected 5 total, got {stats['total']}"
    assert stats["pending"] == 5, f"Expected 5 pending, got {stats['pending']}"
    logger.info(f"  - Statistics: {stats}")

    logger.info("TaskQueue tests PASSED")


async def test_async_storage_adapter():
    """Test AsyncStorageAdapter operations."""
    from src.storage.async_adapter import AsyncStorageAdapter

    logger = structlog.get_logger()
    logger.info("\n=== Testing AsyncStorageAdapter ===")

    storage = AsyncStorageAdapter()
    await storage.connect()

    # Test 1: Research goals
    logger.info("Test 1: Research goals")
    goal = ResearchGoal(
        id="test_goal_001",
        description="Test research goal for supervisor testing",
        constraints=["test constraint"],
        preferences=["test preference"]
    )
    await storage.add_research_goal(goal)
    retrieved = await storage.get_research_goal("test_goal_001")
    assert retrieved is not None, "Goal should be retrievable"
    assert retrieved.description == goal.description
    logger.info("  - Research goal stored and retrieved")

    # Test 2: Hypotheses
    logger.info("Test 2: Hypotheses")
    hyp1 = Hypothesis(
        id="test_hyp_001",
        research_goal_id="test_goal_001",
        title="Test Hypothesis 1",
        summary="Test summary",
        hypothesis_statement="Test statement",
        rationale="Test rationale",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1200.0
    )
    hyp2 = Hypothesis(
        id="test_hyp_002",
        research_goal_id="test_goal_001",
        title="Test Hypothesis 2",
        summary="Test summary 2",
        hypothesis_statement="Test statement 2",
        rationale="Test rationale 2",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1250.0
    )
    await storage.add_hypothesis(hyp1)
    await storage.add_hypothesis(hyp2)

    hypotheses = await storage.get_hypotheses_by_goal("test_goal_001")
    assert len(hypotheses) == 2, f"Expected 2 hypotheses, got {len(hypotheses)}"
    logger.info(f"  - Stored and retrieved {len(hypotheses)} hypotheses")

    # Test 3: Top hypotheses (should be sorted by Elo)
    logger.info("Test 3: Top hypotheses")
    top = await storage.get_top_hypotheses(n=1, goal_id="test_goal_001")
    assert len(top) == 1
    assert top[0].id == "test_hyp_002", "Higher Elo hypothesis should be first"
    logger.info("  - Top hypotheses sorted correctly by Elo")

    # Test 4: Reviews
    logger.info("Test 4: Reviews")
    review = Review(
        id="test_review_001",
        hypothesis_id="test_hyp_001",
        review_type=ReviewType.INITIAL,
        quality_score=0.8,
        correctness_score=0.7,
        novelty_score=0.9,
        passed=True,
        rationale="Test rationale"
    )
    await storage.add_review(review)
    reviews = await storage.get_reviews_for_hypothesis("test_hyp_001")
    assert len(reviews) == 1
    logger.info("  - Review stored and retrieved")

    # Test 5: Tasks
    logger.info("Test 5: Agent tasks")
    task = AgentTask(
        id="test_task_001",
        agent_type=AgentType.GENERATION,
        task_type="generate_hypothesis",
        priority=5,
        parameters={"goal_id": "test_goal_001"},
        status="pending"
    )
    await storage.add_task(task)
    pending = await storage.get_pending_tasks(AgentType.GENERATION)
    assert len(pending) >= 1
    logger.info(f"  - Task stored, {len(pending)} pending tasks")

    # Clean up
    await storage.clear_all()
    await storage.disconnect()

    logger.info("AsyncStorageAdapter tests PASSED")


async def test_supervisor_statistics():
    """Test SupervisorStatistics computations."""
    from src.supervisor.statistics import SupervisorStatistics
    from src.storage.async_adapter import AsyncStorageAdapter

    logger = structlog.get_logger()
    logger.info("\n=== Testing SupervisorStatistics ===")

    storage = AsyncStorageAdapter()
    await storage.connect()

    # Set up test data
    goal = ResearchGoal(
        id="stats_test_goal",
        description="Test goal for statistics",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    # Add hypotheses with varying Elo ratings
    for i in range(5):
        hyp = Hypothesis(
            id=f"stats_hyp_{i}",
            research_goal_id="stats_test_goal",
            title=f"Hypothesis {i}",
            summary=f"Summary {i}",
            hypothesis_statement=f"Statement {i}",
            rationale=f"Rationale {i}",
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
            elo_rating=1200.0 + (i * 20),  # 1200, 1220, 1240, 1260, 1280
            status=HypothesisStatus.IN_TOURNAMENT if i > 0 else HypothesisStatus.GENERATED
        )
        await storage.add_hypothesis(hyp)

    # Create statistics tracker
    stats_tracker = SupervisorStatistics(storage)

    # Test 1: Compute statistics
    logger.info("Test 1: Compute statistics")
    stats = await stats_tracker.compute_statistics("stats_test_goal")

    assert stats.total_hypotheses == 5, f"Expected 5 hypotheses, got {stats.total_hypotheses}"
    assert stats.hypotheses_pending_review == 1, f"Expected 1 pending, got {stats.hypotheses_pending_review}"
    logger.info(f"  - Total hypotheses: {stats.total_hypotheses}")
    logger.info(f"  - Pending review: {stats.hypotheses_pending_review}")

    # Test 2: Convergence calculation
    logger.info("Test 2: Convergence calculation")
    # With Elo ratings of 1200-1280 (std dev ~28), convergence should be moderate
    logger.info(f"  - Tournament convergence: {stats.tournament_convergence_score:.3f}")
    assert 0 <= stats.tournament_convergence_score <= 1, "Convergence should be in [0, 1]"

    # Test 3: Method effectiveness
    logger.info("Test 3: Method effectiveness")
    logger.info(f"  - Method effectiveness: {stats.method_effectiveness}")

    # Test 4: Recommend weights
    logger.info("Test 4: Recommend agent weights")
    weights = await stats_tracker.recommend_agent_weights("stats_test_goal", stats)
    weight_sum = sum(weights.values())
    logger.info(f"  - Recommended weights: {dict((k.value, round(v, 2)) for k, v in weights.items())}")
    assert abs(weight_sum - 1.0) < 0.01, f"Weights should sum to ~1.0, got {weight_sum}"

    # Clean up
    await storage.clear_all()
    await storage.disconnect()

    logger.info("SupervisorStatistics tests PASSED")


async def test_supervisor_agent_initialization():
    """Test SupervisorAgent initialization and configuration."""
    from src.agents.supervisor import SupervisorAgent
    from src.storage.async_adapter import AsyncStorageAdapter

    logger = structlog.get_logger()
    logger.info("\n=== Testing SupervisorAgent Initialization ===")

    storage = AsyncStorageAdapter()
    await storage.connect()

    # Test 1: Initialization
    logger.info("Test 1: Agent initialization")
    supervisor = SupervisorAgent(storage)
    assert supervisor.task_queue is not None
    assert supervisor.statistics is not None
    assert len(supervisor.agent_weights) == 6  # 6 agent types
    logger.info("  - Supervisor initialized with all components")

    # Test 2: Initial weights
    logger.info("Test 2: Initial weights")
    weights = supervisor.agent_weights
    assert AgentType.GENERATION in weights
    assert AgentType.REFLECTION in weights
    assert weights[AgentType.GENERATION] == 0.40
    logger.info(f"  - Initial weights: {dict((k.value, v) for k, v in weights.items())}")

    # Test 3: Task initialization
    logger.info("Test 3: Task initialization")
    supervisor._initialize_tasks("test_goal")
    stats = supervisor.task_queue.get_statistics()
    assert stats["pending"] == 3, f"Expected 3 initial tasks, got {stats['pending']}"
    logger.info(f"  - Created {stats['pending']} initial generation tasks")

    # Clean up
    await storage.clear_all()
    await storage.disconnect()

    logger.info("SupervisorAgent initialization tests PASSED")


async def test_supervisor_terminal_conditions():
    """Test SupervisorAgent terminal condition detection."""
    from src.agents.supervisor import SupervisorAgent
    from src.storage.async_adapter import AsyncStorageAdapter
    from src.supervisor.statistics import SupervisorStatistics

    logger = structlog.get_logger()
    logger.info("\n=== Testing Terminal Conditions ===")

    storage = AsyncStorageAdapter()
    await storage.connect()

    supervisor = SupervisorAgent(storage)

    # Set up test data with high convergence (similar Elo ratings)
    goal_id = "terminal_test_goal"
    goal = ResearchGoal(
        id=goal_id,
        description="Test goal for terminal conditions",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    # Add hypotheses with converged Elo ratings
    for i in range(6):
        hyp = Hypothesis(
            id=f"terminal_hyp_{i}",
            research_goal_id=goal_id,
            title=f"Hypothesis {i}",
            summary=f"Summary {i}",
            hypothesis_statement=f"Statement {i}",
            rationale=f"Rationale {i}",
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
            elo_rating=1200.0 + (i * 2),  # Very similar: 1200, 1202, 1204...
            status=HypothesisStatus.IN_TOURNAMENT
        )
        await storage.add_hypothesis(hyp)

    # Add reviews with high quality
    for i in range(6):
        review = Review(
            id=f"terminal_review_{i}",
            hypothesis_id=f"terminal_hyp_{i}",
            review_type=ReviewType.INITIAL,
            quality_score=0.85,  # High quality
            correctness_score=0.8,
            novelty_score=0.7,
            passed=True,
            rationale="High quality hypothesis"
        )
        await storage.add_review(review)

    # Compute statistics
    stats_tracker = SupervisorStatistics(storage)
    stats = await stats_tracker.compute_statistics(goal_id)

    logger.info(f"  - Convergence score: {stats.tournament_convergence_score:.3f}")

    # Test convergence detection
    supervisor.iteration = 4  # Above minimum iterations
    should_stop, reason = await supervisor._check_terminal_conditions(
        stats=stats,
        min_hypotheses=3,
        quality_threshold=0.7,
        convergence_threshold=0.9
    )

    logger.info(f"  - Should stop: {should_stop}")
    logger.info(f"  - Reason: {reason}")

    # Clean up
    await storage.clear_all()
    await storage.disconnect()

    logger.info("Terminal conditions tests PASSED")


def run_all_tests():
    """Run all supervisor tests."""
    setup_logging("INFO")
    logger = structlog.get_logger()

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 4: SUPERVISOR COMPONENT TESTS")
    logger.info("=" * 60)

    # Synchronous tests
    test_task_queue()

    # Async tests
    asyncio.run(test_async_storage_adapter())
    asyncio.run(test_supervisor_statistics())
    asyncio.run(test_supervisor_agent_initialization())
    asyncio.run(test_supervisor_terminal_conditions())

    logger.info("\n" + "=" * 60)
    logger.info("ALL SUPERVISOR TESTS PASSED")
    logger.info("=" * 60)

    # Cost tracking
    logger.info("\n=== Cost Tracking ===")
    sys.path.append(str(settings.project_root / "04_Scripts"))
    from cost_tracker import get_tracker
    tracker = get_tracker()
    tracker.print_summary()


if __name__ == "__main__":
    run_all_tests()
