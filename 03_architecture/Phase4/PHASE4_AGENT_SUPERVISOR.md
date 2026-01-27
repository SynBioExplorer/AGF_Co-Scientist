# Phase 4 Agent: Supervisor & Task Orchestration

**Branch**: `phase4/supervisor`
**Timeline**: Week 2 (7 days)
**Dependencies**: `BaseStorage` interface (from database agent)
**Priority**: HIGH (blocks Safety and API agents)

---

## Mission

Implement the Supervisor agent that orchestrates all 6 existing agents (Generation, Reflection, Ranking, Evolution, Proximity, Meta-review) with intelligent task scheduling, dynamic resource allocation, and terminal condition detection.

---

## Context

You are working in a **git worktree** on branch `phase4/supervisor`. The Database agent is completing their work in Week 1, and you can begin as soon as `BaseStorage` interface is published.

**Current System State**:
- 6 agents implemented and working (Phases 1-3)
- Current workflow: `src/graphs/workflow.py` (LangGraph-based, manual orchestration)
- No task queue or dynamic weighting
- No convergence detection or statistics tracking

**Your Goal**:
- Implement priority task queue for agent coordination
- Build statistics tracker for effectiveness monitoring
- Create Supervisor agent with orchestration loop
- Integrate with storage layer (use mock storage initially if database not ready)

---

## Deliverables

### Files to Create

1. **src/supervisor/\_\_init\_\_.py** - Package init
2. **src/supervisor/task_queue.py** - Priority-based task queue
3. **src/supervisor/statistics.py** - Agent effectiveness tracking
4. **src/agents/supervisor.py** - Supervisor agent implementation
5. **test_supervisor.py** - Supervisor tests

### Files to Modify

1. **03_architecture/schemas.py** - Ensure `AgentTask`, `SystemStatistics` defined
2. **src/graphs/workflow.py** - Add supervisor integration hooks (optional)

---

## Implementation Guide

### Step 1: Wait for Database Interface (Day 1)

**BLOCKING**: You need `src/storage/base.py` from the Database agent.

```bash
# Check if base.py exists
ls ../main-repo/src/storage/base.py

# If not ready, create a mock for development:
```

**Mock Storage** (temporary, delete after database merges):

**File**: `src/storage/mock_storage.py`

```python
"""Mock storage for supervisor development"""

from typing import List, Optional
from schemas import Hypothesis, Review, TournamentMatch, ResearchGoal
from src.utils.ids import generate_hypothesis_id

class MockStorage:
    """Minimal mock for supervisor testing"""

    def __init__(self):
        self.hypotheses = []
        self.matches = []

    async def get_hypotheses_by_goal(self, goal_id: str) -> List[Hypothesis]:
        return self.hypotheses

    async def get_top_hypotheses(self, n: int = 10, goal_id: str = None) -> List[Hypothesis]:
        return sorted(self.hypotheses, key=lambda h: h.elo_rating, reverse=True)[:n]

    async def get_matches_for_hypothesis(self, hypothesis_id: str) -> List[TournamentMatch]:
        return [m for m in self.matches if m.hypothesis_a_id == hypothesis_id or m.hypothesis_b_id == hypothesis_id]

    async def connect(self):
        pass

    async def disconnect(self):
        pass
```

Use mock until database merges, then switch to `BaseStorage`.

### Step 2: Implement Task Queue (Days 1-2)

**File**: `src/supervisor/task_queue.py`

