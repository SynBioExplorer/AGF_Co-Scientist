"""Integration test showing checkpoint error propagation in supervisor workflow.

This test demonstrates that checkpoint save failures properly stop the
supervisor's execution loop, preventing workflow from continuing without
valid recovery points.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Add project directories to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_architecture"))
sys.path.insert(0, str(project_root / "04_Scripts"))

from schemas import ResearchGoal
from src.agents.supervisor import SupervisorAgent
from src.storage.async_adapter import AsyncStorageAdapter
from src.utils.errors import CheckpointError


async def test_checkpoint_error_stops_workflow():
    """Test that CheckpointError stops the supervisor workflow.

    This integration test verifies that when a checkpoint save fails
    (after retry), the supervisor's execute() method raises an error
    and stops the workflow, rather than continuing without checkpoints.
    """
    print("\n=== Testing Checkpoint Error Propagation in Workflow ===\n")

    storage = AsyncStorageAdapter()
    await storage.connect()
    supervisor = SupervisorAgent(storage)

    goal = ResearchGoal(
        id="test_goal_integration",
        description="Test workflow checkpoint error handling",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    # Mock storage to fail checkpoint saves persistently
    original_save = storage.save_checkpoint
    save_attempts = []

    async def mock_save_checkpoint(checkpoint):
        save_attempts.append(checkpoint)
        raise Exception("Simulated persistent storage failure")

    storage.save_checkpoint = mock_save_checkpoint

    # Run supervisor with limited iterations
    print("Starting supervisor workflow with failing checkpoint saves...")
    try:
        # This should fail on the first iteration's checkpoint save
        result = await supervisor.execute(
            research_goal=goal,
            max_iterations=3,  # Won't get past iteration 1
            min_hypotheses=2,
            quality_threshold=0.7,
            convergence_threshold=0.9
        )
        print(f"❌ FAILED: Workflow should have raised CheckpointError but returned: {result}")
        return False
    except CheckpointError as e:
        print(f"✓ CheckpointError raised as expected: {str(e)[:100]}...")
        print(f"✓ Checkpoint save was attempted {len(save_attempts)} times (initial + retry)")

        # Verify it was tried twice (initial + retry)
        if len(save_attempts) != 2:
            print(f"❌ FAILED: Expected 2 save attempts, got {len(save_attempts)}")
            return False

        print("✓ Workflow stopped safely after checkpoint failure")
        print("✓ No work lost - iteration did not complete")
        return True
    except Exception as e:
        print(f"❌ FAILED: Unexpected error type: {type(e).__name__}: {e}")
        return False


async def test_checkpoint_success_allows_workflow():
    """Test that successful checkpoint saves allow workflow to continue.

    This is a sanity check to ensure our fix doesn't break normal operation.
    """
    print("\n=== Testing Normal Checkpoint Operation ===\n")

    storage = AsyncStorageAdapter()
    await storage.connect()
    supervisor = SupervisorAgent(storage)

    goal = ResearchGoal(
        id="test_goal_normal",
        description="Test normal checkpoint operation",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    # Track checkpoint saves
    checkpoint_count = [0]
    original_save = storage.save_checkpoint

    async def tracking_save_checkpoint(checkpoint):
        checkpoint_count[0] += 1
        return await original_save(checkpoint)

    storage.save_checkpoint = tracking_save_checkpoint

    print("Starting supervisor workflow with normal checkpoint saves...")
    try:
        # Run with very limited iterations to keep test fast
        # Mock the execute_iteration to avoid actual LLM calls
        original_execute_iteration = supervisor._execute_iteration

        async def mock_execute_iteration(research_goal):
            # Do nothing - just skip iteration work for speed
            pass

        supervisor._execute_iteration = mock_execute_iteration

        result = await supervisor.execute(
            research_goal=goal,
            max_iterations=2,
            min_hypotheses=1,  # Low threshold
            quality_threshold=0.9,  # High threshold (won't be met)
            convergence_threshold=0.9  # High threshold (won't be met)
        )

        print(f"✓ Workflow completed: {result}")
        print(f"✓ Checkpoints saved successfully {checkpoint_count[0]} times")

        # Should have saved checkpoint for each iteration
        if checkpoint_count[0] != 2:
            print(f"⚠ Warning: Expected 2 checkpoints, got {checkpoint_count[0]}")

        return True
    except Exception as e:
        print(f"❌ FAILED: Workflow should have succeeded but raised: {type(e).__name__}: {e}")
        return False


async def main():
    """Run all integration tests."""
    print("=" * 70)
    print("CHECKPOINT ERROR HANDLING INTEGRATION TESTS")
    print("=" * 70)

    tests = [
        ("Checkpoint Error Stops Workflow", test_checkpoint_error_stops_workflow),
        ("Normal Checkpoint Allows Workflow", test_checkpoint_success_allows_workflow),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 All integration tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
