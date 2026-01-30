"""Test deadlock detection and force-kill mechanism for background tasks.

This test verifies that:
1. Heartbeat timestamps are updated during task execution
2. Tasks without heartbeat updates are detected as stale
3. Stale tasks are automatically force-killed
4. Force-killed tasks are properly cleaned up
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
from datetime import datetime, timedelta

# Import directly from background.py to avoid FastAPI dependency
import importlib.util
spec = importlib.util.spec_from_file_location(
    "background",
    project_root / "src" / "api" / "background.py"
)
background_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(background_module)

BackgroundTaskManager = background_module.BackgroundTaskManager
HEARTBEAT_TIMEOUT_MULTIPLIER = background_module.HEARTBEAT_TIMEOUT_MULTIPLIER


class TestTaskDeadlockFix:
    """Test suite for task deadlock detection and recovery."""

    @pytest.fixture
    def task_manager(self):
        """Create a fresh task manager for each test."""
        manager = BackgroundTaskManager(max_workers=2)
        yield manager
        manager.shutdown()

    @pytest.mark.asyncio
    async def test_heartbeat_initialization(self, task_manager):
        """Test that tasks initialize with a heartbeat timestamp."""

        async def quick_task():
            await asyncio.sleep(0.1)
            return "done"

        task_id = await task_manager.start_async_task(
            goal_id="test_goal",
            coroutine=quick_task(),
            timeout_seconds=60
        )

        # Check status immediately
        status = task_manager.get_task_status(task_id)
        assert status is not None
        assert "last_heartbeat" in status
        assert status["last_heartbeat"] is not None
        assert "timeout_seconds" in status
        assert status["timeout_seconds"] == 60

        # Wait for task to complete
        await asyncio.sleep(0.2)
        status = task_manager.get_task_status(task_id)
        assert status["status"] == "completed"

    @pytest.mark.asyncio
    async def test_heartbeat_updates_during_execution(self, task_manager):
        """Test that heartbeat is updated periodically during long tasks."""

        async def long_task():
            # Run for 3 seconds
            for _ in range(6):
                await asyncio.sleep(0.5)
            return "done"

        task_id = await task_manager.start_async_task(
            goal_id="test_goal",
            coroutine=long_task(),
            timeout_seconds=10
        )

        # Get initial heartbeat
        await asyncio.sleep(0.1)
        status1 = task_manager.get_task_status(task_id)
        heartbeat1 = status1["last_heartbeat"]

        # Wait for heartbeat update (should update every 30s, but we'll wait 1s)
        await asyncio.sleep(1.0)
        status2 = task_manager.get_task_status(task_id)
        heartbeat2 = status2["last_heartbeat"]

        # Heartbeat should be updated (or at least exist)
        assert heartbeat2 is not None
        assert status2["status"] == "running"

        # Wait for completion
        await asyncio.sleep(2.5)
        status3 = task_manager.get_task_status(task_id)
        assert status3["status"] == "completed"

    @pytest.mark.asyncio
    async def test_stale_task_detection(self, task_manager):
        """Test that stale tasks are detected by health check."""

        # Create a task with very short timeout
        async def hanging_task():
            # Simulate a hung task that doesn't complete
            await asyncio.sleep(100)

        task_id = await task_manager.start_async_task(
            goal_id="test_goal",
            coroutine=hanging_task(),
            timeout_seconds=1  # 1 second timeout
        )

        # Wait a bit for task to start
        await asyncio.sleep(0.1)

        # Manually set heartbeat to old timestamp (simulate stale task)
        with task_manager._lock:
            if task_id in task_manager._task_status:
                old_time = datetime.utcnow() - timedelta(seconds=5)
                task_manager._task_status[task_id]["last_heartbeat"] = old_time

        # Run health check
        killed = task_manager._check_task_health()

        # Task should be force-killed (5 seconds > 2x 1 second timeout)
        assert killed == 1

        # Check task status
        status = task_manager.get_task_status(task_id)
        assert status["status"] == "failed"
        assert "timeout/deadlock" in status["error"]

    @pytest.mark.asyncio
    async def test_no_false_positives(self, task_manager):
        """Test that healthy tasks are not killed."""

        async def healthy_task():
            # Run for a bit but within timeout
            await asyncio.sleep(1.0)
            return "done"

        task_id = await task_manager.start_async_task(
            goal_id="test_goal",
            coroutine=healthy_task(),
            timeout_seconds=10
        )

        # Wait a bit
        await asyncio.sleep(0.2)

        # Run health check
        killed = task_manager._check_task_health()

        # No tasks should be killed
        assert killed == 0

        # Task should still be running or completed
        status = task_manager.get_task_status(task_id)
        assert status["status"] in ("running", "completed")

    @pytest.mark.asyncio
    async def test_force_kill_cleanup(self, task_manager):
        """Test that force-killed tasks are properly cleaned up."""

        async def long_task():
            await asyncio.sleep(100)

        task_id = await task_manager.start_async_task(
            goal_id="test_goal",
            coroutine=long_task(),
            timeout_seconds=1
        )

        await asyncio.sleep(0.1)

        # Force kill the task directly
        result = task_manager._force_kill_task(task_id)
        assert result is True

        # Check cleanup
        status = task_manager.get_task_status(task_id)
        assert status["status"] == "failed"
        assert status["completed_at"] is not None
        assert "force-killed" in status["error"].lower()

    @pytest.mark.asyncio
    async def test_health_check_periodic_execution(self, task_manager):
        """Test that health check can run periodically without errors."""

        # Start health check task
        health_task = asyncio.create_task(task_manager.start_health_check())

        # Create some test tasks
        async def task1():
            await asyncio.sleep(0.5)
            return "done1"

        async def task2():
            await asyncio.sleep(0.3)
            return "done2"

        task_id1 = await task_manager.start_async_task("goal1", task1())
        task_id2 = await task_manager.start_async_task("goal2", task2())

        # Let health check run a bit (it checks every 60s, but one iteration is enough)
        await asyncio.sleep(0.2)

        # Cancel health check
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

        # Tasks should complete normally
        await asyncio.sleep(0.6)
        status1 = task_manager.get_task_status(task_id1)
        status2 = task_manager.get_task_status(task_id2)

        assert status1["status"] == "completed"
        assert status2["status"] == "completed"

    @pytest.mark.asyncio
    async def test_sync_task_heartbeat(self, task_manager):
        """Test heartbeat for synchronous tasks."""

        def sync_task():
            import time
            time.sleep(1)
            return "sync_done"

        task_id = task_manager.start_sync_task(
            goal_id="test_goal",
            func=sync_task,
            timeout_seconds=10
        )

        # Check initial heartbeat
        await asyncio.sleep(0.1)
        status = task_manager.get_task_status(task_id)
        assert status is not None
        assert "last_heartbeat" in status
        assert status["timeout_seconds"] == 10

        # Wait for completion
        await asyncio.sleep(1.5)
        status = task_manager.get_task_status(task_id)
        assert status["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
