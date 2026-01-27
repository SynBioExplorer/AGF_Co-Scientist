"""Dynamic evolution strategy selection.

Selects the appropriate evolution strategy based on hypothesis context,
review feedback, and iteration state. This enables the system to use all
7 evolution strategies (per the Google Co-Scientist paper) instead of
always defaulting to FEASIBILITY.
"""

import random
from typing import List, Optional

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import EvolutionStrategy, Review


# Weights for random strategy selection when no clear signal exists
STRATEGY_WEIGHTS = {
    EvolutionStrategy.GROUNDING: 0.20,       # Literature support - common need
    EvolutionStrategy.COHERENCE: 0.15,       # Logic fixes
    EvolutionStrategy.FEASIBILITY: 0.25,     # Practicality - still important
    EvolutionStrategy.SIMPLIFICATION: 0.10,  # Occasional simplification
    EvolutionStrategy.OUT_OF_BOX: 0.15,      # Novelty exploration
    EvolutionStrategy.INSPIRATION: 0.10,     # New idea generation
    EvolutionStrategy.COMBINATION: 0.05,     # Rare - requires multiple good hypotheses
}


def select_evolution_strategy(
    reviews: Optional[List[Review]] = None,
    hypothesis_count: int = 0
) -> EvolutionStrategy:
    """
    Select evolution strategy based on context.

    Uses a multi-stage selection process:
    1. Early iterations favor divergent/exploratory strategies
    2. Reviews are analyzed for weakness keywords to select targeted strategies
    3. Falls back to weighted random selection for diversity

    Args:
        reviews: Review feedback for the hypothesis (if available)
        hypothesis_count: Total hypotheses generated so far

    Returns:
        Selected EvolutionStrategy
    """
    # Stage 1: Early iterations favor divergent thinking for exploration
    if hypothesis_count < 5:
        return random.choice([
            EvolutionStrategy.OUT_OF_BOX,
            EvolutionStrategy.INSPIRATION
        ])

    # Stage 2: Analyze review feedback for targeted strategy selection
    if reviews:
        strategy = _select_from_reviews(reviews)
        if strategy:
            return strategy

    # Stage 3: Weighted random selection for diversity
    return _weighted_random_selection()


def _select_from_reviews(reviews: List[Review]) -> Optional[EvolutionStrategy]:
    """
    Analyze review content to select an appropriate strategy.

    Maps common weakness keywords to evolution strategies that address them.

    Args:
        reviews: List of reviews to analyze

    Returns:
        Matching EvolutionStrategy or None if no clear signal
    """
    if not reviews:
        return None

    # Combine all review content for keyword analysis
    review_text = " ".join(
        r.content.lower() if hasattr(r, 'content') and r.content else
        (r.rationale.lower() if hasattr(r, 'rationale') and r.rationale else "")
        for r in reviews
    )

    # Also check weaknesses and suggestions lists
    for r in reviews:
        if hasattr(r, 'weaknesses') and r.weaknesses:
            review_text += " " + " ".join(r.weaknesses).lower()
        if hasattr(r, 'suggestions') and r.suggestions:
            review_text += " " + " ".join(r.suggestions).lower()

    # Map weakness keywords to strategies
    # Order matters - check more specific patterns first

    # GROUNDING: needs literature support
    if any(kw in review_text for kw in [
        "evidence", "literature", "citation", "support", "references",
        "documented", "published", "research", "studies"
    ]):
        return EvolutionStrategy.GROUNDING

    # COHERENCE: logical issues
    if any(kw in review_text for kw in [
        "logic", "inconsistent", "contradiction", "coherent", "coherence",
        "conflicting", "illogical", "reasoning"
    ]):
        return EvolutionStrategy.COHERENCE

    # SIMPLIFICATION: too complex
    if any(kw in review_text for kw in [
        "complex", "complicated", "simplify", "unclear", "convoluted",
        "difficult to understand", "too many", "overly"
    ]):
        return EvolutionStrategy.SIMPLIFICATION

    # FEASIBILITY: practicality concerns
    if any(kw in review_text for kw in [
        "practical", "feasible", "testable", "experiment", "implementation",
        "realistic", "achievable", "doable"
    ]):
        return EvolutionStrategy.FEASIBILITY

    # OUT_OF_BOX: lacks novelty
    if any(kw in review_text for kw in [
        "novel", "obvious", "incremental", "boring", "known", "trivial",
        "already established", "not new", "derivative"
    ]):
        return EvolutionStrategy.OUT_OF_BOX

    # COMBINATION: could benefit from merging ideas
    if any(kw in review_text for kw in [
        "combine", "merge", "aspects", "elements", "integrate", "synthesis"
    ]):
        return EvolutionStrategy.COMBINATION

    # INSPIRATION: general improvement needed
    if any(kw in review_text for kw in [
        "inspire", "creative", "fresh", "perspective", "alternative"
    ]):
        return EvolutionStrategy.INSPIRATION

    # No clear signal from reviews
    return None


def _weighted_random_selection() -> EvolutionStrategy:
    """
    Select strategy using weighted random choice.

    Ensures all strategies can be selected while biasing toward
    commonly useful ones.

    Returns:
        Randomly selected EvolutionStrategy based on weights
    """
    return random.choices(
        list(STRATEGY_WEIGHTS.keys()),
        weights=list(STRATEGY_WEIGHTS.values())
    )[0]
