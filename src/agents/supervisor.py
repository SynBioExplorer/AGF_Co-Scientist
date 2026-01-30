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
from src.llm.factory import get_llm_client
from src.supervisor.task_queue import TaskQueue
from src.supervisor.statistics import SupervisorStatistics
from src.storage.async_adapter import AsyncStorageAdapter
from src.config import settings
from src.utils.ids import generate_id, generate_task_id
from src.utils.json_parser import parse_llm_json
from src.utils.strategy_selector import select_evolution_strategy
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
            AgentType.GENERATION: 0.35,          # 35% - create hypotheses
            AgentType.REFLECTION: 0.18,          # 18% - review hypotheses
            AgentType.RANKING: 0.18,             # 18% - tournament matches
            AgentType.OBSERVATION_REVIEW: 0.12,  # 12% - validate against literature (Phase 6 Week 3)
            AgentType.EVOLUTION: 0.09,           # 9% - refine top hypotheses
            AgentType.PROXIMITY: 0.04,           # 4% - cluster similar hypotheses
            AgentType.META_REVIEW: 0.04,         # 4% - synthesize feedback
        }

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
        quality_threshold: float = 0.7,
        convergence_threshold: float = 0.9,
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

            # Check terminal conditions
            should_stop, reason = await self._check_terminal_conditions(
                stats=stats,
                min_hypotheses=min_hypotheses,
                quality_threshold=quality_threshold,
                convergence_threshold=convergence_threshold
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

    async def _execute_iteration(self, research_goal: ResearchGoal) -> None:
        """Execute one iteration of task assignments.

        Processes tasks from the queue based on agent weights, executing
        each task with the appropriate agent.

        Args:
            research_goal: Current research goal.
        """
        # Refresh proximity graph periodically for proximity-aware pairing
        if (settings.proximity_aware_pairing and
            self.iteration % settings.proximity_graph_refresh_frequency == 0):

            hypotheses = await self.storage.get_hypotheses_by_goal(research_goal.id)
            if len(hypotheses) >= 2:
                # Create high-priority proximity graph refresh task
                refresh_task = AgentTask(
                    id=generate_task_id(),
                    agent_type=AgentType.PROXIMITY,
                    task_type="build_proximity_graph",
                    priority=8,  # High priority before tournament round
                    parameters={
                        "goal_id": research_goal.id,
                        "hypothesis_ids": [h.id for h in hypotheses],
                    },
                    status="pending"
                )
                self.task_queue.add_task(refresh_task)
                logger.info(
                    "proximity_graph_refresh_scheduled",
                    iteration=self.iteration,
                    hypothesis_count=len(hypotheses)
                )

        # Calculate tasks per agent based on weights
        tasks_per_iteration = 5  # Base number of tasks per iteration
        executed_count = 0

        for agent_type, weight in self.agent_weights.items():
            if weight <= 0:
                continue

            num_tasks = max(1, int(weight * tasks_per_iteration))

            for _ in range(num_tasks):
                task = self.task_queue.get_next_task(agent_type)
                if not task:
                    # No pending tasks for this agent, create new ones
                    task = await self._create_task_for_agent(
                        agent_type, research_goal
                    )
                    if not task:
                        continue

                # Execute the task
                try:
                    self.task_queue.update_task_status(task.id, "running")
                    result = await self._execute_task(task, research_goal)
                    self.task_queue.update_task_status(
                        task.id, "complete", result=result
                    )
                    executed_count += 1
                except Exception as e:
                    logger.error(
                        "task_execution_failed",
                        task_id=task.id,
                        agent_type=agent_type.value,
                        error=str(e)
                    )
                    self.task_queue.update_task_status(task.id, "failed")

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
            # Create generation task
            return AgentTask(
                id=generate_task_id(),
                agent_type=AgentType.GENERATION,
                task_type="generate_hypothesis",
                priority=8,
                parameters={
                    "goal_id": goal_id,
                    "method": GenerationMethod.LITERATURE_EXPLORATION.value,
                },
                status="pending"
            )

        elif agent_type == AgentType.REFLECTION:
            # Find hypotheses needing review
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

        elif agent_type == AgentType.RANKING:
            # Find hypotheses for tournament
            hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)
            reviewed = [
                h for h in hypotheses
                if h.status != HypothesisStatus.GENERATED
            ]
            if len(reviewed) >= 2:
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
                    top_n=10,
                    proximity_graph=proximity_graph,
                    use_proximity=settings.proximity_aware_pairing,
                    proximity_weight=settings.proximity_pairing_weight,
                    diversity_weight=settings.diversity_pairing_weight
                )

                if pairs:
                    h1, h2 = pairs[0]  # Take first pair
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
            # Find top hypothesis for evolution
            top = await self.storage.get_top_hypotheses(n=1, goal_id=goal_id)
            if top:
                # Get reviews for this hypothesis to inform strategy selection
                reviews = await self.storage.get_reviews_for_hypothesis(top[0].id)
                all_hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)

                # Dynamic strategy selection based on context
                strategy = select_evolution_strategy(
                    reviews=reviews,
                    hypothesis_count=len(all_hypotheses)
                )

                return AgentTask(
                    id=generate_task_id(),
                    agent_type=AgentType.EVOLUTION,
                    task_type="evolve_hypothesis",
                    priority=6,
                    parameters={
                        "hypothesis_id": top[0].id,
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
            use_web_search = params.get("use_web_search", False)

            # Run sync agent in thread pool to avoid blocking event loop
            hypothesis = await asyncio.to_thread(
                agent.execute,
                research_goal=research_goal,
                method=method,
                use_web_search=use_web_search
            )
            await self.storage.add_hypothesis(hypothesis)
            result = {"hypothesis_id": hypothesis.id}

            # Create follow-up reflection task
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
                # Run sync agent in thread pool to avoid blocking event loop
                review = await asyncio.to_thread(
                    agent.execute,
                    hypothesis=hypothesis,
                    review_type=review_type
                )
                await self.storage.add_review(review)

                # Update hypothesis status
                hypothesis.status = HypothesisStatus.INITIAL_REVIEW
                await self.storage.update_hypothesis(hypothesis)

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
                    reviews=reviews if reviews else None
                )
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
                    hypotheses=hypotheses[:10]
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
        convergence_threshold: float
    ) -> tuple[bool, Optional[str]]:
        """Check if terminal conditions are met.

        Args:
            stats: Current system statistics.
            min_hypotheses: Minimum hypotheses required.
            quality_threshold: Quality threshold for stopping.
            convergence_threshold: Convergence threshold for stopping.

        Returns:
            Tuple of (should_stop, reason).
        """
        # Check budget
        try:
            self.cost_tracker.check_budget()
        except BudgetExceededError:
            return True, "Budget exhausted"

        # Don't stop if not enough hypotheses
        if stats.total_hypotheses < min_hypotheses:
            return False, None

        # Check tournament convergence
        if stats.tournament_convergence_score >= convergence_threshold:
            if self.iteration >= 3:  # Require minimum iterations
                return True, f"Tournament converged ({stats.tournament_convergence_score:.2f})"

        # Check quality threshold
        if await self.statistics.calculate_quality_threshold_met(
            stats.research_goal_id, quality_threshold
        ):
            if self.iteration >= 3:
                return True, f"Quality threshold met ({quality_threshold})"

        return False, None

    async def _save_checkpoint(
        self,
        goal_id: str,
        stats: SystemStatistics
    ) -> None:
        """Save a workflow checkpoint.

        Args:
            goal_id: Research goal ID.
            stats: Current statistics.
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
        )

        await self.storage.save_checkpoint(checkpoint)
        logger.info(
            "checkpoint_saved",
            goal_id=goal_id,
            iteration=self.iteration
        )

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

            # Generate research overview (run sync agent in thread pool)
            overview = await asyncio.to_thread(
                agent.generate_research_overview,
                goal=research_goal.description,
                top_hypotheses=top_hypotheses,
                meta_review=meta_review,
                preferences=research_goal.preferences,
                research_goal_id=research_goal.id
            )

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
        logger.info(
            "resuming_from_checkpoint",
            goal_id=research_goal.id,
            iteration=self.iteration
        )

        # Continue execution
        return await self.execute(
            research_goal,
            max_iterations=max_iterations
        )
