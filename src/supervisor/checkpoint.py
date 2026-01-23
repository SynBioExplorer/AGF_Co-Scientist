"""Checkpoint and resume functionality for workflow state

This module provides checkpoint management for the AI Co-Scientist system,
enabling workflow state persistence and recovery. Checkpoints capture
the full system state at regular intervals, allowing workflows to be
resumed after interruption.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import (
    ContextMemory,
    TournamentState,
    ProximityGraph,
    SystemStatistics,
)

from src.storage.base import BaseStorage
from src.utils.ids import generate_id
import structlog

logger = structlog.get_logger()


class CheckpointManager:
    """Save and restore workflow state for resumption

    The CheckpointManager creates periodic snapshots of the workflow state,
    including tournament standings, proximity graphs, reviews, and system
    statistics. These checkpoints enable:

    1. Resume after interruption (crash, timeout, manual stop)
    2. Experiment with different continuation strategies
    3. Track progress over time
    4. Rollback to earlier states if needed

    Usage:
        storage = InMemoryStorage()
        checkpoint_mgr = CheckpointManager(storage)

        # Save checkpoint periodically
        if checkpoint_mgr.should_checkpoint(iteration):
            await checkpoint_mgr.save_checkpoint(
                goal_id=research_goal.id,
                iteration=iteration,
                notes="Completed generation round"
            )

        # Resume from checkpoint
        resume_iteration = await checkpoint_mgr.resume_workflow(goal_id)
        if resume_iteration is not None:
            start_from = resume_iteration + 1
    """

    def __init__(
        self,
        storage: BaseStorage,
        checkpoint_interval: int = 5,
        max_checkpoints: int = 10
    ):
        """Initialize checkpoint manager

        Args:
            storage: Storage backend implementing BaseStorage
            checkpoint_interval: Save checkpoint every N iterations
            max_checkpoints: Maximum checkpoints to retain per goal
        """
        self.storage = storage
        self.checkpoint_interval = checkpoint_interval
        self.max_checkpoints = max_checkpoints
        self.logger = logger.bind(component="CheckpointManager")

    async def save_checkpoint(
        self,
        goal_id: str,
        iteration: int,
        notes: str = "",
        task_queue_state: Optional[Dict[str, Any]] = None
    ) -> ContextMemory:
        """Save checkpoint to storage

        Captures the current state of:
        - Tournament standings (Elo ratings, match history)
        - Proximity graph (hypothesis clustering)
        - All reviews
        - System statistics
        - Supervisor notes

        Args:
            goal_id: Research goal ID
            iteration: Current iteration number
            notes: Optional supervisor notes
            task_queue_state: Optional serialized task queue state

        Returns:
            ContextMemory object saved to storage
        """
        self.logger.info(
            "Saving checkpoint",
            goal_id=goal_id,
            iteration=iteration
        )

        # Gather current state from storage (async calls)
        all_hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)
        all_matches = await self.storage.get_all_matches(goal_id=goal_id)
        all_reviews = await self.storage.get_all_reviews()
        proximity_graph = await self.storage.get_proximity_graph(goal_id)

        # Build tournament state
        tournament_state = TournamentState(
            research_goal_id=goal_id,
            hypotheses=[h.id for h in all_hypotheses],
            elo_ratings={h.id: h.elo_rating for h in all_hypotheses},
            match_history=[m.id for m in all_matches],
            total_matches=len(all_matches),
            win_patterns=self._extract_win_patterns(all_matches, all_hypotheses),
            loss_patterns=self._extract_loss_patterns(all_matches, all_hypotheses),
        )

        # Build system statistics
        stats = SystemStatistics(
            research_goal_id=goal_id,
            total_hypotheses=len(all_hypotheses),
            hypotheses_in_tournament=sum(
                1 for h in all_hypotheses
                if h.status.value == "in_tournament"
            ),
            tournament_matches_completed=len(all_matches),
            tournament_convergence_score=self._calculate_convergence(all_hypotheses),
        )

        # Filter reviews for this goal's hypotheses
        goal_hypothesis_ids = {h.id for h in all_hypotheses}
        goal_reviews = [
            r for r in all_reviews
            if r.hypothesis_id in goal_hypothesis_ids
        ]

        # Create ContextMemory checkpoint
        context = ContextMemory(
            research_goal_id=goal_id,
            tournament_state=tournament_state,
            proximity_graph=proximity_graph,
            system_statistics=stats,
            hypothesis_ids=[h.id for h in all_hypotheses],
            review_ids=[r.id for r in goal_reviews],
            iteration_count=iteration,
        )

        # Add checkpoint ID if ContextMemory supports it (may need schema update)
        # For now, we track by goal_id and iteration

        # Save to storage (async)
        await self.storage.save_checkpoint(context)

        # Prune old checkpoints if needed (async)
        await self._prune_old_checkpoints(goal_id)

        self.logger.info(
            "Checkpoint saved successfully",
            goal_id=goal_id,
            iteration=iteration,
            num_hypotheses=len(all_hypotheses),
            num_matches=len(all_matches)
        )

        return context

    async def load_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Load most recent checkpoint for research goal

        Args:
            goal_id: Research goal ID

        Returns:
            Most recent ContextMemory, or None if no checkpoint exists
        """
        self.logger.info("Loading checkpoint", goal_id=goal_id)

        checkpoint = await self.storage.get_latest_checkpoint(goal_id)

        if checkpoint:
            self.logger.info(
                "Checkpoint loaded",
                goal_id=goal_id,
                iteration=checkpoint.iteration_count
            )
        else:
            self.logger.info(
                "No checkpoint found",
                goal_id=goal_id
            )

        return checkpoint

    async def resume_workflow(self, goal_id: str) -> Optional[int]:
        """Resume workflow from last checkpoint

        Loads the most recent checkpoint and returns the iteration number
        to resume from. The workflow should continue from iteration + 1.

        Args:
            goal_id: Research goal ID

        Returns:
            Iteration number of last checkpoint, or None if no checkpoint
        """
        checkpoint = await self.load_checkpoint(goal_id)

        if not checkpoint:
            return None

        self.logger.info(
            "Resuming workflow from checkpoint",
            goal_id=goal_id,
            iteration=checkpoint.iteration_count,
            num_hypotheses=len(checkpoint.hypothesis_ids)
        )

        return checkpoint.iteration_count

    def should_checkpoint(self, iteration: int) -> bool:
        """Determine if checkpoint should be saved

        Args:
            iteration: Current iteration number

        Returns:
            True if should save checkpoint at this iteration
        """
        # Always checkpoint on first iteration
        if iteration == 0:
            return True

        # Checkpoint at regular intervals
        return iteration % self.checkpoint_interval == 0

    async def get_checkpoint_history(self, goal_id: str) -> List[Dict[str, Any]]:
        """Get summary of all checkpoints for a goal

        Args:
            goal_id: Research goal ID

        Returns:
            List of checkpoint summaries (iteration, timestamp, stats)
        """
        checkpoints = await self.storage.get_all_checkpoints(goal_id)

        return [
            {
                "iteration": cp.iteration_count,
                "created_at": cp.created_at.isoformat() if hasattr(cp, 'created_at') else None,
                "num_hypotheses": len(cp.hypothesis_ids),
                "num_reviews": len(cp.review_ids),
                "has_proximity_graph": cp.proximity_graph is not None,
            }
            for cp in checkpoints
        ]

    def _extract_win_patterns(
        self,
        matches: List,
        hypotheses: List
    ) -> List[str]:
        """Extract patterns from winning hypotheses

        Analyzes tournament matches to identify common characteristics
        of hypotheses that tend to win.

        Args:
            matches: List of TournamentMatch objects
            hypotheses: List of Hypothesis objects

        Returns:
            List of identified winning patterns
        """
        # Simple pattern extraction - could be enhanced with LLM analysis
        patterns = []

        if not matches:
            return patterns

        # Find hypotheses with high win rates
        hyp_by_id = {h.id: h for h in hypotheses}
        win_counts: Dict[str, int] = {}
        match_counts: Dict[str, int] = {}

        for match in matches:
            for hyp_id in [match.hypothesis_a_id, match.hypothesis_b_id]:
                match_counts[hyp_id] = match_counts.get(hyp_id, 0) + 1
                if match.winner_id == hyp_id:
                    win_counts[hyp_id] = win_counts.get(hyp_id, 0) + 1

        # Identify top performers
        for hyp_id, wins in win_counts.items():
            total = match_counts.get(hyp_id, 1)
            win_rate = wins / total
            if win_rate >= 0.6 and total >= 2:
                hyp = hyp_by_id.get(hyp_id)
                if hyp and hyp.category:
                    patterns.append(f"High win rate in category: {hyp.category}")

        return list(set(patterns))[:5]  # Limit to 5 patterns

    def _extract_loss_patterns(
        self,
        matches: List,
        hypotheses: List
    ) -> List[str]:
        """Extract patterns from losing hypotheses

        Args:
            matches: List of TournamentMatch objects
            hypotheses: List of Hypothesis objects

        Returns:
            List of identified losing patterns
        """
        # Simple pattern extraction
        patterns = []

        if not matches:
            return patterns

        hyp_by_id = {h.id: h for h in hypotheses}
        loss_counts: Dict[str, int] = {}
        match_counts: Dict[str, int] = {}

        for match in matches:
            for hyp_id in [match.hypothesis_a_id, match.hypothesis_b_id]:
                match_counts[hyp_id] = match_counts.get(hyp_id, 0) + 1
                if match.winner_id and match.winner_id != hyp_id:
                    loss_counts[hyp_id] = loss_counts.get(hyp_id, 0) + 1

        # Identify poor performers
        for hyp_id, losses in loss_counts.items():
            total = match_counts.get(hyp_id, 1)
            loss_rate = losses / total
            if loss_rate >= 0.6 and total >= 2:
                hyp = hyp_by_id.get(hyp_id)
                if hyp and hyp.category:
                    patterns.append(f"High loss rate in category: {hyp.category}")

        return list(set(patterns))[:5]

    def _calculate_convergence(self, hypotheses: List) -> float:
        """Calculate tournament convergence score

        Measures how stable the Elo rankings are. Higher score means
        the top hypotheses have separated from the rest.

        Args:
            hypotheses: List of Hypothesis objects

        Returns:
            Convergence score between 0.0 and 1.0
        """
        if len(hypotheses) < 2:
            return 0.0

        # Sort by Elo rating
        sorted_hyps = sorted(
            hypotheses,
            key=lambda h: h.elo_rating or 1200.0,
            reverse=True
        )

        # Calculate rating gaps between consecutive hypotheses
        gaps = []
        for i in range(len(sorted_hyps) - 1):
            rating_a = sorted_hyps[i].elo_rating or 1200.0
            rating_b = sorted_hyps[i + 1].elo_rating or 1200.0
            gaps.append(rating_a - rating_b)

        if not gaps:
            return 0.0

        # Higher gaps between top hypotheses = more convergence
        # Use ratio of top gap to average gap
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        top_gap = gaps[0] if gaps else 0

        if avg_gap == 0:
            return 0.0

        # Normalize to 0-1 scale
        convergence = min(1.0, top_gap / (avg_gap * 3))

        return round(convergence, 3)

    async def _prune_old_checkpoints(self, goal_id: str) -> None:
        """Remove old checkpoints if over limit

        Keeps only the most recent max_checkpoints.

        Args:
            goal_id: Research goal ID
        """
        checkpoints = await self.storage.get_all_checkpoints(goal_id)

        if len(checkpoints) <= self.max_checkpoints:
            return

        # Note: Current InMemoryStorage doesn't support deletion
        # This would be implemented in PostgreSQL storage
        self.logger.debug(
            "Checkpoint pruning would remove old checkpoints",
            goal_id=goal_id,
            current_count=len(checkpoints),
            max_allowed=self.max_checkpoints
        )


def get_checkpoint_manager(storage: Optional[BaseStorage] = None) -> CheckpointManager:
    """Get a checkpoint manager instance

    Convenience function that creates a CheckpointManager with the
    global storage instance if none is provided.

    Args:
        storage: Optional storage backend

    Returns:
        CheckpointManager instance
    """
    if storage is None:
        from src.storage.memory import storage as default_storage
        storage = default_storage

    return CheckpointManager(storage)