```python
"""Priority-based task queue for agent coordination"""

from typing import List, Optional, Dict
import heapq
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import AgentTask, AgentType
import structlog

logger = structlog.get_logger()


class TaskQueue:
    """Priority queue for agent tasks with filtering"""

    def __init__(self):
        self._queue: List[tuple] = []  # (priority, counter, task_id, task)
        self._tasks: Dict[str, AgentTask] = {}  # task_id -> task
        self._counter = 0  # FIFO tiebreaker

    def add_task(self, task: AgentTask):
        """Add task to queue with priority

        Args:
            task: AgentTask to add

        Priority determines order:
        - Higher priority (10.0) executed before lower (1.0)
        - Same priority uses FIFO (insertion order)
        """
        priority = task.priority
        # Negative priority for max-heap behavior (heapq is min-heap)
        heapq.heappush(self._queue, (-priority, self._counter, task.id, task))
        self._tasks[task.id] = task
        self._counter += 1

        logger.info(
            "Task added to queue",
            task_id=task.id,
            agent_type=task.agent_type.value,
            priority=priority,
            queue_size=len(self._queue)
        )

    def get_next_task(self, agent_type: Optional[AgentType] = None) -> Optional[AgentTask]:
        """Get highest priority task, optionally filtered by agent type

        Args:
            agent_type: If specified, only return tasks for this agent type

        Returns:
            Highest priority task matching filter, or None if queue empty
        """
        if not self._queue:
            return None

        if agent_type is None:
            # Get highest priority task regardless of type
            _, _, task_id, task = heapq.heappop(self._queue)
            del self._tasks[task_id]
            logger.info("Task retrieved from queue", task_id=task.id)
            return task

        # Filter by agent type (slower, but necessary)
        temp = []
        selected_task = None

        while self._queue:
            priority, counter, task_id, task = heapq.heappop(self._queue)
            if task.agent_type == agent_type and task.status == "pending":
                selected_task = task
                del self._tasks[task_id]
                break
            else:
                temp.append((priority, counter, task_id, task))

        # Put non-matching tasks back
        for item in temp:
            heapq.heappush(self._queue, item)

        if selected_task:
            logger.info("Task retrieved from queue", task_id=selected_task.id, agent_type=agent_type.value)

        return selected_task

    def update_task_status(self, task_id: str, status: str, result: Optional[str] = None):
        """Update task status and result

        Args:
            task_id: Task ID to update
            status: New status (pending, in_progress, completed, failed)
            result: Optional result data (JSON string)
        """
        if task_id in self._tasks:
            self._tasks[task_id].status = status
            if result:
                self._tasks[task_id].result = result
            logger.info("Task status updated", task_id=task_id, status=status)

    def get_pending_count(self, agent_type: Optional[AgentType] = None) -> int:
        """Count pending tasks, optionally filtered by agent type

        Args:
            agent_type: If specified, count only tasks for this agent

        Returns:
            Number of pending tasks
        """
        if agent_type is None:
            return len([t for t in self._tasks.values() if t.status == "pending"])
        else:
            return len([
                t for t in self._tasks.values()
                if t.status == "pending" and t.agent_type == agent_type
            ])

    def get_all_tasks(self, status: Optional[str] = None) -> List[AgentTask]:
        """Get all tasks, optionally filtered by status

        Args:
            status: Optional status filter

        Returns:
            List of tasks
        """
        if status is None:
            return list(self._tasks.values())
        else:
            return [t for t in self._tasks.values() if t.status == status]

    def clear(self):
        """Clear all tasks (for testing)"""
        self._queue = []
        self._tasks = {}
        self._counter = 0
        logger.info("Task queue cleared")
```

**Test TaskQueue**:
```python
# Quick test
from src.supervisor.task_queue import TaskQueue
from schemas import AgentTask, AgentType

queue = TaskQueue()
task1 = AgentTask(id="task1", agent_type=AgentType.GENERATION, priority=10.0, parameters={}, status="pending")
task2 = AgentTask(id="task2", agent_type=AgentType.REFLECTION, priority=5.0, parameters={}, status="pending")

queue.add_task(task1)
queue.add_task(task2)

# Should get task1 first (higher priority)
next_task = queue.get_next_task()
assert next_task.id == "task1"
```

### Step 3: Implement Statistics Tracker (Days 2-3)

**File**: `src/supervisor/statistics.py`

