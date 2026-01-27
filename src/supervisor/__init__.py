"""Supervisor orchestration module for AI Co-Scientist.

This module provides task scheduling, statistics tracking, checkpoint management,
and the Supervisor agent that orchestrates all specialized agents in the system.

Components:
- TaskQueue: Priority-based task queue for agent coordination
- SupervisorStatistics: Agent effectiveness and convergence tracking
- CheckpointManager: Workflow state persistence and resume (Safety Agent)
- SupervisorAgent: Central orchestrator (in src/agents/supervisor.py)
"""

from src.supervisor.task_queue import TaskQueue
from src.supervisor.statistics import SupervisorStatistics
from src.supervisor.checkpoint import CheckpointManager

__all__ = ["TaskQueue", "SupervisorStatistics", "CheckpointManager"]
