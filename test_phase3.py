#!/usr/bin/env python3
"""Test Phase 3: Advanced agents (Evolution, Proximity, Meta-review)"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.config import settings
from src.utils.logging_config import setup_logging
from src.graphs.workflow import CoScientistWorkflow
from src.storage.memory import storage
from src.agents.evolution import EvolutionAgent
from src.agents.proximity import ProximityAgent
from src.agents.meta_review import MetaReviewAgent
import structlog

# Import schemas
sys.path.append(str(settings.architecture_dir))
from schemas import ResearchGoal, EvolutionStrategy


def test_phase3():
    """Test Phase 3: Evolution, Proximity, Meta-review agents"""

    # Setup logging
    setup_logging("INFO")
    logger = structlog.get_logger()

    logger.info("=== Phase 3 Advanced Agents Test ===")
    logger.info(f"LLM Provider: {settings.llm_provider}")

    # Create research goal
    research_goal = ResearchGoal(
        id="goal_phase3_001",
        description="Develop novel therapeutic strategies for treatment-resistant glioblastoma",
        constraints=[
            "Must target tumor microenvironment",
            "Consider blood-brain barrier penetration",
            "Focus on combination therapies"
        ],
        preferences=[
            "Prioritize patient safety",
            "Consider immunotherapy approaches",
            "Leverage existing approved drugs where possible"
        ]
    )

    logger.info("Test: Research Goal", goal=research_goal.description)

    # Step 1: Run Phase 2 workflow to generate hypotheses
    logger.info("\n=== Step 1: Generate Initial Hypotheses (Phase 2 workflow) ===")
    workflow = CoScientistWorkflow()
    final_state = workflow.run(
        research_goal=research_goal,
        max_iterations=2  # Keep it short for testing
    )

    logger.info(
        "Initial workflow complete",
        hypotheses=len(final_state['hypotheses']),
        reviews=len(final_state['reviews']),
        matches=len(final_state['matches'])
    )

    # Step 2: Test Evolution Agent
    logger.info("\n=== Step 2: Test Evolution Agent ===")
    evolution_agent = EvolutionAgent()

    # Get top hypothesis and evolve it
    top_hypotheses = storage.get_top_hypotheses(n=1)
    if top_hypotheses:
        original_hyp = top_hypotheses[0]
        reviews = storage.get_reviews_for_hypothesis(original_hyp.id)

        logger.info(
            "Evolving top hypothesis",
            hypothesis_id=original_hyp.id,
            title=original_hyp.title,
            strategy="FEASIBILITY"
        )

        evolved_hyp = evolution_agent.execute(
            hypothesis=original_hyp,
            strategy=EvolutionStrategy.FEASIBILITY,
            reviews=reviews
        )

        storage.add_hypothesis(evolved_hyp)

        logger.info(
            "Hypothesis evolved successfully",
            original_id=original_hyp.id,
            evolved_id=evolved_hyp.id,
            evolved_title=evolved_hyp.title,
            evolution_rationale=evolved_hyp.evolution_rationale[:150] + "..." if evolved_hyp.evolution_rationale else "N/A"
        )

    # Step 3: Test Proximity Agent
    logger.info("\n=== Step 3: Test Proximity Agent ===")
    proximity_agent = ProximityAgent()

    all_hypotheses = storage.get_all_hypotheses()
    if len(all_hypotheses) >= 2:
        proximity_graph = proximity_agent.execute(
            hypotheses=all_hypotheses,
            research_goal_id=research_goal.id,
            similarity_threshold=0.5
        )

        logger.info(
            "Proximity graph built",
            num_hypotheses=len(all_hypotheses),
            num_edges=len(proximity_graph.edges),
            num_clusters=len(proximity_graph.clusters)
        )

        # Display clusters
        for i, cluster in enumerate(proximity_graph.clusters, 1):
            logger.info(
                f"Cluster {i}",
                hypothesis_count=len(cluster.hypothesis_ids),
                common_themes=cluster.common_themes
            )

    # Step 4: Test Meta-review Agent
    logger.info("\n=== Step 4: Test Meta-review Agent ===")
    meta_review_agent = MetaReviewAgent()

    all_reviews = storage.reviews.values()
    all_matches = storage.get_all_matches()

    if all_reviews and all_matches:
        meta_review = meta_review_agent.execute(
            reviews=list(all_reviews),
            matches=all_matches,
            goal=research_goal.description,
            preferences=research_goal.preferences
        )

        logger.info(
            "Meta-review generated",
            recurring_issues=len(meta_review.recurring_issues),
            common_strengths=len(meta_review.common_strengths),
            suggested_improvements=len(meta_review.suggested_improvements)
        )

        logger.info(
            "\nMeta-review summary",
            recurring_issues=meta_review.recurring_issues,
            common_strengths=meta_review.common_strengths[:3],  # Top 3
            suggested_improvements=meta_review.suggested_improvements[:3]  # Top 3
        )

        # Generate research overview
        logger.info("\n=== Step 5: Generate Research Overview ===")
        top_hypotheses = storage.get_top_hypotheses(n=3)

        overview = meta_review_agent.generate_research_overview(
            goal=research_goal.description,
            top_hypotheses=top_hypotheses,
            meta_review=meta_review,
            preferences=research_goal.preferences
        )

        logger.info(
            "Research overview generated",
            num_directions=len(overview.research_directions),
            num_contacts=len(overview.suggested_contacts),
            num_next_steps=len(overview.recommended_next_steps)
        )

        logger.info(
            "\nResearch overview summary",
            summary=overview.summary[:300] + "..."
        )

        # Display research directions
        for i, direction in enumerate(overview.research_directions, 1):
            logger.info(
                f"\nResearch Direction {i}",
                title=direction.title,
                feasibility=direction.feasibility_score,
                timeline=direction.estimated_timeline
            )

    # Storage statistics
    stats = storage.get_stats()
    logger.info("\n=== Final Storage Statistics ===", **stats)

    # Cost tracking
    logger.info("\n=== Cost Tracking ===")
    sys.path.append(str(settings.project_root / "04_Scripts"))
    from cost_tracker import get_tracker
    tracker = get_tracker()
    tracker.print_summary()

    logger.info("\n=== Phase 3 Test Complete ===")


if __name__ == "__main__":
    test_phase3()
