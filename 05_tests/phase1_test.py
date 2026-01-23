#!/usr/bin/env python3
"""Test Phase 1: Foundation components"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.config import settings
from src.utils.logging_config import setup_logging
from src.utils.ids import generate_hypothesis_id
from src.agents.generation import GenerationAgent
from src.prompts.loader import prompt_manager
import structlog

# Import schemas
sys.path.append(str(settings.architecture_dir))
from schemas import ResearchGoal


def test_phase1():
    """Test all Phase 1 components"""

    # Setup logging
    setup_logging("INFO")
    logger = structlog.get_logger()

    logger.info("=== Phase 1 Foundation Test ===")

    # Test 1: Configuration
    logger.info("Test 1: Configuration loading", budget=settings.budget_aud, model=settings.generation_model)

    # Test 2: ID generation
    hyp_id = generate_hypothesis_id()
    logger.info("Test 2: ID generation", hypothesis_id=hyp_id)

    # Test 3: Prompt loading
    prompt_manager.load_prompt("01_Generation_Agent_Hypothesis_After_Literature_Review.txt")
    logger.info("Test 3: Prompt loading", status="✓")

    # Test 4: Generation Agent
    research_goal = ResearchGoal(
        id="goal_test_001",
        description="Identify novel drug targets for acute myeloid leukemia (AML) treatment",
        constraints=["Must be clinically testable", "Focus on epigenetic mechanisms"],
        preferences=["Prioritize safety", "Consider drug repurposing opportunities"]
    )

    logger.info("Test 4: Generation Agent execution")
    agent = GenerationAgent()
    hypothesis = agent.execute(research_goal)

    logger.info(
        "Hypothesis generated successfully",
        id=hypothesis.id,
        title=hypothesis.title,
        elo_rating=hypothesis.elo_rating
    )

    # Test 5: Cost tracking
    sys.path.append(str(settings.project_root / "04_Scripts"))
    from cost_tracker import get_tracker
    tracker = get_tracker()
    tracker.print_summary()

    logger.info("=== Phase 1 Test Complete ===")


if __name__ == "__main__":
    test_phase1()
