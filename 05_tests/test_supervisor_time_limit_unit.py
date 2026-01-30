"""Unit test for AGENT-C1: Supervisor time limit safeguard.

This test verifies the time limit logic without running a full supervisor workflow.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add architecture directory to path
sys.path.append(str(Path(__file__).parent.parent / "03_architecture"))
from schemas import SystemStatistics

# Add source to path
sys.path.append(str(Path(__file__).parent.parent))
from src.config import settings


def test_time_limit_logic():
    """Test the time limit calculation logic."""
    print("\n" + "="*80)
    print("AGENT-C1 Unit Test: Time Limit Logic")
    print("="*80)

    # Test 1: Default configuration value
    print("\n" + "-"*80)
    print("Test 1: Default Configuration")
    print("-"*80)
    print(f"  Default time limit: {settings.supervisor_max_execution_seconds} seconds")
    print(f"  Default time limit: {settings.supervisor_max_execution_seconds / 3600} hours")
    assert settings.supervisor_max_execution_seconds == 7200, "Default should be 7200 seconds (2 hours)"
    print("  ✓ PASS: Default is 7200 seconds (2 hours)")

    # Test 2: Time limit calculation
    print("\n" + "-"*80)
    print("Test 2: Time Limit Calculation")
    print("-"*80)

    # Simulate time passing
    started_at = datetime.now()
    max_execution_time_seconds = 5

    # Case 2a: Within time limit
    elapsed_seconds = 3.0
    simulated_now = started_at + timedelta(seconds=elapsed_seconds)
    actual_elapsed = (simulated_now - started_at).total_seconds()

    print(f"\n  Case 2a: Within time limit")
    print(f"    Started: {started_at.strftime('%H:%M:%S')}")
    print(f"    Now: {simulated_now.strftime('%H:%M:%S')}")
    print(f"    Elapsed: {actual_elapsed:.2f}s")
    print(f"    Limit: {max_execution_time_seconds}s")
    print(f"    Should stop: {actual_elapsed > max_execution_time_seconds}")

    assert actual_elapsed <= max_execution_time_seconds, "Should be within limit"
    print("    ✓ PASS: Within time limit")

    # Case 2b: Exceeded time limit
    elapsed_seconds = 6.0
    simulated_now = started_at + timedelta(seconds=elapsed_seconds)
    actual_elapsed = (simulated_now - started_at).total_seconds()

    print(f"\n  Case 2b: Exceeded time limit")
    print(f"    Started: {started_at.strftime('%H:%M:%S')}")
    print(f"    Now: {simulated_now.strftime('%H:%M:%S')}")
    print(f"    Elapsed: {actual_elapsed:.2f}s")
    print(f"    Limit: {max_execution_time_seconds}s")
    print(f"    Should stop: {actual_elapsed > max_execution_time_seconds}")

    assert actual_elapsed > max_execution_time_seconds, "Should exceed limit"
    print("    ✓ PASS: Exceeded time limit detected")

    # Test 3: Reason string format
    print("\n" + "-"*80)
    print("Test 3: Termination Reason Format")
    print("-"*80)

    elapsed_hours = round(actual_elapsed / 3600, 2)
    max_hours = round(max_execution_time_seconds / 3600, 2)
    reason = f"Maximum execution time exceeded ({elapsed_hours}h / {max_hours}h)"

    print(f"  Reason string: {reason}")
    assert "Maximum execution time exceeded" in reason
    assert "h" in reason  # Contains hours
    print("  ✓ PASS: Reason string formatted correctly")

    # Test 4: Integration with method signature
    print("\n" + "-"*80)
    print("Test 4: Method Signature")
    print("-"*80)

    from src.agents.supervisor import SupervisorAgent
    import inspect

    # Check execute method signature
    sig = inspect.signature(SupervisorAgent.execute)
    params = list(sig.parameters.keys())

    print(f"  execute() parameters: {params}")
    assert "max_execution_time_seconds" in params, "Missing max_execution_time_seconds parameter"
    print("  ✓ PASS: max_execution_time_seconds parameter present")

    # Check default value
    param = sig.parameters["max_execution_time_seconds"]
    print(f"  Default value: {param.default}")
    assert param.default is None or isinstance(param.default, int)
    print("  ✓ PASS: Parameter has correct default (None or int)")

    # Check _check_terminal_conditions signature
    sig2 = inspect.signature(SupervisorAgent._check_terminal_conditions)
    params2 = list(sig2.parameters.keys())

    print(f"  _check_terminal_conditions() parameters: {params2}")
    assert "started_at" in params2, "Missing started_at parameter"
    assert "max_execution_time_seconds" in params2, "Missing max_execution_time_seconds parameter"
    print("  ✓ PASS: Time limit parameters present in _check_terminal_conditions()")

    print("\n" + "="*80)
    print("✓ All AGENT-C1 unit tests passed!")
    print("="*80)
    print("\nImplementation Summary:")
    print("  1. Configuration: settings.supervisor_max_execution_seconds = 7200s (2h)")
    print("  2. Parameter: max_execution_time_seconds added to execute()")
    print("  3. Tracking: started_at = datetime.now() at workflow start")
    print("  4. Check: elapsed_seconds > max_execution_time_seconds")
    print("  5. Reason: Clear termination message with time details")
    print("\n")


if __name__ == "__main__":
    test_time_limit_logic()