```python
"""Agent effectiveness and tournament convergence tracking"""

from typing import Dict
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import SystemStatistics, AgentType, Hypothesis
from src.storage.base import BaseStorage
import structlog

logger = structlog.get_logger()


class SupervisorStatistics:
    """Compute system statistics for resource allocation"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage

    async def compute_statistics(self, goal_id: str) -> SystemStatistics:
        """Compute current system statistics

        Args:
            goal_id: Research goal ID to compute stats for

        Returns:
            SystemStatistics with all metrics
        """
        logger.info("Computing system statistics", goal_id=goal_id)

        # Get all hypotheses for this goal
        hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)

        # Count by status
        generated = len([h for h in hypotheses if h.status.value == "generated"])
        reviewed = len([h for h in hypotheses if h.status.value in ["initial_review", "full_review"]])
        in_tournament = len([h for h in hypotheses if h.status.value == "in_tournament"])

        # Tournament progress
        all_matches = []
        for h in hypotheses:
            matches = await self.storage.get_matches_for_hypothesis(h.id)
            all_matches.extend(matches)

        total_matches = len(all_matches)

        # Calculate tournament convergence
        # Convergence = 1.0 - (Elo standard deviation / 100)
        # Lower std dev = higher convergence (ratings have stabilized)
        top_hypotheses = await self.storage.get_top_hypotheses(n=5, goal_id=goal_id)
        elo_std = self._calculate_elo_std(top_hypotheses)
        convergence_score = max(0.0, 1.0 - elo_std / 100.0)

        # Agent effectiveness (TODO: refine based on actual performance)
        # For now, use heuristics:
        # - Generation: % of generated hypotheses that pass initial review
        # - Evolution: % of evolved hypotheses that improve Elo
        # - Reflection: Always maintain (1.0)
        agent_effectiveness = {
            AgentType.GENERATION: self._calculate_generation_effectiveness(hypotheses),
            AgentType.EVOLUTION: self._calculate_evolution_effectiveness(hypotheses),
            AgentType.REFLECTION: 1.0,  # Always maintain review capacity
        }

        stats = SystemStatistics(
            hypotheses_generated=len(hypotheses),
            hypotheses_pending_review=generated,
            hypotheses_in_tournament=in_tournament,
            total_matches=total_matches,
            tournament_convergence=convergence_score,
            agent_effectiveness=agent_effectiveness,
            generation_method_success={}  # TODO: Track by generation method
        )

        logger.info(
            "Statistics computed",
            total_hypotheses=len(hypotheses),
            convergence=convergence_score,
            pending_review=generated
        )

        return stats

    def _calculate_elo_std(self, hypotheses: List[Hypothesis]) -> float:
        """Calculate standard deviation of Elo ratings

        Lower std = more convergence (ratings stabilized)
        """
        if not hypotheses:
            return 0.0

        elos = [h.elo_rating for h in hypotheses]
        mean_elo = sum(elos) / len(elos)
        variance = sum((e - mean_elo) ** 2 for e in elos) / len(elos)
        return variance ** 0.5

    def _calculate_generation_effectiveness(self, hypotheses: List[Hypothesis]) -> float:
        """Calculate generation agent effectiveness

        Effectiveness = (# hypotheses reviewed) / (# hypotheses generated)
        """
        generated = len([h for h in hypotheses if h.status.value == "generated"])
        reviewed = len([h for h in hypotheses if h.status.value in ["initial_review", "full_review", "in_tournament"]])

        if generated + reviewed == 0:
            return 0.5  # Default

        return reviewed / (generated + reviewed)

    def _calculate_evolution_effectiveness(self, hypotheses: List[Hypothesis]) -> float:
        """Calculate evolution agent effectiveness

        Effectiveness = (# evolved hypotheses with Elo > parent) / (# evolved hypotheses)
        """
        evolved = [h for h in hypotheses if h.parent_hypothesis_id is not None]
        if not evolved:
            return 0.5  # Default

        # TODO: Compare Elo with parent
        # For now, use placeholder
        return 0.6
```

