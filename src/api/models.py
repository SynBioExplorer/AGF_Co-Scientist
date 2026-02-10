"""Request and response models for AI Co-Scientist API"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==============================================================================
# Request Models
# ==============================================================================


class SubmitGoalRequest(BaseModel):
    """Request to submit a new research goal"""

    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Natural language description of the research goal"
    )
    constraints: List[str] = Field(
        default_factory=list,
        description="Specific constraints the hypotheses must satisfy"
    )
    preferences: List[str] = Field(
        default_factory=list,
        description="Desired attributes for generated hypotheses"
    )
    prior_publications: List[str] = Field(
        default_factory=list,
        description="References to prior publications (DOIs, titles, etc.)"
    )


class SubmitFeedbackRequest(BaseModel):
    """Request to submit scientist feedback on a hypothesis"""

    hypothesis_id: str = Field(..., description="ID of the hypothesis being reviewed")
    rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Rating from 1 (poor) to 5 (excellent)"
    )
    comments: str = Field(..., description="Feedback comments")
    suggested_modifications: Optional[str] = Field(
        None,
        description="Suggested modifications to the hypothesis"
    )


class ChatRequest(BaseModel):
    """Request to chat with the system"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's message"
    )
    goal_id: str = Field(..., description="Research goal ID for context")
    context_hypothesis_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Optional list of hypothesis IDs to include in context"
    )


class WorkflowConfigRequest(BaseModel):
    """Request to configure workflow parameters"""

    max_iterations: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of workflow iterations"
    )
    enable_evolution: bool = Field(
        default=True,
        description="Whether to enable hypothesis evolution"
    )
    enable_web_search: bool = Field(
        default=True,
        description="Whether to enable web search for literature"
    )

    # Frontend compatibility - model configuration
    llm_provider: Optional[str] = Field(
        default=None,
        description="LLM provider to use (e.g., 'google', 'openai')"
    )
    default_model: Optional[str] = Field(
        default=None,
        description="Default LLM model to use for all agents"
    )
    default_temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default temperature parameter for LLM generation"
    )
    agent_models: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Per-agent model configuration (e.g., {'generation': {'model': 'gemini-2.0-flash-exp', 'temperature': 0.7}})"
    )


# ==============================================================================
# Response Models
# ==============================================================================


class GoalStatusResponse(BaseModel):
    """Response for goal status"""

    goal_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: Dict[str, int]  # {"hypotheses_generated": 10, "matches_completed": 15}
    current_iteration: int
    max_iterations: int
    estimated_completion: Optional[str] = None


class HypothesisListResponse(BaseModel):
    """Response for hypothesis list"""

    hypotheses: List[Dict[str, Any]]  # List of hypothesis objects
    total_count: int
    page: int
    page_size: int


class HypothesisDetailResponse(BaseModel):
    """Response for hypothesis details"""

    hypothesis: Dict[str, Any]  # Full hypothesis object
    reviews: List[Dict[str, Any]]  # All reviews
    tournament_record: Dict[str, Any]  # {"wins": 5, "losses": 3, "win_rate": 0.625}
    evolution_history: Optional[List[Dict[str, Any]]] = None  # Parent/child relationships


class StatisticsResponse(BaseModel):
    """Response for system statistics"""

    goal_id: str
    hypotheses_generated: int
    hypotheses_pending_review: int
    hypotheses_in_tournament: int
    total_matches: int
    tournament_convergence: float
    agent_effectiveness: Dict[str, float]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatResponse(BaseModel):
    """Response from chat interface"""

    message: str
    context_used: List[str]  # IDs of hypotheses referenced
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskStatusResponse(BaseModel):
    """Response for background task status"""

    task_id: str
    goal_id: str
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response for health check"""

    status: str  # "healthy", "degraded", "unhealthy"
    storage: str  # "connected", "disconnected"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FeedbackResponse(BaseModel):
    """Response for feedback submission"""

    status: str
    feedback_id: str
    hypothesis_id: str
