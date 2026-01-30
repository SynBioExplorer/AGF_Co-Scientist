"""Async storage adapter for AI Co-Scientist.

This module provides an async adapter that wraps the InMemoryStorage
to match the BaseStorage interface. This allows the Supervisor to work
with async storage methods while using the existing in-memory implementation.

Once the Database agent merges their work, this can be replaced with
the actual PostgreSQL implementation.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import (
    ResearchGoal,
    ResearchPlanConfiguration,
    Hypothesis,
    Review,
    TournamentMatch,
    TournamentState,
    ProximityGraph,
    ProximityEdge,
    HypothesisCluster,
    MetaReviewCritique,
    ResearchOverview,
    AgentTask,
    SystemStatistics,
    ContextMemory,
    ScientistFeedback,
    ChatMessage,
    HypothesisStatus,
    ReviewType,
    AgentType,
)


class AsyncStorageAdapter:
    """Async adapter for storage operations.

    Wraps synchronous operations to provide async interface matching
    the BaseStorage abstract class from the database agent.

    This is a development/testing adapter. For production, use the
    PostgreSQL implementation from the database agent.
    """

    def __init__(self):
        # Internal storage dictionaries
        self._research_goals: Dict[str, ResearchGoal] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._reviews: Dict[str, Review] = {}
        self._matches: Dict[str, TournamentMatch] = {}
        self._tasks: Dict[str, AgentTask] = {}
        self._tournament_states: Dict[str, TournamentState] = {}
        self._proximity_graphs: Dict[str, ProximityGraph] = {}
        self._meta_reviews: Dict[str, List[MetaReviewCritique]] = {}
        self._research_overviews: Dict[str, ResearchOverview] = {}
        self._statistics: Dict[str, List[SystemStatistics]] = {}
        self._checkpoints: Dict[str, List[ContextMemory]] = {}
        self._feedback: Dict[str, List[ScientistFeedback]] = {}
        self._chat_messages: Dict[str, List[ChatMessage]] = {}
        self._connected = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """Initialize connection (no-op for in-memory)."""
        self._connected = True

    async def disconnect(self) -> None:
        """Close connection (no-op for in-memory)."""
        self._connected = False

    async def health_check(self) -> bool:
        """Check if storage is healthy."""
        return self._connected

    # =========================================================================
    # Research Goals
    # =========================================================================

    async def add_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Store a new research goal."""
        self._research_goals[goal.id] = goal
        return goal

    async def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve a research goal by ID."""
        return self._research_goals.get(goal_id)

    async def get_all_research_goals(self) -> List[ResearchGoal]:
        """Retrieve all research goals."""
        return sorted(
            list(self._research_goals.values()),
            key=lambda g: g.created_at,
            reverse=True
        )

    async def update_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Update an existing research goal."""
        self._research_goals[goal.id] = goal
        return goal

    async def delete_research_goal(self, goal_id: str) -> bool:
        """Delete a research goal and associated data."""
        if goal_id not in self._research_goals:
            return False

        del self._research_goals[goal_id]
        # Cascade delete associated data
        self._hypotheses = {
            k: v for k, v in self._hypotheses.items()
            if v.research_goal_id != goal_id
        }
        return True

    # =========================================================================
    # Hypotheses
    # =========================================================================

    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Store a new hypothesis."""
        self._hypotheses[hypothesis.id] = hypothesis
        return hypothesis

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve a hypothesis by ID."""
        return self._hypotheses.get(hypothesis_id)

    async def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Update an existing hypothesis."""
        hypothesis.updated_at = datetime.now()
        self._hypotheses[hypothesis.id] = hypothesis
        return hypothesis

    async def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis."""
        if hypothesis_id in self._hypotheses:
            del self._hypotheses[hypothesis_id]
            return True
        return False

    async def get_all_hypotheses(self) -> List[Hypothesis]:
        """Retrieve all hypotheses sorted by Elo rating."""
        return sorted(
            list(self._hypotheses.values()),
            key=lambda h: h.elo_rating,
            reverse=True
        )

    async def get_hypotheses_by_goal(
        self,
        goal_id: str,
        status: Optional[HypothesisStatus] = None
    ) -> List[Hypothesis]:
        """Get all hypotheses for a research goal."""
        hypotheses = [
            h for h in self._hypotheses.values()
            if h.research_goal_id == goal_id
        ]
        if status:
            hypotheses = [h for h in hypotheses if h.status == status]
        return sorted(hypotheses, key=lambda h: h.elo_rating, reverse=True)

    async def get_top_hypotheses(
        self,
        n: int = 10,
        goal_id: Optional[str] = None
    ) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating."""
        if goal_id:
            hypotheses = await self.get_hypotheses_by_goal(goal_id)
        else:
            hypotheses = await self.get_all_hypotheses()
        return hypotheses[:n]

    async def get_hypotheses_needing_review(
        self,
        goal_id: str,
        limit: int = 10
    ) -> List[Hypothesis]:
        """Get hypotheses that haven't been reviewed."""
        return [
            h for h in await self.get_hypotheses_by_goal(goal_id)
            if h.status == HypothesisStatus.GENERATED
        ][:limit]

    async def get_hypothesis_count(self, goal_id: Optional[str] = None) -> int:
        """Get total count of hypotheses."""
        if goal_id:
            return len(await self.get_hypotheses_by_goal(goal_id))
        return len(self._hypotheses)

    # =========================================================================
    # Reviews
    # =========================================================================

    async def add_review(self, review: Review) -> Review:
        """Store a new review."""
        self._reviews[review.id] = review
        return review

    async def get_review(self, review_id: str) -> Optional[Review]:
        """Retrieve a review by ID."""
        return self._reviews.get(review_id)

    async def get_reviews_for_hypothesis(
        self,
        hypothesis_id: str,
        review_type: Optional[ReviewType] = None
    ) -> List[Review]:
        """Get all reviews for a hypothesis."""
        reviews = [
            r for r in self._reviews.values()
            if r.hypothesis_id == hypothesis_id
        ]
        if review_type:
            reviews = [r for r in reviews if r.review_type == review_type]
        return reviews

    async def get_all_reviews(self, goal_id: Optional[str] = None) -> List[Review]:
        """Get all reviews."""
        if goal_id:
            # Get hypothesis IDs for this goal
            hyp_ids = {h.id for h in await self.get_hypotheses_by_goal(goal_id)}
            return [r for r in self._reviews.values() if r.hypothesis_id in hyp_ids]
        return list(self._reviews.values())

    # =========================================================================
    # Tournament Matches
    # =========================================================================

    async def add_match(self, match: TournamentMatch) -> TournamentMatch:
        """Store a new tournament match."""
        self._matches[match.id] = match
        return match

    async def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        """Retrieve a match by ID."""
        return self._matches.get(match_id)

    async def get_matches_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[TournamentMatch]:
        """Get all matches involving a hypothesis."""
        return [
            m for m in self._matches.values()
            if m.hypothesis_a_id == hypothesis_id or m.hypothesis_b_id == hypothesis_id
        ]

    async def get_all_matches(self, goal_id: Optional[str] = None) -> List[TournamentMatch]:
        """Get all tournament matches."""
        if goal_id:
            hyp_ids = {h.id for h in await self.get_hypotheses_by_goal(goal_id)}
            return [
                m for m in self._matches.values()
                if m.hypothesis_a_id in hyp_ids or m.hypothesis_b_id in hyp_ids
            ]
        return list(self._matches.values())

    async def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for a hypothesis."""
        matches = await self.get_matches_for_hypothesis(hypothesis_id)
        if not matches:
            return 0.0
        wins = sum(1 for m in matches if m.winner_id == hypothesis_id)
        return wins / len(matches)

    async def get_match_count(self, goal_id: Optional[str] = None) -> int:
        """Get total count of tournament matches."""
        matches = await self.get_all_matches(goal_id)
        return len(matches)

    # =========================================================================
    # Tournament State
    # =========================================================================

    async def save_tournament_state(self, state: TournamentState) -> TournamentState:
        """Save tournament state for a research goal."""
        state.updated_at = datetime.now()
        self._tournament_states[state.research_goal_id] = state
        return state

    async def get_tournament_state(self, goal_id: str) -> Optional[TournamentState]:
        """Get tournament state for a research goal."""
        return self._tournament_states.get(goal_id)

    # =========================================================================
    # Proximity Graph
    # =========================================================================

    async def save_proximity_graph(self, graph: ProximityGraph) -> ProximityGraph:
        """Save proximity graph for a research goal."""
        graph.updated_at = datetime.now()
        self._proximity_graphs[graph.research_goal_id] = graph
        return graph

    async def get_proximity_graph(self, goal_id: str) -> Optional[ProximityGraph]:
        """Get proximity graph for a research goal."""
        return self._proximity_graphs.get(goal_id)

    async def add_proximity_edge(
        self,
        goal_id: str,
        edge: ProximityEdge
    ) -> ProximityEdge:
        """Add a single edge to the proximity graph."""
        graph = self._proximity_graphs.get(goal_id)
        if graph:
            graph.edges.append(edge)
            graph.updated_at = datetime.now()
        return edge

    async def get_similar_hypotheses(
        self,
        hypothesis_id: str,
        min_similarity: float = 0.7
    ) -> List[tuple]:
        """Get hypotheses similar to a given hypothesis."""
        results = []
        for graph in self._proximity_graphs.values():
            for edge in graph.edges:
                if edge.hypothesis_a_id == hypothesis_id and edge.similarity_score >= min_similarity:
                    results.append((edge.hypothesis_b_id, edge.similarity_score))
                elif edge.hypothesis_b_id == hypothesis_id and edge.similarity_score >= min_similarity:
                    results.append((edge.hypothesis_a_id, edge.similarity_score))
        return sorted(results, key=lambda x: x[1], reverse=True)

    async def get_diverse_hypotheses(
        self,
        goal_id: str,
        n: int = 10,
        min_elo_rating: float = 1200.0,
        cluster_balance: bool = True
    ) -> List[Hypothesis]:
        """
        Get diverse hypotheses using cluster-aware sampling.

        Strategy:
        1. Fetch proximity graph for goal
        2. Get all hypotheses for goal
        3. For each cluster, select top-rated hypothesis
        4. If fewer clusters than n, fill remainder with top Elo
        5. Return exactly n hypotheses

        Args:
            goal_id: Research goal ID
            n: Number of hypotheses to return (default: 10)
            min_elo_rating: Minimum Elo threshold (default: 1200.0)
            cluster_balance: If True, balance across clusters; else top from each

        Returns:
            List of n diverse hypotheses
        """
        # Get proximity graph
        proximity_graph = await self.get_proximity_graph(goal_id)

        # Get all hypotheses for goal
        all_hypotheses = await self.get_hypotheses_by_goal(goal_id)

        # Filter by minimum Elo
        qualified = [h for h in all_hypotheses if (h.elo_rating or 1200.0) >= min_elo_rating]

        # If no proximity graph, fallback to top Elo
        if not proximity_graph or not proximity_graph.clusters:
            return sorted(qualified, key=lambda h: h.elo_rating or 1200.0, reverse=True)[:n]

        # Cluster-aware selection
        selected = []
        hyp_map = {h.id: h for h in qualified}

        # For each cluster, pick top-rated hypothesis
        for cluster in proximity_graph.clusters:
            cluster_hyps = [hyp_map[hid] for hid in cluster.hypothesis_ids if hid in hyp_map]
            if cluster_hyps:
                top_in_cluster = max(cluster_hyps, key=lambda h: h.elo_rating or 1200.0)
                selected.append(top_in_cluster)

        # If we have more than n, take top n by Elo
        if len(selected) > n:
            selected = sorted(selected, key=lambda h: h.elo_rating or 1200.0, reverse=True)[:n]

        # If we have fewer than n, fill with top remaining hypotheses
        if len(selected) < n:
            selected_ids = {h.id for h in selected}
            remaining = [h for h in qualified if h.id not in selected_ids]
            remaining_sorted = sorted(remaining, key=lambda h: h.elo_rating or 1200.0, reverse=True)
            selected.extend(remaining_sorted[:n - len(selected)])

        # Sort final result by Elo for consistency
        return sorted(selected, key=lambda h: h.elo_rating or 1200.0, reverse=True)

    # =========================================================================
    # Meta-Review
    # =========================================================================

    async def save_meta_review(
        self,
        meta_review: MetaReviewCritique
    ) -> MetaReviewCritique:
        """Save meta-review critique for a research goal."""
        goal_id = meta_review.research_goal_id
        if goal_id not in self._meta_reviews:
            self._meta_reviews[goal_id] = []
        self._meta_reviews[goal_id].insert(0, meta_review)
        return meta_review

    async def get_meta_review(self, goal_id: str) -> Optional[MetaReviewCritique]:
        """Get latest meta-review critique for a research goal."""
        reviews = self._meta_reviews.get(goal_id, [])
        return reviews[0] if reviews else None

    async def get_all_meta_reviews(self, goal_id: str) -> List[MetaReviewCritique]:
        """Get all meta-reviews for a research goal."""
        return self._meta_reviews.get(goal_id, [])

    # =========================================================================
    # Research Overview
    # =========================================================================

    async def save_research_overview(
        self,
        overview: ResearchOverview
    ) -> ResearchOverview:
        """Save research overview for a research goal."""
        overview.updated_at = datetime.now()
        self._research_overviews[overview.research_goal_id] = overview
        return overview

    async def get_research_overview(self, goal_id: str) -> Optional[ResearchOverview]:
        """Get research overview for a research goal."""
        return self._research_overviews.get(goal_id)

    # =========================================================================
    # Agent Tasks
    # =========================================================================

    async def add_task(self, task: AgentTask) -> AgentTask:
        """Add a new agent task."""
        self._tasks[task.id] = task
        return task

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Retrieve a task by ID."""
        return self._tasks.get(task_id)

    async def get_pending_tasks(
        self,
        agent_type: Optional[AgentType] = None,
        limit: int = 100
    ) -> List[AgentTask]:
        """Get pending tasks sorted by priority."""
        tasks = [
            t for t in self._tasks.values()
            if t.status == "pending"
        ]
        if agent_type:
            tasks = [t for t in tasks if t.agent_type == agent_type]
        return sorted(tasks, key=lambda t: t.priority, reverse=True)[:limit]

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> AgentTask:
        """Update task status."""
        task = self._tasks.get(task_id)
        if task:
            task.status = status
            if result:
                task.result = result
            if status == "running" and not task.started_at:
                task.started_at = datetime.now()
            elif status in ("complete", "failed"):
                task.completed_at = datetime.now()
        return task

    async def claim_next_task(
        self,
        agent_type: AgentType,
        worker_id: str
    ) -> Optional[AgentTask]:
        """Atomically claim the next available task."""
        pending = await self.get_pending_tasks(agent_type, limit=1)
        if pending:
            task = pending[0]
            task.status = "running"
            task.started_at = datetime.now()
            return task
        return None

    # =========================================================================
    # System Statistics
    # =========================================================================

    async def save_statistics(self, stats: SystemStatistics) -> SystemStatistics:
        """Save system statistics snapshot."""
        goal_id = stats.research_goal_id
        if goal_id not in self._statistics:
            self._statistics[goal_id] = []
        self._statistics[goal_id].insert(0, stats)
        return stats

    async def get_latest_statistics(self, goal_id: str) -> Optional[SystemStatistics]:
        """Get latest statistics for a research goal."""
        stats = self._statistics.get(goal_id, [])
        return stats[0] if stats else None

    # =========================================================================
    # Context Memory (Checkpoints)
    # =========================================================================

    async def save_checkpoint(self, checkpoint: ContextMemory) -> ContextMemory:
        """Save a workflow checkpoint."""
        goal_id = checkpoint.research_goal_id
        if goal_id not in self._checkpoints:
            self._checkpoints[goal_id] = []
        checkpoint.updated_at = datetime.now()
        self._checkpoints[goal_id].insert(0, checkpoint)
        return checkpoint

    async def get_latest_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Get the most recent checkpoint for a research goal."""
        checkpoints = self._checkpoints.get(goal_id, [])
        return checkpoints[0] if checkpoints else None

    async def get_all_checkpoints(self, goal_id: str) -> List[ContextMemory]:
        """Get all checkpoints for a research goal."""
        return self._checkpoints.get(goal_id, [])

    # =========================================================================
    # Scientist Feedback
    # =========================================================================

    async def add_feedback(self, feedback: ScientistFeedback) -> ScientistFeedback:
        """Store scientist feedback."""
        goal_id = feedback.hypothesis_id or "general"
        if goal_id not in self._feedback:
            self._feedback[goal_id] = []
        self._feedback[goal_id].append(feedback)
        return feedback

    async def get_feedback_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[ScientistFeedback]:
        """Get all feedback for a specific hypothesis."""
        return self._feedback.get(hypothesis_id, [])

    async def get_all_feedback(self, goal_id: str) -> List[ScientistFeedback]:
        """Get all feedback for a research goal."""
        # Get all hypotheses for this goal
        hyp_ids = {h.id for h in await self.get_hypotheses_by_goal(goal_id)}
        feedback = []
        for hyp_id in hyp_ids:
            feedback.extend(self._feedback.get(hyp_id, []))
        return sorted(feedback, key=lambda f: f.created_at)

    # =========================================================================
    # Chat Messages
    # =========================================================================

    async def add_chat_message(self, message: ChatMessage) -> ChatMessage:
        """Store a chat message."""
        # Use a convention: store by goal_id (extracted from context)
        goal_id = "default"  # In practice, pass goal_id
        if goal_id not in self._chat_messages:
            self._chat_messages[goal_id] = []
        self._chat_messages[goal_id].append(message)
        return message

    async def get_chat_history(
        self,
        goal_id: str,
        limit: int = 100
    ) -> List[ChatMessage]:
        """Get chat history for a research goal."""
        messages = self._chat_messages.get(goal_id, [])
        return sorted(messages, key=lambda m: m.created_at)[-limit:]

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def clear_all(self, goal_id: Optional[str] = None) -> None:
        """Clear all stored data."""
        if goal_id:
            # Clear data for specific goal
            if goal_id in self._research_goals:
                del self._research_goals[goal_id]
            self._hypotheses = {
                k: v for k, v in self._hypotheses.items()
                if v.research_goal_id != goal_id
            }
            # Clear other collections for this goal
            if goal_id in self._tournament_states:
                del self._tournament_states[goal_id]
            if goal_id in self._proximity_graphs:
                del self._proximity_graphs[goal_id]
            if goal_id in self._meta_reviews:
                del self._meta_reviews[goal_id]
            if goal_id in self._research_overviews:
                del self._research_overviews[goal_id]
            if goal_id in self._statistics:
                del self._statistics[goal_id]
            if goal_id in self._checkpoints:
                del self._checkpoints[goal_id]
        else:
            # Clear all
            self._research_goals.clear()
            self._hypotheses.clear()
            self._reviews.clear()
            self._matches.clear()
            self._tasks.clear()
            self._tournament_states.clear()
            self._proximity_graphs.clear()
            self._meta_reviews.clear()
            self._research_overviews.clear()
            self._statistics.clear()
            self._checkpoints.clear()
            self._feedback.clear()
            self._chat_messages.clear()

    async def get_stats(self) -> Dict[str, int]:
        """Get storage statistics."""
        return {
            "research_goals": len(self._research_goals),
            "hypotheses": len(self._hypotheses),
            "reviews": len(self._reviews),
            "matches": len(self._matches),
            "tasks": len(self._tasks),
            "tournament_states": len(self._tournament_states),
            "proximity_graphs": len(self._proximity_graphs),
        }

    # =========================================================================
    # Transaction Support (no-op for in-memory)
    # =========================================================================

    async def begin_transaction(self) -> Any:
        """Begin a transaction (no-op for in-memory)."""
        return None

    async def commit_transaction(self, transaction: Any) -> None:
        """Commit a transaction (no-op for in-memory)."""
        pass

    async def rollback_transaction(self, transaction: Any) -> None:
        """Rollback a transaction (no-op for in-memory)."""
        pass


# Global storage instance
async_storage = AsyncStorageAdapter()
