"""
Unit tests for diversity sampling UX enhancement (Phase 6B).

Tests the cluster-aware diversity sampling feature that returns
representative hypotheses from each cluster for better user experience.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_architecture"))

from src.storage.async_adapter import async_storage
from src.utils.ids import generate_hypothesis_id, generate_id
from schemas import (
    Hypothesis, ResearchGoal, ProximityGraph, HypothesisCluster,
    ExperimentalProtocol, GenerationMethod
)


def create_test_hypothesis(
    title: str,
    elo_rating: float,
    cluster_label: str = "default"
) -> Hypothesis:
    """Helper to create test hypothesis."""
    return Hypothesis(
        id=generate_hypothesis_id(),
        research_goal_id="test-goal-1",
        title=title,
        summary=f"Summary for {title}",
        hypothesis_statement=f"Statement for {title}",
        rationale=f"Rationale for {title}",
        mechanism=f"Mechanism for {title}",
        experimental_protocol=ExperimentalProtocol(
            objective="Test objective",
            methodology="Test methodology",
            controls=["Control 1", "Control 2"],
            success_criteria="Test success criteria"
        ),
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=elo_rating,
        created_at=datetime.now()
    )


@pytest.mark.asyncio
async def test_diverse_selection_from_clusters():
    """Test that diverse selection returns one hypothesis per cluster."""
    print("\n" + "=" * 70)
    print("TEST 1: Diverse Selection from Clusters")
    print("=" * 70)

    # Create 3 clusters with 3 hypotheses each
    goal_id = generate_id("goal")

    # Cluster 1: CRISPR approaches (Elo: 1500, 1450, 1400)
    crispr_hyps = [
        create_test_hypothesis("CRISPR Base Editing", 1500, "crispr"),
        create_test_hypothesis("CRISPR Prime Editing", 1450, "crispr"),
        create_test_hypothesis("CRISPR Cas9 Classic", 1400, "crispr")
    ]

    # Cluster 2: Drug screening (Elo: 1480, 1420, 1380)
    drug_hyps = [
        create_test_hypothesis("High-throughput Drug Screen", 1480, "drug"),
        create_test_hypothesis("Targeted Drug Panel", 1420, "drug"),
        create_test_hypothesis("Phenotypic Drug Screen", 1380, "drug")
    ]

    # Cluster 3: Genetic engineering (Elo: 1460, 1410, 1390)
    genetic_hyps = [
        create_test_hypothesis("Synthetic Biology Circuit", 1460, "genetic"),
        create_test_hypothesis("Gene Drive System", 1410, "genetic"),
        create_test_hypothesis("Metabolic Engineering", 1390, "genetic")
    ]

    all_hypotheses = crispr_hyps + drug_hyps + genetic_hyps

    # Create proximity graph with 3 clusters
    proximity_graph = ProximityGraph(
        research_goal_id=goal_id,
        edges=[],
        clusters=[
            HypothesisCluster(
                id="cluster-crispr",
                name="CRISPR Approaches",
                hypothesis_ids=[h.id for h in crispr_hyps]
            ),
            HypothesisCluster(
                id="cluster-drug",
                name="Drug Screening",
                hypothesis_ids=[h.id for h in drug_hyps]
            ),
            HypothesisCluster(
                id="cluster-genetic",
                name="Genetic Engineering",
                hypothesis_ids=[h.id for h in genetic_hyps]
            )
        ]
    )

    # Save to storage
    for hyp in all_hypotheses:
        hyp.research_goal_id = goal_id
        await async_storage.add_hypothesis(hyp)

    await async_storage.save_proximity_graph(proximity_graph)

    # Get diverse selection (n=3)
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=3,
        min_elo_rating=1200.0,
        cluster_balance=True
    )

    # Assertions
    assert len(diverse) == 3, f"Should return exactly 3 hypotheses, got {len(diverse)}"

    # Should have one from each cluster (top-rated)
    diverse_titles = {h.title for h in diverse}
    assert "CRISPR Base Editing" in diverse_titles, "Missing top from CRISPR cluster"
    assert "High-throughput Drug Screen" in diverse_titles, "Missing top from drug cluster"
    assert "Synthetic Biology Circuit" in diverse_titles, "Missing top from genetic cluster"

    # Should be sorted by Elo
    assert diverse[0].elo_rating == 1500, "First should be CRISPR Base Editing (1500)"
    assert diverse[1].elo_rating == 1480, "Second should be High-throughput Drug Screen (1480)"
    assert diverse[2].elo_rating == 1460, "Third should be Synthetic Biology Circuit (1460)"

    print("✓ Returns exactly 3 hypotheses")
    print("✓ One hypothesis per cluster (top-rated)")
    print("✓ Sorted by Elo rating (descending)")
    print("✓ Test passed: Diverse selection from clusters\n")


@pytest.mark.asyncio
async def test_fallback_to_elo_when_no_proximity_graph():
    """Test that system falls back to Elo sorting when no proximity graph exists."""
    print("=" * 70)
    print("TEST 2: Fallback to Elo when No Proximity Graph")
    print("=" * 70)

    goal_id = generate_id("goal")

    # Create hypotheses without proximity graph
    hypotheses = [
        create_test_hypothesis("Hypothesis A", 1600),
        create_test_hypothesis("Hypothesis B", 1500),
        create_test_hypothesis("Hypothesis C", 1400),
        create_test_hypothesis("Hypothesis D", 1300),
        create_test_hypothesis("Hypothesis E", 1200)
    ]

    for hyp in hypotheses:
        hyp.research_goal_id = goal_id
        await async_storage.add_hypothesis(hyp)

    # Get diverse selection (should fallback to Elo)
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=3,
        min_elo_rating=1200.0
    )

    # Should return top 3 by Elo
    assert len(diverse) == 3, f"Should return 3 hypotheses, got {len(diverse)}"
    assert diverse[0].title == "Hypothesis A", "First should be Hypothesis A"
    assert diverse[1].title == "Hypothesis B", "Second should be Hypothesis B"
    assert diverse[2].title == "Hypothesis C", "Third should be Hypothesis C"

    print("✓ Returns top 3 by Elo when no proximity graph")
    print("✓ Graceful fallback behavior works")
    print("✓ Test passed: Fallback to Elo sorting\n")


@pytest.mark.asyncio
async def test_min_elo_filter():
    """Test that min_elo_rating filter works correctly."""
    print("=" * 70)
    print("TEST 3: Minimum Elo Filter")
    print("=" * 70)

    goal_id = generate_id("goal")

    # Create hypotheses with varying Elo
    hypotheses = [
        create_test_hypothesis("High Elo Hyp", 1800),
        create_test_hypothesis("Medium Elo Hyp", 1400),
        create_test_hypothesis("Low Elo Hyp", 1100)
    ]

    for hyp in hypotheses:
        hyp.research_goal_id = goal_id
        await async_storage.add_hypothesis(hyp)

    # Get diverse selection with min_elo=1200
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=10,
        min_elo_rating=1200.0
    )

    # Should exclude low Elo hypothesis
    assert len(diverse) == 2, f"Should return 2 hypotheses, got {len(diverse)}"
    diverse_titles = {h.title for h in diverse}
    assert "High Elo Hyp" in diverse_titles, "Should include high Elo"
    assert "Medium Elo Hyp" in diverse_titles, "Should include medium Elo"
    assert "Low Elo Hyp" not in diverse_titles, "Should exclude low Elo (< 1200)"

    print("✓ Filters out hypotheses below min_elo threshold")
    print("✓ Includes hypotheses above threshold")
    print("✓ Test passed: Min Elo filter\n")


@pytest.mark.asyncio
async def test_fewer_clusters_than_requested_n():
    """Test behavior when there are fewer clusters than requested n."""
    print("=" * 70)
    print("TEST 4: Fewer Clusters than Requested N")
    print("=" * 70)

    goal_id = generate_id("goal")

    # Create 2 clusters with 3 hypotheses each, but request n=5
    cluster1_hyps = [
        create_test_hypothesis("C1-Hyp1", 1600),
        create_test_hypothesis("C1-Hyp2", 1550),
        create_test_hypothesis("C1-Hyp3", 1500)
    ]

    cluster2_hyps = [
        create_test_hypothesis("C2-Hyp1", 1580),
        create_test_hypothesis("C2-Hyp2", 1530),
        create_test_hypothesis("C2-Hyp3", 1480)
    ]

    all_hypotheses = cluster1_hyps + cluster2_hyps

    # Create proximity graph with 2 clusters
    proximity_graph = ProximityGraph(
        research_goal_id=goal_id,
        edges=[],
        clusters=[
            HypothesisCluster(
                id="cluster-1",
                name="Cluster 1",
                hypothesis_ids=[h.id for h in cluster1_hyps]
            ),
            HypothesisCluster(
                id="cluster-2",
                name="Cluster 2",
                hypothesis_ids=[h.id for h in cluster2_hyps]
            )
        ]
    )

    # Save to storage
    for hyp in all_hypotheses:
        hyp.research_goal_id = goal_id
        await async_storage.add_hypothesis(hyp)

    await async_storage.save_proximity_graph(proximity_graph)

    # Request n=5 (more than 2 clusters)
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=5,
        min_elo_rating=1200.0,
        cluster_balance=True
    )

    # Should return 5 hypotheses: 1 per cluster (2) + 3 more by Elo
    assert len(diverse) == 5, f"Should return 5 hypotheses, got {len(diverse)}"

    # Top 2 should be cluster representatives
    diverse_titles = [h.title for h in diverse]
    assert "C1-Hyp1" in diverse_titles, "Should include top from cluster 1"
    assert "C2-Hyp1" in diverse_titles, "Should include top from cluster 2"

    # Should be sorted by Elo
    assert diverse[0].elo_rating == 1600, "First should be highest Elo"

    print("✓ Returns cluster representatives first")
    print("✓ Fills remaining slots with top Elo hypotheses")
    print("✓ Sorted by Elo rating")
    print("✓ Test passed: Fewer clusters than requested N\n")


@pytest.mark.asyncio
async def test_more_clusters_than_requested_n():
    """Test behavior when there are more clusters than requested n."""
    print("=" * 70)
    print("TEST 5: More Clusters than Requested N")
    print("=" * 70)

    goal_id = generate_id("goal")

    # Create 5 clusters with 1 hypothesis each, but request n=3
    cluster_hyps = [
        create_test_hypothesis("Cluster1-Top", 1600),
        create_test_hypothesis("Cluster2-Top", 1550),
        create_test_hypothesis("Cluster3-Top", 1500),
        create_test_hypothesis("Cluster4-Top", 1450),
        create_test_hypothesis("Cluster5-Top", 1400)
    ]

    # Create proximity graph with 5 clusters
    proximity_graph = ProximityGraph(
        research_goal_id=goal_id,
        edges=[],
        clusters=[
            HypothesisCluster(
                id=f"cluster-{i}",
                name=f"Cluster {i+1}",
                hypothesis_ids=[cluster_hyps[i].id]
            )
            for i in range(5)
        ]
    )

    # Save to storage
    for hyp in cluster_hyps:
        hyp.research_goal_id = goal_id
        await async_storage.add_hypothesis(hyp)

    await async_storage.save_proximity_graph(proximity_graph)

    # Request n=3 (fewer than 5 clusters)
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=3,
        min_elo_rating=1200.0,
        cluster_balance=True
    )

    # Should return top 3 by Elo
    assert len(diverse) == 3, f"Should return 3 hypotheses, got {len(diverse)}"
    assert diverse[0].title == "Cluster1-Top", "First should be Cluster1-Top (1600)"
    assert diverse[1].title == "Cluster2-Top", "Second should be Cluster2-Top (1550)"
    assert diverse[2].title == "Cluster3-Top", "Third should be Cluster3-Top (1500)"

    print("✓ Returns top N cluster representatives by Elo")
    print("✓ Excludes lower-rated clusters when N < cluster count")
    print("✓ Test passed: More clusters than requested N\n")


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        print("\n" + "=" * 70)
        print("DIVERSITY SAMPLING UX TESTS (PHASE 6B)")
        print("=" * 70 + "\n")

        await test_diverse_selection_from_clusters()
        await test_fallback_to_elo_when_no_proximity_graph()
        await test_min_elo_filter()
        await test_fewer_clusters_than_requested_n()
        await test_more_clusters_than_requested_n()

        print("=" * 70)
        print("RESULTS: 5 passed, 0 failed")
        print("=" * 70 + "\n")

    asyncio.run(run_tests())
