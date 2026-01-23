"""In-memory state storage for Phase 2"""

from typing import Dict, List, Optional
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, Review, TournamentMatch, ResearchGoal


class InMemoryStorage:
    """Simple in-memory storage for hypotheses, reviews, and matches

    This is a prototype implementation for Phase 2.
    Phase 3+ will use PostgreSQL + Redis for persistence.
    """

    def __init__(self):
        self.research_goals: Dict[str, ResearchGoal] = {}
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.reviews: Dict[str, Review] = {}
        self.matches: Dict[str, TournamentMatch] = {}

    # Research Goals
    def add_research_goal(self, goal: ResearchGoal) -> None:
        """Store a research goal"""
        self.research_goals[goal.id] = goal

    def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve a research goal by ID"""
        return self.research_goals.get(goal_id)

    # Hypotheses
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

    # Reviews
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

    # Tournament Matches
    def add_match(self, match: TournamentMatch) -> None:
        """Store a tournament match"""
        self.matches[match.id] = match

    def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        """Retrieve a match by ID"""
        return self.matches.get(match_id)

    def get_all_matches(self) -> List[TournamentMatch]:
        """Get all tournament matches"""
        return list(self.matches.values())

    def get_matches_for_hypothesis(self, hypothesis_id: str) -> List[TournamentMatch]:
        """Get all matches involving a specific hypothesis"""
        return [
            m for m in self.matches.values()
            if m.hypothesis_a_id == hypothesis_id or m.hypothesis_b_id == hypothesis_id
        ]

    # Statistics
    def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for a hypothesis"""
        matches = self.get_matches_for_hypothesis(hypothesis_id)
        if not matches:
            return 0.0

        wins = sum(1 for m in matches if m.winner_id == hypothesis_id)
        return wins / len(matches)

    def get_top_hypotheses(self, n: int = 10) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating"""
        all_hyps = self.get_all_hypotheses()
        return sorted(
            all_hyps,
            key=lambda h: h.elo_rating or 1500.0,
            reverse=True
        )[:n]

    # Clear data (for testing)
    def clear_all(self) -> None:
        """Clear all stored data"""
        self.research_goals.clear()
        self.hypotheses.clear()
        self.reviews.clear()
        self.matches.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get storage statistics"""
        return {
            "research_goals": len(self.research_goals),
            "hypotheses": len(self.hypotheses),
            "reviews": len(self.reviews),
            "matches": len(self.matches)
        }


# Global storage instance for Phase 2
storage = InMemoryStorage()
