"""Supervisor Agent for multi-agent orchestration.

This module provides the SupervisorAgent class that orchestrates all 6
specialized agents (Generation, Reflection, Ranking, Evolution, Proximity,
Meta-review) with intelligent task scheduling, dynamic resource allocation,
and terminal condition detection.

The Supervisor implements the control flow described in the Google AI
Co-Scientist paper:
1. Parse research goal into configuration
2. Initialize task queue with generation tasks
3. Execute continuous loop:
   - Assign agents to tasks based on weights
   - Execute tasks asynchronously
   - Compute statistics periodically
   - Adjust resource allocation based on effectiveness
   - Check terminal conditions
4. Generate final research overview

Terminal conditions:
- Elo ratings converge (top hypotheses stabilize)
- Compute budget exhausted
- Quality threshold met
- Scientist manually stops
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import sys
from pathlib import Path

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import (
    ResearchGoal,
    ResearchPlanConfiguration,
    EvaluationCriterion,
    AgentTask,
    AgentType,
    SystemStatistics,
    Hypothesis,
    ContextMemory,
    HypothesisStatus,
    GenerationMethod,
    ReviewType,
    EvolutionStrategy,
)

# Add scripts directory for cost tracker
sys.path.append(str(Path(__file__).parent.parent.parent / "04_Scripts"))
from cost_tracker import get_tracker, BudgetExceededError

from src.agents.base import BaseAgent
from src.agents.safety import SafetyAgent
from src.llm.factory import get_llm_client
from src.supervisor.task_queue import TaskQueue
from src.supervisor.statistics import SupervisorStatistics
from src.storage.async_adapter import AsyncStorageAdapter
from src.config import settings
from src.utils.ids import generate_id, generate_task_id
from src.utils.json_parser import parse_llm_json
from src.utils.strategy_selector import select_evolution_strategy
from src.utils.errors import LLMClientError, CheckpointError
from src.observability.tracing import trace_agent

import structlog

logger = structlog.get_logger()


class SupervisorAgent(BaseAgent):
    """Central orchestrator for the multi-agent AI Co-Scientist system.

    The Supervisor agent coordinates all 6 specialized agents, managing
    task scheduling, resource allocation, and terminal condition detection.

    Attributes:
        storage: Async storage adapter for data persistence.
        task_queue: Priority-based task queue for agent coordination.
        statistics: Statistics tracker for effectiveness monitoring.
        agent_weights: Current resource allocation weights per agent type.
        iteration: Current iteration number.
        cost_tracker: Budget tracking and enforcement.
    """

    def __init__(self, storage: AsyncStorageAdapter):
        """Initialize Supervisor agent.

        Args:
            storage: Async storage adapter for data access.
        """
        llm_client = get_llm_client(
            model=settings.supervisor_model,
            agent_name="supervisor"
        )
        super().__init__(llm_client, "SupervisorAgent")

        self.storage = storage
        self.task_queue = TaskQueue()
        self.statistics = SupervisorStatistics(storage)
        self.agent_weights: Dict[AgentType, float] = self._initialize_weights()
        self.iteration = 0
        self.cost_tracker = get_tracker(budget_aud=settings.budget_aud)

        # Safety agent for hypothesis review
        self.safety_agent = SafetyAgent()
        self.safety_threshold = settings.safety_threshold

        # Context memory for self-improving loop (Paper Section 3.1)
        self._context_insights: list[str] = []
        self._explored_directions: list[str] = []
        self._used_match_pairs: set[tuple[str, str]] = set()
        self._last_evolved_ids: list[str] = []

        # Concurrency control for async worker execution (Paper Figure 2)
        self._worker_semaphore = asyncio.Semaphore(settings.max_workers)

        # Agent instances (lazy-loaded)
        self._agents: Dict[AgentType, Any] = {}

    def _initialize_weights(self) -> Dict[AgentType, float]:
        """Set initial agent weights for resource allocation.

        Weights sum to ~1.0 and represent the proportion of compute
        resources allocated to each agent type.

        Returns:
            Dictionary mapping agent type to weight.
        """
        return {
            AgentType.GENERATION: 0.25,          # 25% - create hypotheses
            AgentType.REFLECTION: 0.25,          # 25% - INITIAL + FULL + DEEP_VERIFICATION reviews
            AgentType.RANKING: 0.20,             # 20% - tournament matches
            AgentType.EVOLUTION: 0.13,           # 13% - refine top hypotheses
            AgentType.OBSERVATION_REVIEW: 0.08,  # 8% - validate against literature
            AgentType.PROXIMITY: 0.05,           # 5% - cluster similar hypotheses
            AgentType.META_REVIEW: 0.04,         # 4% - synthesize feedback
        }

    async def _update_context_memory(self, goal_id: str) -> None:
        """Accumulate insights from meta-review and hypotheses into context memory.

        Called at the end of each iteration to grow the self-improving loop.
        """
        meta_review = await self.storage.get_meta_review(goal_id)
        if meta_review:
            tag = f"[Iter {self.iteration}]"
            for s in getattr(meta_review, "recurring_strengths", []):
                self._context_insights.append(f"{tag} Strength: {s}")
            for w in getattr(meta_review, "recurring_weaknesses", []):
                self._context_insights.append(f"{tag} Weakness: {w}")
            for o in getattr(meta_review, "improvement_opportunities", []):
                self._context_insights.append(f"{tag} Opportunity: {o}")

        hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)
        for h in hypotheses:
            if h.title not in self._explored_directions:
                self._explored_directions.append(h.title)

        # Truncate to prevent unbounded growth
        self._context_insights = self._context_insights[-30:]
        self._explored_directions = self._explored_directions[-60:]

        logger.info(
            "context_memory_updated",
            goal_id=goal_id,
            iteration=self.iteration,
            insights=len(self._context_insights),
            explored=len(self._explored_directions),
        )

    def _format_context_for_prompt(self) -> str:
        """Format accumulated context memory as a prompt section for agents."""
        if not self._context_insights and not self._explored_directions:
            return ""

        parts = []
        if self._context_insights:
            parts.append("ACCUMULATED INSIGHTS FROM PRIOR ITERATIONS:")
            for item in self._context_insights[-15:]:
                parts.append(f"  - {item}")

        if self._explored_directions:
            parts.append("\nALREADY EXPLORED DIRECTIONS (do NOT repeat these):")
            for d in self._explored_directions[-20:]:
                parts.append(f"  - {d}")

        return "\n".join(parts)

    def _get_agent(self, agent_type: AgentType) -> Any:
        """Get or create an agent instance.

        Args:
            agent_type: Type of agent to get.

        Returns:
            Agent instance.
        """
        if agent_type not in self._agents:
            if agent_type == AgentType.GENERATION:
                from src.agents.generation import GenerationAgent
                self._agents[agent_type] = GenerationAgent()
            elif agent_type == AgentType.REFLECTION:
                from src.agents.reflection import ReflectionAgent
                self._agents[agent_type] = ReflectionAgent()
            elif agent_type == AgentType.RANKING:
                from src.agents.ranking import RankingAgent
                self._agents[agent_type] = RankingAgent()
            elif agent_type == AgentType.EVOLUTION:
                from src.agents.evolution import EvolutionAgent
                self._agents[agent_type] = EvolutionAgent()
            elif agent_type == AgentType.PROXIMITY:
                from src.agents.proximity import ProximityAgent
                self._agents[agent_type] = ProximityAgent()
            elif agent_type == AgentType.META_REVIEW:
                from src.agents.meta_review import MetaReviewAgent
                self._agents[agent_type] = MetaReviewAgent()
            elif agent_type == AgentType.OBSERVATION_REVIEW:
                from src.agents.observation_review import ObservationReviewAgent
                self._agents[agent_type] = ObservationReviewAgent()
        return self._agents.get(agent_type)

    @trace_agent("SupervisorAgent")
    async def execute(
        self,
        research_goal: ResearchGoal,
        max_iterations: int = 20,
        min_hypotheses: int = 6,
        quality_threshold: float = 0.85,
        convergence_threshold: float = 0.9,
        max_execution_time_seconds: int | None = None,
    ) -> str:
        """Run supervisor orchestration loop.

        This is the main entry point for the Supervisor agent. It
        orchestrates the full hypothesis generation and evaluation
        pipeline until terminal conditions are met.

        Args:
            research_goal: Research goal to work on.
            max_iterations: Maximum iterations before stopping.
            min_hypotheses: Minimum hypotheses before allowing convergence stop.
            quality_threshold: Average quality score threshold.
            convergence_threshold: Elo convergence threshold.
            max_execution_time_seconds: Maximum total execution time in seconds.
                Defaults to settings.supervisor_max_execution_seconds (7200 = 2 hours).

        Returns:
            Status message with summary of execution.
        """
        self.log_execution(
            task="supervisor_orchestration",
            goal=research_goal.description[:100],
            max_iterations=max_iterations
        )

        # Store research goal
        await self.storage.add_research_goal(research_goal)

        # Step 1: Parse research goal into configuration
        config = await self._parse_research_goal(research_goal)
        logger.info(
            "research_config_created",
            config_id=config.research_goal_id,
            criteria=config.evaluation_criteria
        )

        # Step 2: Initialize task queue with generation tasks
        self._initialize_tasks(research_goal.id)

        # Step 3: Execution loop
        self.iteration = 0
        terminal_reason = None

        # Track workflow start time for absolute time limit (AGENT-C1 fix)
        started_at = datetime.now()
        if max_execution_time_seconds is None:
            max_execution_time_seconds = settings.supervisor_max_execution_seconds

        logger.info(
            "supervisor_time_limit_set",
            max_execution_time_seconds=max_execution_time_seconds,
            max_execution_hours=round(max_execution_time_seconds / 3600, 2)
        )

        self.max_iterations = max_iterations
        while self.iteration < max_iterations:
            self.iteration += 1
            logger.info(
                "iteration_start",
                iteration=self.iteration,
                max_iterations=max_iterations
            )

            try:
                # Check budget before iteration
                self.cost_tracker.check_budget()
            except BudgetExceededError as e:
                terminal_reason = f"Budget exhausted: {e}"
                logger.warning("budget_exhausted", error=str(e))
                break

            # Compute statistics
            stats = await self.statistics.compute_statistics(research_goal.id)

            # Check terminal conditions (including time limit)
            should_stop, reason = await self._check_terminal_conditions(
                stats=stats,
                min_hypotheses=min_hypotheses,
                quality_threshold=quality_threshold,
                convergence_threshold=convergence_threshold,
                started_at=started_at,
                max_execution_time_seconds=max_execution_time_seconds
            )
            if should_stop:
                terminal_reason = reason
                logger.info("terminal_condition_met", reason=reason)
                break

            # Adjust agent weights based on effectiveness
            self.agent_weights = await self.statistics.recommend_agent_weights(
                research_goal.id, stats
            )
            logger.info(
                "weights_adjusted",
                weights={k.value: round(v, 2) for k, v in self.agent_weights.items()}
            )

            # Execute one iteration
            await self._execute_iteration(research_goal)

            # Update context memory (self-improving loop)
            await self._update_context_memory(research_goal.id)

            # Save checkpoint
            await self._save_checkpoint(research_goal.id, stats)

            # Log progress
            logger.info(
                "iteration_complete",
                iteration=self.iteration,
                hypotheses=stats.total_hypotheses,
                convergence=round(stats.tournament_convergence_score, 3)
            )

        # Step 4: Generate final research overview
        logger.info("generating_final_overview")
        overview = await self._generate_final_overview(research_goal)

        # Print cost summary
        self.cost_tracker.print_summary()

        return (
            f"Supervisor completed after {self.iteration} iterations. "
            f"Reason: {terminal_reason or 'max iterations reached'}. "
            f"Generated {overview.research_goal_id if overview else 'no'} overview."
        )

    async def _parse_research_goal(
        self,
        goal: ResearchGoal
    ) -> ResearchPlanConfiguration:
        """Parse natural language goal into structured configuration.

        Uses the LLM to extract evaluation criteria, domain constraints,
        and quality thresholds from the research goal.

        Args:
            goal: Research goal from user.

        Returns:
            Structured configuration for the research.
        """
        prompt = f"""Parse this research goal into a structured configuration:

