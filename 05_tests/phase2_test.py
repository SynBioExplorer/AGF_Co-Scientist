#!/usr/bin/env python3
"""Test Phase 2: Core Pipeline (Generate → Review → Rank)"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.config import settings
from src.utils.logging_config import setup_logging
from src.graphs.workflow import CoScientistWorkflow
from src.storage.memory import storage
import structlog

# Import schemas
sys.path.append(str(settings.architecture_dir))
from schemas import ResearchGoal, ReviewType


def test_phase2():
    """Test Phase 2: Generate → Review → Rank pipeline"""

    # Setup logging
    setup_logging("INFO")
    logger = structlog.get_logger()

    logger.info("=== Phase 2 Core Pipeline Test ===")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    # Create research goal
    research_goal = ResearchGoal(
        id="goal_phase2_001",
        description="Identify novel drug targets for acute myeloid leukemia (AML) treatment",
        constraints=["Must be clinically testable", "Focus on epigenetic mechanisms"],
        preferences=["Prioritize safety", "Consider drug repurposing opportunities"]
    )

    logger.info("Test: Research Goal", goal=research_goal.description)

    # Initialize workflow
    workflow = CoScientistWorkflow()

    # Run workflow (3 iterations for testing)
    logger.info("Running workflow with 3 iterations...")
    final_state = workflow.run(
        research_goal=research_goal,
        max_iterations=3
    )

    # Print results
    logger.info("\n=== Workflow Results ===")
    logger.info(f"Iterations completed: {final_state['iteration']}")
    logger.info(f"Total hypotheses generated: {len(final_state['hypotheses'])}")
    logger.info(f"Total reviews completed: {len(final_state['reviews'])}")
    logger.info(f"Total tournament matches: {len(final_state['matches'])}")

    # Display top hypotheses
    logger.info("\n=== Top Hypotheses (by Elo Rating) ===")
    top_hypotheses = storage.get_top_hypotheses(n=3)

    for i, hyp in enumerate(top_hypotheses, 1):
        logger.info(
            f"\n#{i}. {hyp.title}",
            id=hyp.id,
            elo_rating=round(hyp.elo_rating, 2),
            statement=hyp.hypothesis_statement[:150] + "..."
        )

        # Get reviews for this hypothesis
        reviews = storage.get_reviews_for_hypothesis(hyp.id)
        if reviews:
            review = reviews[0]
            logger.info(
                "   Review scores",
                correctness=review.correctness_score,
                quality=review.quality_score,
                novelty=review.novelty_score,
                passed=review.passed
            )

        # Get match history
        matches = storage.get_matches_for_hypothesis(hyp.id)
        wins = sum(1 for m in matches if m.winner_id == hyp.id)
        logger.info(
            "   Tournament record",
            wins=wins,
            total_matches=len(matches),
            win_rate=f"{wins/len(matches)*100:.1f}%" if matches else "N/A"
        )

    # Storage statistics
    stats = storage.get_stats()
    logger.info("\n=== Storage Statistics ===", **stats)

    # Cost tracking
    logger.info("\n=== Cost Tracking ===")
    sys.path.append(str(settings.project_root / "04_Scripts"))
    from cost_tracker import get_tracker
    tracker = get_tracker()
    tracker.print_summary()

    logger.info("\n=== Phase 2 Test Complete ===")


if __name__ == "__main__":
    test_phase2()
