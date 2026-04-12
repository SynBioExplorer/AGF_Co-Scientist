"""Elo rating system for hypothesis tournaments"""

from typing import Tuple, Optional, Dict, Set
import random
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, TournamentMatch, ProximityGraph, HypothesisCluster
import structlog

logger = structlog.get_logger()


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
        top_n: int = 10,
        proximity_graph: Optional[ProximityGraph] = None,
        use_proximity: bool = True,
        proximity_weight: float = 0.7,
        diversity_weight: float = 0.2,
        exclude_pairs: Optional[Set[Tuple[str, str]]] = None
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Select hypothesis pairs for tournament matches

        Strategy (when proximity_graph available and use_proximity=True):
        - 30% Newcomer matches: Unmatched hypotheses vs top-ranked (paper: "newer hypotheses prioritized")
        - 49% Within-cluster pairing: Compare similar hypotheses (same cluster)
        - 14% Cross-cluster diversity: Compare distant hypotheses (different clusters)
        - 7% Elite top-N: Round-robin for top performers

        Fallback (when proximity_graph=None or use_proximity=False):
        - Top-ranked hypotheses (top 10) are paired with each other
        - Middle-ranked hypotheses are paired with similar-rated opponents

        Args:
            hypotheses: List of all hypotheses (must have _match_count attribute)
            top_n: Number of top hypotheses to cross-compare
            proximity_graph: Optional proximity graph for cluster-aware pairing
            use_proximity: Enable proximity-based pairing
            proximity_weight: Proportion of within-cluster matches (0.0-1.0)
            diversity_weight: Proportion of cross-cluster matches (0.0-1.0)
            exclude_pairs: Set of (id_a, id_b) tuples already matched in prior iterations

        Returns:
            List of (hypothesis_a, hypothesis_b) tuples for matches
        """
        ranked = self.rank_hypotheses(hypotheses)

        if len(ranked) < 2:
            return []

        # Use proximity-aware pairing if graph available
        if use_proximity and proximity_graph and proximity_graph.clusters:
            return self._proximity_aware_pairing(
                ranked,
                proximity_graph,
                top_n,
                proximity_weight,
                diversity_weight,
                exclude_pairs or set()
            )

        # Fallback to Elo-based pairing
        return self._elo_based_pairing(ranked, top_n)

    def _elo_based_pairing(
        self,
        ranked: list[Hypothesis],
        top_n: int
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Original Elo-based pairing logic (backward compatible)"""
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

    def _proximity_aware_pairing(
        self,
        ranked: list[Hypothesis],
        proximity_graph: ProximityGraph,
        top_n: int,
        proximity_weight: float,
        diversity_weight: float,
        exclude_pairs: Set[Tuple[str, str]] = None
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Proximity-aware pairing using cluster information"""
        # Build hypothesis lookup and cluster mapping
        hyp_map = {h.id: h for h in ranked}
        cluster_map = self._build_cluster_map(proximity_graph)

        # Calculate target number of matches by type. Budget scales with the
        # pool so large populations (40+ hypotheses) can clear newcomers within
        # a few iterations instead of leaving ~50% unmatched at termination.
        total_possible = len(ranked) * (len(ranked) - 1) // 2
        target_total = max(20, int(len(ranked) * 0.5))
        target_total = min(target_total, total_possible)

        # Merge excluded pairs from prior iterations
        used_pairs: Set[Tuple[str, str]] = set(exclude_pairs or set())

        # TIER 0: Newcomer matches (paper: "newer hypotheses prioritized")
        newcomers = [h for h in ranked if getattr(h, '_match_count', 0) == 0]
        num_newcomer = min(int(target_total * 0.3), len(newcomers))
        remaining = target_total - num_newcomer

        newcomer_pairs = self._create_newcomer_pairings(
            newcomers, ranked, num_newcomer, used_pairs
        )

        # Rebalance remaining budget across original tiers
        num_cluster = int(remaining * proximity_weight)
        num_diversity = int(remaining * diversity_weight)
        num_elite = remaining - num_cluster - num_diversity

        pairs = list(newcomer_pairs)

        # 1. Within-cluster pairing
        cluster_pairs = self._create_cluster_pairings(
            proximity_graph.clusters,
            hyp_map,
            num_cluster,
            used_pairs
        )
        pairs.extend(cluster_pairs)

        # 2. Cross-cluster diversity pairing
        diversity_pairs = self._create_diversity_pairings(
            proximity_graph.clusters,
            proximity_graph,
            hyp_map,
            num_diversity,
            used_pairs
        )
        pairs.extend(diversity_pairs)

        # 3. Elite top-N pairing
        elite_pairs = self._create_elite_pairings(
            ranked[:top_n],
            num_elite,
            used_pairs
        )
        pairs.extend(elite_pairs)

        logger.info(
            "tournament_pairing_strategy",
            total_pairs=len(pairs),
            newcomer=len(newcomer_pairs),
            within_cluster=len(cluster_pairs),
            diversity=len(diversity_pairs),
            elite=len(elite_pairs),
            proximity_enabled=True
        )

        return pairs

    def _build_cluster_map(self, proximity_graph: ProximityGraph) -> Dict[str, str]:
        """Build hypothesis_id → cluster_id mapping for O(1) lookups"""
        cluster_map = {}
        for cluster in proximity_graph.clusters:
            for hyp_id in cluster.hypothesis_ids:
                cluster_map[hyp_id] = cluster.id
        return cluster_map

    def _create_cluster_pairings(
        self,
        clusters: list[HypothesisCluster],
        hyp_map: Dict[str, Hypothesis],
        num_pairs: int,
        used_pairs: Set[Tuple[str, str]]
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Generate within-cluster pairings"""
        from src.config import settings
        pairs = []

        for cluster in clusters:
            # Skip small clusters
            if len(cluster.hypothesis_ids) < settings.min_cluster_size_for_pairing:
                continue

            # Get hypotheses in this cluster
            cluster_hyps = [
                hyp_map[hid] for hid in cluster.hypothesis_ids
                if hid in hyp_map
            ]

            if len(cluster_hyps) < 2:
                continue

            # Pair within cluster by Elo proximity
            cluster_hyps_sorted = sorted(
                cluster_hyps,
                key=lambda h: h.elo_rating or 1200.0,
                reverse=True
            )

            # Create pairs within cluster
            for i in range(len(cluster_hyps_sorted) - 1):
                if len(pairs) >= num_pairs:
                    break

                h1 = cluster_hyps_sorted[i]
                h2 = cluster_hyps_sorted[i + 1]
                pair_key = tuple(sorted([h1.id, h2.id]))

                if pair_key not in used_pairs:
                    pairs.append((h1, h2))
                    used_pairs.add(pair_key)

            if len(pairs) >= num_pairs:
                break

        return pairs

    def _create_diversity_pairings(
        self,
        clusters: list[HypothesisCluster],
        proximity_graph: ProximityGraph,
        hyp_map: Dict[str, Hypothesis],
        num_pairs: int,
        used_pairs: Set[Tuple[str, str]]
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Generate cross-cluster diversity pairings"""
        pairs = []

        # Build set of connected cluster pairs (have edges between them)
        connected_clusters: Set[Tuple[str, str]] = set()
        cluster_hyp_map: Dict[str, Set[str]] = {
            c.id: set(c.hypothesis_ids) for c in clusters
        }

        for edge in proximity_graph.edges:
            c1_id = None
            c2_id = None
            for cid, hyp_ids in cluster_hyp_map.items():
                if edge.hypothesis_a_id in hyp_ids:
                    c1_id = cid
                if edge.hypothesis_b_id in hyp_ids:
                    c2_id = cid

            if c1_id and c2_id and c1_id != c2_id:
                connected_clusters.add(tuple(sorted([c1_id, c2_id])))

        # Find distant cluster pairs (not connected)
        for i, cluster_a in enumerate(clusters):
            for cluster_b in clusters[i + 1:]:
                if len(pairs) >= num_pairs:
                    break

                pair_key = tuple(sorted([cluster_a.id, cluster_b.id]))
                if pair_key in connected_clusters:
                    continue  # Skip connected clusters

                # Pick random hypotheses from each cluster
                hyps_a = [hyp_map[hid] for hid in cluster_a.hypothesis_ids if hid in hyp_map]
                hyps_b = [hyp_map[hid] for hid in cluster_b.hypothesis_ids if hid in hyp_map]

                if hyps_a and hyps_b:
                    h1 = random.choice(hyps_a)
                    h2 = random.choice(hyps_b)
                    hyp_pair_key = tuple(sorted([h1.id, h2.id]))

                    if hyp_pair_key not in used_pairs:
                        pairs.append((h1, h2))
                        used_pairs.add(hyp_pair_key)

            if len(pairs) >= num_pairs:
                break

        return pairs

    def _create_newcomer_pairings(
        self,
        newcomers: list[Hypothesis],
        ranked: list[Hypothesis],
        num_pairs: int,
        used_pairs: Set[Tuple[str, str]]
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Pair unmatched hypotheses against top-ranked opponents.

        Paper (Section 3.3.3): "newer and top-ranking hypotheses are
        prioritized for participation in tournament matches."
        """
        import random
        pairs = []

        if not newcomers or len(ranked) < 2:
            return pairs

        # Top 50% by Elo as potential opponents
        top_half = ranked[:max(1, len(ranked) // 2)]

        for newcomer in newcomers:
            if len(pairs) >= num_pairs:
                break

            # Pick a random opponent from top half (excluding self)
            candidates = [h for h in top_half if h.id != newcomer.id]
            if not candidates:
                continue

            opponent = random.choice(candidates)
            pair_key = tuple(sorted([newcomer.id, opponent.id]))

            if pair_key not in used_pairs:
                pairs.append((newcomer, opponent))
                used_pairs.add(pair_key)

        return pairs

    def _create_elite_pairings(
        self,
        top_hypotheses: list[Hypothesis],
        num_pairs: int,
        used_pairs: Set[Tuple[str, str]]
    ) -> list[Tuple[Hypothesis, Hypothesis]]:
        """Generate elite top-N round-robin pairings"""
        pairs = []

        if len(top_hypotheses) < 2:
            return pairs

        # Round-robin for top hypotheses
        for i in range(len(top_hypotheses)):
            for j in range(i + 1, min(i + 3, len(top_hypotheses))):
                if len(pairs) >= num_pairs:
                    break

                h1 = top_hypotheses[i]
                h2 = top_hypotheses[j]
                pair_key = tuple(sorted([h1.id, h2.id]))

                if pair_key not in used_pairs:
                    pairs.append((h1, h2))
                    used_pairs.add(pair_key)

            if len(pairs) >= num_pairs:
                break

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