### Step 4: Implement Supervisor Agent (Days 3-5)

**File**: `src/agents/supervisor.py`

```python
"""Supervisor agent for multi-agent orchestration"""

from typing import Dict, List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import (
    ResearchGoal, ResearchPlanConfiguration, AgentTask,
    AgentType, SystemStatistics, Hypothesis
)
from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.supervisor.task_queue import TaskQueue
from src.supervisor.statistics import SupervisorStatistics
from src.storage.base import BaseStorage
from src.config import settings
from src.utils.ids import generate_id
import asyncio
import structlog

logger = structlog.get_logger()


class SupervisorAgent(BaseAgent):
    """Central orchestrator for multi-agent system"""

    def __init__(self, storage: BaseStorage):
        llm_client = get_llm_client(
            model=settings.supervisor_model,
            agent_name="supervisor"
        )
        super().__init__(llm_client, "SupervisorAgent")

        self.storage = storage
        self.task_queue = TaskQueue()
        self.statistics = SupervisorStatistics(storage)
        self.agent_weights: Dict[AgentType, float] = self._initialize_weights()

    def _initialize_weights(self) -> Dict[AgentType, float]:
        """Set initial agent weights (resource allocation)

        Weights sum to ~1.0, representing % of compute resources
        """
        return {
            AgentType.GENERATION: 0.4,   # 40% - create hypotheses
            AgentType.REFLECTION: 0.2,   # 20% - review hypotheses
            AgentType.RANKING: 0.2,      # 20% - tournament matches
            AgentType.EVOLUTION: 0.1,    # 10% - refine top hypotheses
            AgentType.PROXIMITY: 0.05,   # 5% - cluster similar hypotheses
            AgentType.META_REVIEW: 0.05  # 5% - synthesize feedback
        }

    async def execute(self, research_goal: ResearchGoal, max_iterations: int = 20) -> str:
        """Run supervisor orchestration loop

        Args:
            research_goal: Research goal to work on
            max_iterations: Maximum iterations before stopping

        Returns:
            Status message
        """
        self.log_execution(
            task="supervisor_orchestration",
            goal=research_goal.description[:100],
            max_iterations=max_iterations
        )

        # Step 1: Parse research goal into configuration
        config = await self._parse_research_goal(research_goal)
        logger.info("Research plan configuration created", config_id=config.id)

        # Step 2: Initialize task queue with generation tasks
        self._initialize_tasks(research_goal.id, config)

        # Step 3: Execution loop
        iteration = 0
        while iteration < max_iterations:
            logger.info(f"\n{'='*50}")
            logger.info(f"Iteration {iteration + 1}/{max_iterations}")
            logger.info(f"{'='*50}")

            # Compute statistics
            stats = await self.statistics.compute_statistics(research_goal.id)

            # Check terminal conditions
            if self._should_terminate(stats, iteration):
                logger.info("Terminal condition reached", iteration=iteration)
                break

            # Adjust agent weights based on effectiveness
            self._adjust_weights(stats)

            # Execute one iteration
            await self._execute_iteration(research_goal.id, stats)

            iteration += 1

        # Step 4: Generate final research overview
        logger.info("Generating final research overview")
        await self._generate_final_overview(research_goal)

        return f"Supervisor completed after {iteration} iterations"

    async def _parse_research_goal(self, goal: ResearchGoal) -> ResearchPlanConfiguration:
        """Parse natural language goal into structured configuration

        Uses LLM to extract evaluation criteria, constraints, etc.

        Args:
            goal: Research goal from user

        Returns:
            Structured configuration
        """
        prompt = f"""
        Parse this research goal into a structured configuration:

        Goal: {goal.description}
        Constraints: {', '.join(goal.constraints)}
        Preferences: {', '.join(goal.preferences)}

        Extract:
        1. Evaluation criteria (e.g., novelty, feasibility, testability)
        2. Domain constraints (e.g., "clinical trials only", "in vitro only")
        3. Quality threshold (0.0-1.0, what review score is acceptable)

        Return JSON:
        {{
            "evaluation_criteria": ["criterion1", "criterion2"],
            "domain_constraints": ["constraint1"],
            "quality_threshold": 0.7
        }}
        """

        # TODO: Invoke LLM, parse JSON response
        # For now, return default config
        return ResearchPlanConfiguration(
            id=generate_id("config"),
            research_goal_id=goal.id,
            evaluation_criteria=["novelty", "feasibility", "testability"],
            domain_constraints=goal.constraints,
            enabled_tools=["web_search", "literature_review"],
            quality_threshold=0.7
        )

    def _initialize_tasks(self, goal_id: str, config: ResearchPlanConfiguration):
        """Create initial generation tasks

        Args:
            goal_id: Research goal ID
            config: Parsed configuration
        """
        # Start with 3 hypothesis generation tasks
        for i in range(3):
            task = AgentTask(
                id=generate_id("task"),
                agent_type=AgentType.GENERATION,
                priority=10.0,  # High priority for initial generation
                parameters={"goal_id": goal_id, "method": "literature"},
                status="pending"
            )
            self.task_queue.add_task(task)

        logger.info("Initial tasks added to queue", count=3)

    def _adjust_weights(self, stats: SystemStatistics):
        """Dynamically adjust agent weights based on effectiveness

        Args:
            stats: Current system statistics
        """
        # Generation weight based on success rate
        gen_effectiveness = stats.agent_effectiveness.get(AgentType.GENERATION, 0.5)
        self.agent_weights[AgentType.GENERATION] = 0.4 if gen_effectiveness > 0.5 else 0.2

        # Evolution weight based on improvement rate
        evo_effectiveness = stats.agent_effectiveness.get(AgentType.EVOLUTION, 0.3)
        self.agent_weights[AgentType.EVOLUTION] = 0.3 if evo_effectiveness > 0.3 else 0.0

        # Reflection always maintains capacity
        self.agent_weights[AgentType.REFLECTION] = 0.2

        # Ranking based on pending comparisons
        pending_comparisons = stats.hypotheses_in_tournament
        self.agent_weights[AgentType.RANKING] = min(0.2, pending_comparisons / 100.0)

        logger.info("Agent weights adjusted", weights=self.agent_weights)

    async def _execute_iteration(self, goal_id: str, stats: SystemStatistics):
        """Execute one iteration of task assignments

        Args:
            goal_id: Research goal ID
            stats: Current statistics
        """
        # Assign tasks based on weights
        tasks_to_execute = []

        for agent_type, weight in self.agent_weights.items():
            # Scale weight to number of tasks (weight * 10)
            num_tasks = int(weight * 10)

            for _ in range(num_tasks):
                task = self.task_queue.get_next_task(agent_type)
                if task:
                    tasks_to_execute.append(task)

        logger.info(f"Executing {len(tasks_to_execute)} tasks in parallel")

        # TODO: Execute tasks using actual agents
        # For now, just log
        for task in tasks_to_execute:
            logger.info(f"Would execute task: {task.id} ({task.agent_type.value})")

    def _should_terminate(self, stats: SystemStatistics, iteration: int) -> bool:
        """Check if terminal conditions are met

        Args:
            stats: Current statistics
            iteration: Current iteration number

        Returns:
            True if should terminate
        """
        # Budget exhausted
        from cost_tracker import get_tracker
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent / "04_Scripts"))
        tracker = get_tracker()
        if tracker.is_over_budget():
            logger.info("Terminating: Budget exhausted")
            return True

        # Tournament convergence (after min iterations)
        if stats.tournament_convergence > 0.9 and iteration > 5:
            logger.info("Terminating: Tournament converged", convergence=stats.tournament_convergence)
            return True

        # Quality threshold met
        # TODO: Check average review scores of top hypotheses

        return False

    async def _generate_final_overview(self, goal: ResearchGoal):
        """Trigger meta-review agent for final synthesis

        Args:
            goal: Research goal
        """
        # TODO: Call Meta-review agent to generate ResearchOverview
        logger.info("Would generate research overview", goal_id=goal.id)
```

