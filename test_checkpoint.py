#!/usr/bin/env python3
"""Test Checkpoint Manager for workflow state persistence and recovery"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.config import settings
from src.utils.logging_config import setup_logging
from src.storage.memory import InMemoryStorage
from src.supervisor.checkpoint import CheckpointManager, get_checkpoint_manager
from src.utils.ids import generate_id
import structlog

# Import schemas
sys.path.append(str(settings.architecture_dir))
from schemas import (
    ResearchGoal,
    Hypothesis,
    Review,
    ReviewType,
    TournamentMatch,
    ProximityGraph,
    ProximityEdge,
    HypothesisCluster,
    GenerationMethod,
    HypothesisStatus,
)


def create_test_data(storage: InMemoryStorage, goal_id: str):
    """Create test data for checkpoint testing"""

    # Create research goal
    goal = ResearchGoal(
        id=goal_id,
        description="Test research goal for checkpoint testing",
        constraints=["Constraint 1", "Constraint 2"],
        preferences=["Preference 1"]
    )
    storage.add_research_goal(goal)

    # Create hypotheses
    hypotheses = []
    for i in range(3):
        hyp = Hypothesis(
            id=f"hyp_{goal_id}_{i}",
            research_goal_id=goal_id,
            title=f"Test Hypothesis {i+1}",
            summary=f"Summary for hypothesis {i+1}",
            hypothesis_statement=f"Test statement {i+1}",
            rationale=f"Test rationale {i+1}",
            mechanism=f"Test mechanism {i+1}",
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
            elo_rating=1200.0 + (i * 50),  # Different ratings
            status=HypothesisStatus.IN_TOURNAMENT,
            category=f"category_{i % 2}"  # Two categories
        )
        hypotheses.append(hyp)
        storage.add_hypothesis(hyp)

    # Create reviews
    for i, hyp in enumerate(hypotheses):
        review = Review(
            id=f"rev_{goal_id}_{i}",
            hypothesis_id=hyp.id,
            review_type=ReviewType.INITIAL,
            passed=True,
            rationale="Test review rationale",
            quality_score=0.7 + (i * 0.1),
            novelty_score=0.6,
            testability_score=0.8,
            safety_score=0.9
        )
        storage.add_review(review)

    # Create tournament matches
    if len(hypotheses) >= 2:
        match = TournamentMatch(
            id=f"match_{goal_id}_1",
            hypothesis_a_id=hypotheses[0].id,
            hypothesis_b_id=hypotheses[1].id,
            winner_id=hypotheses[0].id,
            decision_rationale="Hypothesis A showed superior novelty",
            comparison_criteria=["novelty", "testability"],
            elo_change_a=16.0,
            elo_change_b=-16.0
        )
        storage.add_match(match)

    # Create proximity graph
    if len(hypotheses) >= 2:
        edges = [
            ProximityEdge(
                hypothesis_a_id=hypotheses[0].id,
                hypothesis_b_id=hypotheses[1].id,
                similarity_score=0.75,
                shared_concepts=["common_theme_1"]
            )
        ]
        clusters = [
            HypothesisCluster(
                id=f"cluster_{goal_id}_1",
                name="Test Cluster",
                hypothesis_ids=[hypotheses[0].id, hypotheses[1].id],
                representative_id=hypotheses[0].id,
                common_themes=["shared_theme"]
            )
        ]
        graph = ProximityGraph(
            research_goal_id=goal_id,
            edges=edges,
            clusters=clusters
        )
        storage.save_proximity_graph(graph)

    return goal, hypotheses


def test_checkpoint_manager():
    """Test CheckpointManager save, load, and resume functionality"""

    # Setup logging
    setup_logging("INFO")
    logger = structlog.get_logger()

    logger.info("=== Checkpoint Manager Test ===")

    # Create fresh storage instance for testing
    storage = InMemoryStorage()
    checkpoint_manager = CheckpointManager(storage, checkpoint_interval=2)

    # =========================================================================
    # Test 1: Create test data
    # =========================================================================
    logger.info("\n=== Test 1: Create Test Data ===")

    goal_id = "goal_checkpoint_test_001"
    goal, hypotheses = create_test_data(storage, goal_id)

    stats = storage.get_stats()
    logger.info(
        "Test data created",
        goal_id=goal_id,
        num_hypotheses=stats["hypotheses"],
        num_reviews=stats["reviews"],
        num_matches=stats["matches"]
    )

    # =========================================================================
    # Test 2: Save checkpoint
    # =========================================================================
    logger.info("\n=== Test 2: Save Checkpoint ===")

    checkpoint = checkpoint_manager.save_checkpoint(
        goal_id=goal_id,
        iteration=5,
        notes="Test checkpoint at iteration 5"
    )

    logger.info(
        "Checkpoint saved",
        goal_id=checkpoint.research_goal_id,
        iteration=checkpoint.iteration_count,
        num_hypothesis_ids=len(checkpoint.hypothesis_ids),
        num_review_ids=len(checkpoint.review_ids),
        has_tournament_state=checkpoint.tournament_state is not None,
        has_proximity_graph=checkpoint.proximity_graph is not None,
        has_statistics=checkpoint.system_statistics is not None
    )

    # Validate checkpoint contents
    assert checkpoint.research_goal_id == goal_id
    assert checkpoint.iteration_count == 5
    assert len(checkpoint.hypothesis_ids) == 3
    assert checkpoint.tournament_state is not None
    assert len(checkpoint.tournament_state.elo_ratings) == 3

    # =========================================================================
    # Test 3: Load checkpoint
    # =========================================================================
    logger.info("\n=== Test 3: Load Checkpoint ===")

    loaded_checkpoint = checkpoint_manager.load_checkpoint(goal_id)

    assert loaded_checkpoint is not None
    assert loaded_checkpoint.iteration_count == 5
    assert loaded_checkpoint.research_goal_id == goal_id

    logger.info(
        "Checkpoint loaded successfully",
        iteration=loaded_checkpoint.iteration_count,
        hypothesis_ids=loaded_checkpoint.hypothesis_ids
    )

    # =========================================================================
    # Test 4: Save multiple checkpoints
    # =========================================================================
    logger.info("\n=== Test 4: Save Multiple Checkpoints ===")

    # Save more checkpoints at different iterations
    for iteration in [10, 15, 20]:
        checkpoint_manager.save_checkpoint(
            goal_id=goal_id,
            iteration=iteration,
            notes=f"Checkpoint at iteration {iteration}"
        )

    all_checkpoints = storage.get_all_checkpoints(goal_id)
    logger.info(
        "Multiple checkpoints saved",
        num_checkpoints=len(all_checkpoints),
        iterations=[cp.iteration_count for cp in all_checkpoints]
    )

    assert len(all_checkpoints) == 4  # 5, 10, 15, 20

    # =========================================================================
    # Test 5: Resume workflow
    # =========================================================================
    logger.info("\n=== Test 5: Resume Workflow ===")

    resume_iteration = checkpoint_manager.resume_workflow(goal_id)

    assert resume_iteration == 20  # Most recent checkpoint
    logger.info(
        "Workflow would resume from",
        iteration=resume_iteration,
        next_iteration=resume_iteration + 1
    )

    # =========================================================================
    # Test 6: should_checkpoint logic
    # =========================================================================
    logger.info("\n=== Test 6: should_checkpoint Logic ===")

    # With interval=2
    checkpoint_manager.checkpoint_interval = 2

    should_checkpoint_results = {
        0: checkpoint_manager.should_checkpoint(0),   # Always true for iteration 0
        1: checkpoint_manager.should_checkpoint(1),   # False (1 % 2 != 0)
        2: checkpoint_manager.should_checkpoint(2),   # True (2 % 2 == 0)
        3: checkpoint_manager.should_checkpoint(3),   # False
        4: checkpoint_manager.should_checkpoint(4),   # True
        10: checkpoint_manager.should_checkpoint(10), # True
    }

    logger.info("should_checkpoint results", results=should_checkpoint_results)

    assert should_checkpoint_results[0] == True
    assert should_checkpoint_results[1] == False
    assert should_checkpoint_results[2] == True
    assert should_checkpoint_results[4] == True

    # =========================================================================
    # Test 7: Get checkpoint history
    # =========================================================================
    logger.info("\n=== Test 7: Checkpoint History ===")

    history = checkpoint_manager.get_checkpoint_history(goal_id)

    logger.info("Checkpoint history", num_checkpoints=len(history))
    for entry in history:
        logger.info(
            "Checkpoint entry",
            iteration=entry["iteration"],
            num_hypotheses=entry["num_hypotheses"],
            num_reviews=entry["num_reviews"],
            has_graph=entry["has_proximity_graph"]
        )

    assert len(history) == 4

    # =========================================================================
    # Test 8: Nonexistent goal
    # =========================================================================
    logger.info("\n=== Test 8: Nonexistent Goal ===")

    no_checkpoint = checkpoint_manager.load_checkpoint("nonexistent_goal")
    assert no_checkpoint is None

    resume_none = checkpoint_manager.resume_workflow("nonexistent_goal")
    assert resume_none is None

    logger.info("Correctly handled nonexistent goal (returned None)")

    # =========================================================================
    # Test 9: Convergence calculation
    # =========================================================================
    logger.info("\n=== Test 9: Convergence Score ===")

    # Check convergence in checkpoint
    latest = checkpoint_manager.load_checkpoint(goal_id)
    if latest and latest.system_statistics:
        logger.info(
            "Tournament statistics",
            convergence_score=latest.system_statistics.tournament_convergence_score,
            total_hypotheses=latest.system_statistics.total_hypotheses,
            matches_completed=latest.system_statistics.tournament_matches_completed
        )

    # =========================================================================
    # Test 10: get_checkpoint_manager factory function
    # =========================================================================
    logger.info("\n=== Test 10: Factory Function ===")

    # Test with explicit storage
    cm1 = get_checkpoint_manager(storage)
    assert cm1.storage is storage

    # Test with default storage (uses global storage instance)
    cm2 = get_checkpoint_manager()
    assert cm2 is not None

    logger.info("Factory function working correctly")

    # =========================================================================
    # Summary
    # =========================================================================
    logger.info("\n=== Test Summary ===")
    logger.info(
        "All checkpoint tests passed",
        checkpoints_saved=4,
        checkpoints_loaded=True,
        resume_working=True,
        factory_working=True
    )

    # Final storage stats
    final_stats = storage.get_stats()
    logger.info("Final storage statistics", **final_stats)

    logger.info("\n=== Checkpoint Manager Test Complete ===")


if __name__ == "__main__":
    test_checkpoint_manager()
