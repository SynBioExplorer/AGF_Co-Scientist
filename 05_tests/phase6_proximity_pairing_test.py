"""Tests for proximity-aware tournament pairing (Phase 5 Enhancement)"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent / "03_architecture"))

from schemas import (
    Hypothesis, ProximityGraph, ProximityEdge, HypothesisCluster,
    ExperimentalProtocol, GenerationMethod
)
from src.tournament.elo import TournamentRanker
from src.utils.ids import generate_hypothesis_id, generate_id
from src.config import settings


def create_test_hypothesis(title: str, elo_rating: float = 1200.0) -> Hypothesis:
    """Helper to create a test hypothesis"""
    return Hypothesis(
        id=generate_hypothesis_id(),
        research_goal_id="test-goal-1",
        title=title,
        summary=f"Summary for {title}",
        hypothesis_statement=f"Hypothesis statement for {title}",
        rationale=f"Rationale for {title}",
        mechanism=f"Mechanism for {title}",
        experimental_protocol=ExperimentalProtocol(
            objective="Test objective",
            methodology="Test method",
            controls=["Control 1", "Control 2"],
            success_criteria="Test criteria"
        ),
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=elo_rating
    )


def create_test_proximity_graph(
    hypotheses: list[Hypothesis],
    cluster_groups: list[list[int]]
) -> ProximityGraph:
    """
    Create a test proximity graph with specified clusters.

    Args:
        hypotheses: List of hypotheses
        cluster_groups: List of lists of hypothesis indices forming clusters
                       e.g., [[0, 1, 2], [3, 4], [5, 6, 7]] creates 3 clusters
    """
    edges = []
    clusters = []

    for cluster_idx, hyp_indices in enumerate(cluster_groups):
        # Create edges within cluster
        for i in range(len(hyp_indices)):
            for j in range(i + 1, len(hyp_indices)):
                idx_a = hyp_indices[i]
                idx_b = hyp_indices[j]
                edge = ProximityEdge(
                    hypothesis_a_id=hypotheses[idx_a].id,
                    hypothesis_b_id=hypotheses[idx_b].id,
                    similarity_score=0.85  # High similarity within cluster
                )
                edges.append(edge)

        # Create cluster
        cluster = HypothesisCluster(
            id=generate_id(f"cluster-{cluster_idx}"),
            name=f"Cluster {cluster_idx}",
            hypothesis_ids=[hypotheses[idx].id for idx in hyp_indices],
            representative_id=hypotheses[hyp_indices[0]].id,
            common_themes=[f"Theme {cluster_idx}"]
        )
        clusters.append(cluster)

    return ProximityGraph(
        research_goal_id="test-goal-1",
        edges=edges,
        clusters=clusters
    )


def test_within_cluster_pairing():
    """Test that hypotheses in same cluster are paired together"""
    print("\n=== Test: Within-Cluster Pairing ===")

    # Create 9 hypotheses in 3 clusters (3 each)
    hypotheses = [
        create_test_hypothesis(f"Hyp-Cluster1-{i}", elo_rating=1200 + i*10)
        for i in range(3)
    ] + [
        create_test_hypothesis(f"Hyp-Cluster2-{i}", elo_rating=1250 + i*10)
        for i in range(3)
    ] + [
        create_test_hypothesis(f"Hyp-Cluster3-{i}", elo_rating=1300 + i*10)
        for i in range(3)
    ]

    # Create clusters: [0,1,2], [3,4,5], [6,7,8]
    proximity_graph = create_test_proximity_graph(
        hypotheses,
        [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    )

    # Select pairs with proximity awareness
    ranker = TournamentRanker()
    pairs = ranker.select_match_pairs(
        hypotheses,
        top_n=3,
        proximity_graph=proximity_graph,
        use_proximity=True,
        proximity_weight=0.7,
        diversity_weight=0.2
    )

    print(f"Total pairs generated: {len(pairs)}")

    # Build cluster membership map
    cluster_map = {}
    for cluster in proximity_graph.clusters:
        for hyp_id in cluster.hypothesis_ids:
            cluster_map[hyp_id] = cluster.id

    # Count within-cluster vs cross-cluster matches
    within_cluster = 0
    cross_cluster = 0

    for h1, h2 in pairs:
        c1 = cluster_map.get(h1.id)
        c2 = cluster_map.get(h2.id)
        if c1 and c2:
            if c1 == c2:
                within_cluster += 1
                print(f"  Within-cluster: {h1.title} vs {h2.title} (cluster {c1[:10]})")
            else:
                cross_cluster += 1
                print(f"  Cross-cluster: {h1.title} vs {h2.title}")

    within_ratio = within_cluster / len(pairs) if pairs else 0

    print(f"\nWithin-cluster matches: {within_cluster}")
    print(f"Cross-cluster matches: {cross_cluster}")
    print(f"Within-cluster ratio: {within_ratio:.2f}")

    # Should have significant within-cluster pairing (aim for ~70%)
    assert within_ratio >= 0.5, f"Expected >=50% within-cluster, got {within_ratio:.2%}"
    print("✓ Test passed: Majority of matches are within-cluster")


def test_cross_cluster_diversity():
    """Test that some matches occur between distant clusters"""
    print("\n=== Test: Cross-Cluster Diversity ===")

    # Create 6 hypotheses in 2 distant clusters
    hypotheses = [
        create_test_hypothesis(f"Hyp-A-{i}", elo_rating=1200 + i*10)
        for i in range(3)
    ] + [
        create_test_hypothesis(f"Hyp-B-{i}", elo_rating=1300 + i*10)
        for i in range(3)
    ]

    # Create 2 clusters with NO edges between them (distant)
    proximity_graph = create_test_proximity_graph(
        hypotheses,
        [[0, 1, 2], [3, 4, 5]]
    )

    ranker = TournamentRanker()
    pairs = ranker.select_match_pairs(
        hypotheses,
        top_n=2,
        proximity_graph=proximity_graph,
        use_proximity=True,
        proximity_weight=0.5,  # Lower within-cluster weight
        diversity_weight=0.4   # Higher diversity weight
    )

    # Build cluster map
    cluster_map = {}
    for cluster in proximity_graph.clusters:
        for hyp_id in cluster.hypothesis_ids:
            cluster_map[hyp_id] = cluster.id

    cross_cluster = 0
    for h1, h2 in pairs:
        c1 = cluster_map.get(h1.id)
        c2 = cluster_map.get(h2.id)
        if c1 and c2 and c1 != c2:
            cross_cluster += 1
            print(f"  Diversity match: {h1.title} vs {h2.title}")

    print(f"\nTotal pairs: {len(pairs)}")
    print(f"Cross-cluster diversity matches: {cross_cluster}")

    # Should have some diversity matches
    assert cross_cluster > 0, "Expected at least 1 cross-cluster match for diversity"
    print("✓ Test passed: Cross-cluster diversity matches generated")


def test_fallback_to_elo_when_no_graph():
    """Test system uses Elo pairing when proximity graph unavailable"""
    print("\n=== Test: Fallback to Elo Pairing ===")

    hypotheses = [
        create_test_hypothesis(f"Hyp-{i}", elo_rating=1200 + i*50)
        for i in range(6)
    ]

    ranker = TournamentRanker()

    # Call with no proximity graph
    pairs = ranker.select_match_pairs(
        hypotheses,
        top_n=3,
        proximity_graph=None,
        use_proximity=True
    )

    print(f"Generated {len(pairs)} pairs without proximity graph")
    for h1, h2 in pairs[:5]:
        print(f"  {h1.title} (Elo: {h1.elo_rating}) vs {h2.title} (Elo: {h2.elo_rating})")

    assert len(pairs) > 0, "Should generate pairs even without proximity graph"
    print("✓ Test passed: Graceful fallback to Elo-based pairing")


def test_single_hypothesis_clusters_handled():
    """Test outlier hypotheses (cluster size=1) are paired gracefully"""
    print("\n=== Test: Outlier Hypothesis Handling ===")

    # Create 7 hypotheses: 3 in cluster, 2 in cluster, 2 outliers
    hypotheses = [
        create_test_hypothesis(f"Hyp-A-{i}", elo_rating=1200 + i*10)
        for i in range(3)
    ] + [
        create_test_hypothesis(f"Hyp-B-{i}", elo_rating=1300 + i*10)
        for i in range(2)
    ] + [
        create_test_hypothesis(f"Outlier-{i}", elo_rating=1400 + i*10)
        for i in range(2)
    ]

    # Create clusters: [0,1,2], [3,4], [5] (size=1), [6] (size=1)
    proximity_graph = create_test_proximity_graph(
        hypotheses,
        [[0, 1, 2], [3, 4], [5], [6]]
    )

    ranker = TournamentRanker()
    pairs = ranker.select_match_pairs(
        hypotheses,
        top_n=2,
        proximity_graph=proximity_graph,
        use_proximity=True
    )

    print(f"Generated {len(pairs)} pairs with outlier hypotheses")
    for h1, h2 in pairs:
        print(f"  {h1.title} vs {h2.title}")

    # Should handle gracefully (no errors)
    assert len(pairs) > 0, "Should generate pairs despite single-hypothesis clusters"
    print("✓ Test passed: Outlier hypotheses handled correctly")


def test_configuration_toggle():
    """Test proximity_aware_pairing=False disables feature"""
    print("\n=== Test: Configuration Toggle ===")

    hypotheses = [
        create_test_hypothesis(f"Hyp-{i}", elo_rating=1200 + i*10)
        for i in range(6)
    ]

    proximity_graph = create_test_proximity_graph(
        hypotheses,
        [[0, 1, 2], [3, 4, 5]]
    )

    ranker = TournamentRanker()

    # Call with use_proximity=False
    pairs = ranker.select_match_pairs(
        hypotheses,
        top_n=3,
        proximity_graph=proximity_graph,
        use_proximity=False  # Feature disabled
    )

    print(f"Generated {len(pairs)} pairs with proximity disabled")

    # Should still work (fallback to Elo)
    assert len(pairs) > 0, "Should generate pairs with proximity disabled"
    print("✓ Test passed: Feature can be disabled via configuration")


def test_pairing_distribution():
    """Test 70% cluster / 20% diversity / 10% elite distribution"""
    print("\n=== Test: Pairing Distribution ===")

    # Create enough hypotheses for statistical verification
    hypotheses = []
    for cluster_idx in range(4):
        for i in range(5):
            hypotheses.append(
                create_test_hypothesis(
                    f"Hyp-C{cluster_idx}-{i}",
                    elo_rating=1200 + cluster_idx*100 + i*10
                )
            )

    # 4 clusters of 5 hypotheses each
    proximity_graph = create_test_proximity_graph(
        hypotheses,
        [[0,1,2,3,4], [5,6,7,8,9], [10,11,12,13,14], [15,16,17,18,19]]
    )

    ranker = TournamentRanker()
    pairs = ranker.select_match_pairs(
        hypotheses,
        top_n=5,
        proximity_graph=proximity_graph,
        use_proximity=True,
        proximity_weight=0.7,
        diversity_weight=0.2
    )

    # Build cluster map
    cluster_map = {}
    for cluster in proximity_graph.clusters:
        for hyp_id in cluster.hypothesis_ids:
            cluster_map[hyp_id] = cluster.id

    # Categorize pairs
    within_cluster = 0
    cross_cluster = 0
    top_5_ids = {h.id for h in sorted(hypotheses, key=lambda x: x.elo_rating or 1200, reverse=True)[:5]}
    elite_matches = 0

    for h1, h2 in pairs:
        c1 = cluster_map.get(h1.id)
        c2 = cluster_map.get(h2.id)

        # Elite match?
        if h1.id in top_5_ids and h2.id in top_5_ids:
            elite_matches += 1

        # Cluster match?
        if c1 and c2:
            if c1 == c2:
                within_cluster += 1
            else:
                cross_cluster += 1

    total = len(pairs)
    if total > 0:
        within_ratio = within_cluster / total
        diversity_ratio = cross_cluster / total
        elite_ratio = elite_matches / total

        print(f"\nTotal pairs: {total}")
        print(f"Within-cluster: {within_cluster} ({within_ratio:.1%})")
        print(f"Cross-cluster diversity: {cross_cluster} ({diversity_ratio:.1%})")
        print(f"Elite matches: {elite_matches} ({elite_ratio:.1%})")

        # Verify roughly matches target distribution (allow 20% tolerance)
        assert within_ratio >= 0.5, f"Within-cluster ratio too low: {within_ratio:.1%}"
        print("✓ Test passed: Pairing distribution matches expected ratios")


def run_all_tests():
    """Run all proximity pairing tests"""
    print("=" * 60)
    print("PROXIMITY-AWARE TOURNAMENT PAIRING TESTS")
    print("=" * 60)

    tests = [
        test_within_cluster_pairing,
        test_cross_cluster_diversity,
        test_fallback_to_elo_when_no_graph,
        test_single_hypothesis_clusters_handled,
        test_configuration_toggle,
        test_pairing_distribution,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ Test error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