### Step 5: Create Tests (Days 6-7)

**File**: `test_supervisor.py`

```python
#!/usr/bin/env python3
"""Test supervisor components"""

import pytest
import asyncio
from src.supervisor.task_queue import TaskQueue
from src.supervisor.statistics import SupervisorStatistics
from src.agents.supervisor import SupervisorAgent
from src.storage.mock_storage import MockStorage
from schemas import AgentTask, AgentType, ResearchGoal

def test_task_queue_priority():
    """Test task queue priority ordering"""
    queue = TaskQueue()

    task1 = AgentTask(id="low", agent_type=AgentType.GENERATION, priority=1.0, parameters={}, status="pending")
    task2 = AgentTask(id="high", agent_type=AgentType.GENERATION, priority=10.0, parameters={}, status="pending")

    queue.add_task(task1)
    queue.add_task(task2)

    # Should get high priority first
    next_task = queue.get_next_task()
    assert next_task.id == "high"

@pytest.mark.asyncio
async def test_statistics_computation():
    """Test statistics computation"""
    storage = MockStorage()
    await storage.connect()

    stats_tracker = SupervisorStatistics(storage)
    stats = await stats_tracker.compute_statistics("test_goal")

    assert stats.hypotheses_generated >= 0
    assert 0.0 <= stats.tournament_convergence <= 1.0

@pytest.mark.asyncio
async def test_supervisor_orchestration():
    """Test supervisor orchestration loop"""
    storage = MockStorage()
    await storage.connect()

    supervisor = SupervisorAgent(storage)

    goal = ResearchGoal(
        id="test_goal",
        description="Test goal",
        constraints=[],
        preferences=[]
    )

    # Run 1 iteration
    result = await supervisor.execute(goal, max_iterations=1)
    assert "completed" in result.lower()
```

