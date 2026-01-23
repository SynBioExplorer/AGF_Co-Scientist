"""Priority-based task queue for agent coordination.

This module provides the TaskQueue class that manages agent tasks using a
priority-based scheduling system. Tasks are executed in order of priority,
with FIFO ordering for tasks of equal priority.

The queue supports:
- Priority-based ordering (higher priority first)
- Filtering by agent type
- Status tracking (pending, running, complete, failed)
- Task retrieval and updates
"""

from typing import List, Optional, Dict
from datetime import datetime
import heapq
import sys
from pathlib import Path

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import AgentTask, AgentType

import structlog

logger = structlog.get_logger()


class TaskQueue:
    """Priority queue for agent tasks with filtering.

    Tasks are ordered by priority (higher first), with FIFO ordering
    for tasks of equal priority. Supports filtering by agent type
    for worker processes that specialize in certain task types.

    Attributes:
        _queue: Heap-based priority queue (uses negative priority for max-heap)
        _tasks: Dictionary mapping task_id to AgentTask for fast lookups
        _counter: Monotonic counter for FIFO tiebreaking
    """

    def __init__(self):
        """Initialize empty task queue."""
        self._queue: List[tuple] = []  # (neg_priority, counter, task_id, task)
        self._tasks: Dict[str, AgentTask] = {}  # task_id -> task
        self._counter = 0  # FIFO tiebreaker

    def add_task(self, task: AgentTask) -> None:
        """Add task to queue with priority.

        Args:
            task: AgentTask to add to the queue.

        Priority determines order:
        - Higher priority (10) executed before lower (1)
        - Same priority uses FIFO (insertion order)
        """
        priority = task.priority
        # Negative priority for max-heap behavior (heapq is min-heap)
        heapq.heappush(
            self._queue,
            (-priority, self._counter, task.id, task)
        )
        self._tasks[task.id] = task
        self._counter += 1

        logger.info(
            "task_added_to_queue",
            task_id=task.id,
            agent_type=task.agent_type.value,
            task_type=task.task_type,
            priority=priority,
            queue_size=len(self._queue)
        )

    def get_next_task(
        self,
        agent_type: Optional[AgentType] = None
    ) -> Optional[AgentTask]:
        """Get highest priority task, optionally filtered by agent type.

        This method removes the task from the queue. If filtering by
        agent_type, non-matching tasks are temporarily removed and
        then restored.

        Args:
            agent_type: If specified, only return tasks for this agent type.

        Returns:
            Highest priority pending task matching filter, or None if empty.
        """
        if not self._queue:
            return None

        if agent_type is None:
            # Get highest priority task regardless of type
            while self._queue:
                neg_priority, counter, task_id, task = heapq.heappop(self._queue)
                # Skip if task was already removed or not pending
                if task_id in self._tasks and task.status == "pending":
                    del self._tasks[task_id]
                    logger.info(
                        "task_retrieved",
                        task_id=task.id,
                        agent_type=task.agent_type.value
                    )
                    return task
            return None

        # Filter by agent type (temporarily remove non-matching)
        temp = []
        selected_task = None

        while self._queue:
            item = heapq.heappop(self._queue)
            neg_priority, counter, task_id, task = item

            # Skip if task was removed or not pending
            if task_id not in self._tasks or task.status != "pending":
                continue

            if task.agent_type == agent_type:
                selected_task = task
                del self._tasks[task_id]
                break
            else:
                temp.append(item)

        # Restore non-matching tasks
        for item in temp:
            heapq.heappush(self._queue, item)

        if selected_task:
            logger.info(
                "task_retrieved_filtered",
                task_id=selected_task.id,
                agent_type=agent_type.value
            )

        return selected_task

    def peek_next_task(
        self,
        agent_type: Optional[AgentType] = None
    ) -> Optional[AgentTask]:
        """Peek at highest priority task without removing it.

        Args:
            agent_type: If specified, only return tasks for this agent type.

        Returns:
            Highest priority pending task matching filter, or None if empty.
        """
        if not self._queue:
            return None

        if agent_type is None:
            # Find first pending task
            for neg_priority, counter, task_id, task in sorted(self._queue):
                if task_id in self._tasks and task.status == "pending":
                    return task
            return None

        # Filter by agent type
        for neg_priority, counter, task_id, task in sorted(self._queue):
            if task_id in self._tasks and task.status == "pending":
                if task.agent_type == agent_type:
                    return task
        return None

    def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict] = None
    ) -> bool:
        """Update task status and optionally set result.

        Args:
            task_id: Task ID to update.
            status: New status (pending, running, complete, failed).
            result: Optional result data (dict) for completed tasks.

        Returns:
            True if task was found and updated, False otherwise.
        """
        if task_id not in self._tasks:
            logger.warning("task_not_found", task_id=task_id)
            return False

        task = self._tasks[task_id]
        old_status = task.status
        task.status = status

        if result:
            task.result = result

        if status == "running" and not task.started_at:
            task.started_at = datetime.now()
        elif status in ("complete", "failed"):
            task.completed_at = datetime.now()

        logger.info(
            "task_status_updated",
            task_id=task_id,
            old_status=old_status,
            new_status=status
        )
        return True

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID without removing it.

        Args:
            task_id: Task ID to retrieve.

        Returns:
            The task if found, None otherwise.
        """
        return self._tasks.get(task_id)

    def get_pending_count(
        self,
        agent_type: Optional[AgentType] = None
    ) -> int:
        """Count pending tasks, optionally filtered by agent type.

        Args:
            agent_type: If specified, count only tasks for this agent.

        Returns:
            Number of pending tasks.
        """
        tasks = self._tasks.values()
        if agent_type:
            return len([
                t for t in tasks
                if t.status == "pending" and t.agent_type == agent_type
            ])
        return len([t for t in tasks if t.status == "pending"])

    def get_running_count(
        self,
        agent_type: Optional[AgentType] = None
    ) -> int:
        """Count running tasks, optionally filtered by agent type.

        Args:
            agent_type: If specified, count only tasks for this agent.

        Returns:
            Number of running tasks.
        """
        tasks = self._tasks.values()
        if agent_type:
            return len([
                t for t in tasks
                if t.status == "running" and t.agent_type == agent_type
            ])
        return len([t for t in tasks if t.status == "running"])

    def get_all_tasks(
        self,
        status: Optional[str] = None,
        agent_type: Optional[AgentType] = None
    ) -> List[AgentTask]:
        """Get all tasks, optionally filtered.

        Args:
            status: Optional status filter (pending, running, complete, failed).
            agent_type: Optional agent type filter.

        Returns:
            List of matching tasks sorted by priority (highest first).
        """
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        if agent_type:
            tasks = [t for t in tasks if t.agent_type == agent_type]

        return sorted(tasks, key=lambda t: t.priority, reverse=True)

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the queue.

        Args:
            task_id: Task ID to remove.

        Returns:
            True if task was found and removed, False otherwise.
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            # Note: Task remains in heap but will be skipped in get_next_task
            logger.info("task_removed", task_id=task_id)
            return True
        return False

    def clear(self) -> None:
        """Clear all tasks from the queue."""
        self._queue = []
        self._tasks = {}
        self._counter = 0
        logger.info("task_queue_cleared")

    def get_statistics(self) -> Dict[str, int]:
        """Get queue statistics.

        Returns:
            Dictionary with task counts by status.
        """
        stats = {
            "total": len(self._tasks),
            "pending": 0,
            "running": 0,
            "complete": 0,
            "failed": 0,
        }

        for task in self._tasks.values():
            if task.status in stats:
                stats[task.status] += 1

        return stats

    def get_statistics_by_agent(self) -> Dict[str, Dict[str, int]]:
        """Get queue statistics grouped by agent type.

        Returns:
            Dictionary mapping agent type to task counts.
        """
        stats: Dict[str, Dict[str, int]] = {}

        for task in self._tasks.values():
            agent_type = task.agent_type.value
            if agent_type not in stats:
                stats[agent_type] = {"pending": 0, "running": 0, "complete": 0, "failed": 0}
            if task.status in stats[agent_type]:
                stats[agent_type][task.status] += 1

        return stats

    def __len__(self) -> int:
        """Return total number of tasks in queue."""
        return len(self._tasks)

    def __repr__(self) -> str:
        """String representation of queue state."""
        stats = self.get_statistics()
        return (
            f"TaskQueue(total={stats['total']}, pending={stats['pending']}, "
            f"running={stats['running']}, complete={stats['complete']})"
        )
