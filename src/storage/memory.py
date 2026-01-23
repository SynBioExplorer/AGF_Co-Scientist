"""In-memory state storage implementing BaseStorage interface

This is a prototype implementation suitable for development and testing.
Production deployments should use PostgreSQL storage (src/storage/postgres.py).
"""

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

from src.storage.base import BaseStorage


class InMemoryStorage(BaseStorage):
    """In-memory storage implementation

    Stores all data in Python dictionaries. Data is lost when the
    process terminates. Suitable for development, testing, and
    short-running workflows.

    For persistent storage, use PostgreSQLStorage instead.
    """

    def __init__(self):
        self.research_goals: Dict[str, ResearchGoal] = {}
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.reviews: Dict[str, Review] = {}
        self.matches: Dict[str, TournamentMatch] = {}
        self.checkpoints: Dict[str, List[ContextMemory]] = {}  # goal_id -> list of checkpoints
        self.proximity_graphs: Dict[str, ProximityGraph] = {}  # goal_id -> graph
        self.safety_reviews: Dict[str, Dict] = {}  # f"{entity_type}_{entity_id}" -> assessment

    # =========================================================================
    # Research Goals
    # =========================================================================

    def add_research_goal(self, goal: ResearchGoal) -> None:
        """Store a research goal"""
        self.research_goals[goal.id] = goal

    def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve a research goal by ID"""
        return self.research_goals.get(goal_id)

    def get_all_research_goals(self) -> List[ResearchGoal]:
        """Get all research goals"""
        return list(self.research_goals.values())

    # =========================================================================
    # Hypotheses
    # =========================================================================

    def add_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Store a hypothesis"""
        self.hypotheses[hypothesis.id] = hypothesis

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve a hypothesis by ID"""
        return self.hypotheses.get(hypothesis_id)

    def update_hypothesis(self, hypothesis: Hypothesis) -> None:
        """Update an existing hypothesis (e.g., after Elo change)"""
        if hypothesis.id in self.hypotheses:
            self.hypotheses[hypothesis.id] = hypothesis

    def get_all_hypotheses(self) -> List[Hypothesis]:
        """Get all hypotheses"""
        return list(self.hypotheses.values())

    def get_hypotheses_by_goal(self, goal_id: str) -> List[Hypothesis]:
        """Get all hypotheses for a specific research goal"""
        return [
            h for h in self.hypotheses.values()
            if h.research_goal_id == goal_id
        ]

    # =========================================================================
    # Reviews
    # =========================================================================

    def add_review(self, review: Review) -> None:
        """Store a review"""
        self.reviews[review.id] = review

    def get_review(self, review_id: str) -> Optional[Review]:
        """Retrieve a review by ID"""
        return self.reviews.get(review_id)

    def get_reviews_for_hypothesis(self, hypothesis_id: str) -> List[Review]:
        """Get all reviews for a specific hypothesis"""
        return [
            r for r in self.reviews.values()
            if r.hypothesis_id == hypothesis_id
        ]

    def get_all_reviews(self) -> List[Review]:
        """Get all stored reviews"""
        return list(self.reviews.values())

    # =========================================================================
    # Tournament Matches
    # =========================================================================

    def add_match(self, match: TournamentMatch) -> None:
        """Store a tournament match"""
        self.matches[match.id] = match

    def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        """Retrieve a match by ID"""
        return self.matches.get(match_id)

    def get_all_matches(self, goal_id: Optional[str] = None) -> List[TournamentMatch]:
        """Get all tournament matches, optionally filtered by goal"""
        all_matches = list(self.matches.values())

        if goal_id is None:
            return all_matches

        # Filter by goal - need to check hypothesis goal_ids
        goal_hypothesis_ids = {
            h.id for h in self.hypotheses.values()
            if h.research_goal_id == goal_id
        }

        return [
            m for m in all_matches
            if m.hypothesis_a_id in goal_hypothesis_ids
            or m.hypothesis_b_id in goal_hypothesis_ids
        ]

    def get_matches_for_hypothesis(self, hypothesis_id: str) -> List[TournamentMatch]:
        """Get all matches involving a specific hypothesis"""
        return [
            m for m in self.matches.values()
            if m.hypothesis_a_id == hypothesis_id or m.hypothesis_b_id == hypothesis_id
        ]

    # =========================================================================
    # Statistics & Rankings
    # =========================================================================

    def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for a hypothesis"""
        matches = self.get_matches_for_hypothesis(hypothesis_id)
        if not matches:
            return 0.0

        wins = sum(1 for m in matches if m.winner_id == hypothesis_id)
        return wins / len(matches)

    def get_top_hypotheses(self, n: int = 10, goal_id: Optional[str] = None) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating"""
        if goal_id:
            hyps = self.get_hypotheses_by_goal(goal_id)
        else:
            hyps = self.get_all_hypotheses()

        return sorted(
            hyps,
            key=lambda h: h.elo_rating or 1200.0,
            reverse=True
        )[:n]

    def get_stats(self) -> Dict[str, int]:
        """Get storage statistics"""
        return {
            "research_goals": len(self.research_goals),
            "hypotheses": len(self.hypotheses),
            "reviews": len(self.reviews),
            "matches": len(self.matches),
            "checkpoints": sum(len(v) for v in self.checkpoints.values()),
            "proximity_graphs": len(self.proximity_graphs),
            "safety_reviews": len(self.safety_reviews),
        }

    # =========================================================================
    # Checkpoint/Resume
    # =========================================================================

    def save_checkpoint(self, context: ContextMemory) -> None:
        """Save a checkpoint (ContextMemory) to storage"""
        goal_id = context.research_goal_id

        if goal_id not in self.checkpoints:
            self.checkpoints[goal_id] = []

        self.checkpoints[goal_id].append(context)

    def get_latest_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Get the most recent checkpoint for a research goal"""
        checkpoints = self.checkpoints.get(goal_id, [])

        if not checkpoints:
            return None

        # Return the most recent (last in list)
        return checkpoints[-1]

    def get_all_checkpoints(self, goal_id: str) -> List[ContextMemory]:
        """Get all checkpoints for a research goal (oldest first)"""
        return self.checkpoints.get(goal_id, [])

    # =========================================================================
    # Proximity Graph
    # =========================================================================

    def save_proximity_graph(self, graph: ProximityGraph) -> None:
        """Save a proximity graph to storage"""
        self.proximity_graphs[graph.research_goal_id] = graph

    def get_proximity_graph(self, goal_id: str) -> Optional[ProximityGraph]:
        """Get the proximity graph for a research goal"""
        return self.proximity_graphs.get(goal_id)

    # =========================================================================
    # Safety Reviews
    # =========================================================================

    def save_safety_review(
        self,
        entity_id: str,
        entity_type: str,
        assessment: Dict
    ) -> None:
        """Save a safety review assessment"""
        key = f"{entity_type}_{entity_id}"
        self.safety_reviews[key] = assessment

    def get_safety_review(
        self,
        entity_id: str,
        entity_type: str
    ) -> Optional[Dict]:
        """Get safety review for an entity"""
        key = f"{entity_type}_{entity_id}"
        return self.safety_reviews.get(key)

    # =========================================================================
    # Utility
    # =========================================================================

    def clear_all(self) -> None:
        """Clear all stored data"""
        self.research_goals.clear()
        self.hypotheses.clear()
        self.reviews.clear()
        self.matches.clear()
        self.checkpoints.clear()
        self.proximity_graphs.clear()
        self.safety_reviews.clear()


# Global storage instance
storage = InMemoryStorage()
