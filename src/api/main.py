"""FastAPI application for AI Co-Scientist system.

This module provides the REST API with:
- Automatic periodic cleanup of background tasks and chat history
- Timeout protection for long-running supervisor workflows
- Configurable CORS and API key injection
"""

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional, List
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_Architecture"))

from src.api.models import (
    SubmitGoalRequest,
    SubmitFeedbackRequest,
    GoalStatusResponse,
    HypothesisListResponse,
    HypothesisDetailResponse,
    StatisticsResponse,
    TaskStatusResponse,
    HealthResponse,
    FeedbackResponse,
    WorkflowConfigRequest,
)
from pydantic import BaseModel
from src.api.background import task_manager
from src.api.chat import cleanup_old_history as cleanup_chat_history
from src.storage.async_adapter import async_storage as storage
from src.agents.supervisor import SupervisorAgent
from src.utils.ids import generate_id
from src.utils.logging_config import setup_logging
from src.config import settings
from schemas import ResearchGoal, HypothesisStatus, ScientistFeedback
import structlog

# Setup logging
setup_logging("INFO")
logger = structlog.get_logger()

# Track cleanup tasks for graceful shutdown
_cleanup_tasks: List[asyncio.Task] = []


async def _periodic_chat_cleanup():
    """Background task to clean up old chat history."""
    while True:
        try:
            await asyncio.sleep(settings.task_cleanup_interval_hours * 3600)
            cleaned = cleanup_chat_history(max_age_hours=settings.chat_history_max_age_hours)
            if cleaned > 0:
                logger.info("Periodic chat cleanup completed", goals_cleaned=cleaned)
        except asyncio.CancelledError:
            logger.info("Chat cleanup task cancelled")
            break
        except Exception as e:
            logger.error("Chat cleanup failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown.

    Startup:
    - Connect to storage backend
    - Start periodic cleanup tasks for background tasks and chat history

    Shutdown:
    - Cancel all cleanup tasks
    - Clean up all completed tasks
    - Disconnect from storage
    """
    global _cleanup_tasks

    # Startup
    logger.info(
        "AI Co-Scientist API starting up",
        task_cleanup_interval=settings.task_cleanup_interval_hours,
        task_max_age=settings.task_max_age_hours,
        chat_max_age=settings.chat_history_max_age_hours,
    )
    await storage.connect()

    # Start periodic cleanup tasks
    task_cleanup = asyncio.create_task(
        task_manager.start_periodic_cleanup(
            interval_hours=settings.task_cleanup_interval_hours,
            max_age_hours=settings.task_max_age_hours
        )
    )
    _cleanup_tasks.append(task_cleanup)

    chat_cleanup = asyncio.create_task(_periodic_chat_cleanup())
    _cleanup_tasks.append(chat_cleanup)

    logger.info("Periodic cleanup tasks started")

    yield

    # Shutdown
    logger.info("AI Co-Scientist API shutting down")

    # Cancel cleanup tasks
    for task in _cleanup_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _cleanup_tasks.clear()

    # Clean up all completed tasks before shutdown
    task_manager.cleanup_completed_tasks(max_age_hours=0)
    task_manager.shutdown()

    await storage.disconnect()
    logger.info("AI Co-Scientist API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="AI Co-Scientist API",
    description="Multi-agent system for scientific hypothesis generation and evaluation",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Middleware for API Key Injection
# ==============================================================================


@app.middleware("http")
async def inject_api_keys_middleware(request: Request, call_next):
    """Inject API keys from headers into environment variables.

    This allows the frontend to dynamically provide API keys that override
    the .env file configuration. Useful for multi-user scenarios or when
    users want to use their own API keys.
    """
    # Store original env vars to restore after request
    original_env = {}

    # Map headers to environment variables
    header_env_map = {
        "x-google-api-key": "GOOGLE_API_KEY",
        "x-openai-api-key": "OPENAI_API_KEY",
        "x-tavily-api-key": "TAVILY_API_KEY",
        "x-langsmith-api-key": "LANGCHAIN_API_KEY",
    }

    # Inject API keys from headers
    for header, env_var in header_env_map.items():
        if header in request.headers:
            # Save original value
            original_env[env_var] = os.environ.get(env_var)
            # Set new value from header
            os.environ[env_var] = request.headers[header]

    # Enable LangSmith tracing if API key provided
    if "x-langsmith-api-key" in request.headers:
        original_env["LANGCHAIN_TRACING_V2"] = os.environ.get("LANGCHAIN_TRACING_V2")
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        # Set project name if not already set
        if "LANGCHAIN_PROJECT" not in os.environ:
            original_env["LANGCHAIN_PROJECT"] = None
            os.environ["LANGCHAIN_PROJECT"] = "ai-coscientist"

    try:
        # Process request
        response = await call_next(request)
        return response
    finally:
        # Restore original environment variables
        for env_var, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = original_value


# ==============================================================================
# Helper Functions
# ==============================================================================


async def run_supervisor_workflow(
    goal: ResearchGoal,
    max_iterations: int,
    enable_evolution: bool
) -> str:
    """Run supervisor-orchestrated workflow asynchronously with timeout protection.

    This replaces the simplified CoScientistWorkflow with the full
    SupervisorAgent which provides:
    - Dynamic task queue with weighted agent selection
    - Terminal condition detection (budget, convergence, quality)
    - Checkpoint/resume capability
    - Statistics tracking for weight adaptation
    - Timeout protection to prevent hung workflows

    Args:
        goal: Research goal to work on.
        max_iterations: Maximum iterations before stopping.
        enable_evolution: Whether to enable hypothesis evolution.

    Returns:
        Status message with summary of execution.

    Raises:
        asyncio.TimeoutError: If workflow exceeds maximum allowed time.
    """
    # Calculate total timeout based on iterations
    # Each iteration gets supervisor_iteration_timeout seconds
    total_timeout = settings.supervisor_iteration_timeout * max_iterations

    logger.info(
        "Starting SupervisorAgent execution",
        goal_id=goal.id,
        max_iterations=max_iterations,
        enable_evolution=enable_evolution,
        total_timeout_seconds=total_timeout
    )

    supervisor = SupervisorAgent(storage)

    try:
        # Execute supervisor orchestration with timeout protection
        # Note: enable_evolution is handled by the supervisor's dynamic weighting
        # The Evolution agent weight is adjusted based on effectiveness
        result = await asyncio.wait_for(
            supervisor.execute(
                research_goal=goal,
                max_iterations=max_iterations
            ),
            timeout=total_timeout
        )

        logger.info(
            "SupervisorAgent execution completed",
            goal_id=goal.id,
            result=result
        )

        return result

    except asyncio.TimeoutError:
        error_msg = (
            f"Workflow timed out after {total_timeout}s "
            f"({max_iterations} iterations × {settings.supervisor_iteration_timeout}s)"
        )
        logger.error(
            "SupervisorAgent execution timed out",
            goal_id=goal.id,
            timeout_seconds=total_timeout,
            max_iterations=max_iterations
        )
        # Return error message instead of raising (background task handles gracefully)
        return f"ERROR: {error_msg}"

    except Exception as e:
        logger.error(
            "SupervisorAgent execution failed",
            goal_id=goal.id,
            error=str(e),
            error_type=type(e).__name__
        )
        return f"ERROR: {str(e)}"


async def compute_statistics(goal_id: str) -> dict:
    """Compute statistics for a research goal"""
    hypotheses = await storage.get_hypotheses_by_goal(goal_id)
    all_matches = await storage.get_all_matches()
    goal_matches = [
        m for m in all_matches
        if any(
            h.id in (m.hypothesis_a_id, m.hypothesis_b_id)
            for h in hypotheses
        )
    ]

    # Count hypotheses by status
    pending_review = len([h for h in hypotheses if h.status == HypothesisStatus.GENERATED])
    in_tournament = len([h for h in hypotheses if h.status == HypothesisStatus.IN_TOURNAMENT])

    # Calculate convergence (simplified: variance of top 5 Elo ratings)
    if len(hypotheses) >= 2:
        top_ratings = sorted([h.elo_rating for h in hypotheses], reverse=True)[:5]
        mean_rating = sum(top_ratings) / len(top_ratings)
        variance = sum((r - mean_rating) ** 2 for r in top_ratings) / len(top_ratings)
        # Normalize to 0-1 (lower variance = higher convergence)
        convergence = max(0.0, 1.0 - (variance / 10000))
    else:
        convergence = 0.0

    return {
        "hypotheses_generated": len(hypotheses),
        "hypotheses_pending_review": pending_review,
        "hypotheses_in_tournament": in_tournament,
        "total_matches": len(goal_matches),
        "tournament_convergence": convergence,
    }


# ==============================================================================
# Health Check
# ==============================================================================


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check system health status"""
    # Simple health check - verify storage is accessible
    try:
        await storage.get_stats()
        storage_status = "connected"
        status = "healthy"
    except Exception:
        storage_status = "disconnected"
        status = "degraded"

    return HealthResponse(
        status=status,
        storage=storage_status,
    )


# ==============================================================================
# Research Goals
# ==============================================================================


class SubmitGoalWithConfigRequest(BaseModel):
    """Combined request for goal submission with config"""
    description: str
    constraints: List[str] = []
    preferences: List[str] = []
    prior_publications: List[str] = []
    config: Optional[WorkflowConfigRequest] = None


@app.post("/goals", response_model=GoalStatusResponse, tags=["Goals"])
async def submit_goal(request: SubmitGoalWithConfigRequest):
    """Submit a new research goal and start the workflow.

    This endpoint creates a new research goal and starts the hypothesis
    generation workflow in the background. Use GET /goals/{goal_id} to
    check progress.
    """
    logger.info(
        "Received goal submission",
        description=request.description[:100]
    )

    # Use default config if not provided
    config = request.config or WorkflowConfigRequest()

    # Create ResearchGoal
    goal = ResearchGoal(
        id=generate_id("goal"),
        description=request.description,
        constraints=request.constraints,
        preferences=request.preferences,
        prior_publications=request.prior_publications,
    )

    # Save to storage
    await storage.add_research_goal(goal)

    # Start supervisor workflow in background (async)
    task_id = await task_manager.start_async_task(
        goal_id=goal.id,
        coroutine=run_supervisor_workflow(
            goal=goal,
            max_iterations=config.max_iterations,
            enable_evolution=config.enable_evolution
        )
    )

    logger.info(
        "Workflow started",
        goal_id=goal.id,
        task_id=task_id,
        max_iterations=config.max_iterations
    )

    return GoalStatusResponse(
        goal_id=goal.id,
        status="processing",
        progress={"hypotheses_generated": 0, "matches_completed": 0},
        current_iteration=0,
        max_iterations=config.max_iterations,
    )


@app.get("/goals/{goal_id}", response_model=GoalStatusResponse, tags=["Goals"])
async def get_goal_status(goal_id: str):
    """Get the status and progress of a research goal"""
    # Get goal from storage
    goal = await storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Get task status
    tasks = task_manager.get_tasks_for_goal(goal_id)
    latest_task = tasks[-1] if tasks else None

    # Determine status
    if latest_task:
        task_status = latest_task["status"]
        if task_status == "running":
            status = "processing"
        elif task_status == "completed":
            status = "completed"
        elif task_status == "failed":
            status = "failed"
        else:
            status = "processing"
    else:
        status = "pending"

    # Get statistics
    stats = await compute_statistics(goal_id)

    return GoalStatusResponse(
        goal_id=goal_id,
        status=status,
        progress={
            "hypotheses_generated": stats["hypotheses_generated"],
            "matches_completed": stats["total_matches"],
        },
        current_iteration=0,  # Would need to track this in workflow state
        max_iterations=20,  # Default, would need to store this
    )


@app.get("/goals/{goal_id}/tasks", response_model=list[TaskStatusResponse], tags=["Goals"])
async def get_goal_tasks(goal_id: str):
    """Get all background tasks for a research goal"""
    goal = await storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    tasks = task_manager.get_tasks_for_goal(goal_id)

    return [
        TaskStatusResponse(
            task_id=t["task_id"],
            goal_id=t["goal_id"],
            status=t["status"],
            started_at=t.get("started_at"),
            completed_at=t.get("completed_at"),
            error=t.get("error"),
        )
        for t in tasks
    ]


# ==============================================================================
# Hypotheses
# ==============================================================================


@app.get("/goals/{goal_id}/hypotheses", response_model=HypothesisListResponse, tags=["Hypotheses"])
async def get_hypotheses(
    goal_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Results per page"),
    sort_by: str = Query("elo", pattern="^(elo|created|title|diverse)$", description="Sort field or sampling strategy"),
    min_elo: float = Query(1200.0, ge=0, le=3000, description="Minimum Elo rating filter"),
):
    """
    Get paginated list of hypotheses for a research goal.

    Query Parameters:
    - sort_by: "elo" (default), "created", "title", or "diverse" (cluster-aware sampling)
    - min_elo: Minimum Elo rating filter (default: 1200.0)
    - page, page_size: Pagination parameters
    """
    # Verify goal exists
    goal = await storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Use diversity sampling if requested
    if sort_by == "diverse":
        from src.config import settings
        if settings.diversity_sampling_enabled:
            all_hypotheses = await storage.get_diverse_hypotheses(
                goal_id=goal_id,
                n=100,  # Get all for pagination
                min_elo_rating=min_elo,
                cluster_balance=True
            )
        else:
            # Fallback to Elo if diversity sampling disabled
            all_hypotheses = await storage.get_hypotheses_by_goal(goal_id)
            all_hypotheses = [h for h in all_hypotheses if (h.elo_rating or 1200.0) >= min_elo]
            all_hypotheses.sort(key=lambda h: h.elo_rating or 1200.0, reverse=True)
    else:
        # Original behavior
        all_hypotheses = await storage.get_hypotheses_by_goal(goal_id)

        # Apply minimum Elo filter
        all_hypotheses = [h for h in all_hypotheses if (h.elo_rating or 1200.0) >= min_elo]

        # Sort by specified field
        if sort_by == "elo":
            all_hypotheses.sort(key=lambda h: h.elo_rating or 1200.0, reverse=True)
        elif sort_by == "created":
            all_hypotheses.sort(key=lambda h: h.created_at, reverse=True)
        elif sort_by == "title":
            all_hypotheses.sort(key=lambda h: h.title.lower())

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    page_hypotheses = all_hypotheses[start:end]

    return HypothesisListResponse(
        hypotheses=[h.model_dump() for h in page_hypotheses],
        total_count=len(all_hypotheses),
        page=page,
        page_size=page_size,
    )


@app.get("/hypotheses/{hypothesis_id}", response_model=HypothesisDetailResponse, tags=["Hypotheses"])
async def get_hypothesis_detail(hypothesis_id: str):
    """Get detailed information about a specific hypothesis"""
    # Get hypothesis
    hypothesis = await storage.get_hypothesis(hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    # Get reviews
    reviews = await storage.get_reviews_for_hypothesis(hypothesis_id)

    # Get tournament matches
    matches = await storage.get_matches_for_hypothesis(hypothesis_id)
    wins = len([m for m in matches if m.winner_id == hypothesis_id])
    losses = len(matches) - wins
    win_rate = wins / len(matches) if matches else 0.0

    # Get evolution history (parent hypotheses)
    evolution_history = None
    if hypothesis.parent_hypothesis_ids:
        parents = []
        for parent_id in hypothesis.parent_hypothesis_ids:
            parent = await storage.get_hypothesis(parent_id)
            if parent:
                parents.append({
                    "id": parent.id,
                    "title": parent.title,
                    "elo_rating": parent.elo_rating,
                })
        if parents:
            evolution_history = parents

    return HypothesisDetailResponse(
        hypothesis=hypothesis.model_dump(),
        reviews=[r.model_dump() for r in reviews],
        tournament_record={
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_matches": len(matches),
        },
        evolution_history=evolution_history,
    )


# ==============================================================================
# Feedback
# ==============================================================================


@app.post("/hypotheses/{hypothesis_id}/feedback", response_model=FeedbackResponse, tags=["Feedback"])
async def submit_feedback(hypothesis_id: str, request: SubmitFeedbackRequest):
    """Submit scientist feedback on a hypothesis"""
    # Verify hypothesis exists
    hypothesis = await storage.get_hypothesis(hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    # Create feedback ID
    feedback_id = generate_id("feedback")

    # Log and store feedback
    logger.info(
        "Feedback received",
        feedback_id=feedback_id,
        hypothesis_id=hypothesis_id,
        rating=request.rating,
        comments=request.comments[:100] if request.comments else None,
    )

    # Store feedback in async storage
    feedback = ScientistFeedback(
        id=feedback_id,
        hypothesis_id=hypothesis_id,
        feedback_type="review",
        content=request.comments or "",
    )
    await storage.add_feedback(feedback)

    return FeedbackResponse(
        status="feedback_received",
        feedback_id=feedback_id,
        hypothesis_id=hypothesis_id,
    )


# ==============================================================================
# Statistics
# ==============================================================================


@app.get("/goals/{goal_id}/stats", response_model=StatisticsResponse, tags=["Statistics"])
async def get_statistics(goal_id: str):
    """Get system statistics for a research goal"""
    # Verify goal exists
    goal = await storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Compute statistics
    stats = await compute_statistics(goal_id)

    return StatisticsResponse(
        goal_id=goal_id,
        hypotheses_generated=stats["hypotheses_generated"],
        hypotheses_pending_review=stats["hypotheses_pending_review"],
        hypotheses_in_tournament=stats["hypotheses_in_tournament"],
        total_matches=stats["total_matches"],
        tournament_convergence=stats["tournament_convergence"],
        agent_effectiveness={},  # Would need to track per-agent metrics
    )


# ==============================================================================
# Research Overview
# ==============================================================================


@app.get("/goals/{goal_id}/overview", tags=["Overview"])
async def get_research_overview(goal_id: str):
    """Get the final research overview for a completed goal.

    This endpoint returns the comprehensive research overview generated
    by the Meta-review agent after the workflow completes.
    """
    # Verify goal exists
    goal = await storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Check if workflow is complete
    tasks = task_manager.get_tasks_for_goal(goal_id)
    if not tasks or tasks[-1]["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail="Research overview not yet available. Workflow still in progress."
        )

    # Get top hypotheses
    top_hypotheses = await storage.get_top_hypotheses(n=10)
    goal_hypotheses = [h for h in top_hypotheses if h.research_goal_id == goal_id][:5]

    if not goal_hypotheses:
        raise HTTPException(
            status_code=404,
            detail="No hypotheses found for this goal"
        )

    # Build overview response with win rates
    top_hypotheses_data = []
    for i, h in enumerate(goal_hypotheses):
        win_rate = await storage.get_hypothesis_win_rate(h.id)
        top_hypotheses_data.append({
            "rank": i + 1,
            "id": h.id,
            "title": h.title,
            "summary": h.summary,
            "elo_rating": h.elo_rating,
            "win_rate": win_rate,
        })

    return {
        "goal_id": goal_id,
        "goal_description": goal.description,
        "top_hypotheses": top_hypotheses_data,
        "statistics": await compute_statistics(goal_id),
    }


# ==============================================================================
# Task Management
# ==============================================================================


@app.post("/tasks/{task_id}/cancel", tags=["Tasks"])
async def cancel_task(task_id: str):
    """Cancel a running background task"""
    if task_manager.cancel_task(task_id):
        return {"status": "cancelled", "task_id": task_id}
    else:
        raise HTTPException(
            status_code=404,
            detail="Task not found or already complete"
        )


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse, tags=["Tasks"])
async def get_task_status(task_id: str):
    """Get status of a background task"""
    status = task_manager.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task_id,
        goal_id=status["goal_id"],
        status=status["status"],
        started_at=status.get("started_at"),
        completed_at=status.get("completed_at"),
        error=status.get("error"),
    )


# ==============================================================================
# Import chat router
# ==============================================================================


# Import and include chat router (created separately)
from src.api.chat import router as chat_router
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])

# Import and include tools router
from src.api.tools import router as tools_router
app.include_router(tools_router, prefix="/api/v1", tags=["Tools"])

# Import and include documents router
from src.api.documents import router as documents_router
app.include_router(documents_router, prefix="/api/v1", tags=["Documents"])


# ==============================================================================
# Run server
# ==============================================================================


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
