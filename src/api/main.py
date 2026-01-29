"""FastAPI application for AI Co-Scientist system"""

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import sys
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
from src.api.background import task_manager
from src.storage.async_adapter import async_storage as storage
from src.agents.supervisor import SupervisorAgent
from src.utils.ids import generate_id
from src.utils.logging_config import setup_logging
from schemas import ResearchGoal, HypothesisStatus, ScientistFeedback
import structlog

# Setup logging
setup_logging("INFO")
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    # Startup
    logger.info("AI Co-Scientist API starting up")
    await storage.connect()
    yield
    # Shutdown
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
# Helper Functions
# ==============================================================================


async def run_supervisor_workflow(
    goal: ResearchGoal,
    max_iterations: int,
    enable_evolution: bool
) -> str:
    """Run supervisor-orchestrated workflow asynchronously.

    This replaces the simplified CoScientistWorkflow with the full
    SupervisorAgent which provides:
    - Dynamic task queue with weighted agent selection
    - Terminal condition detection (budget, convergence, quality)
    - Checkpoint/resume capability
    - Statistics tracking for weight adaptation

    Args:
        goal: Research goal to work on.
        max_iterations: Maximum iterations before stopping.
        enable_evolution: Whether to enable hypothesis evolution.

    Returns:
        Status message with summary of execution.
    """
    logger.info(
        "Starting SupervisorAgent execution",
        goal_id=goal.id,
        max_iterations=max_iterations,
        enable_evolution=enable_evolution
    )

    supervisor = SupervisorAgent(storage)

    # Execute supervisor orchestration
    # Note: enable_evolution is handled by the supervisor's dynamic weighting
    # The Evolution agent weight is adjusted based on effectiveness
    result = await supervisor.execute(
        research_goal=goal,
        max_iterations=max_iterations
    )

    logger.info(
        "SupervisorAgent execution completed",
        goal_id=goal.id,
        result=result
    )

    return result


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


@app.post("/goals", response_model=GoalStatusResponse, tags=["Goals"])
async def submit_goal(
    request: SubmitGoalRequest,
    config: Optional[WorkflowConfigRequest] = None
):
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
    if config is None:
        config = WorkflowConfigRequest()

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
    sort_by: str = Query("elo", pattern="^(elo|created|title)$", description="Sort field"),
):
    """Get paginated list of hypotheses for a research goal"""
    # Verify goal exists
    goal = await storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Get all hypotheses for goal
    all_hypotheses = await storage.get_hypotheses_by_goal(goal_id)

    # Sort
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
