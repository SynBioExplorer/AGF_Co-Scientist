"""In-memory storage implementation for AI Co-Scientist.

This implementation stores all data in Python dictionaries. Useful for:
- Testing and development (fast, no external dependencies)
- Phase 1-3 backward compatibility
- Unit testing storage abstraction

All methods are async for API compatibility with database backends.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import sys
from pathlib import Path
import structlog

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import (
    ResearchGoal,
    ResearchPlanConfiguration,
    Hypothesis,
    HypothesisStatus,
    Review,
    ReviewType,
    TournamentMatch,
    TournamentState,
    ProximityGraph,
    ProximityEdge,
    HypothesisCluster,
    MetaReviewCritique,
    ResearchOverview,
    AgentTask,
    AgentType,
    SystemStatistics,
    ContextMemory,
    ScientistFeedback,
    ChatMessage,
)

from src.storage.base import BaseStorage

logger = structlog.get_logger()


class InMemoryStorage(BaseStorage):
    """In-memory storage for testing and development.

    All data is stored in Python dictionaries. Data is lost when the
    process terminates. Suitable for:
    - Unit tests
    - Development and debugging
    - Demos and prototypes
    - Phase 1-3 backward compatibility
    """

    def __init__(self):
        """Initialize empty storage containers."""
        # Core data
        self._research_goals: Dict[str, ResearchGoal] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._reviews: Dict[str, Review] = {}
        self._matches: Dict[str, TournamentMatch] = {}

        # Tournament and proximity
        self._tournament_states: Dict[str, TournamentState] = {}
        self._proximity_graphs: Dict[str, ProximityGraph] = {}
        self._proximity_edges: Dict[str, List[ProximityEdge]] = {}  # goal_id -> edges
        self._clusters: Dict[str, HypothesisCluster] = {}

        # Meta-review and overview
        self._meta_reviews: Dict[str, List[MetaReviewCritique]] = {}  # goal_id -> list
        self._overviews: Dict[str, ResearchOverview] = {}

        # System management
        self._tasks: Dict[str, AgentTask] = {}
        self._statistics: Dict[str, List[SystemStatistics]] = {}  # goal_id -> list
        self._checkpoints: Dict[str, List[ContextMemory]] = {}  # goal_id -> list

        # Scientist interaction
        self._feedback: Dict[str, ScientistFeedback] = {}
        self._chat_messages: Dict[str, List[ChatMessage]] = {}  # goal_id -> list

        # Research plan configurations
        self._plan_configs: Dict[str, ResearchPlanConfiguration] = {}

        self._connected = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> None:
        """No-op for in-memory storage."""
        self._connected = True
        logger.info("InMemoryStorage connected")

    async def disconnect(self) -> None:
        """No-op for in-memory storage."""
        self._connected = False
        logger.info("InMemoryStorage disconnected")

    async def health_check(self) -> bool:
        """Always healthy for in-memory storage."""
        return True

    # =========================================================================
    # Research Goals
    # =========================================================================

    async def add_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Store a new research goal."""
        self._research_goals[goal.id] = goal
        logger.info("Research goal added", goal_id=goal.id)
        return goal

    async def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve a research goal by ID."""
        return self._research_goals.get(goal_id)

    async def get_all_research_goals(self) -> List[ResearchGoal]:
        """Get all research goals, newest first."""
        goals = list(self._research_goals.values())
        return sorted(goals, key=lambda g: g.created_at, reverse=True)

    async def update_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Update an existing research goal."""
        if goal.id in self._research_goals:
            self._research_goals[goal.id] = goal
            logger.info("Research goal updated", goal_id=goal.id)
        return goal

    async def delete_research_goal(self, goal_id: str) -> bool:
        """Delete a research goal and all associated data."""
        if goal_id not in self._research_goals:
            return False

        # Cascade delete
        del self._research_goals[goal_id]

        # Remove associated hypotheses
        hyp_ids_to_remove = [
            h.id for h in self._hypotheses.values()
            if h.research_goal_id == goal_id
        ]
        for hyp_id in hyp_ids_to_remove:
            del self._hypotheses[hyp_id]
            # Remove associated reviews
            review_ids_to_remove = [
                r.id for r in self._reviews.values()
                if r.hypothesis_id == hyp_id
            ]
            for rev_id in review_ids_to_remove:
                del self._reviews[rev_id]

        # Remove matches
        match_ids_to_remove = [
            m.id for m in self._matches.values()
            if m.hypothesis_a_id in hyp_ids_to_remove or m.hypothesis_b_id in hyp_ids_to_remove
        ]
        for match_id in match_ids_to_remove:
            del self._matches[match_id]

        # Remove other associated data
        self._tournament_states.pop(goal_id, None)
        self._proximity_graphs.pop(goal_id, None)
        self._proximity_edges.pop(goal_id, None)
        self._meta_reviews.pop(goal_id, None)
        self._overviews.pop(goal_id, None)
        self._statistics.pop(goal_id, None)
        self._checkpoints.pop(goal_id, None)
        self._chat_messages.pop(goal_id, None)
        self._plan_configs.pop(goal_id, None)

        logger.info("Research goal deleted with cascade", goal_id=goal_id)
        return True

    # =========================================================================
    # Hypotheses
    # =========================================================================

    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Store a new hypothesis."""
        self._hypotheses[hypothesis.id] = hypothesis
        logger.info("Hypothesis added", hypothesis_id=hypothesis.id)
        return hypothesis

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve a hypothesis by ID."""
        return self._hypotheses.get(hypothesis_id)

    async def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Update an existing hypothesis."""
        if hypothesis.id in self._hypotheses:
            # Update the updated_at timestamp
            hypothesis.updated_at = datetime.now()
            self._hypotheses[hypothesis.id] = hypothesis
            logger.debug("Hypothesis updated", hypothesis_id=hypothesis.id)
        return hypothesis

    async def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis."""
        if hypothesis_id not in self._hypotheses:
            return False
        del self._hypotheses[hypothesis_id]
        # Cascade delete reviews
        review_ids = [r.id for r in self._reviews.values() if r.hypothesis_id == hypothesis_id]
        for rev_id in review_ids:
            del self._reviews[rev_id]
        logger.info("Hypothesis deleted", hypothesis_id=hypothesis_id)
        return True

    async def get_all_hypotheses(self) -> List[Hypothesis]:
        """Get all hypotheses, sorted by Elo rating."""
        hypotheses = list(self._hypotheses.values())
        return sorted(hypotheses, key=lambda h: h.elo_rating, reverse=True)

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
        """Get hypotheses without reviews."""
        hypotheses = await self.get_hypotheses_by_goal(goal_id, HypothesisStatus.GENERATED)
        # Filter to those without reviews
        result = []
        for h in hypotheses:
            reviews = await self.get_reviews_for_hypothesis(h.id)
            if not reviews:
                result.append(h)
                if len(result) >= limit:
                    break
        return result

    async def get_hypothesis_count(self, goal_id: Optional[str] = None) -> int:
        """Get total count of hypotheses."""
        if goal_id:
            return len([h for h in self._hypotheses.values() if h.research_goal_id == goal_id])
        return len(self._hypotheses)

    # =========================================================================
    # Reviews
    # =========================================================================

    async def add_review(self, review: Review) -> Review:
        """Store a new review."""
        self._reviews[review.id] = review
        logger.info("Review added", review_id=review.id, hypothesis_id=review.hypothesis_id)
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
        return sorted(reviews, key=lambda r: r.created_at, reverse=True)

    async def get_all_reviews(self, goal_id: Optional[str] = None) -> List[Review]:
        """Get all reviews."""
        if goal_id:
            # Get hypothesis IDs for this goal
            hyp_ids = {h.id for h in self._hypotheses.values() if h.research_goal_id == goal_id}
            return [r for r in self._reviews.values() if r.hypothesis_id in hyp_ids]
        return list(self._reviews.values())

    # =========================================================================
    # Tournament Matches
    # =========================================================================

    async def add_match(self, match: TournamentMatch) -> TournamentMatch:
        """Store a new tournament match."""
        self._matches[match.id] = match
        logger.info("Match added", match_id=match.id)
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
            hyp_ids = {h.id for h in self._hypotheses.values() if h.research_goal_id == goal_id}
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
        """Get total count of matches."""
        matches = await self.get_all_matches(goal_id)
        return len(matches)

    # =========================================================================
    # Tournament State
    # =========================================================================

    async def save_tournament_state(self, state: TournamentState) -> TournamentState:
        """Save tournament state."""
        state.updated_at = datetime.now()
        self._tournament_states[state.research_goal_id] = state
        return state

    async def get_tournament_state(self, goal_id: str) -> Optional[TournamentState]:
        """Get tournament state."""
        return self._tournament_states.get(goal_id)

    # =========================================================================
    # Proximity Graph
    # =========================================================================

    async def save_proximity_graph(self, graph: ProximityGraph) -> ProximityGraph:
        """Save proximity graph."""
        graph.updated_at = datetime.now()
        self._proximity_graphs[graph.research_goal_id] = graph
        # Store edges and clusters separately for efficient querying
        self._proximity_edges[graph.research_goal_id] = graph.edges
        for cluster in graph.clusters:
            self._clusters[cluster.id] = cluster
        return graph

    async def get_proximity_graph(self, goal_id: str) -> Optional[ProximityGraph]:
        """Get proximity graph."""
        return self._proximity_graphs.get(goal_id)

    async def add_proximity_edge(
        self,
        goal_id: str,
        edge: ProximityEdge
    ) -> ProximityEdge:
        """Add a single edge to the proximity graph."""
        if goal_id not in self._proximity_edges:
            self._proximity_edges[goal_id] = []
        self._proximity_edges[goal_id].append(edge)

        # Update the full graph if it exists
        if goal_id in self._proximity_graphs:
            self._proximity_graphs[goal_id].edges.append(edge)
            self._proximity_graphs[goal_id].updated_at = datetime.now()

        return edge

    async def get_similar_hypotheses(
        self,
        hypothesis_id: str,
        min_similarity: float = 0.7
    ) -> List[tuple[str, float]]:
        """Get hypotheses similar to a given hypothesis."""
        result = []
        for edges in self._proximity_edges.values():
            for edge in edges:
                if edge.similarity_score >= min_similarity:
                    if edge.hypothesis_a_id == hypothesis_id:
                        result.append((edge.hypothesis_b_id, edge.similarity_score))
                    elif edge.hypothesis_b_id == hypothesis_id:
                        result.append((edge.hypothesis_a_id, edge.similarity_score))
        return sorted(result, key=lambda x: x[1], reverse=True)

    # =========================================================================
    # Meta-Review
    # =========================================================================

    async def save_meta_review(
        self,
        meta_review: MetaReviewCritique
    ) -> MetaReviewCritique:
        """Save meta-review critique."""
        goal_id = meta_review.research_goal_id
        if goal_id not in self._meta_reviews:
            self._meta_reviews[goal_id] = []
        self._meta_reviews[goal_id].append(meta_review)
        return meta_review

    async def get_meta_review(self, goal_id: str) -> Optional[MetaReviewCritique]:
        """Get latest meta-review."""
        reviews = self._meta_reviews.get(goal_id, [])
        if not reviews:
            return None
        return sorted(reviews, key=lambda r: r.created_at, reverse=True)[0]

    async def get_all_meta_reviews(self, goal_id: str) -> List[MetaReviewCritique]:
        """Get all meta-reviews for a goal."""
        reviews = self._meta_reviews.get(goal_id, [])
        return sorted(reviews, key=lambda r: r.created_at, reverse=True)

    # =========================================================================
    # Research Overview
    # =========================================================================

    async def save_research_overview(
        self,
        overview: ResearchOverview
    ) -> ResearchOverview:
        """Save research overview."""
        overview.updated_at = datetime.now()
        self._overviews[overview.research_goal_id] = overview
        return overview

    async def get_research_overview(self, goal_id: str) -> Optional[ResearchOverview]:
        """Get research overview."""
        return self._overviews.get(goal_id)

    # =========================================================================
    # Agent Tasks
    # =========================================================================

    async def add_task(self, task: AgentTask) -> AgentTask:
        """Add a task to the queue."""
        self._tasks[task.id] = task
        logger.debug("Task added", task_id=task.id, agent=task.agent_type)
        return task

    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def get_pending_tasks(
        self,
        agent_type: Optional[AgentType] = None,
        limit: int = 100
    ) -> List[AgentTask]:
        """Get pending tasks."""
        tasks = [t for t in self._tasks.values() if t.status == "pending"]
        if agent_type:
            tasks = [t for t in tasks if t.agent_type == agent_type]
        # Sort by priority (highest first), then by created_at
        tasks = sorted(tasks, key=lambda t: (-t.priority, t.created_at))
        return tasks[:limit]

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
            if status == "running":
                task.started_at = datetime.now()
            elif status in ("complete", "failed"):
                task.completed_at = datetime.now()
            self._tasks[task_id] = task
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
            # Store worker_id in parameters
            task.parameters["worker_id"] = worker_id
            self._tasks[task.id] = task
            return task
        return None

    # =========================================================================
    # System Statistics
    # =========================================================================

    async def save_statistics(self, stats: SystemStatistics) -> SystemStatistics:
        """Save system statistics."""
        goal_id = stats.research_goal_id
        if goal_id not in self._statistics:
            self._statistics[goal_id] = []
        self._statistics[goal_id].append(stats)
        return stats

    async def get_latest_statistics(self, goal_id: str) -> Optional[SystemStatistics]:
        """Get latest statistics."""
        stats_list = self._statistics.get(goal_id, [])
        if not stats_list:
            return None
        return sorted(stats_list, key=lambda s: s.computed_at, reverse=True)[0]

    # =========================================================================
    # Context Memory (Checkpoints)
    # =========================================================================

    async def save_checkpoint(self, checkpoint: ContextMemory) -> ContextMemory:
        """Save a checkpoint."""
        checkpoint.updated_at = datetime.now()
        goal_id = checkpoint.research_goal_id
        if goal_id not in self._checkpoints:
            self._checkpoints[goal_id] = []
        self._checkpoints[goal_id].append(checkpoint)
        logger.info("Checkpoint saved", goal_id=goal_id, iteration=checkpoint.iteration_count)
        return checkpoint

    async def get_latest_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Get latest checkpoint."""
        checkpoints = self._checkpoints.get(goal_id, [])
        if not checkpoints:
            return None
        return sorted(checkpoints, key=lambda c: c.updated_at, reverse=True)[0]

    async def get_all_checkpoints(self, goal_id: str) -> List[ContextMemory]:
        """Get all checkpoints."""
        checkpoints = self._checkpoints.get(goal_id, [])
        return sorted(checkpoints, key=lambda c: c.updated_at, reverse=True)

    # =========================================================================
    # Scientist Feedback
    # =========================================================================

    async def add_feedback(self, feedback: ScientistFeedback) -> ScientistFeedback:
        """Store scientist feedback."""
        self._feedback[feedback.id] = feedback
        return feedback

    async def get_feedback_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[ScientistFeedback]:
        """Get feedback for a hypothesis."""
        return [
            f for f in self._feedback.values()
            if f.hypothesis_id == hypothesis_id
        ]

    async def get_all_feedback(self, goal_id: str) -> List[ScientistFeedback]:
        """Get all feedback for a goal."""
        # Need to find feedback by goal - feedback has hypothesis_id
        hyp_ids = {h.id for h in self._hypotheses.values() if h.research_goal_id == goal_id}
        return [
            f for f in self._feedback.values()
            if f.hypothesis_id in hyp_ids or f.hypothesis_id is None
        ]

    # =========================================================================
    # Chat Messages
    # =========================================================================

    async def add_chat_message(self, message: ChatMessage) -> ChatMessage:
        """Store a chat message."""
        # Infer goal_id from hypothesis references or use a default storage
        # For now, store all messages in a flat structure
        goal_id = "default"
        if goal_id not in self._chat_messages:
            self._chat_messages[goal_id] = []
        self._chat_messages[goal_id].append(message)
        return message

    async def get_chat_history(
        self,
        goal_id: str,
        limit: int = 100
    ) -> List[ChatMessage]:
        """Get chat history."""
        messages = self._chat_messages.get(goal_id, [])
        # Sort by created_at (oldest first for conversation flow)
        messages = sorted(messages, key=lambda m: m.created_at)
        return messages[-limit:] if len(messages) > limit else messages

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def clear_all(self, goal_id: Optional[str] = None) -> None:
        """Clear all stored data."""
        if goal_id:
            await self.delete_research_goal(goal_id)
        else:
            self._research_goals.clear()
            self._hypotheses.clear()
            self._reviews.clear()
            self._matches.clear()
            self._tournament_states.clear()
            self._proximity_graphs.clear()
            self._proximity_edges.clear()
            self._clusters.clear()
            self._meta_reviews.clear()
            self._overviews.clear()
            self._tasks.clear()
            self._statistics.clear()
            self._checkpoints.clear()
            self._feedback.clear()
            self._chat_messages.clear()
            self._plan_configs.clear()
            logger.info("All storage cleared")

    async def get_stats(self) -> Dict[str, int]:
        """Get storage statistics."""
        return {
            "research_goals": len(self._research_goals),
            "hypotheses": len(self._hypotheses),
            "reviews": len(self._reviews),
            "matches": len(self._matches),
            "tournament_states": len(self._tournament_states),
            "proximity_graphs": len(self._proximity_graphs),
            "meta_reviews": sum(len(v) for v in self._meta_reviews.values()),
            "overviews": len(self._overviews),
            "tasks": len(self._tasks),
            "checkpoints": sum(len(v) for v in self._checkpoints.values()),
            "feedback": len(self._feedback),
        }

    # =========================================================================
    # Transaction Support (no-op for in-memory)
    # =========================================================================

    async def begin_transaction(self) -> Any:
        """No-op for in-memory storage."""
        return None

    async def commit_transaction(self, transaction: Any) -> None:
        """No-op for in-memory storage."""
        pass

    async def rollback_transaction(self, transaction: Any) -> None:
        """No-op for in-memory storage."""
        pass


# =============================================================================
# Global storage instance for backward compatibility with Phase 1-3
# =============================================================================

# Synchronous wrapper class for backward compatibility
class SyncInMemoryStorage:
    """Synchronous wrapper for backward compatibility with Phase 1-3 code.

    This wrapper provides synchronous methods that wrap the async InMemoryStorage.
    For new code, use the async InMemoryStorage directly.
    """

    def __init__(self):
        self._async_storage = InMemoryStorage()

    # Sync versions of commonly used methods
    def add_research_goal(self, goal: ResearchGoal) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_storage.add_research_goal(goal))

    def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_research_goal(goal_id))

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_storage.add_hypothesis(hypothesis))

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_hypothesis(hypothesis_id))

    def update_hypothesis(self, hypothesis: Hypothesis) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_storage.update_hypothesis(hypothesis))

    def get_all_hypotheses(self) -> List[Hypothesis]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_all_hypotheses())

    def get_hypotheses_by_goal(self, goal_id: str) -> List[Hypothesis]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_hypotheses_by_goal(goal_id))

    def add_review(self, review: Review) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_storage.add_review(review))

    def get_review(self, review_id: str) -> Optional[Review]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_review(review_id))

    def get_reviews_for_hypothesis(self, hypothesis_id: str) -> List[Review]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_reviews_for_hypothesis(hypothesis_id))

    def add_match(self, match: TournamentMatch) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_storage.add_match(match))

    def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_match(match_id))

    def get_all_matches(self) -> List[TournamentMatch]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_all_matches())

    def get_matches_for_hypothesis(self, hypothesis_id: str) -> List[TournamentMatch]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_matches_for_hypothesis(hypothesis_id))

    def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_hypothesis_win_rate(hypothesis_id))

    def get_top_hypotheses(self, n: int = 10) -> List[Hypothesis]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_top_hypotheses(n))

    def get_all_reviews(self) -> List[Review]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_all_reviews())

    def clear_all(self) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self._async_storage.clear_all())

    def get_stats(self) -> Dict[str, int]:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._async_storage.get_stats())


# Global storage instance for backward compatibility
storage = SyncInMemoryStorage()
