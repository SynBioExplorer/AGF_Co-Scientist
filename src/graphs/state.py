"""State definition for LangGraph workflow"""

from typing import TypedDict, List, Optional, Annotated
import operator
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import ResearchGoal, Hypothesis, Review, TournamentMatch


class WorkflowState(TypedDict):
    """State passed between nodes in the workflow

    This defines the shared state for the Generate → Review → Rank pipeline.
    """

    # Research context
    research_goal: ResearchGoal

    # Hypotheses
    hypotheses: Annotated[List[Hypothesis], operator.add]  # Accumulate new hypotheses

    # Reviews
    reviews: Annotated[List[Review], operator.add]  # Accumulate reviews

    # Tournament matches
    matches: Annotated[List[TournamentMatch], operator.add]  # Accumulate matches

    # Control flow
    iteration: int  # Current iteration number
    max_iterations: int  # Maximum iterations before stopping
    convergence_threshold: float  # Elo variance threshold for convergence

    # Statistics
    top_hypothesis_id: Optional[str]  # ID of current top-ranked hypothesis
    average_quality_score: Optional[float]  # Average quality from reviews

    # Flags
    should_continue: bool  # Whether to continue the loop
    reason_for_stopping: Optional[str]  # Why the workflow stopped
