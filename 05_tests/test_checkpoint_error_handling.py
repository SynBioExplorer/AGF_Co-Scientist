"""Test checkpoint error handling in SupervisorAgent.

This test verifies that checkpoint save failures:
1. Are properly caught and retried
2. Raise CheckpointError if retry fails
3. Allow BudgetExceededError to propagate
4. Log appropriate error messages
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add project directories to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_architecture"))
sys.path.insert(0, str(project_root / "04_Scripts"))

from schemas import ResearchGoal, SystemStatistics
from src.agents.supervisor import SupervisorAgent
from src.storage.async_adapter import AsyncStorageAdapter
from src.utils.errors import CheckpointError
from cost_tracker import BudgetExceededError


@pytest.mark.asyncio
async def test_checkpoint_save_success():
    """Test that successful checkpoint save works without errors."""
    storage = AsyncStorageAdapter()
    await storage.connect()
    supervisor = SupervisorAgent(storage)

    # Create a research goal
    goal = ResearchGoal(
        id="test_goal_checkpoint_001",
        description="Test checkpoint save",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    # Create mock statistics
    stats = SystemStatistics(
        research_goal_id=goal.id,
        total_hypotheses=5,
        hypotheses_in_tournament=3,
        tournament_matches_completed=2,
        tournament_convergence_score=0.5
    )

    # Should complete without error
    await supervisor._save_checkpoint(goal.id, stats)

    # Verify checkpoint was saved
    checkpoint = await storage.get_latest_checkpoint(goal.id)
    assert checkpoint is not None
    assert checkpoint.research_goal_id == goal.id


@pytest.mark.asyncio
async def test_checkpoint_save_retry_on_failure():
    """Test that checkpoint save is retried once on failure."""
    storage = AsyncStorageAdapter()
    await storage.connect()
    supervisor = SupervisorAgent(storage)

    goal = ResearchGoal(
        id="test_goal_checkpoint_002",
        description="Test checkpoint retry",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    stats = SystemStatistics(
        research_goal_id=goal.id,
        total_hypotheses=5,
        hypotheses_in_tournament=3,
        tournament_matches_completed=2,
        tournament_convergence_score=0.5
    )

    # Mock storage to fail once then succeed
    original_save = storage.save_checkpoint
    call_count = 0

    async def mock_save_checkpoint(checkpoint):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Simulated transient storage error")
        return await original_save(checkpoint)

    storage.save_checkpoint = mock_save_checkpoint

    # Should succeed on retry
    await supervisor._save_checkpoint(goal.id, stats)

    # Verify it was called twice (initial + retry)
    assert call_count == 2

    # Verify checkpoint was eventually saved
    checkpoint = await storage.get_latest_checkpoint(goal.id)
    assert checkpoint is not None


@pytest.mark.asyncio
async def test_checkpoint_save_raises_error_after_retry_failure():
    """Test that CheckpointError is raised if retry also fails."""
    storage = AsyncStorageAdapter()
    await storage.connect()
    supervisor = SupervisorAgent(storage)

    goal = ResearchGoal(
        id="test_goal_checkpoint_003",
        description="Test checkpoint failure",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    stats = SystemStatistics(
        research_goal_id=goal.id,
        total_hypotheses=5,
        hypotheses_in_tournament=3,
        tournament_matches_completed=2,
        tournament_convergence_score=0.5
    )

    # Mock storage to always fail
    call_count = 0

    async def mock_save_checkpoint(checkpoint):
        nonlocal call_count
        call_count += 1
        raise Exception(f"Simulated persistent storage error (attempt {call_count})")

    storage.save_checkpoint = mock_save_checkpoint

    # Should raise CheckpointError after retry
    with pytest.raises(CheckpointError) as exc_info:
        await supervisor._save_checkpoint(goal.id, stats)

    # Verify error message contains relevant info
    assert goal.id in str(exc_info.value)
    assert "iteration" in str(exc_info.value).lower()

    # Verify it was called twice (initial + retry)
    assert call_count == 2


@pytest.mark.asyncio
async def test_checkpoint_save_budget_error_propagates():
    """Test that BudgetExceededError is propagated without retry."""
    storage = AsyncStorageAdapter()
    await storage.connect()
    supervisor = SupervisorAgent(storage)

    goal = ResearchGoal(
        id="test_goal_checkpoint_004",
        description="Test budget error propagation",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    stats = SystemStatistics(
        research_goal_id=goal.id,
        total_hypotheses=5,
        hypotheses_in_tournament=3,
        tournament_matches_completed=2,
        tournament_convergence_score=0.5
    )

    # Mock storage to raise BudgetExceededError
    call_count = 0

    async def mock_save_checkpoint(checkpoint):
        nonlocal call_count
        call_count += 1
        raise BudgetExceededError(current_cost=60.0, budget=50.0, currency="AUD")

    storage.save_checkpoint = mock_save_checkpoint

    # Should propagate BudgetExceededError without retry
    with pytest.raises(BudgetExceededError):
        await supervisor._save_checkpoint(goal.id, stats)

    # Verify it was only called once (no retry for budget errors)
    assert call_count == 1


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_checkpoint_save_success())
    print("✓ Test checkpoint save success passed")

    asyncio.run(test_checkpoint_save_retry_on_failure())
    print("✓ Test checkpoint save retry on failure passed")

    asyncio.run(test_checkpoint_save_raises_error_after_retry_failure())
    print("✓ Test checkpoint save raises error after retry failure passed")

    asyncio.run(test_checkpoint_save_budget_error_propagates())
    print("✓ Test checkpoint save budget error propagates passed")

    print("\n✅ All checkpoint error handling tests passed!")