Goal: {goal.description}
Constraints: {', '.join(goal.constraints) if goal.constraints else 'None specified'}
Preferences: {', '.join(goal.preferences) if goal.preferences else 'None specified'}
Laboratory Context: {goal.laboratory_context or 'Not specified'}

Extract the following as JSON:
{{
    "evaluation_criteria": ["criterion1", "criterion2", ...],
    "domain_constraints": ["constraint1", "constraint2", ...],
    "tools_enabled": ["web_search", "literature_review", ...],
    "quality_threshold": 0.7,
    "require_novelty": true
}}

Focus on:
1. Key evaluation criteria (novelty, feasibility, testability, safety, etc.)
2. Domain-specific constraints from the goal
3. What tools would be useful
4. Appropriate quality threshold (0.5-0.9)

Respond with ONLY the JSON object."""

        response = self.llm_client.invoke(prompt)

        try:
            data = parse_llm_json(response, agent_name="SupervisorAgent")

            # Convert criterion strings to EvaluationCriterion objects
            criteria_names = data.get("evaluation_criteria", [])
            evaluation_criteria = [
                EvaluationCriterion(
                    name=name,
                    description=f"Evaluation based on {name}",
                    weight=1.0
                )
                for name in criteria_names
            ]

            return ResearchPlanConfiguration(
                research_goal_id=goal.id,
                evaluation_criteria=evaluation_criteria,
                domain_constraints=data.get("domain_constraints", goal.constraints),
                tools_enabled=data.get("tools_enabled", ["web_search"]),
                require_novelty=data.get("require_novelty", True),
            )
        except Exception as e:
            logger.warning(
                "config_parse_failed_using_defaults",
                error=str(e)
            )
            # Return default configuration with proper EvaluationCriterion objects
            default_criteria = ["novelty", "feasibility", "testability"]
            evaluation_criteria = [
                EvaluationCriterion(
                    name=name,
                    description=f"Evaluation based on {name}",
                    weight=1.0
                )
                for name in default_criteria
            ]

            return ResearchPlanConfiguration(
                research_goal_id=goal.id,
                evaluation_criteria=evaluation_criteria,
                domain_constraints=goal.constraints,
                tools_enabled=["web_search", "literature_review"],
                require_novelty=True,
            )

    def _initialize_tasks(self, goal_id: str) -> None:
        """Create initial generation tasks.

        Starts the pipeline with several hypothesis generation tasks
        using different generation methods for diversity.

        Args:
            goal_id: Research goal ID.
        """
        # Clear any existing tasks
        self.task_queue.clear()

        # Create initial generation tasks with different methods
        methods = [
            GenerationMethod.LITERATURE_EXPLORATION,
            GenerationMethod.LITERATURE_EXPLORATION,
            GenerationMethod.SIMULATED_DEBATE,
        ]

        for i, method in enumerate(methods):
            task = AgentTask(
                id=generate_task_id(),
                agent_type=AgentType.GENERATION,
                task_type="generate_hypothesis",
                priority=10 - i,  # Slightly decreasing priority
                parameters={
                    "goal_id": goal_id,
                    "method": method.value,
                    "use_web_search": i == 0,  # First task uses web search
                },
                status="pending"
            )
            self.task_queue.add_task(task)

        logger.info(
            "initial_tasks_created",
            count=len(methods),
            goal_id=goal_id
        )

    async def _execute_task_with_semaphore(
        self,
        task: AgentTask,
        research_goal: ResearchGoal
    ) -> tuple:
        """Execute a task with concurrency control via semaphore.

        Returns:
            Tuple of (task, result_or_None, error_or_None).
        """
        async with self._worker_semaphore:
            try:
                self.task_queue.update_task_status(task.id, "running")
                result = await self._execute_task(task, research_goal)
                self.task_queue.update_task_status(task.id, "complete", result=result)
                return (task, result, None)
            except Exception as e:
                logger.error(
                    "task_execution_failed",
                    task_id=task.id,
                    agent_type=task.agent_type.value,
                    error=str(e)
                )
                self.task_queue.update_task_status(task.id, "failed")
                return (task, None, e)

    async def _execute_iteration(self, research_goal: ResearchGoal) -> None:
        """Execute one iteration with phase-based parallel execution.

        Tasks are organized into dependency-ordered phases (Paper Figure 2).
        Within each phase, tasks run concurrently via asyncio.gather.

        Phases:
          1. GENERATION, PROXIMITY (create hypotheses + update graph)
          2. REFLECTION, OBSERVATION_REVIEW (review new hypotheses)
          3. RANKING, EVOLUTION (tournament + refine)
          4. META_REVIEW (synthesize feedback)

        Args:
            research_goal: Current research goal.
        """
        # Refresh proximity graph periodically
        if (settings.proximity_aware_pairing and
            self.iteration % settings.proximity_graph_refresh_frequency == 0):
            hypotheses = await self.storage.get_hypotheses_by_goal(research_goal.id)
            if len(hypotheses) >= 2:
                self.task_queue.add_task(AgentTask(
                    id=generate_task_id(),
                    agent_type=AgentType.PROXIMITY,
                    task_type="build_proximity_graph",
                    priority=8,
                    parameters={
                        "goal_id": research_goal.id,
                        "hypothesis_ids": [h.id for h in hypotheses],
                    },
                    status="pending"
                ))

        execution_phases = [
            [AgentType.GENERATION, AgentType.PROXIMITY],
            [AgentType.REFLECTION, AgentType.OBSERVATION_REVIEW],
            [AgentType.RANKING, AgentType.EVOLUTION],
            [AgentType.META_REVIEW],
        ]

        tasks_per_iteration = 12
        executed_count = 0

        for phase_idx, phase_agents in enumerate(execution_phases):
            phase_tasks: list[AgentTask] = []

            for agent_type in phase_agents:
                weight = self.agent_weights.get(agent_type, 0)
                if weight <= 0:
                    continue

                num_tasks = max(1, int(weight * tasks_per_iteration))
                for _ in range(num_tasks):
                    task = self.task_queue.get_next_task(agent_type)
                    if not task:
                        task = await self._create_task_for_agent(
                            agent_type, research_goal
                        )
                        if not task:
                            continue
                        self.task_queue.add_task(task)  # Register so update_task_status can find it
                    phase_tasks.append(task)

            if not phase_tasks:
                continue

            # Execute all tasks in this phase concurrently
            results = await asyncio.gather(
                *[self._execute_task_with_semaphore(t, research_goal) for t in phase_tasks],
                return_exceptions=True
            )

            for item in results:
                if isinstance(item, Exception):
                    logger.error("phase_gather_error", phase=phase_idx + 1, error=str(item))
                    continue
                _task, _result, _error = item
                if _error is None:
                    executed_count += 1

        logger.info(
            "iteration_tasks_executed",
            count=executed_count,
            queue_stats=self.task_queue.get_statistics()
        )

    async def _create_task_for_agent(
        self,
        agent_type: AgentType,
        research_goal: ResearchGoal
    ) -> Optional[AgentTask]:
        """Create a new task for an agent type.

        Determines what work is needed based on current system state
        and creates an appropriate task.

        Args:
            agent_type: Type of agent needing work.
            research_goal: Current research goal.

        Returns:
            New task or None if no work needed.
        """
        goal_id = research_goal.id

        if agent_type == AgentType.GENERATION:
            # Paper Section 3.3.1 lists 4 generation methods; we rotate 3 of them
            # for diversity. RESEARCH_EXPANSION falls back to LITERATURE if no
            # research overview is available yet (early iterations).
            import random
            method = random.choices(
                [
                    GenerationMethod.LITERATURE_EXPLORATION,
                    GenerationMethod.SIMULATED_DEBATE,
                    GenerationMethod.RESEARCH_EXPANSION,
                ],
                weights=[0.35, 0.35, 0.30], k=1
            )[0]
            return AgentTask(
                id=generate_task_id(),
                agent_type=AgentType.GENERATION,
                task_type="generate_hypothesis",
                priority=8,
                parameters={
                    "goal_id": goal_id,
                    "method": method.value,
                },
                status="pending"
            )

        elif agent_type == AgentType.REFLECTION:
            # Find hypotheses needing initial review first
            needing_review = await self.storage.get_hypotheses_needing_review(
                goal_id, limit=1
            )
            if needing_review:
                return AgentTask(
                    id=generate_task_id(),
                    agent_type=AgentType.REFLECTION,
                    task_type="review_hypothesis",
                    priority=9,
                    parameters={
                        "hypothesis_id": needing_review[0].id,
                        "review_type": ReviewType.INITIAL.value,
                    },
                    status="pending"
                )

            # No initial reviews needed - schedule deep verification for top hypotheses
            top_hyps = await self.storage.get_top_hypotheses(n=3, goal_id=goal_id)
            for hyp in top_hyps:
                if hyp.status == HypothesisStatus.FULL_REVIEW:
                    reviews = await self.storage.get_reviews_for_hypothesis(hyp.id)
                    has_deep = any(r.review_type == ReviewType.DEEP_VERIFICATION for r in reviews)
                    if not has_deep:
                        return AgentTask(
                            id=generate_task_id(),
                            agent_type=AgentType.REFLECTION,
                            task_type="deep_verification_review",
                            priority=8,
                            parameters={
                                "hypothesis_id": hyp.id,
                                "review_type": ReviewType.DEEP_VERIFICATION.value,
                            },
                            status="pending"
                        )

        elif agent_type == AgentType.RANKING:
            # Find hypotheses for tournament
            hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)
            reviewed = [
                h for h in hypotheses
                if h.status != HypothesisStatus.GENERATED
            ]
            if len(reviewed) >= 2:
                # Annotate each hypothesis with match count so the ranker
                # can prioritize newcomers (paper: "newer hypotheses prioritized")
                from collections import Counter
                all_matches = await self.storage.get_all_matches(goal_id)
                match_counts: Counter = Counter()
                for m in (all_matches or []):
                    match_counts[m.hypothesis_a_id] += 1
                    match_counts[m.hypothesis_b_id] += 1
                for h in reviewed:
                    h._match_count = match_counts.get(h.id, 0)

                # Get proximity graph if proximity-aware pairing is enabled
                proximity_graph = None
                if settings.proximity_aware_pairing:
                    try:
                        proximity_graph = await self.storage.get_proximity_graph(goal_id)
                    except Exception as e:
                        logger.warning(
                            "proximity_graph_retrieval_failed",
                            goal_id=goal_id,
                            error=str(e)
                        )

                # Use TournamentRanker with proximity graph
                from src.tournament.elo import TournamentRanker
                ranker = TournamentRanker()

                pairs = ranker.select_match_pairs(
                    hypotheses=reviewed,
                    top_n=min(20, len(reviewed)),
                    proximity_graph=proximity_graph,
                    use_proximity=settings.proximity_aware_pairing,
                    proximity_weight=settings.proximity_pairing_weight,
                    diversity_weight=settings.diversity_pairing_weight,
                    exclude_pairs=self._used_match_pairs,
                )

                if pairs:
                    # Record all pairs to prevent re-matching in future iterations
                    for h_a, h_b in pairs:
                        self._used_match_pairs.add(tuple(sorted([h_a.id, h_b.id])))

                    # Queue extra pairs beyond the first, respecting ranking budget
                    tasks_per_iteration = 12
                    ranking_weight = self.agent_weights.get(AgentType.RANKING, 0)
                    num_ranking_tasks = max(1, int(ranking_weight * tasks_per_iteration))
                    extra_budget = max(0, num_ranking_tasks - 1)

                    for h_extra_a, h_extra_b in pairs[1:1 + extra_budget]:
                        self.task_queue.add_task(AgentTask(
                            id=generate_task_id(),
                            agent_type=AgentType.RANKING,
                            task_type="tournament_match",
                            priority=7,
                            parameters={
                                "hypothesis_a_id": h_extra_a.id,
                                "hypothesis_b_id": h_extra_b.id,
                                "cluster_aware": proximity_graph is not None,
                            },
                            status="pending"
                        ))

                    h1, h2 = pairs[0]
                    return AgentTask(
                        id=generate_task_id(),
                        agent_type=AgentType.RANKING,
                        task_type="tournament_match",
                        priority=7,
                        parameters={
                            "hypothesis_a_id": h1.id,
                            "hypothesis_b_id": h2.id,
                            "cluster_aware": proximity_graph is not None,
                        },
                        status="pending"
                    )

        elif agent_type == AgentType.EVOLUTION:
            # Select from top-5, skipping recently-evolved parents to
            # prevent monoculture (paper says "top-ranked hypotheses",
            # not "the single top hypothesis" repeatedly).
            top = await self.storage.get_top_hypotheses(n=5, goal_id=goal_id)
            if top:
                recent = set(self._last_evolved_ids[-3:])
                candidate = next((h for h in top if h.id not in recent), top[0])

                reviews = await self.storage.get_reviews_for_hypothesis(candidate.id)
                all_hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)

                strategy = select_evolution_strategy(
                    reviews=reviews,
                    hypothesis_count=len(all_hypotheses)
                )

                self._last_evolved_ids.append(candidate.id)
                logger.info(
                    "evolution_parent_selected",
                    parent_id=candidate.id,
                    parent_title=candidate.title[:80],
                    skipped_recent=len(recent),
                )

                return AgentTask(
                    id=generate_task_id(),
                    agent_type=AgentType.EVOLUTION,
                    task_type="evolve_hypothesis",
                    priority=6,
                    parameters={
                        "hypothesis_id": candidate.id,
                        "strategy": strategy.value,
                    },
                    status="pending"
                )

        elif agent_type == AgentType.PROXIMITY:
            # Build/update proximity graph
            hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)
            if len(hypotheses) >= 2:
                return AgentTask(
                    id=generate_task_id(),
                    agent_type=AgentType.PROXIMITY,
                    task_type="build_proximity_graph",
                    priority=4,
                    parameters={
                        "goal_id": goal_id,
                        "hypothesis_ids": [h.id for h in hypotheses[:10]],
                    },
                    status="pending"
                )

        elif agent_type == AgentType.META_REVIEW:
            # Generate meta-review if enough data
            reviews = await self.storage.get_all_reviews(goal_id)
            matches = await self.storage.get_all_matches(goal_id)
            if len(reviews) >= 3 and len(matches) >= 2:
                return AgentTask(
                    id=generate_task_id(),
                    agent_type=AgentType.META_REVIEW,
                    task_type="generate_meta_review",
                    priority=3,
                    parameters={
                        "goal_id": goal_id,
                    },
                    status="pending"
                )

        elif agent_type == AgentType.OBSERVATION_REVIEW:
            # Schedule observation review for hypotheses that have passed initial
            # review but don't yet have an observation review (Paper Section 3.3.2)
            eligible_statuses = {
                HypothesisStatus.INITIAL_REVIEW,
                HypothesisStatus.FULL_REVIEW,
                HypothesisStatus.IN_TOURNAMENT,
            }
            hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)
            for h in hypotheses:
                if h.status in eligible_statuses:
                    existing = await self.storage.get_observation_review(h.id)
                    if not existing:
                        return AgentTask(
                            id=generate_task_id(),
                            agent_type=AgentType.OBSERVATION_REVIEW,
                            task_type="observation_review",
                            priority=5,
                            parameters={
                                "hypothesis_id": h.id,
                            },
                            status="pending"
                        )

        return None

    async def _execute_task(
        self,
        task: AgentTask,
        research_goal: ResearchGoal
    ) -> Dict[str, Any]:
        """Execute a single task with the appropriate agent.

        Args:
            task: Task to execute.
            research_goal: Current research goal.

        Returns:
            Task result dictionary.
        """
        agent = self._get_agent(task.agent_type)
        if not agent:
            raise ValueError(f"No agent for type: {task.agent_type}")

        params = task.parameters
        result: Dict[str, Any] = {}

        if task.agent_type == AgentType.GENERATION:
            method = GenerationMethod(params.get("method", "literature_exploration"))
            use_literature_expansion = params.get("use_web_search", False)

            # For research expansion: fetch the research overview, meta-review,
            # and existing hypothesis titles so the agent can target gaps.
            research_overview = None
            meta_review = None
            existing_titles = None
            if method == GenerationMethod.RESEARCH_EXPANSION:
                research_overview = await self.storage.get_research_overview(research_goal.id)
                meta_review = await self.storage.get_meta_review(research_goal.id)
                all_hyps = await self.storage.get_hypotheses_by_goal(research_goal.id)
                existing_titles = [h.title for h in all_hyps]

            # GenerationAgent.execute is async
            hypothesis = await agent.execute(
                research_goal=research_goal,
                method=method,
                use_literature_expansion=use_literature_expansion,
                context_instructions=self._format_context_for_prompt(),
                research_overview=research_overview,
                meta_review=meta_review,
                existing_titles=existing_titles,
            )

            # Safety review (skip if threshold is 0 to disable)
            if self.safety_threshold > 0:
                try:
                    safety_assessment = await self.safety_agent.review_hypothesis(hypothesis)
                    if not self.safety_agent.is_safe(safety_assessment, self.safety_threshold):
                        logger.warning(
                            "hypothesis_failed_safety_review",
                            hypothesis_id=hypothesis.id,
                            hypothesis_title=hypothesis.title[:50],
                            safety_score=safety_assessment.get("safety_score"),
                        )
                        hypothesis.status = HypothesisStatus.REQUIRES_SAFETY_REVIEW
                        await self.storage.add_hypothesis(hypothesis)
                        return {
                            "error": "safety_failed",
                            "hypothesis_id": hypothesis.id,
                            "safety_score": safety_assessment.get("safety_score"),
                            "status": "requires_safety_review"
                        }
                except BudgetExceededError:
                    raise
                except Exception as e:
                    logger.warning("safety_review_skipped", error=str(e))

            # Keep status as GENERATED (default) so the reflection filler
            # can pick up this hypothesis via get_hypotheses_needing_review.
            # Status will transition to INITIAL_REVIEW after the actual review runs.
            await self.storage.add_hypothesis(hypothesis)
            result = {"hypothesis_id": hypothesis.id}

            # Create follow-up reflection task (hypothesis passed safety)
            self.task_queue.add_task(AgentTask(
                id=generate_task_id(),
                agent_type=AgentType.REFLECTION,
                task_type="review_hypothesis",
                priority=9,
                parameters={
                    "hypothesis_id": hypothesis.id,
                    "review_type": ReviewType.INITIAL.value,
                },
                status="pending"
            ))

        elif task.agent_type == AgentType.REFLECTION:
            hypothesis_id = params["hypothesis_id"]
            hypothesis = await self.storage.get_hypothesis(hypothesis_id)
            if hypothesis:
                review_type = ReviewType(params.get("review_type", "initial"))
                # ReflectionAgent.execute is async
                review = await agent.execute(
                    hypothesis=hypothesis,
                    review_type=review_type,
                    context_guidance=self._format_context_for_prompt()
                )
                await self.storage.add_review(review)

                # Update hypothesis status based on review type
                if review_type == ReviewType.DEEP_VERIFICATION:
                    if review.passed:
                        hypothesis.status = HypothesisStatus.IN_TOURNAMENT
                elif review_type == ReviewType.FULL:
                    hypothesis.status = HypothesisStatus.FULL_REVIEW
                else:
                    hypothesis.status = HypothesisStatus.INITIAL_REVIEW
                await self.storage.update_hypothesis(hypothesis)

                # Schedule next review stage in the quality pipeline:
                # INITIAL passed -> queue FULL review
                # FULL passed -> queue DEEP_VERIFICATION
                if review.passed:
                    if review_type == ReviewType.INITIAL:
                        self.task_queue.add_task(AgentTask(
                            id=generate_task_id(),
                            agent_type=AgentType.REFLECTION,
                            task_type="review_hypothesis",
                            priority=8,
                            parameters={
                                "hypothesis_id": hypothesis.id,
                                "review_type": ReviewType.FULL.value,
                            },
                            status="pending"
                        ))
                    elif review_type == ReviewType.FULL:
                        self.task_queue.add_task(AgentTask(
                            id=generate_task_id(),
                            agent_type=AgentType.REFLECTION,
                            task_type="deep_verification_review",
                            priority=7,
                            parameters={
                                "hypothesis_id": hypothesis.id,
                                "review_type": ReviewType.DEEP_VERIFICATION.value,
                            },
                            status="pending"
                        ))

                result = {"review_id": review.id, "passed": review.passed}

        elif task.agent_type == AgentType.RANKING:
            h_a_id = params["hypothesis_a_id"]
            h_b_id = params["hypothesis_b_id"]
            h_a = await self.storage.get_hypothesis(h_a_id)
            h_b = await self.storage.get_hypothesis(h_b_id)

            if h_a and h_b:
                # Get reviews for both hypotheses
                reviews_a = await self.storage.get_reviews_for_hypothesis(h_a_id)
                reviews_b = await self.storage.get_reviews_for_hypothesis(h_b_id)

                # Run sync agent in thread pool to avoid blocking event loop
                match = await asyncio.to_thread(
                    agent.execute,
                    hypothesis_a=h_a,
                    hypothesis_b=h_b,
                    multi_turn=True,
                    goal=research_goal.description,
                )
                await self.storage.add_match(match)

                # Update Elo ratings
                h_a.elo_rating += match.elo_change_a
                h_b.elo_rating += match.elo_change_b
                h_a.status = HypothesisStatus.IN_TOURNAMENT
                h_b.status = HypothesisStatus.IN_TOURNAMENT
                await self.storage.update_hypothesis(h_a)
                await self.storage.update_hypothesis(h_b)

                result = {"match_id": match.id, "winner_id": match.winner_id}

        elif task.agent_type == AgentType.EVOLUTION:
            hypothesis_id = params["hypothesis_id"]
            hypothesis = await self.storage.get_hypothesis(hypothesis_id)
            if hypothesis:
                strategy = EvolutionStrategy(params.get("strategy", "feasibility"))
                # Get reviews for evolution context
                reviews = await self.storage.get_reviews_for_hypothesis(hypothesis_id)
                # Run sync agent in thread pool to avoid blocking event loop
                evolved = await asyncio.to_thread(
                    agent.execute,
                    hypothesis=hypothesis,
                    strategy=strategy,
                    reviews=reviews if reviews else None,
                    context_guidance=self._format_context_for_prompt(),
                    research_goal_description=research_goal.description
                )

                # Safety review for evolved hypothesis (skip if threshold is 0)
                if self.safety_threshold > 0:
                    try:
                        safety_assessment = await self.safety_agent.review_hypothesis(evolved)
                        if not self.safety_agent.is_safe(safety_assessment, self.safety_threshold):
                            logger.warning(
                                "evolved_hypothesis_failed_safety_review",
                                evolved_id=evolved.id,
                                parent_id=hypothesis_id,
                                safety_score=safety_assessment.get("safety_score"),
                            )
                            evolved.status = HypothesisStatus.REQUIRES_SAFETY_REVIEW
                            await self.storage.add_hypothesis(evolved)
                            hypothesis.status = HypothesisStatus.EVOLVED
                            await self.storage.update_hypothesis(hypothesis)
                            return {
                                "error": "safety_failed",
                                "evolved_hypothesis_id": evolved.id,
                                "parent_id": hypothesis_id,
                                "status": "requires_safety_review"
                            }
                    except BudgetExceededError:
                        raise
                    except Exception as e:
                        logger.warning("safety_review_skipped_evolved", error=str(e))

                await self.storage.add_hypothesis(evolved)

                # Mark original as evolved
                hypothesis.status = HypothesisStatus.EVOLVED
                await self.storage.update_hypothesis(hypothesis)

                result = {"evolved_hypothesis_id": evolved.id}

        elif task.agent_type == AgentType.PROXIMITY:
            hypotheses = await self.storage.get_hypotheses_by_goal(
                research_goal.id
            )
            if len(hypotheses) >= 2:
                # Run sync agent in thread pool to avoid blocking event loop
                graph = await asyncio.to_thread(
                    agent.execute,
                    hypotheses=hypotheses[:10],
                    research_goal_id=research_goal.id
                )
                await self.storage.save_proximity_graph(graph)
                result = {
                    "num_edges": len(graph.edges),
                    "num_clusters": len(graph.clusters)
                }

        elif task.agent_type == AgentType.META_REVIEW:
            reviews = await self.storage.get_all_reviews(research_goal.id)
            matches = await self.storage.get_all_matches(research_goal.id)

            # Run sync agent in thread pool to avoid blocking event loop
            meta_review = await asyncio.to_thread(
                agent.execute,
                reviews=reviews,
                matches=matches,
                goal=research_goal.description,
                preferences=research_goal.preferences
            )
            # Set proper research_goal_id
            meta_review.research_goal_id = research_goal.id
            await self.storage.save_meta_review(meta_review)
            result = {"meta_review_id": meta_review.id}

        elif task.agent_type == AgentType.OBSERVATION_REVIEW:
            # Phase 6 Week 3: Observation Review Agent
            hypothesis_id = params["hypothesis_id"]
            hypothesis = await self.storage.get_hypothesis(hypothesis_id)

            if hypothesis:
                # Import required modules
                from src.literature.citation_graph import CitationGraph

                # Get citation graph if available
                # For now, create an empty graph - in production this would be passed from generation
                citation_graph = params.get("citation_graph")
                if not citation_graph:
                    # Try to get observation review without citation graph
                    # This will create an empty review with a warning
                    citation_graph = CitationGraph()

                # Execute observation review
                observation_review = await agent.execute_with_citation_graph(
                    hypothesis=hypothesis,
                    citation_graph=citation_graph,
                    research_goal=research_goal,
                    max_observations=params.get("max_observations", 20)
                )

                # Store observation review
                await self.storage.add_observation_review(observation_review)

                result = {
                    "observation_review_id": observation_review.id,
                    "overall_score": observation_review.overall_score,
                    "explained_count": observation_review.observations_explained_count
                }

                logger.info(
                    "Observation review completed",
                    hypothesis_id=hypothesis_id,
                    overall_score=observation_review.overall_score
                )

        return result

    async def _check_terminal_conditions(
        self,
        stats: SystemStatistics,
        min_hypotheses: int,
        quality_threshold: float,
        convergence_threshold: float,
        started_at: datetime,
        max_execution_time_seconds: int
    ) -> tuple[bool, Optional[str]]:
        """Check if terminal conditions are met.

        Args:
            stats: Current system statistics.
            min_hypotheses: Minimum hypotheses required.
            quality_threshold: Quality threshold for stopping.
            convergence_threshold: Convergence threshold for stopping.
            started_at: Workflow start timestamp.
            max_execution_time_seconds: Maximum execution time.

        Returns:
            Tuple of (should_stop, reason).
        """
        # Check time limit (AGENT-C1 fix: prevent infinite loops)
        elapsed_seconds = (datetime.now() - started_at).total_seconds()
        if elapsed_seconds > max_execution_time_seconds:
            elapsed_hours = round(elapsed_seconds / 3600, 2)
            max_hours = round(max_execution_time_seconds / 3600, 2)
            return True, f"Maximum execution time exceeded ({elapsed_hours}h / {max_hours}h)"

        # Check budget
        try:
            self.cost_tracker.check_budget()
        except BudgetExceededError:
            return True, "Budget exhausted"

        # Don't stop if not enough hypotheses
        if stats.total_hypotheses < min_hypotheses:
            return False, None

        # Require at least 40% of max_iterations before allowing early stop.
        # This ensures sufficient exploration before convergence checks
        # can terminate the workflow.
        min_iterations_before_stop = max(5, int(self.max_iterations * 0.7))

        # Check tournament convergence
        if stats.tournament_convergence_score >= convergence_threshold:
            if self.iteration >= min_iterations_before_stop:
                return True, f"Tournament converged ({stats.tournament_convergence_score:.2f})"

        # Check quality threshold
        if await self.statistics.calculate_quality_threshold_met(
            stats.research_goal_id, quality_threshold
        ):
            if self.iteration >= min_iterations_before_stop:
                return True, f"Quality threshold met ({quality_threshold})"

        return False, None

    async def _save_checkpoint(
        self,
        goal_id: str,
        stats: SystemStatistics
    ) -> None:
        """Save a workflow checkpoint with retry logic.

        Checkpoint saves are critical for workflow resumption. If a checkpoint
        save fails, the iteration cannot proceed safely, as system crashes would
        result in lost work without recovery points.

        Args:
            goal_id: Research goal ID.
            stats: Current statistics.

        Raises:
            CheckpointError: If checkpoint save fails after retry.
            BudgetExceededError: Always propagated (terminal condition).
        """
        # Get current state
        hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)
        tournament_state = await self.storage.get_tournament_state(goal_id)
        proximity_graph = await self.storage.get_proximity_graph(goal_id)
        meta_review = await self.storage.get_meta_review(goal_id)
        overview = await self.storage.get_research_overview(goal_id)

        checkpoint = ContextMemory(
            research_goal_id=goal_id,
            tournament_state=tournament_state,
            proximity_graph=proximity_graph,
            latest_meta_review=meta_review,
            latest_research_overview=overview,
            system_statistics=stats,
            hypothesis_ids=[h.id for h in hypotheses],
            iteration_count=self.iteration,
            accumulated_insights=self._context_insights,
            explored_directions=self._explored_directions,
        )

        # First attempt to save checkpoint
        try:
            await self.storage.save_checkpoint(checkpoint)
            logger.info(
                "checkpoint_saved_successfully",
                goal_id=goal_id,
                iteration=self.iteration,
                num_hypotheses=len(hypotheses)
            )
            return
        except BudgetExceededError:
            # Budget errors are terminal conditions - always propagate
            raise
        except Exception as e:
            logger.error(
                "checkpoint_save_failed_attempting_retry",
                goal_id=goal_id,
                iteration=self.iteration,
                error=str(e),
                error_type=type(e).__name__
            )

            # Retry checkpoint save once
            try:
                logger.info(
                    "retrying_checkpoint_save",
                    goal_id=goal_id,
                    iteration=self.iteration
                )
                await self.storage.save_checkpoint(checkpoint)
                logger.info(
                    "checkpoint_save_succeeded_on_retry",
                    goal_id=goal_id,
                    iteration=self.iteration
                )
                return
            except Exception as retry_error:
                logger.error(
                    "checkpoint_retry_failed_workflow_cannot_continue_safely",
                    goal_id=goal_id,
                    iteration=self.iteration,
                    original_error=str(e),
                    retry_error=str(retry_error),
                    error_type=type(retry_error).__name__
                )
                raise CheckpointError(
                    f"Failed to save checkpoint after retry for goal {goal_id} "
                    f"at iteration {self.iteration}. Original error: {e}. "
                    f"Retry error: {retry_error}"
                ) from retry_error

    async def _generate_final_overview(
        self,
        research_goal: ResearchGoal
    ) -> Optional[Any]:
        """Generate final research overview using Meta-review agent.

        Args:
            research_goal: Research goal.

        Returns:
            ResearchOverview or None if generation fails.
        """
        try:
            agent = self._get_agent(AgentType.META_REVIEW)
            if not agent:
                return None

            # Get top hypotheses (use diversity sampling if enabled)
            from src.config import settings
            if settings.diversity_sampling_for_overview:
                top_hypotheses = await self.storage.get_diverse_hypotheses(
                    goal_id=research_goal.id,
                    n=5,
                    min_elo_rating=settings.diversity_sampling_min_elo,
                    cluster_balance=True
                )
                logger.info(
                    "supervisor_final_overview_diverse_sampling",
                    goal_id=research_goal.id,
                    num_hypotheses=len(top_hypotheses)
                )
            else:
                top_hypotheses = await self.storage.get_top_hypotheses(
                    n=5, goal_id=research_goal.id
                )

            # Get or generate meta-review
            meta_review = await self.storage.get_meta_review(research_goal.id)
            if not meta_review:
                # Generate one (run sync agent in thread pool)
                reviews = await self.storage.get_all_reviews(research_goal.id)
                matches = await self.storage.get_all_matches(research_goal.id)
                meta_review = await asyncio.to_thread(
                    agent.execute,
                    reviews=reviews,
                    matches=matches,
                    goal=research_goal.description,
                    preferences=research_goal.preferences
                )
                meta_review.research_goal_id = research_goal.id
                await self.storage.save_meta_review(meta_review)

            # Generate research overview with retry (asyncio.to_thread
            # can hit "generator didn't stop after throw()" on some LLM calls)
            overview = None
            overview_kwargs = dict(
                goal=research_goal.description,
                top_hypotheses=top_hypotheses,
                meta_review=meta_review,
                preferences=research_goal.preferences,
                research_goal_id=research_goal.id
            )
            for attempt in range(2):
                try:
                    overview = await asyncio.to_thread(
                        agent.generate_research_overview, **overview_kwargs
                    )
                    break
                except Exception as e:
                    logger.warning("overview_generation_retry", attempt=attempt + 1, error=str(e)[:200])
                    if attempt == 1:
                        try:
                            overview = agent.generate_research_overview(**overview_kwargs)
                        except Exception as e2:
                            logger.error("overview_generation_failed_final", error=str(e2)[:200])

            if overview:
                await self.storage.save_research_overview(overview)
                logger.info(
                    "research_overview_generated",
                    overview_id=overview.id,
                    num_directions=len(overview.research_directions)
                )

            return overview

        except Exception as e:
            logger.error(
                "overview_generation_failed",
                error=str(e)
            )
            return None

    async def resume_from_checkpoint(
        self,
        research_goal: ResearchGoal,
        max_iterations: int = 20
    ) -> str:
        """Resume execution from the latest checkpoint.

        Args:
            research_goal: Research goal to resume.
            max_iterations: Maximum total iterations.

        Returns:
            Status message.
        """
        checkpoint = await self.storage.get_latest_checkpoint(research_goal.id)
        if not checkpoint:
            return await self.execute(research_goal, max_iterations)

        # Restore state
        self.iteration = checkpoint.iteration_count
        self._context_insights = checkpoint.accumulated_insights or []
        self._explored_directions = checkpoint.explored_directions or []
        logger.info(
            "resuming_from_checkpoint",
            goal_id=research_goal.id,
            iteration=self.iteration,
            restored_insights=len(self._context_insights),
            restored_directions=len(self._explored_directions),
        )

        # Continue execution
        return await self.execute(
            research_goal,
            max_iterations=max_iterations
        )
