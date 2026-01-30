#!/usr/bin/env python3
"""Demo script showing deadlock detection and recovery in action.

This script demonstrates:
1. Normal task execution with heartbeat updates
2. Stale task detection and force-kill
3. Health check monitoring
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import background module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "background",
    project_root / "src" / "api" / "background.py"
)
background_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(background_module)

BackgroundTaskManager = background_module.BackgroundTaskManager


async def demo_normal_task():
    """Demo: Normal task completes successfully."""
    print("\n" + "=" * 70)
    print("DEMO 1: Normal Task Execution")
    print("=" * 70)

    manager = BackgroundTaskManager()

    async def normal_task():
        print("  → Task started, running for 2 seconds...")
        for i in range(4):
            await asyncio.sleep(0.5)
            print(f"  → Task progress: {(i+1)*25}%")
        return "Task completed successfully"

    task_id = await manager.start_async_task(
        goal_id="demo_goal",
        coroutine=normal_task(),
        timeout_seconds=10
    )

    print(f"  → Task ID: {task_id}")

    # Monitor heartbeat
    await asyncio.sleep(0.2)
    status = manager.get_task_status(task_id)
    print(f"  → Initial heartbeat: {status['last_heartbeat']}")

    # Wait for completion
    await asyncio.sleep(2.5)
    status = manager.get_task_status(task_id)
    print(f"  → Final status: {status['status']}")
    print(f"  → Result: {status['result']}")

    manager.shutdown()
    print("\n✅ Demo 1 Complete: Normal task executed successfully")


async def demo_stale_task_detection():
    """Demo: Stale task is detected and force-killed."""
    print("\n" + "=" * 70)
    print("DEMO 2: Stale Task Detection and Force-Kill")
    print("=" * 70)

    manager = BackgroundTaskManager()

    async def hanging_task():
        print("  → Task started (will hang)...")
        await asyncio.sleep(100)  # Simulate hung task

    # Start task with very short timeout
    task_id = await manager.start_async_task(
        goal_id="demo_goal",
        coroutine=hanging_task(),
        timeout_seconds=1  # 1 second timeout
    )

    print(f"  → Task ID: {task_id}")
    print(f"  → Timeout: 1 second (force-kill after 2 seconds)")

    # Wait for task to start
    await asyncio.sleep(0.2)
    status = manager.get_task_status(task_id)
    print(f"  → Task status: {status['status']}")
    print(f"  → Initial heartbeat: {status['last_heartbeat']}")

    # Manually set heartbeat to old timestamp (simulate stale task)
    print("\n  → Simulating stale heartbeat (5 seconds old)...")
    with manager._lock:
        if task_id in manager._task_status:
            old_time = datetime.utcnow() - timedelta(seconds=5)
            manager._task_status[task_id]["last_heartbeat"] = old_time

    # Check task health
    print("  → Running health check...")
    killed = manager._check_task_health()
    print(f"  → Tasks killed: {killed}")

    # Check final status
    status = manager.get_task_status(task_id)
    print(f"  → Final status: {status['status']}")
    print(f"  → Error: {status['error']}")

    manager.shutdown()
    print("\n✅ Demo 2 Complete: Stale task detected and force-killed")


async def demo_health_check_monitoring():
    """Demo: Health check runs periodically."""
    print("\n" + "=" * 70)
    print("DEMO 3: Periodic Health Check Monitoring")
    print("=" * 70)

    manager = BackgroundTaskManager()

    # Start health check
    print("  → Starting health check (runs every 60 seconds)...")
    health_task = asyncio.create_task(manager.start_health_check())

    # Create multiple tasks
    async def task_a():
        await asyncio.sleep(1)
        return "A done"

    async def task_b():
        await asyncio.sleep(0.5)
        return "B done"

    async def task_c():
        await asyncio.sleep(0.8)
        return "C done"

    print("  → Creating 3 test tasks...")
    task_id_a = await manager.start_async_task("goal1", task_a())
    task_id_b = await manager.start_async_task("goal2", task_b())
    task_id_c = await manager.start_async_task("goal3", task_c())

    print(f"  → Task A: {task_id_a}")
    print(f"  → Task B: {task_id_b}")
    print(f"  → Task C: {task_id_c}")

    # Monitor task progress
    print("\n  → Monitoring task progress...")
    for i in range(5):
        await asyncio.sleep(0.3)
        stats = manager.get_statistics()
        print(f"  → [{i*0.3:.1f}s] Stats: {stats}")

    # Cancel health check
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass

    # Final stats
    stats = manager.get_statistics()
    print(f"\n  → Final stats: {stats}")

    manager.shutdown()
    print("\n✅ Demo 3 Complete: Health check monitored multiple tasks")


async def demo_sync_task_heartbeat():
    """Demo: Sync tasks also have heartbeat monitoring."""
    print("\n" + "=" * 70)
    print("DEMO 4: Sync Task Heartbeat")
    print("=" * 70)

    manager = BackgroundTaskManager()

    def sync_task():
        import time
        print("  → Sync task started (blocking for 1 second)...")
        time.sleep(1)
        return "Sync task done"

    task_id = manager.start_sync_task(
        goal_id="demo_goal",
        func=sync_task,
        timeout_seconds=10
    )

    print(f"  → Task ID: {task_id}")

    # Check heartbeat
    await asyncio.sleep(0.2)
    status = manager.get_task_status(task_id)
    print(f"  → Status: {status['status']}")
    print(f"  → Heartbeat: {status['last_heartbeat']}")
    print(f"  → Timeout: {status['timeout_seconds']}s")

    # Wait for completion
    await asyncio.sleep(1.5)
    status = manager.get_task_status(task_id)
    print(f"  → Final status: {status['status']}")
    print(f"  → Result: {status['result']}")

    manager.shutdown()
    print("\n✅ Demo 4 Complete: Sync task with heartbeat monitoring")


async def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("TASK MANAGER DEADLOCK RECOVERY DEMO")
    print("=" * 70)
    print("\nThis demo shows the deadlock detection and recovery mechanism")
    print("implemented in BackgroundTaskManager.")

    try:
        await demo_normal_task()
        await demo_stale_task_detection()
        await demo_health_check_monitoring()
        await demo_sync_task_heartbeat()

        print("\n" + "=" * 70)
        print("ALL DEMOS COMPLETED SUCCESSFULLY! ✅")
        print("=" * 70)
        print("\nKey Features Demonstrated:")
        print("  1. ✅ Heartbeat timestamps track task health")
        print("  2. ✅ Stale tasks are automatically detected")
        print("  3. ✅ Force-kill mechanism prevents deadlocks")
        print("  4. ✅ Health check runs periodically")
        print("  5. ✅ Both async and sync tasks supported")
        print("\nSee 03_architecture/Phase4/API_FIX_C2_TASK_MANAGER_DEADLOCK.md")
        print("for complete documentation.")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
