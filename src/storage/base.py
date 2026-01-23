"""Abstract storage interface for AI Co-Scientist data persistence.

This module defines the BaseStorage abstract class that all storage backends
must implement. This enables switching between in-memory, PostgreSQL, or other
storage backends via configuration.

Priority: HIGHEST - Published Day 1 to unblock Supervisor Agent development.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import (
    # Core models
    ResearchGoal,
    ResearchPlanConfiguration,
    Hypothesis,
    # Review models
    Review,
    DeepVerificationReview,
    # Tournament models
    TournamentMatch,
    TournamentState,
    # Proximity models
    ProximityGraph,
    ProximityEdge,
    HypothesisCluster,
    # Meta-review models
    MetaReviewCritique,
    ResearchOverview,
    ResearchDirection,
    ResearchContact,
    # System models
    AgentTask,
    SystemStatistics,
    ContextMemory,
    # Scientist interaction models
    ScientistFeedback,
    ChatMessage,
    # Enums
    HypothesisStatus,
    ReviewType,
    AgentType,
)


class BaseStorage(ABC):
    """Abstract base class for all storage implementations.

    All methods are async to support both in-memory (trivially async) and
    database-backed (truly async with connection pools) implementations.

    Storage backends:
    - InMemoryStorage: For testing and development
    - PostgreSQLStorage: For production with persistence
    - CachedStorage: PostgreSQL + Redis caching layer
    """

    # =========================================================================
    # Connection Management
    # =========================================================================

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection pool or resources.

        Called once at application startup. For in-memory storage, this is a no-op.
        For database storage, this creates the connection pool.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection pool or release resources.

        Called at application shutdown. Ensures clean resource cleanup.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if storage backend is healthy and responsive.

        Returns:
            True if storage is operational, False otherwise.
        """
        pass

    # =========================================================================
    # Research Goals
    # =========================================================================

    @abstractmethod
    async def add_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Store a new research goal.

        Args:
            goal: The research goal to store.

        Returns:
            The stored research goal (with any generated fields populated).
        """
        pass

    @abstractmethod
    async def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve a research goal by ID.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            The research goal if found, None otherwise.
        """
        pass

    @abstractmethod
    async def get_all_research_goals(self) -> List[ResearchGoal]:
        """Retrieve all research goals.

        Returns:
            List of all research goals, ordered by creation date (newest first).
        """
        pass

    @abstractmethod
    async def update_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Update an existing research goal.

        Args:
            goal: The research goal with updated fields.

        Returns:
            The updated research goal.
        """
        pass

    @abstractmethod
    async def delete_research_goal(self, goal_id: str) -> bool:
        """Delete a research goal and all associated data.

        This cascades to delete all hypotheses, reviews, matches, etc.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            True if deleted, False if not found.
        """
        pass

    # =========================================================================
    # Hypotheses
    # =========================================================================

    @abstractmethod
    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Store a new hypothesis.

        Args:
            hypothesis: The hypothesis to store.

        Returns:
            The stored hypothesis.
        """
        pass

    @abstractmethod
    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve a hypothesis by ID.

        Args:
            hypothesis_id: Unique identifier of the hypothesis.

        Returns:
            The hypothesis if found, None otherwise.
        """
        pass

    @abstractmethod
    async def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Update an existing hypothesis (e.g., Elo rating, status).

        Args:
            hypothesis: The hypothesis with updated fields.

        Returns:
            The updated hypothesis.
        """
        pass

    @abstractmethod
    async def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete a hypothesis.

        Args:
            hypothesis_id: Unique identifier of the hypothesis.

        Returns:
            True if deleted, False if not found.
        """
        pass

    @abstractmethod
    async def get_all_hypotheses(self) -> List[Hypothesis]:
        """Retrieve all hypotheses across all research goals.

        Returns:
            List of all hypotheses, ordered by Elo rating (highest first).
        """
        pass

    @abstractmethod
    async def get_hypotheses_by_goal(
        self,
        goal_id: str,
        status: Optional[HypothesisStatus] = None
    ) -> List[Hypothesis]:
        """Get all hypotheses for a research goal, optionally filtered by status.

        Args:
            goal_id: Unique identifier of the research goal.
            status: Optional status filter.

        Returns:
            List of matching hypotheses, ordered by Elo rating (highest first).
        """
        pass

    @abstractmethod
    async def get_top_hypotheses(
        self,
        n: int = 10,
        goal_id: Optional[str] = None
    ) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating.

        Args:
            n: Number of hypotheses to return.
            goal_id: Optional filter by research goal.

        Returns:
            Top N hypotheses ordered by Elo rating (highest first).
        """
        pass

    @abstractmethod
    async def get_hypotheses_needing_review(
        self,
        goal_id: str,
        limit: int = 10
    ) -> List[Hypothesis]:
        """Get hypotheses that haven't been reviewed yet.

        Args:
            goal_id: Unique identifier of the research goal.
            limit: Maximum number to return.

        Returns:
            Hypotheses with status GENERATED (no reviews yet).
        """
        pass

    @abstractmethod
    async def get_hypothesis_count(self, goal_id: Optional[str] = None) -> int:
        """Get total count of hypotheses.

        Args:
            goal_id: Optional filter by research goal.

        Returns:
            Total count of hypotheses.
        """
        pass

    # =========================================================================
    # Reviews
    # =========================================================================

    @abstractmethod
    async def add_review(self, review: Review) -> Review:
        """Store a new review.

        Args:
            review: The review to store.

        Returns:
            The stored review.
        """
        pass

    @abstractmethod
    async def get_review(self, review_id: str) -> Optional[Review]:
        """Retrieve a review by ID.

        Args:
            review_id: Unique identifier of the review.

        Returns:
            The review if found, None otherwise.
        """
        pass

    @abstractmethod
    async def get_reviews_for_hypothesis(
        self,
        hypothesis_id: str,
        review_type: Optional[ReviewType] = None
    ) -> List[Review]:
        """Get all reviews for a hypothesis, optionally filtered by type.

        Args:
            hypothesis_id: Unique identifier of the hypothesis.
            review_type: Optional filter by review type.

        Returns:
            List of reviews for the hypothesis.
        """
        pass

    @abstractmethod
    async def get_all_reviews(self, goal_id: Optional[str] = None) -> List[Review]:
        """Get all reviews, optionally filtered by research goal.

        Args:
            goal_id: Optional filter by research goal.

        Returns:
            List of all matching reviews.
        """
        pass

    # =========================================================================
    # Tournament Matches
    # =========================================================================

    @abstractmethod
    async def add_match(self, match: TournamentMatch) -> TournamentMatch:
        """Store a new tournament match.

        Args:
            match: The tournament match to store.

        Returns:
            The stored match.
        """
        pass

    @abstractmethod
    async def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        """Retrieve a match by ID.

        Args:
            match_id: Unique identifier of the match.

        Returns:
            The match if found, None otherwise.
        """
        pass

    @abstractmethod
    async def get_matches_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[TournamentMatch]:
        """Get all matches involving a hypothesis.

        Args:
            hypothesis_id: Unique identifier of the hypothesis.

        Returns:
            List of matches where this hypothesis participated.
        """
        pass

    @abstractmethod
    async def get_all_matches(self, goal_id: Optional[str] = None) -> List[TournamentMatch]:
        """Get all tournament matches, optionally filtered by research goal.

        Args:
            goal_id: Optional filter by research goal.

        Returns:
            List of all matches.
        """
        pass

    @abstractmethod
    async def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for a hypothesis.

        Args:
            hypothesis_id: Unique identifier of the hypothesis.

        Returns:
            Win rate as a float between 0.0 and 1.0.
            Returns 0.0 if no matches found.
        """
        pass

    @abstractmethod
    async def get_match_count(self, goal_id: Optional[str] = None) -> int:
        """Get total count of tournament matches.

        Args:
            goal_id: Optional filter by research goal.

        Returns:
            Total count of matches.
        """
        pass

    # =========================================================================
    # Tournament State
    # =========================================================================

    @abstractmethod
    async def save_tournament_state(self, state: TournamentState) -> TournamentState:
        """Save or update tournament state for a research goal.

        Args:
            state: The tournament state to save.

        Returns:
            The saved tournament state.
        """
        pass

    @abstractmethod
    async def get_tournament_state(self, goal_id: str) -> Optional[TournamentState]:
        """Get tournament state for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            The tournament state if found, None otherwise.
        """
        pass

    # =========================================================================
    # Proximity Graph
    # =========================================================================

    @abstractmethod
    async def save_proximity_graph(self, graph: ProximityGraph) -> ProximityGraph:
        """Save or update proximity graph for a research goal.

        This saves the graph along with all edges and clusters.

        Args:
            graph: The proximity graph to save.

        Returns:
            The saved proximity graph.
        """
        pass

    @abstractmethod
    async def get_proximity_graph(self, goal_id: str) -> Optional[ProximityGraph]:
        """Get proximity graph for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            The proximity graph if found, None otherwise.
        """
        pass

    @abstractmethod
    async def add_proximity_edge(
        self,
        goal_id: str,
        edge: ProximityEdge
    ) -> ProximityEdge:
        """Add a single edge to the proximity graph.

        Args:
            goal_id: Unique identifier of the research goal.
            edge: The edge to add.

        Returns:
            The added edge.
        """
        pass

    @abstractmethod
    async def get_similar_hypotheses(
        self,
        hypothesis_id: str,
        min_similarity: float = 0.7
    ) -> List[tuple[str, float]]:
        """Get hypotheses similar to a given hypothesis.

        Args:
            hypothesis_id: The hypothesis to find similar ones for.
            min_similarity: Minimum similarity threshold (0.0-1.0).

        Returns:
            List of (hypothesis_id, similarity_score) tuples.
        """
        pass

    # =========================================================================
    # Meta-Review
    # =========================================================================

    @abstractmethod
    async def save_meta_review(
        self,
        meta_review: MetaReviewCritique
    ) -> MetaReviewCritique:
        """Save or update meta-review critique for a research goal.

        Args:
            meta_review: The meta-review critique to save.

        Returns:
            The saved meta-review critique.
        """
        pass

    @abstractmethod
    async def get_meta_review(self, goal_id: str) -> Optional[MetaReviewCritique]:
        """Get latest meta-review critique for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            The meta-review critique if found, None otherwise.
        """
        pass

    @abstractmethod
    async def get_all_meta_reviews(self, goal_id: str) -> List[MetaReviewCritique]:
        """Get all meta-reviews for a research goal (historical).

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            List of meta-reviews ordered by creation date (newest first).
        """
        pass

    # =========================================================================
    # Research Overview
    # =========================================================================

    @abstractmethod
    async def save_research_overview(
        self,
        overview: ResearchOverview
    ) -> ResearchOverview:
        """Save or update research overview for a research goal.

        Args:
            overview: The research overview to save.

        Returns:
            The saved research overview.
        """
        pass

    @abstractmethod
    async def get_research_overview(self, goal_id: str) -> Optional[ResearchOverview]:
        """Get latest research overview for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            The research overview if found, None otherwise.
        """
        pass

    # =========================================================================
    # Agent Tasks (for Supervisor)
    # =========================================================================

    @abstractmethod
    async def add_task(self, task: AgentTask) -> AgentTask:
        """Add a new agent task to the queue.

        Args:
            task: The task to add.

        Returns:
            The stored task.
        """
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[AgentTask]:
        """Retrieve a task by ID.

        Args:
            task_id: Unique identifier of the task.

        Returns:
            The task if found, None otherwise.
        """
        pass

    @abstractmethod
    async def get_pending_tasks(
        self,
        agent_type: Optional[AgentType] = None,
        limit: int = 100
    ) -> List[AgentTask]:
        """Get pending tasks, optionally filtered by agent type.

        Args:
            agent_type: Optional filter by agent type.
            limit: Maximum number of tasks to return.

        Returns:
            List of pending tasks ordered by priority (highest first).
        """
        pass

    @abstractmethod
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> AgentTask:
        """Update task status and optionally set result.

        Args:
            task_id: Unique identifier of the task.
            status: New status (pending/running/complete/failed).
            result: Optional result data for completed tasks.

        Returns:
            The updated task.
        """
        pass

    @abstractmethod
    async def claim_next_task(
        self,
        agent_type: AgentType,
        worker_id: str
    ) -> Optional[AgentTask]:
        """Atomically claim the next available task for an agent type.

        This is used by worker processes to claim tasks without conflicts.

        Args:
            agent_type: Type of agent claiming the task.
            worker_id: Identifier of the worker process.

        Returns:
            The claimed task if available, None otherwise.
        """
        pass

    # =========================================================================
    # System Statistics
    # =========================================================================

    @abstractmethod
    async def save_statistics(self, stats: SystemStatistics) -> SystemStatistics:
        """Save system statistics snapshot.

        Args:
            stats: The statistics to save.

        Returns:
            The saved statistics.
        """
        pass

    @abstractmethod
    async def get_latest_statistics(self, goal_id: str) -> Optional[SystemStatistics]:
        """Get latest statistics for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            The latest statistics if found, None otherwise.
        """
        pass

    # =========================================================================
    # Context Memory (Checkpoints)
    # =========================================================================

    @abstractmethod
    async def save_checkpoint(self, checkpoint: ContextMemory) -> ContextMemory:
        """Save a workflow checkpoint.

        Used for pause/resume functionality and crash recovery.

        Args:
            checkpoint: The context memory checkpoint to save.

        Returns:
            The saved checkpoint.
        """
        pass

    @abstractmethod
    async def get_latest_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Get the most recent checkpoint for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            The latest checkpoint if found, None otherwise.
        """
        pass

    @abstractmethod
    async def get_all_checkpoints(self, goal_id: str) -> List[ContextMemory]:
        """Get all checkpoints for a research goal (historical).

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            List of checkpoints ordered by creation date (newest first).
        """
        pass

    # =========================================================================
    # Scientist Feedback
    # =========================================================================

    @abstractmethod
    async def add_feedback(self, feedback: ScientistFeedback) -> ScientistFeedback:
        """Store scientist feedback.

        Args:
            feedback: The feedback to store.

        Returns:
            The stored feedback.
        """
        pass

    @abstractmethod
    async def get_feedback_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[ScientistFeedback]:
        """Get all feedback for a specific hypothesis.

        Args:
            hypothesis_id: Unique identifier of the hypothesis.

        Returns:
            List of feedback items.
        """
        pass

    @abstractmethod
    async def get_all_feedback(self, goal_id: str) -> List[ScientistFeedback]:
        """Get all feedback for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.

        Returns:
            List of all feedback ordered by creation date.
        """
        pass

    # =========================================================================
    # Chat Messages
    # =========================================================================

    @abstractmethod
    async def add_chat_message(self, message: ChatMessage) -> ChatMessage:
        """Store a chat message.

        Args:
            message: The message to store.

        Returns:
            The stored message.
        """
        pass

    @abstractmethod
    async def get_chat_history(
        self,
        goal_id: str,
        limit: int = 100
    ) -> List[ChatMessage]:
        """Get chat history for a research goal.

        Args:
            goal_id: Unique identifier of the research goal.
            limit: Maximum number of messages to return.

        Returns:
            List of messages ordered by creation date (oldest first).
        """
        pass

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @abstractmethod
    async def clear_all(self, goal_id: Optional[str] = None) -> None:
        """Clear all stored data.

        Args:
            goal_id: If provided, only clear data for this research goal.
                    If None, clear all data (use with caution).
        """
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, int]:
        """Get storage statistics.

        Returns:
            Dictionary with counts of stored items by type.
        """
        pass

    # =========================================================================
    # Transaction Support
    # =========================================================================

    @abstractmethod
    async def begin_transaction(self) -> Any:
        """Begin a database transaction.

        Returns:
            Transaction context (implementation-specific).
        """
        pass

    @abstractmethod
    async def commit_transaction(self, transaction: Any) -> None:
        """Commit a transaction.

        Args:
            transaction: The transaction context to commit.
        """
        pass

    @abstractmethod
    async def rollback_transaction(self, transaction: Any) -> None:
        """Rollback a transaction.

        Args:
            transaction: The transaction context to rollback.
        """
        pass
