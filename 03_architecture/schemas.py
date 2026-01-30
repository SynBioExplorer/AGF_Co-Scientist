"""
AI Co-Scientist Data Schemas

This module defines the core data structures for the AI co-scientist multi-agent system
based on Google's published architecture. These schemas represent the information flow
between agents and the persistent state of the system.

Reference: Google AI Co-Scientist Paper (2024)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enumerations
# =============================================================================


class HypothesisStatus(str, Enum):
    """Status of a hypothesis in the system pipeline."""

    GENERATED = "generated"  # Initial generation complete
    INITIAL_REVIEW = "initial_review"  # Passed initial review
    FULL_REVIEW = "full_review"  # Passed full review with literature search
    IN_TOURNAMENT = "in_tournament"  # Active in ranking tournament
    EVOLVED = "evolved"  # Has been refined by Evolution agent
    ARCHIVED = "archived"  # No longer active (superseded or rejected)


class ReviewType(str, Enum):
    """Types of reviews performed by the Reflection agent."""

    INITIAL = "initial"  # Quick assessment without external tools
    FULL = "full"  # Comprehensive review with literature search
    DEEP_VERIFICATION = "deep_verification"  # Decomposition into sub-assumptions
    OBSERVATION = "observation"  # Can hypothesis explain existing observations?
    SIMULATION = "simulation"  # Step-wise simulation of mechanism/experiment
    TOURNAMENT = "tournament"  # Adapted review based on tournament state


class EvolutionStrategy(str, Enum):
    """Strategies used by the Evolution agent to refine hypotheses."""

    GROUNDING = "grounding"  # Enhance with literature support
    COHERENCE = "coherence"  # Improve logical consistency
    FEASIBILITY = "feasibility"  # Make more practical/testable
    INSPIRATION = "inspiration"  # Create new hypothesis inspired by existing
    COMBINATION = "combination"  # Merge best aspects of multiple hypotheses
    SIMPLIFICATION = "simplification"  # Simplify for easier verification
    OUT_OF_BOX = "out_of_box"  # Divergent thinking, explore novel directions


class AgentType(str, Enum):
    """Types of specialized agents in the co-scientist system."""

    SUPERVISOR = "supervisor"
    GENERATION = "generation"
    REFLECTION = "reflection"
    RANKING = "ranking"
    PROXIMITY = "proximity"
    EVOLUTION = "evolution"
    META_REVIEW = "meta_review"
    OBSERVATION_REVIEW = "observation_review"  # Phase 6 Week 3


class GenerationMethod(str, Enum):
    """Methods used by the Generation agent to create hypotheses."""

    LITERATURE_EXPLORATION = "literature_exploration"  # Web search and synthesis
    SIMULATED_DEBATE = "simulated_debate"  # Self-play scientific debate
    ITERATIVE_ASSUMPTIONS = "iterative_assumptions"  # Conditional reasoning hops
    RESEARCH_EXPANSION = "research_expansion"  # Explore unexplored areas


# =============================================================================
# Core Data Structures
# =============================================================================


class ResearchGoal(BaseModel):
    """
    The scientist's input research goal that initiates the co-scientist system.

    The research goal serves as the entry point and can range from simple statements
    to extensive documents with hundreds of prior publication PDFs.
    """

    id: str = Field(..., description="Unique identifier for the research goal")
    description: str = Field(
        ..., description="Natural language description of the research goal"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Specific constraints the hypotheses must satisfy",
    )
    preferences: list[str] = Field(
        default_factory=list,
        description="Desired attributes for generated hypotheses",
    )
    prior_publications: list[str] = Field(
        default_factory=list,
        description="References to prior publications (PDFs, DOIs, etc.)",
    )
    laboratory_context: Optional[str] = Field(
        None, description="Context about the scientist's lab setting and capabilities"
    )
    created_at: datetime = Field(default_factory=datetime.now)


class ResearchPlanConfiguration(BaseModel):
    """
    Parsed configuration derived from the research goal.

    The co-scientist parses the research goal to derive this configuration
    which captures proposal preferences, attributes, and evaluation criteria.
    """

    research_goal_id: str = Field(
        ..., description="Reference to the source research goal"
    )
    require_novelty: bool = Field(
        True, description="Whether to exclusively propose novel hypotheses"
    )
    evaluation_criteria: list[EvaluationCriterion] = Field(
        default_factory=list, description="Criteria for evaluating hypothesis quality"
    )
    output_format: Optional[str] = Field(
        None, description="Preferred format for outputs (e.g., NIH Specific Aims)"
    )
    domain_constraints: list[str] = Field(
        default_factory=list,
        description="Domain-specific constraints (e.g., FDA-approved drugs only)",
    )
    tools_enabled: list[str] = Field(
        default_factory=list,
        description="External tools to use (web_search, alphafold, etc.)",
    )


class EvaluationCriterion(BaseModel):
    """A single criterion for evaluating hypothesis quality."""

    name: str = Field(..., description="Name of the criterion (e.g., 'novelty')")
    description: str = Field(..., description="How this criterion is evaluated")
    weight: float = Field(
        1.0, ge=0.0, le=1.0, description="Relative importance weight"
    )


class Hypothesis(BaseModel):
    """
    A research hypothesis generated by the co-scientist system.

    Hypotheses are the core outputs, containing the scientific claim,
    supporting rationale, and proposed experimental validation.
    """

    id: str = Field(..., description="Unique identifier for the hypothesis")
    research_goal_id: str = Field(
        ..., description="Reference to the associated research goal"
    )

    # Core content
    title: str = Field(..., description="Concise title summarizing the hypothesis")
    summary: str = Field(..., description="Brief summary of the core idea")
    hypothesis_statement: str = Field(
        ..., description="The formal hypothesis statement"
    )
    rationale: str = Field(
        ..., description="Scientific reasoning supporting the hypothesis"
    )
    mechanism: Optional[str] = Field(
        None, description="Proposed mechanism of action (if applicable)"
    )

    # Experimental validation
    experimental_protocol: Optional[ExperimentalProtocol] = Field(
        None, description="Proposed experiments to test the hypothesis"
    )

    # Supporting information
    literature_citations: list[Citation] = Field(
        default_factory=list, description="Citations supporting the hypothesis"
    )
    assumptions: list[Assumption] = Field(
        default_factory=list, description="Underlying assumptions of the hypothesis"
    )
    category: Optional[str] = Field(
        None, description="Category/theme of the hypothesis"
    )

    # Metadata
    status: HypothesisStatus = Field(
        HypothesisStatus.GENERATED, description="Current status in the pipeline"
    )
    generation_method: GenerationMethod = Field(
        ..., description="How this hypothesis was generated"
    )
    parent_hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="IDs of hypotheses this was derived from (for evolution)",
    )
    elo_rating: float = Field(
        1200.0, description="Current Elo rating from tournament"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Assumption(BaseModel):
    """
    An assumption underlying a hypothesis.

    Used by the Reflection agent during deep verification review to
    decompose and validate each component of a hypothesis.
    """

    id: str = Field(..., description="Unique identifier")
    statement: str = Field(..., description="The assumption statement")
    sub_assumptions: list[Assumption] = Field(
        default_factory=list, description="Further decomposed sub-assumptions"
    )
    is_fundamental: bool = Field(
        True, description="Whether this assumption is fundamental to the hypothesis"
    )
    verification_status: Optional[str] = Field(
        None, description="Result of verification (valid/invalid/uncertain)"
    )
    evidence: list[str] = Field(
        default_factory=list, description="Evidence supporting or refuting"
    )


class Citation(BaseModel):
    """A literature citation supporting a hypothesis."""

    title: str = Field(..., description="Title of the cited work")
    authors: list[str] = Field(default_factory=list, description="Author names")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    url: Optional[str] = Field(None, description="URL to the publication")
    relevance: str = Field(
        ..., description="How this citation supports the hypothesis"
    )


class ExperimentalProtocol(BaseModel):
    """Proposed experimental protocol to validate a hypothesis."""

    objective: str = Field(..., description="What the experiment aims to test")
    methodology: str = Field(..., description="Detailed experimental approach")
    expected_outcomes: list[str] = Field(
        default_factory=list, description="Predicted results if hypothesis is correct"
    )
    controls: list[str] = Field(
        default_factory=list, description="Control conditions"
    )
    materials: list[str] = Field(
        default_factory=list, description="Required materials and reagents"
    )
    success_criteria: str = Field(
        ..., description="How to determine if hypothesis is validated"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Known limitations of the approach"
    )
    estimated_timeline: Optional[str] = Field(
        None, description="Estimated time to complete"
    )


# =============================================================================
# Review Structures
# =============================================================================


class Review(BaseModel):
    """
    A review of a hypothesis performed by the Reflection agent.

    Reviews assess correctness, quality, novelty, and safety of hypotheses.
    """

    id: str = Field(..., description="Unique identifier for the review")
    hypothesis_id: str = Field(..., description="ID of the reviewed hypothesis")
    review_type: ReviewType = Field(..., description="Type of review performed")

    # Assessment scores (0-1 scale)
    correctness_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Assessment of scientific correctness"
    )
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Overall quality assessment"
    )
    novelty_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Degree of novelty"
    )
    testability_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="How testable the hypothesis is"
    )
    safety_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Safety/ethics assessment"
    )

    # Qualitative feedback
    strengths: list[str] = Field(
        default_factory=list, description="Identified strengths"
    )
    weaknesses: list[str] = Field(
        default_factory=list, description="Identified weaknesses"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Suggestions for improvement"
    )
    critiques: list[str] = Field(
        default_factory=list, description="Specific critiques"
    )

    # For novelty review
    known_aspects: list[str] = Field(
        default_factory=list, description="Aspects already known in literature"
    )
    novel_aspects: list[str] = Field(
        default_factory=list, description="Genuinely novel aspects"
    )

    # For observation review
    explained_observations: list[str] = Field(
        default_factory=list,
        description="Existing observations the hypothesis can explain",
    )

    # For simulation review
    simulation_steps: list[str] = Field(
        default_factory=list, description="Steps in mechanism simulation"
    )
    potential_failures: list[str] = Field(
        default_factory=list, description="Identified potential failure scenarios"
    )

    # Decision
    passed: bool = Field(..., description="Whether the hypothesis passed this review")
    rationale: str = Field(..., description="Reasoning for the decision")

    # Metadata
    literature_searched: list[str] = Field(
        default_factory=list, description="Search queries used"
    )
    created_at: datetime = Field(default_factory=datetime.now)


class DeepVerificationReview(Review):
    """
    Extended review for deep verification of hypothesis assumptions.

    Decomposes the hypothesis into constituent assumptions, evaluates each
    independently, and identifies potential invalidating elements.
    """

    verified_assumptions: list[Assumption] = Field(
        default_factory=list, description="Assumptions that were verified"
    )
    invalidated_assumptions: list[Assumption] = Field(
        default_factory=list, description="Assumptions found to be invalid"
    )
    invalidation_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons for potential hypothesis invalidation",
    )


# =============================================================================
# Tournament Structures
# =============================================================================


class TournamentMatch(BaseModel):
    """
    A pairwise comparison between two hypotheses in the tournament.

    Top-ranked hypotheses are compared through multi-turn scientific debates,
    while lower-ranked ones undergo single-turn comparisons.
    """

    id: str = Field(..., description="Unique identifier for the match")
    hypothesis_a_id: str = Field(..., description="First hypothesis in comparison")
    hypothesis_b_id: str = Field(..., description="Second hypothesis in comparison")

    # Debate content
    debate_turns: list[DebateTurn] = Field(
        default_factory=list, description="Turns in the scientific debate"
    )
    is_multi_turn: bool = Field(
        False, description="Whether this was a multi-turn debate"
    )

    # Outcome
    winner_id: Optional[str] = Field(None, description="ID of the winning hypothesis")
    decision_rationale: str = Field(
        ..., description="Reasoning for the winner decision"
    )
    comparison_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria used (novelty, correctness, testability)",
    )

    # Elo updates
    elo_change_a: float = Field(0.0, description="Elo rating change for hypothesis A")
    elo_change_b: float = Field(0.0, description="Elo rating change for hypothesis B")

    created_at: datetime = Field(default_factory=datetime.now)


class DebateTurn(BaseModel):
    """A single turn in a scientific debate between hypotheses."""

    turn_number: int = Field(..., description="Turn number in the debate")
    hypothesis_id: str = Field(..., description="Which hypothesis is being argued for")
    argument: str = Field(..., description="The argument made in this turn")
    counterpoints: list[str] = Field(
        default_factory=list, description="Counterpoints to the opposing hypothesis"
    )


class TournamentState(BaseModel):
    """
    Current state of the Elo-based tournament.

    Tracks all hypotheses, their ratings, and match history.
    """

    research_goal_id: str = Field(
        ..., description="Associated research goal"
    )
    hypotheses: list[str] = Field(
        default_factory=list, description="IDs of all hypotheses in tournament"
    )
    elo_ratings: dict[str, float] = Field(
        default_factory=dict, description="Current Elo ratings by hypothesis ID"
    )
    match_history: list[str] = Field(
        default_factory=list, description="IDs of completed matches"
    )
    total_matches: int = Field(0, description="Total number of matches conducted")

    # Statistics
    win_patterns: list[str] = Field(
        default_factory=list, description="Identified patterns in winning hypotheses"
    )
    loss_patterns: list[str] = Field(
        default_factory=list, description="Identified patterns in losing hypotheses"
    )

    updated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Proximity Graph
# =============================================================================


class ProximityEdge(BaseModel):
    """An edge in the proximity graph connecting similar hypotheses."""

    hypothesis_a_id: str = Field(..., description="First hypothesis")
    hypothesis_b_id: str = Field(..., description="Second hypothesis")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score between hypotheses"
    )
    shared_concepts: list[str] = Field(
        default_factory=list, description="Concepts shared by both hypotheses"
    )


class ProximityGraph(BaseModel):
    """
    Graph structure for hypothesis similarity computed by Proximity agent.

    Enables clustering, de-duplication, and efficient exploration of the
    hypothesis landscape.
    """

    research_goal_id: str = Field(..., description="Associated research goal")
    edges: list[ProximityEdge] = Field(
        default_factory=list, description="Similarity edges between hypotheses"
    )
    clusters: list[HypothesisCluster] = Field(
        default_factory=list, description="Identified clusters of similar hypotheses"
    )
    updated_at: datetime = Field(default_factory=datetime.now)


class HypothesisCluster(BaseModel):
    """A cluster of similar hypotheses identified by the Proximity agent."""

    id: str = Field(..., description="Unique identifier for the cluster")
    name: str = Field(..., description="Descriptive name for the cluster theme")
    hypothesis_ids: list[str] = Field(
        default_factory=list, description="IDs of hypotheses in this cluster"
    )
    representative_id: Optional[str] = Field(
        None, description="ID of the most representative hypothesis"
    )
    common_themes: list[str] = Field(
        default_factory=list, description="Common themes across hypotheses"
    )


# =============================================================================
# Meta-Review and Research Overview
# =============================================================================


class MetaReviewCritique(BaseModel):
    """
    Synthesized feedback from all reviews, generated by the Meta-review agent.

    Identifies recurring patterns in tournament debates and provides feedback
    to optimize other agents' performance in subsequent iterations.
    """

    id: str = Field(..., description="Unique identifier")
    research_goal_id: str = Field(..., description="Associated research goal")

    # Patterns identified
    recurring_strengths: list[str] = Field(
        default_factory=list, description="Common strengths across top hypotheses"
    )
    recurring_weaknesses: list[str] = Field(
        default_factory=list, description="Common weaknesses to avoid"
    )
    improvement_opportunities: list[str] = Field(
        default_factory=list, description="Identified opportunities for improvement"
    )

    # Feedback for agents
    generation_feedback: list[str] = Field(
        default_factory=list, description="Feedback for Generation agent"
    )
    reflection_feedback: list[str] = Field(
        default_factory=list, description="Feedback for Reflection agent"
    )
    evolution_feedback: list[str] = Field(
        default_factory=list, description="Feedback for Evolution agent"
    )

    created_at: datetime = Field(default_factory=datetime.now)


class ResearchDirection(BaseModel):
    """A potential research direction identified in the research overview."""

    name: str = Field(..., description="Name of the research direction")
    description: str = Field(..., description="Description of the direction")
    justification: str = Field(..., description="Why this direction is important")
    suggested_experiments: list[str] = Field(
        default_factory=list, description="Specific experiments within this direction"
    )
    example_topics: list[str] = Field(
        default_factory=list, description="Illustrative example topics"
    )
    related_hypothesis_ids: list[str] = Field(
        default_factory=list, description="IDs of related hypotheses"
    )


class ResearchContact(BaseModel):
    """A suggested domain expert for collaboration or review."""

    name: str = Field(..., description="Name of the researcher")
    affiliation: Optional[str] = Field(None, description="Institutional affiliation")
    expertise: list[str] = Field(
        default_factory=list, description="Areas of expertise"
    )
    relevance_reasoning: str = Field(
        ..., description="Why this expert is relevant to the research"
    )
    publications: list[str] = Field(
        default_factory=list, description="Relevant publications"
    )


class ResearchOverview(BaseModel):
    """
    Comprehensive research overview synthesized by the Meta-review agent.

    Provides a roadmap for future research, outlining potential areas and
    directions relevant to the research goal.
    """

    id: str = Field(..., description="Unique identifier")
    research_goal_id: str = Field(..., description="Associated research goal")

    # Overview content
    executive_summary: str = Field(
        ..., description="High-level summary of the research landscape"
    )
    current_knowledge_boundary: str = Field(
        ..., description="Summary of current knowledge relevant to the goal"
    )
    research_directions: list[ResearchDirection] = Field(
        default_factory=list, description="Identified research directions"
    )
    top_hypotheses_summary: list[str] = Field(
        default_factory=list, description="Summaries of top-ranked hypotheses"
    )

    # Additional resources
    suggested_contacts: list[ResearchContact] = Field(
        default_factory=list, description="Suggested domain experts"
    )
    key_literature: list[Citation] = Field(
        default_factory=list, description="Key literature references"
    )

    # Format
    output_format: Optional[str] = Field(
        None, description="Format used (e.g., NIH Specific Aims)"
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# System State and Task Management
# =============================================================================


class AgentTask(BaseModel):
    """A task assigned to a specialized agent by the Supervisor."""

    id: str = Field(..., description="Unique identifier for the task")
    agent_type: AgentType = Field(..., description="Type of agent to execute the task")
    task_type: str = Field(
        ..., description="Specific task type (e.g., 'generate_hypothesis')"
    )
    priority: int = Field(1, ge=1, le=10, description="Task priority (1=lowest)")
    parameters: dict = Field(
        default_factory=dict, description="Task-specific parameters"
    )
    status: str = Field("pending", description="Task status (pending/running/complete)")
    result: Optional[dict] = Field(None, description="Task result when complete")
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)


class SystemStatistics(BaseModel):
    """
    Comprehensive statistics computed by the Supervisor agent.

    Used to inform resource allocation decisions and determine if a
    terminal state has been reached.
    """

    research_goal_id: str = Field(..., description="Associated research goal")

    # Hypothesis counts
    total_hypotheses: int = Field(0, description="Total hypotheses generated")
    hypotheses_pending_review: int = Field(0, description="Awaiting review")
    hypotheses_in_tournament: int = Field(0, description="Active in tournament")
    hypotheses_archived: int = Field(0, description="Archived/rejected")

    # Tournament progress
    tournament_matches_completed: int = Field(0, description="Matches completed")
    tournament_convergence_score: float = Field(
        0.0, description="How stable the rankings are"
    )

    # Agent effectiveness
    generation_success_rate: float = Field(
        0.0, description="Rate of generated hypotheses passing initial review"
    )
    evolution_improvement_rate: float = Field(
        0.0, description="Rate of evolution producing higher-ranked hypotheses"
    )
    method_effectiveness: dict[str, float] = Field(
        default_factory=dict,
        description="Effectiveness scores by generation method",
    )

    # Resource allocation
    agent_weights: dict[str, float] = Field(
        default_factory=dict, description="Current weight allocation per agent"
    )

    computed_at: datetime = Field(default_factory=datetime.now)


class ContextMemory(BaseModel):
    """
    Persistent context memory for the co-scientist system.

    Enables iterative computation and scientific reasoning over long time
    horizons by storing and retrieving agent and system states.
    """

    research_goal_id: str = Field(..., description="Associated research goal")

    # Current state
    research_plan_config: Optional[ResearchPlanConfiguration] = Field(None)
    tournament_state: Optional[TournamentState] = Field(None)
    proximity_graph: Optional[ProximityGraph] = Field(None)
    latest_meta_review: Optional[MetaReviewCritique] = Field(None)
    latest_research_overview: Optional[ResearchOverview] = Field(None)
    system_statistics: Optional[SystemStatistics] = Field(None)

    # History
    hypothesis_ids: list[str] = Field(
        default_factory=list, description="All hypothesis IDs"
    )
    review_ids: list[str] = Field(default_factory=list, description="All review IDs")
    iteration_count: int = Field(0, description="Number of iterations completed")

    # Scientist feedback
    scientist_reviews: list[str] = Field(
        default_factory=list, description="IDs of scientist-provided reviews"
    )
    scientist_hypotheses: list[str] = Field(
        default_factory=list, description="IDs of scientist-contributed hypotheses"
    )

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Observation Review (Phase 6 Week 3)
# =============================================================================


class ObservationType(str, Enum):
    """Types of scientific observations that can be extracted from papers."""

    EXPERIMENTAL = "experimental"
    CLINICAL = "clinical"
    DATASET = "dataset"
    RESULT = "result"
    MECHANISM = "mechanism"
    PHENOMENON = "phenomenon"


class Observation(BaseModel):
    """
    A specific observation extracted from a scientific paper.

    Observations are concrete findings, results, or phenomena reported in the
    literature that can be used to validate hypotheses.
    """

    id: str = Field(..., description="Unique identifier")
    paper_id: str = Field(..., description="DOI, PMID, or paper identifier")
    paper_title: str = Field(..., description="Title of the source paper")
    observation_type: ObservationType = Field(
        ..., description="Type of observation"
    )
    text: str = Field(..., description="The observation text")
    context: str = Field(
        ..., description="Surrounding context from the paper (2-3 sentences)"
    )
    relevance_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Relevance to research goal"
    )
    citation_count: int = Field(
        0, description="Citation count of source paper (proxy for impact)"
    )

    extracted_at: datetime = Field(default_factory=datetime.now)


class ObservationExplanation(BaseModel):
    """
    Evaluation of how well a hypothesis explains a specific observation.
    """

    observation_id: str = Field(..., description="ID of the observation")
    hypothesis_id: str = Field(..., description="ID of the hypothesis")

    explains: bool = Field(
        ..., description="Whether hypothesis explains this observation"
    )
    explanation_score: float = Field(
        ..., ge=0.0, le=1.0, description="How well it explains (0=not at all, 1=perfectly)"
    )
    reasoning: str = Field(
        ..., description="LLM reasoning for the explanation score"
    )

    # Mechanistic alignment
    mechanism_match: bool = Field(
        False, description="Does hypothesis mechanism align with observation?"
    )
    prediction_match: bool = Field(
        False, description="Does hypothesis predict this observation?"
    )


class ObservationReviewScore(BaseModel):
    """
    Aggregate score for how well a hypothesis explains a set of observations.

    This implements the "Observation Review" component from the Google paper,
    which validates hypotheses against long-tail observations from literature.
    """

    id: str = Field(..., description="Unique identifier")
    hypothesis_id: str = Field(..., description="ID of the hypothesis reviewed")
    research_goal_id: str = Field(..., description="Associated research goal")

    # Observations evaluated
    observations: list[Observation] = Field(
        default_factory=list, description="Observations used for review"
    )
    explanations: list[ObservationExplanation] = Field(
        default_factory=list, description="Per-observation explanations"
    )

    # Aggregate scores
    overall_score: float = Field(
        ..., ge=0.0, le=1.0, description="Overall explanation score (mean of explanations)"
    )
    observations_explained_count: int = Field(
        0, description="Number of observations explained (score >= 0.5)"
    )
    observations_total_count: int = Field(
        0, description="Total observations evaluated"
    )

    # Analysis
    strengths: list[str] = Field(
        default_factory=list,
        description="Observations hypothesis explains particularly well",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Observations hypothesis fails to explain",
    )
    summary: str = Field(
        ..., description="Summary of observation review findings"
    )

    created_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Scientist Interaction
# =============================================================================


class ScientistFeedback(BaseModel):
    """Feedback provided by a scientist on a hypothesis or the system."""

    id: str = Field(..., description="Unique identifier")
    hypothesis_id: Optional[str] = Field(
        None, description="ID of hypothesis being reviewed (if applicable)"
    )
    feedback_type: str = Field(
        ..., description="Type: review, suggestion, goal_refinement, direction"
    )
    content: str = Field(..., description="The feedback content")
    created_at: datetime = Field(default_factory=datetime.now)


class ChatMessage(BaseModel):
    """A message in the scientist-system chat interface."""

    id: str = Field(..., description="Unique identifier")
    role: str = Field(..., description="Role: scientist or system")
    content: str = Field(..., description="Message content")
    hypothesis_references: list[str] = Field(
        default_factory=list, description="IDs of referenced hypotheses"
    )
    created_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Model rebuild to handle forward references
# =============================================================================

# Rebuild models that have forward references
ResearchPlanConfiguration.model_rebuild()
Assumption.model_rebuild()
