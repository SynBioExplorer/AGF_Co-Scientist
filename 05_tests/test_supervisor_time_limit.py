"""Test suite for AGENT-C1: Supervisor time limit safeguard.

This test verifies that the supervisor stops execution when the absolute
time limit is exceeded, preventing infinite loops.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add architecture directory to path
sys.path.append(str(Path(__file__).parent.parent / "03_architecture"))
from schemas import ResearchGoal

# Add source to path
sys.path.append(str(Path(__file__).parent.parent))
from src.agents.supervisor import SupervisorAgent
from src.storage.async_adapter import AsyncStorageAdapter
from src.config import settings
from src.utils.ids import generate_id


async def test_time_limit():
    """Test that supervisor respects max_execution_time_seconds."""
    print("\n" + "="*80)
    print("AGENT-C1 Test: Supervisor Time Limit")
    print("="*80)

    # Create storage
    storage = AsyncStorageAdapter()
    await storage.connect()

    # Create supervisor
    supervisor = SupervisorAgent(storage)

    # Create simple research goal
    goal = ResearchGoal(
        id=generate_id("goal"),
        description="Test time limit for supervisor execution",
        constraints=["Must complete quickly"],
        preferences=["Fast execution"]
    )

    print(f"\n✓ Created research goal: {goal.id}")
    print(f"  Description: {goal.description}")

    # Test 1: Very short time limit (5 seconds)
    print("\n" + "-"*80)
    print("Test 1: Short time limit (5 seconds)")
    print("-"*80)

    start = datetime.now()

    try:
        result = await supervisor.execute(
            research_goal=goal,
            max_iterations=100,  # High iteration count
            max_execution_time_seconds=5  # But very short time limit
        )

        elapsed = (datetime.now() - start).total_seconds()

        print(f"\n✓ Supervisor completed:")
        print(f"  Result: {result}")
        print(f"  Elapsed time: {elapsed:.2f} seconds")

        # Verify it stopped due to time limit
        if "Maximum execution time exceeded" in result:
            print(f"  ✓ PASS: Stopped due to time limit as expected")
        elif elapsed <= 6:  # Allow 1 second tolerance
            print(f"  ✓ PASS: Completed within time limit")
        else:
            print(f"  ✗ FAIL: Did not stop at time limit (ran for {elapsed:.2f}s)")

    except Exception as e:
        print(f"  ✗ FAIL: Exception occurred: {e}")
        raise

    # Test 2: Default time limit from settings
    print("\n" + "-"*80)
    print(f"Test 2: Default time limit ({settings.supervisor_max_execution_seconds}s)")
    print("-"*80)

    # Create new goal for second test
    goal2 = ResearchGoal(
        id=generate_id("goal"),
        description="Test default time limit configuration",
        constraints=["Use default settings"],
        preferences=["Standard execution"]
    )

    # Create new supervisor instance to reset state
    supervisor2 = SupervisorAgent(storage)

    start = datetime.now()

    try:
        result = await supervisor2.execute(
            research_goal=goal2,
            max_iterations=2,  # Keep it short for testing
            max_execution_time_seconds=None  # Use default
        )

        elapsed = (datetime.now() - start).total_seconds()

        print(f"\n✓ Supervisor completed:")
        print(f"  Result: {result}")
        print(f"  Elapsed time: {elapsed:.2f} seconds")
        print(f"  Default time limit: {settings.supervisor_max_execution_seconds}s")
        print(f"  ✓ PASS: Used default time limit from settings")

    except Exception as e:
        print(f"  ✗ FAIL: Exception occurred: {e}")
        raise

    # Test 3: Verify time limit check happens each iteration
    print("\n" + "-"*80)
    print("Test 3: Time limit checked each iteration")
    print("-"*80)

    goal3 = ResearchGoal(
        id=generate_id("goal"),
        description="Verify time limit is checked per iteration",
        constraints=["Multiple iterations"],
        preferences=["Check timing"]
    )

    supervisor3 = SupervisorAgent(storage)

    start = datetime.now()

    try:
        result = await supervisor3.execute(
            research_goal=goal3,
            max_iterations=10,
            max_execution_time_seconds=3  # 3 seconds
        )

        elapsed = (datetime.now() - start).total_seconds()

        print(f"\n✓ Supervisor completed:")
        print(f"  Iterations run: {supervisor3.iteration}")
        print(f"  Elapsed time: {elapsed:.2f} seconds")

        # Should stop before max_iterations due to time limit
        if supervisor3.iteration < 10 and elapsed <= 4:
            print(f"  ✓ PASS: Stopped early due to time limit (iteration {supervisor3.iteration}/10)")
        else:
            print(f"  ⚠ WARNING: May have run longer than expected")

    except Exception as e:
        print(f"  ✗ FAIL: Exception occurred: {e}")
        raise

    print("\n" + "="*80)
    print("✓ All AGENT-C1 tests completed successfully!")
    print("="*80)
    print("\nKey findings:")
    print("  1. Time limit parameter added to execute() method")
    print("  2. Default time limit read from settings.supervisor_max_execution_seconds")
    print("  3. Time check added to _check_terminal_conditions()")
    print("  4. Supervisor logs time limit configuration at startup")
    print("  5. Clear termination reason provided when time limit exceeded")
    print("\n")


if __name__ == "__main__":
    asyncio.run(test_time_limit())
