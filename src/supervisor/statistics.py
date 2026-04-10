"""Agent effectiveness and tournament convergence tracking.

This module provides the SupervisorStatistics class that computes system
metrics used by the Supervisor agent for resource allocation decisions
and terminal condition detection.

Key metrics:
- Tournament convergence: How stable are the Elo rankings?
- Agent effectiveness: How well is each agent performing?
- Generation success rate: % of hypotheses passing review
- Evolution improvement rate: % of evolved hypotheses with higher Elo

These metrics are computed periodically and used to:
1. Adjust agent weights (resource allocation)
2. Detect terminal conditions (convergence reached)
3. Identify which generation methods are most effective
"""

from typing import Dict, List, Optional
from datetime import datetime
import math
import sys
from pathlib import Path

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import (
    SystemStatistics,
    AgentType,
    Hypothesis,
    HypothesisStatus,
    GenerationMethod,
)

from src.storage.async_adapter import AsyncStorageAdapter

import structlog

logger = structlog.get_logger()


class SupervisorStatistics:
    """Compute system statistics for resource allocation and convergence.

    This class analyzes the current state of hypotheses, reviews, and
    tournaments to compute metrics that guide the Supervisor agent's
    decision-making.

    Attributes:
        storage: Async storage adapter for data access.
    """

    def __init__(self, storage: AsyncStorageAdapter):
        """Initialize statistics tracker.

        Args:
            storage: Async storage adapter for data access.
        """
        self.storage = storage

    async def compute_statistics(self, goal_id: str) -> SystemStatistics:
        """Compute current system statistics for a research goal.

        This is the main entry point for statistics computation. It
        aggregates all metrics into a SystemStatistics object.

        Args:
            goal_id: Research goal ID to compute stats for.

        Returns:
            SystemStatistics with all computed metrics.
        """
        logger.info("computing_statistics", goal_id=goal_id)

        # Get all hypotheses for this goal
        hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)

        # Count by status
        status_counts = self._count_by_status(hypotheses)

        # Get match count
        match_count = await self.storage.get_match_count(goal_id)

        # Calculate tournament convergence
        top_hypotheses = await self.storage.get_top_hypotheses(n=10, goal_id=goal_id)
        convergence_score = self._calculate_convergence(top_hypotheses)

        # Calculate agent effectiveness
        generation_success = await self._calculate_generation_success_rate(
            goal_id, hypotheses
        )
        evolution_improvement = await self._calculate_evolution_improvement_rate(
            hypotheses
        )

        # Calculate method effectiveness
        method_effectiveness = self._calculate_method_effectiveness(hypotheses)

        # Get current agent weights (will be set by supervisor)
        # Default weights if not available
        agent_weights = {
            AgentType.GENERATION.value: 0.4,
            AgentType.REFLECTION.value: 0.2,
            AgentType.RANKING.value: 0.2,
            AgentType.EVOLUTION.value: 0.1,
            AgentType.PROXIMITY.value: 0.05,
            AgentType.META_REVIEW.value: 0.05,
        }

        stats = SystemStatistics(
            research_goal_id=goal_id,
            total_hypotheses=len(hypotheses),
            hypotheses_pending_review=status_counts.get("generated", 0),
            hypotheses_in_tournament=status_counts.get("in_tournament", 0),
            hypotheses_archived=status_counts.get("archived", 0),
            tournament_matches_completed=match_count,
            tournament_convergence_score=convergence_score,
            generation_success_rate=generation_success,
            evolution_improvement_rate=evolution_improvement,
            method_effectiveness=method_effectiveness,
            agent_weights=agent_weights,
            computed_at=datetime.now(),
        )

        logger.info(
            "statistics_computed",
            goal_id=goal_id,
            total_hypotheses=len(hypotheses),
            convergence=convergence_score,
            generation_success=generation_success,
            evolution_improvement=evolution_improvement,
        )

        return stats

    def _count_by_status(self, hypotheses: List[Hypothesis]) -> Dict[str, int]:
        """Count hypotheses by status.

        Args:
            hypotheses: List of hypotheses to count.

        Returns:
            Dictionary mapping status name to count.
        """
        counts: Dict[str, int] = {}
        for h in hypotheses:
            status = h.status.value
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _calculate_convergence(self, hypotheses: List[Hypothesis]) -> float:
        """Calculate tournament convergence score.

        Convergence measures how stable the Elo rankings are. Higher
        convergence means the top hypotheses have stabilized and further
        tournaments are unlikely to change the rankings significantly.

        The score combines two factors:
        1. Elo stability: low std deviation among rated hypotheses
        2. Match coverage: what fraction of hypotheses have been tested

        Without the coverage factor, hypotheses that are all at the
        default 1200 Elo (untested) would appear "converged" when they
        have actually never been matched.

        Args:
            hypotheses: Top hypotheses to analyze.

        Returns:
            Convergence score between 0.0 and 1.0.
        """
        if len(hypotheses) < 2:
            return 0.0

        elos = [h.elo_rating for h in hypotheses]
        mean_elo = sum(elos) / len(elos)
        variance = sum((e - mean_elo) ** 2 for e in elos) / len(elos)
        std_dev = math.sqrt(variance)

        # Elo stability: 1 - (std_dev / 100), clamped to [0, 1]
        elo_stability = max(0.0, min(1.0, 1.0 - std_dev / 100.0))

        # Match coverage: fraction of hypotheses that have moved off
        # the default 1200 rating (i.e. have actually been matched).
        default_elo = 1200.0
        matched_count = sum(1 for e in elos if abs(e - default_elo) > 1.0)
        coverage = matched_count / len(elos)

        # True convergence requires both stable ratings AND sufficient
        # match coverage. If most hypotheses are untested, convergence
        # stays low regardless of how uniform the ratings look.
        convergence = elo_stability * coverage

        return convergence

    async def _calculate_generation_success_rate(
        self,
        goal_id: str,
        hypotheses: List[Hypothesis]
    ) -> float:
        """Calculate generation agent success rate.

        Success is measured as the percentage of generated hypotheses
        that pass initial review (i.e., status progressed beyond GENERATED).

        Args:
            goal_id: Research goal ID.
            hypotheses: All hypotheses for the goal.

        Returns:
            Success rate between 0.0 and 1.0.
        """
        if not hypotheses:
            return 0.0

        # Count hypotheses that progressed past initial generation
        generated = len([
            h for h in hypotheses
            if h.status == HypothesisStatus.GENERATED
        ])
        progressed = len([
            h for h in hypotheses
            if h.status in (
                HypothesisStatus.INITIAL_REVIEW,
                HypothesisStatus.FULL_REVIEW,
                HypothesisStatus.IN_TOURNAMENT,
                HypothesisStatus.EVOLVED,
            )
        ])

        total = generated + progressed
        if total == 0:
            return 0.5  # Default when no data

        return progressed / total

    async def _calculate_evolution_improvement_rate(
        self,
        hypotheses: List[Hypothesis]
    ) -> float:
        """Calculate evolution agent improvement rate.

        Improvement is measured as the percentage of evolved hypotheses
        that have a higher Elo rating than their parent.

        Args:
            hypotheses: All hypotheses.

        Returns:
            Improvement rate between 0.0 and 1.0.
        """
        # Find evolved hypotheses (those with parent IDs)
        evolved = [
            h for h in hypotheses
            if h.parent_hypothesis_ids and len(h.parent_hypothesis_ids) > 0
        ]

        if not evolved:
            return 0.5  # Default when no evolved hypotheses

        # Build ID -> hypothesis map
        hyp_map = {h.id: h for h in hypotheses}

        improved_count = 0
        for h in evolved:
            # Get parent Elo (use first parent if multiple)
            parent_id = h.parent_hypothesis_ids[0]
            parent = hyp_map.get(parent_id)

            if parent and h.elo_rating > parent.elo_rating:
                improved_count += 1

        return improved_count / len(evolved)

    def _calculate_method_effectiveness(
        self,
        hypotheses: List[Hypothesis]
    ) -> Dict[str, float]:
        """Calculate effectiveness of each generation method.

        Effectiveness is measured by the average Elo rating of hypotheses
        generated by each method, normalized to [0, 1].

        Args:
            hypotheses: All hypotheses.

        Returns:
            Dictionary mapping method name to effectiveness score.
        """
        method_elos: Dict[str, List[float]] = {}

        for h in hypotheses:
            method = h.generation_method.value
            if method not in method_elos:
                method_elos[method] = []
            method_elos[method].append(h.elo_rating)

        # Calculate average Elo per method
        method_avg: Dict[str, float] = {}
        for method, elos in method_elos.items():
            method_avg[method] = sum(elos) / len(elos)

        # Normalize to [0, 1] based on range of Elo ratings
        # Initial Elo is 1200, typical range is 1000-1400
        effectiveness: Dict[str, float] = {}
        for method, avg_elo in method_avg.items():
            # Map 1000-1400 range to 0.0-1.0
            normalized = (avg_elo - 1000) / 400.0
            effectiveness[method] = max(0.0, min(1.0, normalized))

        return effectiveness

    async def calculate_quality_threshold_met(
        self,
        goal_id: str,
        threshold: float = 0.7
    ) -> bool:
        """Check if quality threshold has been met.

        Quality is determined by the average review score of the top
        hypotheses.

        Args:
            goal_id: Research goal ID.
            threshold: Quality threshold (0.0-1.0).

        Returns:
            True if quality threshold is met.
        """
        top_hypotheses = await self.storage.get_top_hypotheses(n=5, goal_id=goal_id)

        if not top_hypotheses:
            return False

        # Get reviews for top hypotheses and calculate average quality
        total_quality = 0.0
        review_count = 0

        for h in top_hypotheses:
            reviews = await self.storage.get_reviews_for_hypothesis(h.id)
            for r in reviews:
                if r.quality_score is not None:
                    total_quality += r.quality_score
                    review_count += 1

        if review_count == 0:
            return False

        avg_quality = total_quality / review_count
        return avg_quality >= threshold

    async def get_agent_workload(self, goal_id: str) -> Dict[str, Dict[str, int]]:
        """Get current workload statistics per agent type.

        Args:
            goal_id: Research goal ID.

        Returns:
            Dictionary mapping agent type to workload metrics.
        """
        hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)

        workload: Dict[str, Dict[str, int]] = {
            AgentType.GENERATION.value: {"pending": 0, "completed": len(hypotheses)},
            AgentType.REFLECTION.value: {"pending": 0, "completed": 0},
            AgentType.RANKING.value: {"pending": 0, "completed": 0},
            AgentType.EVOLUTION.value: {"pending": 0, "completed": 0},
            AgentType.PROXIMITY.value: {"pending": 0, "completed": 0},
            AgentType.META_REVIEW.value: {"pending": 0, "completed": 0},
        }

        # Count hypotheses needing review
        needing_review = len([
            h for h in hypotheses
            if h.status == HypothesisStatus.GENERATED
        ])
        workload[AgentType.REFLECTION.value]["pending"] = needing_review

        # Count reviews completed
        reviews = await self.storage.get_all_reviews(goal_id)
        workload[AgentType.REFLECTION.value]["completed"] = len(reviews)

        # Count matches
        match_count = await self.storage.get_match_count(goal_id)
        workload[AgentType.RANKING.value]["completed"] = match_count

        # Count evolved hypotheses
        evolved = len([h for h in hypotheses if h.parent_hypothesis_ids])
        workload[AgentType.EVOLUTION.value]["completed"] = evolved

        return workload

    async def recommend_agent_weights(
        self,
        goal_id: str,
        stats: SystemStatistics
    ) -> Dict[AgentType, float]:
        """Recommend agent weights based on current statistics.

        This implements the dynamic weight adjustment logic described
        in the Google paper. Weights are adjusted based on:
        - Generation success rate
        - Evolution improvement rate
        - Tournament convergence
        - Pending work backlog

        Args:
            goal_id: Research goal ID.
            stats: Current system statistics.

        Returns:
            Recommended weights per agent type (sum to ~1.0).
        """
        # Base weights - MUST match SupervisorAgent._initialize_weights
        base: Dict[AgentType, float] = {
            AgentType.GENERATION: 0.25,
            AgentType.REFLECTION: 0.25,
            AgentType.RANKING: 0.20,
            AgentType.EVOLUTION: 0.13,
            AgentType.OBSERVATION_REVIEW: 0.08,
            AgentType.PROXIMITY: 0.05,
            AgentType.META_REVIEW: 0.04,
        }

        weights: Dict[AgentType, float] = dict(base)

        # Adjust generation weight based on success rate
        # Lower success rate -> reduce generation (focus on quality)
        if stats.generation_success_rate < 0.5:
            weights[AgentType.GENERATION] = base[AgentType.GENERATION] * 0.5

        # Adjust reflection weight based on pending reviews
        # More pending reviews -> increase reflection weight
        if stats.hypotheses_pending_review > 5:
            weights[AgentType.REFLECTION] = base[AgentType.REFLECTION] * 1.5

        # Adjust ranking weight based on tournament progress
        # High convergence -> reduce ranking (tournament is stable)
        if stats.tournament_convergence_score > 0.8:
            weights[AgentType.RANKING] = base[AgentType.RANKING] * 0.5

        # Adjust evolution weight based on improvement rate
        # Low improvement rate -> reduce evolution (not working well)
        if stats.evolution_improvement_rate < 0.3:
            weights[AgentType.EVOLUTION] = base[AgentType.EVOLUTION] * 0.5
        elif stats.evolution_improvement_rate > 0.6:
            weights[AgentType.EVOLUTION] = base[AgentType.EVOLUTION] * 1.5

        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights
