"""Elo rating system for hypothesis tournaments"""

from typing import Tuple
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, TournamentMatch


class EloCalculator:
    """Calculate Elo rating changes for hypothesis comparisons"""

    def __init__(self, k_factor: int = 32, initial_rating: float = 1500.0):
        """Initialize Elo calculator

        Args:
            k_factor: Sensitivity of rating changes (default 32)
            initial_rating: Starting rating for new hypotheses (default 1500.0)
        """
        self.k_factor = k_factor
        self.initial_rating = initial_rating

    def calculate_expected_score(
        self,
        rating_a: float,
        rating_b: float
    ) -> Tuple[float, float]:
        """Calculate expected scores for both players

        Args:
            rating_a: Elo rating of player A
            rating_b: Elo rating of player B

        Returns:
            Tuple of (expected_score_a, expected_score_b)
        """
        expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        expected_b = 1 - expected_a
        return expected_a, expected_b

    def calculate_rating_change(
        self,
        winner_rating: float,
        loser_rating: float
    ) -> Tuple[float, float]:
        """Calculate rating changes after a match

        Args:
            winner_rating: Current rating of the winner
            loser_rating: Current rating of the loser

        Returns:
            Tuple of (winner_change, loser_change)
        """
        expected_winner, expected_loser = self.calculate_expected_score(
            winner_rating, loser_rating
        )

        winner_change = self.k_factor * (1 - expected_winner)
        loser_change = self.k_factor * (0 - expected_loser)

        return winner_change, loser_change

    def update_ratings(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis,
        winner_id: str
    ) -> Tuple[float, float]:
        """Update ratings based on match outcome

        Args:
            hypothesis_a: First hypothesis
            hypothesis_b: Second hypothesis
            winner_id: ID of the winning hypothesis

        Returns:
            Tuple of (new_rating_a, new_rating_b)
        """
        rating_a = hypothesis_a.elo_rating or self.initial_rating
        rating_b = hypothesis_b.elo_rating or self.initial_rating

        expected_a, expected_b = self.calculate_expected_score(rating_a, rating_b)

        # Determine actual scores (1 for win, 0 for loss)
        if winner_id == hypothesis_a.id:
            actual_a, actual_b = 1.0, 0.0
        elif winner_id == hypothesis_b.id:
            actual_a, actual_b = 0.0, 1.0
        else:
            raise ValueError(f"Invalid winner_id: {winner_id}")

        # Calculate changes
        change_a = self.k_factor * (actual_a - expected_a)
        change_b = self.k_factor * (actual_b - expected_b)

        # Apply changes
        new_rating_a = rating_a + change_a
        new_rating_b = rating_b + change_b

        return new_rating_a, new_rating_b

    def apply_match_results(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis,
        match: TournamentMatch
    ) -> Tuple[Hypothesis, Hypothesis]:
        """Apply match results and update hypothesis ratings

        Args:
            hypothesis_a: First hypothesis
            hypothesis_b: Second hypothesis
            match: Completed tournament match

        Returns:
            Tuple of updated (hypothesis_a, hypothesis_b)
        """
        # Update ratings
        new_rating_a, new_rating_b = self.update_ratings(
            hypothesis_a,
            hypothesis_b,
            match.winner_id
        )

        # Create updated hypothesis objects
        updated_a = hypothesis_a.model_copy(
            update={"elo_rating": new_rating_a}
        )
        updated_b = hypothesis_b.model_copy(
            update={"elo_rating": new_rating_b}
        )

        return updated_a, updated_b


class TournamentRanker:
    """Manage tournament rankings and match scheduling"""

    def __init__(self, k_factor: int = 32):
        self.elo_calculator = EloCalculator(k_factor=k_factor)

    def rank_hypotheses(
        self,
        hypotheses: list[Hypothesis]
    ) -> list[Hypothesis]:
        """Sort hypotheses by Elo rating (descending)

        Args:
            hypotheses: List of hypotheses to rank

        Returns:
            Sorted list of hypotheses (highest rating first)
        """
        return sorted(
            hypotheses,
            key=lambda h: h.elo_rating or self.elo_calculator.initial_rating,
            reverse=True
        )

    def select_match_pairs(
        self,
        hypotheses: list[Hypothesis],
        top_n: int = 10
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Select hypothesis pairs for tournament matches

        Strategy:
        - Top-ranked hypotheses (top 10) are paired with each other
        - Middle-ranked hypotheses are paired with similar-rated opponents
        - New hypotheses (default rating) are paired with established ones

        Args:
            hypotheses: List of all hypotheses
            top_n: Number of top hypotheses to cross-compare

        Returns:
            List of (hypothesis_a, hypothesis_b) tuples for matches
        """
        ranked = self.rank_hypotheses(hypotheses)

        if len(ranked) < 2:
            return []

        pairs = []

        # Top hypotheses: round-robin
        top_hypotheses = ranked[:top_n]
        if len(top_hypotheses) >= 2:
            for i in range(len(top_hypotheses)):
                for j in range(i + 1, min(i + 3, len(top_hypotheses))):
                    pairs.append((top_hypotheses[i], top_hypotheses[j]))

        # Middle hypotheses: pair with similar ratings
        middle_hypotheses = ranked[top_n:]
        for i in range(0, len(middle_hypotheses) - 1, 2):
            pairs.append((middle_hypotheses[i], middle_hypotheses[i + 1]))

        return pairs

    def should_use_multi_turn(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis,
        top_n: int = 10,
        all_hypotheses: list[Hypothesis] = None
    ) -> bool:
        """Determine if match should use multi-turn debate

        Multi-turn debates are used for:
        - Matches between top-ranked hypotheses
        - Close rating comparisons (within 100 points)

        Args:
            hypothesis_a: First hypothesis
            hypothesis_b: Second hypothesis
            top_n: Number of top hypotheses
            all_hypotheses: Full list of hypotheses for ranking

        Returns:
            True if multi-turn debate should be used
        """
        # Check if both are in top N
        if all_hypotheses:
            ranked = self.rank_hypotheses(all_hypotheses)
            top_ids = {h.id for h in ranked[:top_n]}
            if hypothesis_a.id in top_ids and hypothesis_b.id in top_ids:
                return True

        # Check if ratings are close
        rating_a = hypothesis_a.elo_rating or self.elo_calculator.initial_rating
        rating_b = hypothesis_b.elo_rating or self.elo_calculator.initial_rating
        rating_diff = abs(rating_a - rating_b)

        return rating_diff < 100  # Close match threshold
