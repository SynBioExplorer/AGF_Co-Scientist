"""Background task management for long-running operations.

This module provides task management with:
- Automatic cleanup of completed tasks to prevent memory leaks
- Result size limiting to prevent memory bloat
- Periodic cleanup via background task
- Thread-safe operations
"""

from typing import Dict, Optional, Callable, Any, List
import asyncio
import uuid
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import structlog

logger = structlog.get_logger()

# Maximum size for stored results (10KB)
MAX_RESULT_SIZE = 10 * 1024

# Heartbeat configuration
HEARTBEAT_INTERVAL_SECONDS = 30  # Update heartbeat every 30 seconds
HEARTBEAT_TIMEOUT_MULTIPLIER = 2  # Force kill after 2x timeout
HEALTH_CHECK_INTERVAL_SECONDS = 60  # Check task health every 60 seconds
DEFAULT_TASK_TIMEOUT_SECONDS = 3600  # Default 1 hour timeout


class BackgroundTaskManager:
    """Manage background tasks for supervisor execution and long-running operations.

    Features:
    - Automatic periodic cleanup of old completed tasks
    - Result size limiting to prevent memory bloat
    - Thread-safe status updates
    - Graceful shutdown with task cancellation

    Since the workflow runs synchronously, we use a ThreadPoolExecutor to run
    workflows in background threads without blocking the API.
    """

    def __init__(self, max_workers: int = 4):
        """Initialize the background task manager.

        Args:
            max_workers: Maximum number of concurrent worker threads
        """
        self._tasks: Dict[str, asyncio.Task] = {}
        self._task_status: Dict[str, Dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock = Lock()  # Thread-safe status updates

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get the running event loop.

        In FastAPI context, there should always be a running loop.
        If not, we're being called from a sync context which is an error.
        """
        if self._loop is None or self._loop.is_closed():
            # Get the running loop from FastAPI's context
            self._loop = asyncio.get_running_loop()
        return self._loop

    async def start_periodic_cleanup(
        self,
        interval_hours: int = 1,
        max_age_hours: int = 24
    ) -> None:
        """Start background cleanup task that runs periodically.

        This should be called during application startup to ensure
        old completed tasks are automatically cleaned up.

        Args:
            interval_hours: How often to run cleanup (default: 1 hour)
            max_age_hours: Maximum age for completed tasks (default: 24 hours)
        """
        logger.info(
            "Starting periodic task cleanup",
            interval_hours=interval_hours,
            max_age_hours=max_age_hours
        )

        while True:
            try:
                await asyncio.sleep(interval_hours * 3600)
                cleaned = self.cleanup_completed_tasks(max_age_hours=max_age_hours)
                logger.info(
                    "Periodic cleanup completed",
                    tasks_cleaned=cleaned,
                    tasks_remaining=len(self._task_status)
                )
            except asyncio.CancelledError:
                logger.info("Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error("Periodic cleanup failed", error=str(e))
                # Continue running despite errors

    async def start_health_check(self) -> None:
        """Start background health check task that monitors for deadlocks.

        This runs periodically to:
        - Update heartbeat timestamps for running tasks
        - Detect stale tasks (no heartbeat for 2x timeout)
        - Force-kill tasks that exceed timeout

        This should be called during application startup.
        """
        logger.info(
            "Starting task health check",
            interval_seconds=HEALTH_CHECK_INTERVAL_SECONDS,
            heartbeat_timeout_multiplier=HEARTBEAT_TIMEOUT_MULTIPLIER
        )

        while True:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
                killed = self._check_task_health()
                if killed > 0:
                    logger.warning(
                        "Health check force-killed stale tasks",
                        tasks_killed=killed
                    )
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error("Health check failed", error=str(e))
                # Continue running despite errors

    def _truncate_result(self, result: Any) -> Any:
        """Truncate result to prevent memory bloat.

        Large results are converted to string and truncated.

        Args:
            result: The task result to potentially truncate.

        Returns:
            Truncated result if too large, original otherwise.
        """
        if result is None:
            return None

        result_str = str(result)
        if len(result_str) > MAX_RESULT_SIZE:
            truncated = result_str[:MAX_RESULT_SIZE]
            return f"{truncated}...[truncated, original size: {len(result_str)} bytes]"

        return result

    def _update_heartbeat(self, task_id: str) -> None:
        """Update the heartbeat timestamp for a running task.

        Args:
            task_id: Task ID to update heartbeat for
        """
        with self._lock:
            if task_id in self._task_status:
                status = self._task_status[task_id]["status"]
                if status == "running":
                    self._task_status[task_id]["last_heartbeat"] = datetime.utcnow()

    def _check_task_health(self) -> int:
        """Check health of all running tasks and force-kill stale ones.

        A task is considered stale if:
        - It has no heartbeat timestamp, OR
        - Its last heartbeat is older than 2x the configured timeout

        Returns:
            Number of tasks force-killed
        """
        now = datetime.utcnow()
        tasks_to_kill = []

        # First pass: identify stale tasks (with lock)
        with self._lock:
            for task_id in list(self._task_status.keys()):
                status = self._task_status[task_id]

                # Only check running tasks
                if status["status"] != "running":
                    continue

                # Get task timeout (default if not specified)
                timeout_seconds = status.get("timeout_seconds", DEFAULT_TASK_TIMEOUT_SECONDS)
                max_allowed_seconds = timeout_seconds * HEARTBEAT_TIMEOUT_MULTIPLIER

                # Check if task is stale
                last_heartbeat = status.get("last_heartbeat")
                started_at = status["started_at"]

                is_stale = False
                reason = ""

                if last_heartbeat is None:
                    # No heartbeat ever recorded - check if started too long ago
                    elapsed = (now - started_at).total_seconds()
                    if elapsed > max_allowed_seconds:
                        is_stale = True
                        reason = f"no heartbeat after {elapsed:.0f}s (max: {max_allowed_seconds:.0f}s)"
                else:
                    # Check last heartbeat
                    heartbeat_age = (now - last_heartbeat).total_seconds()
                    if heartbeat_age > max_allowed_seconds:
                        is_stale = True
                        reason = f"heartbeat stale for {heartbeat_age:.0f}s (max: {max_allowed_seconds:.0f}s)"

                if is_stale:
                    tasks_to_kill.append((task_id, reason))
                    logger.warning(
                        "Detected stale task for force-kill",
                        task_id=task_id,
                        reason=reason
                    )

        # Second pass: kill stale tasks (outside lock to avoid deadlock)
        killed = 0
        for task_id, reason in tasks_to_kill:
            if self._force_kill_task(task_id):
                killed += 1

        return killed

    def _force_kill_task(self, task_id: str) -> bool:
        """Force-kill a task that has exceeded timeout.

        This cancels the task and marks it as failed with timeout error.

        Args:
            task_id: Task ID to force-kill

        Returns:
            True if task was killed, False if not found or already complete
        """
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]

        # Cancel the task
        if not task.done():
            task.cancel()

        # Update status
        with self._lock:
            if task_id in self._task_status:
                self._task_status[task_id]["status"] = "failed"
                self._task_status[task_id]["completed_at"] = datetime.utcnow()
                self._task_status[task_id]["error"] = "Task force-killed due to timeout/deadlock"

        logger.error(
            "Task force-killed",
            task_id=task_id,
            reason="timeout/deadlock"
        )

        return True

    def start_sync_task(
        self,
        goal_id: str,
        func: Callable[..., Any],
        *args,
        timeout_seconds: Optional[int] = None,
        **kwargs
    ) -> str:
        """Start a synchronous function as a background task.

        This runs the function in a thread pool executor to avoid blocking.

        Args:
            goal_id: Research goal ID associated with this task
            func: Synchronous function to execute
            *args: Positional arguments for the function
            timeout_seconds: Optional timeout in seconds (default: 3600)
            **kwargs: Keyword arguments for the function

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        timeout = timeout_seconds or DEFAULT_TASK_TIMEOUT_SECONDS

        # Initialize task status (thread-safe)
        now = datetime.utcnow()
        with self._lock:
            self._task_status[task_id] = {
                "goal_id": goal_id,
                "status": "running",
                "started_at": now,
                "completed_at": None,
                "error": None,
                "result": None,
                "last_heartbeat": now,  # Initialize heartbeat
                "timeout_seconds": timeout
            }

        logger.info("Background task started", task_id=task_id, goal_id=goal_id, timeout_seconds=timeout)

        # Run the sync function in thread pool
        loop = self._get_loop()

        async def run_in_executor_with_heartbeat():
            """Wrapper that updates heartbeat periodically during execution."""
            # Create heartbeat task
            async def heartbeat_loop():
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                    self._update_heartbeat(task_id)

            heartbeat_task = asyncio.create_task(heartbeat_loop())

            try:
                result = await loop.run_in_executor(
                    self._executor,
                    lambda: func(*args, **kwargs)
                )
                self._on_task_success(task_id, result)
            except Exception as e:
                self._on_task_error(task_id, e)
            finally:
                # Stop heartbeat
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        # Create and store the task
        task = asyncio.create_task(run_in_executor_with_heartbeat())
        self._tasks[task_id] = task

        return task_id

    async def start_async_task(
        self,
        goal_id: str,
        coroutine,
        timeout_seconds: Optional[int] = None
    ) -> str:
        """Start an async coroutine as a background task.

        Args:
            goal_id: Research goal ID associated with this task
            coroutine: Async coroutine to execute
            timeout_seconds: Optional timeout in seconds (default: 3600)

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        timeout = timeout_seconds or DEFAULT_TASK_TIMEOUT_SECONDS

        # Initialize task status (thread-safe)
        now = datetime.utcnow()
        with self._lock:
            self._task_status[task_id] = {
                "goal_id": goal_id,
                "status": "running",
                "started_at": now,
                "completed_at": None,
                "error": None,
                "result": None,
                "last_heartbeat": now,  # Initialize heartbeat
                "timeout_seconds": timeout
            }

        # Wrap coroutine with heartbeat updates
        async def coroutine_with_heartbeat():
            """Wrapper that updates heartbeat periodically during execution."""
            # Create heartbeat task
            async def heartbeat_loop():
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                    self._update_heartbeat(task_id)

            heartbeat_task = asyncio.create_task(heartbeat_loop())

            try:
                result = await coroutine
                return result
            finally:
                # Stop heartbeat
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        # Create task
        task = asyncio.create_task(coroutine_with_heartbeat())
        self._tasks[task_id] = task

        # Add completion callback
        task.add_done_callback(lambda t: self._on_task_complete(task_id, t))

        logger.info("Background async task started", task_id=task_id, goal_id=goal_id, timeout_seconds=timeout)
        return task_id

    def _on_task_success(self, task_id: str, result: Any) -> None:
        """Handle successful task completion."""
        with self._lock:
            if task_id in self._task_status:
                self._task_status[task_id]["status"] = "completed"
                self._task_status[task_id]["completed_at"] = datetime.utcnow()
                self._task_status[task_id]["result"] = self._truncate_result(result)
        logger.info("Background task completed successfully", task_id=task_id)

    def _on_task_error(self, task_id: str, error: Exception) -> None:
        """Handle task error."""
        with self._lock:
            if task_id in self._task_status:
                self._task_status[task_id]["status"] = "failed"
                self._task_status[task_id]["completed_at"] = datetime.utcnow()
                self._task_status[task_id]["error"] = str(error)[:1000]  # Limit error size
        logger.error("Background task failed", task_id=task_id, error=str(error))

    def _on_task_complete(self, task_id: str, task: asyncio.Task) -> None:
        """Callback when async task completes."""
        with self._lock:
            if task_id not in self._task_status:
                return

            if task.cancelled():
                self._task_status[task_id]["status"] = "cancelled"
                logger.info("Background task cancelled", task_id=task_id)
            elif task.exception():
                self._task_status[task_id]["status"] = "failed"
                self._task_status[task_id]["error"] = str(task.exception())[:1000]
                logger.error(
                    "Background task failed",
                    task_id=task_id,
                    error=str(task.exception())
                )
            else:
                self._task_status[task_id]["status"] = "completed"
                self._task_status[task_id]["result"] = self._truncate_result(task.result())
                logger.info("Background task completed", task_id=task_id)

            self._task_status[task_id]["completed_at"] = datetime.utcnow()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None if not found
        """
        with self._lock:
            status = self._task_status.get(task_id)
            return dict(status) if status else None  # Return copy

    def get_tasks_for_goal(self, goal_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a specific goal.

        Args:
            goal_id: Research goal ID

        Returns:
            List of task status dicts
        """
        with self._lock:
            return [
                {"task_id": tid, **dict(status)}
                for tid, status in self._task_status.items()
                if status["goal_id"] == goal_id
            ]

    def get_statistics(self) -> Dict[str, int]:
        """Get task manager statistics.

        Returns:
            Dict with counts of tasks in each status.
        """
        with self._lock:
            stats = {
                "total": len(self._task_status),
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0
            }
            for status in self._task_status.values():
                status_key = status["status"]
                if status_key in stats:
                    stats[status_key] += 1
            return stats

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled, False if not found or already complete
        """
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        if task.done():
            return False

        task.cancel()
        with self._lock:
            if task_id in self._task_status:
                self._task_status[task_id]["status"] = "cancelled"
                self._task_status[task_id]["completed_at"] = datetime.utcnow()
        logger.info("Background task cancelled", task_id=task_id)
        return True

    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> int:
        """Remove completed tasks older than specified age.

        Args:
            max_age_hours: Maximum age in hours before cleanup.
                Use 0 to clean all completed tasks regardless of age.

        Returns:
            Number of tasks cleaned up
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=max_age_hours) if max_age_hours > 0 else now
        cleaned = 0

        with self._lock:
            for task_id in list(self._task_status.keys()):
                status = self._task_status[task_id]
                if status["status"] in ("completed", "failed", "cancelled"):
                    completed_at = status.get("completed_at")
                    # Clean if older than cutoff, or if max_age_hours is 0
                    if max_age_hours == 0 or (completed_at and completed_at < cutoff):
                        del self._task_status[task_id]
                        if task_id in self._tasks:
                            del self._tasks[task_id]
                        cleaned += 1

        if cleaned > 0:
            logger.info("Cleaned up old tasks", count=cleaned)

        return cleaned

    def shutdown(self) -> None:
        """Shutdown the task manager and executor."""
        # Cancel cleanup task if running
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()

        # Cancel health check task if running
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()

        # Cancel all running tasks
        for task_id, task in list(self._tasks.items()):
            if not task.done():
                task.cancel()
                with self._lock:
                    if task_id in self._task_status:
                        self._task_status[task_id]["status"] = "cancelled"

        # Clear all task data to free memory
        with self._lock:
            self._task_status.clear()
            self._tasks.clear()

        # Shutdown thread pool
        self._executor.shutdown(wait=False)
        logger.info("Background task manager shutdown")


# Global instance
task_manager = BackgroundTaskManager()
