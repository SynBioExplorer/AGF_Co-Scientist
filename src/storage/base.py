"""Abstract base storage interface for AI Co-Scientist system

This module defines the storage interface that all storage implementations
must follow. Enables swapping between InMemoryStorage (development) and
PostgreSQL (production) without changing application code.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import (
    Hypothesis,
    Review,
    TournamentMatch,
    ResearchGoal,
    ContextMemory,
    ProximityGraph,
)


class BaseStorage(ABC):
    """Abstract base class for storage implementations

    All storage backends (in-memory, PostgreSQL, etc.) must implement
    this interface to ensure consistent behavior across the system.

    Methods are synchronous by default. Async implementations can
    override with async versions if needed.
    """

    # =========================================================================
    # Connection Management
    # =========================================================================

    def connect(self) -> None:
        """Establish connection to storage backend

        For in-memory storage, this is a no-op.
        For database storage, this opens the connection.
        """
        pass

    def disconnect(self) -> None:
        """Close connection to storage backend"""
        pass

    # =========================================================================
    # Research Goals
    # =========================================================================

    @abstractmethod
    def add_research_goal(self, goal: ResearchGoal) -> None:
        """Store a research goal

        Args:
            goal: Research goal to store
        """
        pass

    @abstractmethod
    def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve a research goal by ID

        Args:
            goal_id: Unique identifier of the goal

        Returns:
            ResearchGoal if found, None otherwise
        """
        pass

    def get_all_research_goals(self) -> List[ResearchGoal]:
        """Get all research goals

        Returns:
            List of all stored research goals
        """
        return []

    # =========================================================================
    # Hypotheses
    # =========================================================================

    @abstractmethod
    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Store a hypothesis

        Args:
            hypothesis: Hypothesis to store
        """
        pass

    @abstractmethod
    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve a hypothesis by ID

        Args:
            hypothesis_id: Unique identifier of the hypothesis

        Returns:
            Hypothesis if found, None otherwise
        """
        pass

    @abstractmethod
    def update_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Update an existing hypothesis

        Used primarily for Elo rating updates after tournament matches.

        Args:
            hypothesis: Hypothesis with updated fields
        """
        pass

    @abstractmethod
    def get_all_hypotheses(self) -> List[Hypothesis]:
        """Get all stored hypotheses

        Returns:
            List of all hypotheses
        """
        pass

    @abstractmethod
    def get_hypotheses_by_goal(self, goal_id: str) -> List[Hypothesis]:
        """Get all hypotheses for a specific research goal

        Args:
            goal_id: Research goal ID

        Returns:
            List of hypotheses associated with the goal
        """
        pass

    # =========================================================================
    # Reviews
    # =========================================================================

    @abstractmethod
    def add_review(self, review: Review) -> None:
        """Store a review

        Args:
            review: Review to store
        """
        pass

    @abstractmethod
    def get_review(self, review_id: str) -> Optional[Review]:
        """Retrieve a review by ID

        Args:
            review_id: Unique identifier of the review

        Returns:
            Review if found, None otherwise
        """
        pass

    @abstractmethod
    def get_reviews_for_hypothesis(self, hypothesis_id: str) -> List[Review]:
        """Get all reviews for a specific hypothesis

        Args:
            hypothesis_id: Hypothesis ID

        Returns:
            List of reviews for the hypothesis
        """
        pass

    def get_all_reviews(self) -> List[Review]:
        """Get all stored reviews

        Returns:
            List of all reviews
        """
        return []

    # =========================================================================
    # Tournament Matches
    # =========================================================================

    @abstractmethod
    def add_match(self, match: TournamentMatch) -> None:
        """Store a tournament match

        Args:
            match: Tournament match to store
        """
        pass

    @abstractmethod
    def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        """Retrieve a match by ID

        Args:
            match_id: Unique identifier of the match

        Returns:
            TournamentMatch if found, None otherwise
        """
        pass

    @abstractmethod
    def get_all_matches(self, goal_id: Optional[str] = None) -> List[TournamentMatch]:
        """Get all tournament matches

        Args:
            goal_id: Optional filter by research goal ID

        Returns:
            List of all matches (optionally filtered)
        """
        pass

    @abstractmethod
    def get_matches_for_hypothesis(self, hypothesis_id: str) -> List[TournamentMatch]:
        """Get all matches involving a specific hypothesis

        Args:
            hypothesis_id: Hypothesis ID

        Returns:
            List of matches where hypothesis participated
        """
        pass

    # =========================================================================
    # Statistics & Rankings
    # =========================================================================

    @abstractmethod
    def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for a hypothesis

        Args:
            hypothesis_id: Hypothesis ID

        Returns:
            Win rate as float between 0.0 and 1.0
        """
        pass

    @abstractmethod
    def get_top_hypotheses(self, n: int = 10, goal_id: Optional[str] = None) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating

        Args:
            n: Number of hypotheses to return
            goal_id: Optional filter by research goal ID

        Returns:
            List of top hypotheses sorted by Elo rating (descending)
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, int]:
        """Get storage statistics

        Returns:
            Dict with counts: research_goals, hypotheses, reviews, matches
        """
        pass

    # =========================================================================
    # Checkpoint/Resume
    # =========================================================================

    def save_checkpoint(self, context: ContextMemory) -> None:
        """Save a checkpoint (ContextMemory) to storage

        Args:
            context: ContextMemory containing current system state
        """
        pass

    def get_latest_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Get the most recent checkpoint for a research goal

        Args:
            goal_id: Research goal ID

        Returns:
            Most recent ContextMemory, or None if no checkpoint exists
        """
        return None

    def get_all_checkpoints(self, goal_id: str) -> List[ContextMemory]:
        """Get all checkpoints for a research goal

        Args:
            goal_id: Research goal ID

        Returns:
            List of all checkpoints ordered by creation time (oldest first)
        """
        return []

    # =========================================================================
    # Proximity Graph
    # =========================================================================

    def save_proximity_graph(self, graph: ProximityGraph) -> None:
        """Save a proximity graph to storage

        Args:
            graph: ProximityGraph to store
        """
        pass

    def get_proximity_graph(self, goal_id: str) -> Optional[ProximityGraph]:
        """Get the proximity graph for a research goal

        Args:
            goal_id: Research goal ID

        Returns:
            ProximityGraph if found, None otherwise
        """
        return None

    # =========================================================================
    # Safety Reviews (for SafetyAgent integration)
    # =========================================================================

    def save_safety_review(
        self,
        entity_id: str,
        entity_type: str,  # "goal" or "hypothesis"
        assessment: Dict
    ) -> None:
        """Save a safety review assessment

        Args:
            entity_id: ID of the reviewed goal or hypothesis
            entity_type: "goal" or "hypothesis"
            assessment: Safety assessment dict from SafetyAgent
        """
        pass

    def get_safety_review(
        self,
        entity_id: str,
        entity_type: str
    ) -> Optional[Dict]:
        """Get safety review for an entity

        Args:
            entity_id: ID of the goal or hypothesis
            entity_type: "goal" or "hypothesis"

        Returns:
            Safety assessment dict, or None if not reviewed
        """
        return None

    # =========================================================================
    # Utility
    # =========================================================================

    @abstractmethod
    def clear_all(self) -> None:
        """Clear all stored data

        WARNING: This is destructive. Use only for testing.
        """
        pass