---

## Testing Checklist

- [ ] TaskQueue maintains priority order
- [ ] TaskQueue filters by agent type
- [ ] Statistics tracker computes convergence
- [ ] Agent weights adjust based on effectiveness
- [ ] Terminal conditions trigger correctly
- [ ] Supervisor initializes task queue
- [ ] Supervisor executes multiple iterations
- [ ] Integration with mock storage works

---

## Success Criteria

**Week 2 Complete When**:

1. ✅ Task queue with priority scheduling works
2. ✅ Statistics tracker computes all metrics
3. ✅ Supervisor agent orchestrates execution loop
4. ✅ Agent weights dynamically adjust
5. ✅ Terminal conditions detect convergence/budget
6. ✅ Tests pass
7. ✅ Committed and pushed to `phase4/supervisor` branch

---

## Integration Notes

**After Database Merges**:
1. Replace `MockStorage` with `BaseStorage`
2. Test with actual PostgreSQL backend
3. Update imports in supervisor.py

**For Safety/API Agents**:
- Your `SupervisorAgent` class will be used by API agent
- Safety agent will hook into task queue

---

## Git Workflow

```bash
# Daily commits
git add .
git commit -m "feat(supervisor): [description]"
git push origin phase4/supervisor

# Example commits:
# Day 1: "feat(supervisor): implement priority task queue"
# Day 2: "feat(supervisor): add statistics tracker"
# Day 3: "feat(supervisor): implement supervisor agent skeleton"
# Day 4: "feat(supervisor): add weight adjustment logic"
# Day 5: "feat(supervisor): complete orchestration loop"
# Day 6: "test(supervisor): add comprehensive tests"
# Day 7: "docs(supervisor): finalize supervisor component"
```

---

Your mission: Build the brain of the AI Co-Scientist system! 🧠
