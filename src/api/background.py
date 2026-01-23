"""Background task management for long-running operations"""

from typing import Dict, Optional, Callable, Any, List
import asyncio
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import structlog

logger = structlog.get_logger()


class BackgroundTaskManager:
    """Manage background tasks for supervisor execution and long-running operations.

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

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get the running event loop.

        In FastAPI context, there should always be a running loop.
        If not, we're being called from a sync context which is an error.
        """
        if self._loop is None or self._loop.is_closed():
            # Get the running loop from FastAPI's context
            self._loop = asyncio.get_running_loop()
        return self._loop

    def start_sync_task(
        self,
        goal_id: str,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> str:
        """Start a synchronous function as a background task.

        This runs the function in a thread pool executor to avoid blocking.

        Args:
            goal_id: Research goal ID associated with this task
            func: Synchronous function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())

        # Initialize task status
        self._task_status[task_id] = {
            "goal_id": goal_id,
            "status": "running",
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "error": None,
            "result": None
        }

        logger.info("Background task started", task_id=task_id, goal_id=goal_id)

        # Run the sync function in thread pool
        loop = self._get_loop()

        async def run_in_executor():
            try:
                result = await loop.run_in_executor(
                    self._executor,
                    lambda: func(*args, **kwargs)
                )
                self._on_task_success(task_id, result)
            except Exception as e:
                self._on_task_error(task_id, e)

        # Create and store the task
        task = asyncio.create_task(run_in_executor())
        self._tasks[task_id] = task

        return task_id

    async def start_async_task(
        self,
        goal_id: str,
        coroutine
    ) -> str:
        """Start an async coroutine as a background task.

        Args:
            goal_id: Research goal ID associated with this task
            coroutine: Async coroutine to execute

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())

        # Initialize task status
        self._task_status[task_id] = {
            "goal_id": goal_id,
            "status": "running",
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "error": None,
            "result": None
        }

        # Create task
        task = asyncio.create_task(coroutine)
        self._tasks[task_id] = task

        # Add completion callback
        task.add_done_callback(lambda t: self._on_task_complete(task_id, t))

        logger.info("Background async task started", task_id=task_id, goal_id=goal_id)
        return task_id

    def _on_task_success(self, task_id: str, result: Any) -> None:
        """Handle successful task completion."""
        self._task_status[task_id]["status"] = "completed"
        self._task_status[task_id]["completed_at"] = datetime.utcnow()
        self._task_status[task_id]["result"] = result
        logger.info("Background task completed successfully", task_id=task_id)

    def _on_task_error(self, task_id: str, error: Exception) -> None:
        """Handle task error."""
        self._task_status[task_id]["status"] = "failed"
        self._task_status[task_id]["completed_at"] = datetime.utcnow()
        self._task_status[task_id]["error"] = str(error)
        logger.error("Background task failed", task_id=task_id, error=str(error))

    def _on_task_complete(self, task_id: str, task: asyncio.Task) -> None:
        """Callback when async task completes."""
        if task.cancelled():
            self._task_status[task_id]["status"] = "cancelled"
            logger.info("Background task cancelled", task_id=task_id)
        elif task.exception():
            self._task_status[task_id]["status"] = "failed"
            self._task_status[task_id]["error"] = str(task.exception())
            logger.error(
                "Background task failed",
                task_id=task_id,
                error=str(task.exception())
            )
        else:
            self._task_status[task_id]["status"] = "completed"
            self._task_status[task_id]["result"] = task.result()
            logger.info("Background task completed", task_id=task_id)

        self._task_status[task_id]["completed_at"] = datetime.utcnow()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status.

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None if not found
        """
        return self._task_status.get(task_id)

    def get_tasks_for_goal(self, goal_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a specific goal.

        Args:
            goal_id: Research goal ID

        Returns:
            List of task status dicts
        """
        return [
            {"task_id": tid, **status}
            for tid, status in self._task_status.items()
            if status["goal_id"] == goal_id
        ]

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
        self._task_status[task_id]["status"] = "cancelled"
        self._task_status[task_id]["completed_at"] = datetime.utcnow()
        logger.info("Background task cancelled", task_id=task_id)
        return True

    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> int:
        """Remove completed tasks older than specified age.

        Args:
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Number of tasks cleaned up
        """
        from datetime import timedelta

        now = datetime.utcnow()
        cutoff = now - timedelta(hours=max_age_hours)
        cleaned = 0

        for task_id in list(self._task_status.keys()):
            status = self._task_status[task_id]
            if status["status"] in ("completed", "failed", "cancelled"):
                completed_at = status.get("completed_at")
                if completed_at and completed_at < cutoff:
                    del self._task_status[task_id]
                    if task_id in self._tasks:
                        del self._tasks[task_id]
                    cleaned += 1

        if cleaned > 0:
            logger.info("Cleaned up old tasks", count=cleaned)

        return cleaned

    def shutdown(self) -> None:
        """Shutdown the task manager and executor."""
        # Cancel all running tasks
        for task_id, task in self._tasks.items():
            if not task.done():
                task.cancel()
                self._task_status[task_id]["status"] = "cancelled"

        # Shutdown thread pool
        self._executor.shutdown(wait=False)
        logger.info("Background task manager shutdown")


# Import List for type hint
from typing import List

# Global instance
task_manager = BackgroundTaskManager()
