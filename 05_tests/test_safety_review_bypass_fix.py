#!/usr/bin/env python3
"""Test AGENT-H2: Safety Review Bypass Fix

This test verifies that the safety review is now mandatory and cannot be bypassed.
It tests both Generation and Evolution task execution paths.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import settings
from src.utils.logging_config import setup_logging
from src.agents.supervisor import SupervisorAgent
from src.storage.async_adapter import AsyncStorageAdapter
from src.storage.memory import InMemoryStorage
import structlog

# Import schemas
sys.path.append(str(settings.architecture_dir))
from schemas import (
    ResearchGoal,
    Hypothesis,
    ExperimentalProtocol,
    GenerationMethod,
    AgentTask,
    AgentType,
    EvolutionStrategy,
    ReviewType,
)

# Import errors
from src.utils.errors import BudgetExceededError, LLMClientError


async def test_safety_review_bypass_fix():
    """Test that safety review failures are properly handled"""

    # Setup logging
    setup_logging("INFO")
    logger = structlog.get_logger()

    logger.info("=== Safety Review Bypass Fix Test (AGENT-H2) ===")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    # Initialize storage and supervisor
    storage = AsyncStorageAdapter()
    await storage.connect()
    supervisor = SupervisorAgent(storage)

    # Create test research goal
    research_goal = ResearchGoal(
        id="test_goal_001",
        description="Test safety review enforcement",
        constraints=["Test constraint"],
        preferences=["Test preference"],
    )
    await storage.add_research_goal(research_goal)

    # =========================================================================
    # Test 1: Generation task with UNSAFE hypothesis
    # =========================================================================
    logger.info("\n=== Test 1: Generation Task - Unsafe Hypothesis ===")

    # Create a mock hypothesis that will fail safety review
    unsafe_hypothesis = Hypothesis(
        id="unsafe_hyp_001",
        research_goal_id=research_goal.id,
        title="Unsafe test hypothesis",
        summary="This should fail safety review",
        hypothesis_statement="Test statement",
        rationale="Test rationale",
        mechanism="Test mechanism",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1200.0,
    )

    # Mock the safety agent to return UNSAFE assessment
    unsafe_assessment = {
        "safety_score": 0.3,  # Below 0.5 threshold
        "risks": ["Test risk 1", "Test risk 2"],
        "hazard_categories": {"biological": 0.8},
        "mitigations": [],
    }

    # Create mock agent that returns unsafe hypothesis
    mock_gen_agent = Mock()
    mock_gen_agent.execute = Mock(return_value=unsafe_hypothesis)

    # Mock _get_agent to return our mock agent
    original_get_agent = supervisor._get_agent
    def mock_get_agent(agent_type):
        if agent_type == AgentType.GENERATION:
            return mock_gen_agent
        return original_get_agent(agent_type)

    with patch.object(supervisor, '_get_agent', side_effect=mock_get_agent):
        # Mock SafetyAgent.review_hypothesis to return unsafe assessment
        async_mock = AsyncMock(return_value=unsafe_assessment)
        with patch.object(supervisor.safety_agent, 'review_hypothesis', async_mock):
            # Mock SafetyAgent.is_safe to return False
            with patch.object(supervisor.safety_agent, 'is_safe', return_value=False):

                # Create generation task
                task = AgentTask(
                    id="gen_task_001",
                    agent_type=AgentType.GENERATION,
                    task_type="generate_hypothesis",
                    priority=10,
                    parameters={
                        "goal_id": research_goal.id,
                        "method": GenerationMethod.LITERATURE_EXPLORATION.value,
                        "use_web_search": False,
                    },
                    status="pending"
                )

                # Execute task
                result = await supervisor._execute_task(task, research_goal)

                # Verify result indicates safety failure
                assert "error" in result, "Result should contain 'error' field"
                assert result["error"] == "safety_failed", f"Expected error='safety_failed', got {result.get('error')}"
                assert result["status"] == "requires_safety_review"
                assert "safety_score" in result
                assert result["safety_score"] == 0.3

                logger.info(
                    "Test 1 PASSED: Unsafe hypothesis properly flagged",
                    result=result
                )

                # Verify hypothesis was stored with REQUIRES_SAFETY_REVIEW status
                stored_hyp = await storage.get_hypothesis(result["hypothesis_id"])
                assert stored_hyp is not None
                assert stored_hyp.status.value == "requires_safety_review"
                logger.info("Hypothesis stored with correct status", status=stored_hyp.status.value)

    # =========================================================================
    # Test 2: Generation task with SAFE hypothesis
    # =========================================================================
    logger.info("\n=== Test 2: Generation Task - Safe Hypothesis ===")

    # Create a mock hypothesis that will PASS safety review
    safe_hypothesis = Hypothesis(
        id="safe_hyp_001",
        research_goal_id=research_goal.id,
        title="Safe test hypothesis",
        summary="This should pass safety review",
        hypothesis_statement="Test statement",
        rationale="Test rationale",
        mechanism="Test mechanism",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1200.0,
    )

    # Mock the safety agent to return SAFE assessment
    safe_assessment = {
        "safety_score": 0.9,  # Above 0.5 threshold
        "risks": [],
        "hazard_categories": {},
        "mitigations": [],
    }

    # Create mock agent that returns safe hypothesis
    mock_gen_agent_safe = Mock()
    mock_gen_agent_safe.execute = Mock(return_value=safe_hypothesis)

    # Mock _get_agent to return our mock agent
    def mock_get_agent_safe(agent_type):
        if agent_type == AgentType.GENERATION:
            return mock_gen_agent_safe
        return original_get_agent(agent_type)

    with patch.object(supervisor, '_get_agent', side_effect=mock_get_agent_safe):
        # Mock SafetyAgent.review_hypothesis to return safe assessment
        async_mock_safe = AsyncMock(return_value=safe_assessment)
        with patch.object(supervisor.safety_agent, 'review_hypothesis', async_mock_safe):
            # Mock SafetyAgent.is_safe to return True
            with patch.object(supervisor.safety_agent, 'is_safe', return_value=True):

                # Create generation task
                task = AgentTask(
                    id="gen_task_002",
                    agent_type=AgentType.GENERATION,
                    task_type="generate_hypothesis",
                    priority=10,
                    parameters={
                        "goal_id": research_goal.id,
                        "method": GenerationMethod.LITERATURE_EXPLORATION.value,
                        "use_web_search": False,
                    },
                    status="pending"
                )

                # Execute task
                result = await supervisor._execute_task(task, research_goal)

                # Verify result indicates success
                assert "error" not in result, f"Safe hypothesis should not have error, got {result}"
                assert "hypothesis_id" in result
                assert result["hypothesis_id"] == safe_hypothesis.id

                logger.info(
                    "Test 2 PASSED: Safe hypothesis properly accepted",
                    result=result
                )

                # Verify hypothesis was stored with INITIAL_REVIEW status
                stored_hyp = await storage.get_hypothesis(result["hypothesis_id"])
                assert stored_hyp is not None
                assert stored_hyp.status.value == "initial_review"
                logger.info("Hypothesis stored with correct status", status=stored_hyp.status.value)

    # =========================================================================
    # Test 3: Evolution task with UNSAFE evolved hypothesis
    # =========================================================================
    logger.info("\n=== Test 3: Evolution Task - Unsafe Evolved Hypothesis ===")

    # Create base hypothesis for evolution
    base_hypothesis = Hypothesis(
        id="base_hyp_001",
        research_goal_id=research_goal.id,
        title="Base hypothesis",
        summary="Base for evolution",
        hypothesis_statement="Test statement",
        rationale="Test rationale",
        mechanism="Test mechanism",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1400.0,
    )
    await storage.add_hypothesis(base_hypothesis)

    # Create evolved hypothesis that will fail safety
    unsafe_evolved = Hypothesis(
        id="unsafe_evolved_001",
        research_goal_id=research_goal.id,
        title="Unsafe evolved hypothesis",
        summary="This evolved version should fail safety review",
        hypothesis_statement="Evolved statement",
        rationale="Evolved rationale",
        mechanism="Evolved mechanism",
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,  # Evolved still uses a generation method
        elo_rating=1200.0,
        parent_hypothesis_ids=[base_hypothesis.id],  # Note: plural "ids"
    )

    # Create mock agent that returns unsafe evolved hypothesis
    mock_evol_agent = Mock()
    mock_evol_agent.execute = Mock(return_value=unsafe_evolved)

    # Mock _get_agent to return our mock agent
    def mock_get_agent_evol(agent_type):
        if agent_type == AgentType.EVOLUTION:
            return mock_evol_agent
        return original_get_agent(agent_type)

    with patch.object(supervisor, '_get_agent', side_effect=mock_get_agent_evol):
        # Mock SafetyAgent.review_hypothesis to return unsafe assessment
        async_mock_evolved = AsyncMock(return_value=unsafe_assessment)
        with patch.object(supervisor.safety_agent, 'review_hypothesis', async_mock_evolved):
            # Mock SafetyAgent.is_safe to return False
            with patch.object(supervisor.safety_agent, 'is_safe', return_value=False):

                # Create evolution task
                task = AgentTask(
                    id="evol_task_001",
                    agent_type=AgentType.EVOLUTION,
                    task_type="evolve_hypothesis",
                    priority=10,
                    parameters={
                        "hypothesis_id": base_hypothesis.id,
                        "strategy": EvolutionStrategy.FEASIBILITY.value,
                    },
                    status="pending"
                )

                # Execute task
                result = await supervisor._execute_task(task, research_goal)

                # Verify result indicates safety failure
                assert "error" in result, "Result should contain 'error' field"
                assert result["error"] == "safety_failed"
                assert result["status"] == "requires_safety_review"
                assert "evolved_hypothesis_id" in result
                assert result["evolved_hypothesis_id"] == unsafe_evolved.id

                logger.info(
                    "Test 3 PASSED: Unsafe evolved hypothesis properly flagged",
                    result=result
                )

                # Verify evolved hypothesis was stored with REQUIRES_SAFETY_REVIEW status
                stored_evolved = await storage.get_hypothesis(result["evolved_hypothesis_id"])
                assert stored_evolved is not None
                assert stored_evolved.status.value == "requires_safety_review"
                logger.info("Evolved hypothesis stored with correct status", status=stored_evolved.status.value)

    # =========================================================================
    # Test 4: Safety review error propagation (BudgetExceededError)
    # =========================================================================
    logger.info("\n=== Test 4: Safety Review Error Propagation - Budget Error ===")

    # Create mock agent that returns hypothesis
    mock_gen_agent_budget = Mock()
    mock_gen_agent_budget.execute = Mock(return_value=safe_hypothesis)

    # Mock _get_agent to return our mock agent
    def mock_get_agent_budget(agent_type):
        if agent_type == AgentType.GENERATION:
            return mock_gen_agent_budget
        return original_get_agent(agent_type)

    with patch.object(supervisor, '_get_agent', side_effect=mock_get_agent_budget):
        # Mock SafetyAgent.review_hypothesis to raise BudgetExceededError
        async_mock_budget = AsyncMock(side_effect=BudgetExceededError("Test budget exceeded"))
        with patch.object(supervisor.safety_agent, 'review_hypothesis', async_mock_budget):

            # Create generation task
            task = AgentTask(
                id="gen_task_003",
                agent_type=AgentType.GENERATION,
                task_type="generate_hypothesis",
                priority=10,
                parameters={
                    "goal_id": research_goal.id,
                    "method": GenerationMethod.LITERATURE_EXPLORATION.value,
                    "use_web_search": False,
                },
                status="pending"
            )

            # Execute task - should raise BudgetExceededError
            try:
                result = await supervisor._execute_task(task, research_goal)
                assert False, "BudgetExceededError should have been raised"
            except BudgetExceededError as e:
                logger.info("Test 4 PASSED: BudgetExceededError properly propagated", error=str(e))

    # =========================================================================
    # Test 5: Safety review error propagation (LLMClientError)
    # =========================================================================
    logger.info("\n=== Test 5: Safety Review Error Propagation - LLM Error ===")

    # Create mock agent that returns hypothesis
    mock_gen_agent_llm = Mock()
    mock_gen_agent_llm.execute = Mock(return_value=safe_hypothesis)

    # Mock _get_agent to return our mock agent
    def mock_get_agent_llm(agent_type):
        if agent_type == AgentType.GENERATION:
            return mock_gen_agent_llm
        return original_get_agent(agent_type)

    with patch.object(supervisor, '_get_agent', side_effect=mock_get_agent_llm):
        # Mock SafetyAgent.review_hypothesis to raise LLMClientError
        async_mock_llm = AsyncMock(side_effect=LLMClientError("Test LLM error"))
        with patch.object(supervisor.safety_agent, 'review_hypothesis', async_mock_llm):

            # Create generation task
            task = AgentTask(
                id="gen_task_004",
                agent_type=AgentType.GENERATION,
                task_type="generate_hypothesis",
                priority=10,
                parameters={
                    "goal_id": research_goal.id,
                    "method": GenerationMethod.LITERATURE_EXPLORATION.value,
                    "use_web_search": False,
                },
                status="pending"
            )

            # Execute task - should raise LLMClientError
            try:
                result = await supervisor._execute_task(task, research_goal)
                assert False, "LLMClientError should have been raised"
            except LLMClientError as e:
                logger.info("Test 5 PASSED: LLMClientError properly propagated", error=str(e))

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n=== Test Summary ===")
    logger.info(
        "All safety review bypass fix tests PASSED",
        tests_passed=5
    )

    logger.info("\n=== Safety Review Bypass Fix Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_safety_review_bypass_fix())
