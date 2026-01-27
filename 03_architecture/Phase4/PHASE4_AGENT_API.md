# Phase 4 Agent: FastAPI Web Interface

**Branch**: `phase4/api`
**Timeline**: Week 4 (7 days)
**Dependencies**: ALL previous components (Database, Supervisor, Safety)
**Priority**: FINAL (integrates everything)

---

## Mission

Build a production-ready FastAPI backend that exposes REST endpoints for web interface interaction, scientist feedback, and chat functionality. This is the final component that brings the entire AI Co-Scientist system together.

---

## Context

You are working in a **git worktree** on branch `phase4/api`. All other Phase 4 components are complete (Database, Supervisor, Safety).

**Current System State**:
- PostgreSQL database operational
- Supervisor orchestrating agents
- Safety reviews integrated
- Checkpointing functional
- NO web interface

**Your Goal**:
- Create FastAPI REST API with 8+ endpoints
- Implement chat interface for scientist Q&A
- Add background task management for long-running jobs
- Enable scientist feedback collection
- Provide real-time statistics

---

## Deliverables

### Files to Create

1. **src/api/\_\_init\_\_.py** - Package init
2. **src/api/main.py** - FastAPI application
3. **src/api/chat.py** - Chat interface router
4. **src/api/models.py** - Request/response models (Pydantic)
5. **src/api/background.py** - Background task management
6. **test_api.py** - API endpoint tests
7. **requirements-api.txt** - API-specific dependencies

### Files to Modify

1. **03_architecture/environment.yml** - Add FastAPI dependencies
2. **src/config.py** - Add API configuration settings

---

## Implementation Guide

### Step 1: Install Dependencies (Day 1)

```bash
# Activate conda environment
conda activate coscientist

# Install FastAPI and ASGI server
conda install -c conda-forge fastapi uvicorn python-multipart

# Verify installation
python -c "import fastapi, uvicorn; print('✓ FastAPI installed')"
```

Update `03_architecture/environment.yml`:
```yaml
dependencies:
  # ... existing deps
  - fastapi>=0.109.0
  - uvicorn>=0.27.0
  - python-multipart>=0.0.6
```

### Step 2: Rebase on Main (Day 1)

```bash
# Get all previous work
git fetch origin main
git rebase origin/main

# Resolve any conflicts
# Test that everything works
python test_phase3.py
```

### Step 3: Create API Models (Day 1)

**File**: `src/api/models.py`

```python
"""Request and response models for API"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


# ==================== Request Models ====================

class SubmitGoalRequest(BaseModel):
    """Request to submit new research goal"""
    description: str = Field(..., min_length=10, max_length=5000)
    constraints: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    prior_publications: List[str] = Field(default_factory=list)


class SubmitFeedbackRequest(BaseModel):
    """Request to submit scientist feedback on hypothesis"""
    hypothesis_id: str
    rating: Optional[int] = Field(None, ge=1, le=5)
    comments: str
    suggested_modifications: Optional[str] = None


class ChatRequest(BaseModel):
    """Request to chat with system"""
    message: str = Field(..., min_length=1, max_length=2000)
    goal_id: str
    context_hypothesis_ids: Optional[List[str]] = Field(default_factory=list)


# ==================== Response Models ====================

class GoalStatusResponse(BaseModel):
    """Response for goal status"""
    goal_id: str
    status: str  # "processing", "completed", "failed"
    progress: Dict[str, int]  # {"hypotheses_generated": 10, "matches_completed": 15}
    current_iteration: int
    max_iterations: int
    estimated_completion: Optional[str] = None


class HypothesisListResponse(BaseModel):
    """Response for hypothesis list"""
    hypotheses: List[Dict]  # List of hypothesis objects
    total_count: int
    page: int
    page_size: int


class HypothesisDetailResponse(BaseModel):
    """Response for hypothesis details"""
    hypothesis: Dict  # Full hypothesis object
    reviews: List[Dict]  # All reviews
    tournament_record: Dict  # {"wins": 5, "losses": 3, "win_rate": 0.625}
    evolution_history: Optional[List[Dict]] = None  # Parent/child relationships


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
```

### Step 4: Create Background Task Manager (Days 2-3)

**File**: `src/api/background.py`

```python
"""Background task management for long-running operations"""

from typing import Dict, Optional
import asyncio
import uuid
from datetime import datetime
import structlog

logger = structlog.get_logger()


class BackgroundTaskManager:
    """Manage background tasks (supervisor execution, etc.)"""

    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._task_status: Dict[str, Dict] = {}

    def start_task(self, goal_id: str, coroutine) -> str:
        """Start background task

        Args:
            goal_id: Research goal ID
            coroutine: Async coroutine to execute

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())

        # Create task
        task = asyncio.create_task(coroutine)
        self._tasks[task_id] = task
        self._task_status[task_id] = {
            "goal_id": goal_id,
            "status": "running",
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "error": None
        }

        # Add completion callback
        task.add_done_callback(lambda t: self._on_task_complete(task_id, t))

        logger.info("Background task started", task_id=task_id, goal_id=goal_id)
        return task_id

    def _on_task_complete(self, task_id: str, task: asyncio.Task):
        """Callback when task completes"""
        if task.exception():
            self._task_status[task_id]["status"] = "failed"
            self._task_status[task_id]["error"] = str(task.exception())
            logger.error("Background task failed", task_id=task_id, error=task.exception())
        else:
            self._task_status[task_id]["status"] = "completed"
            logger.info("Background task completed", task_id=task_id)

        self._task_status[task_id]["completed_at"] = datetime.utcnow()

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status

        Args:
            task_id: Task ID

        Returns:
            Task status dict or None if not found
        """
        return self._task_status.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel running task

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled, False if not found
        """
        if task_id in self._tasks:
            self._tasks[task_id].cancel()
            self._task_status[task_id]["status"] = "cancelled"
            logger.info("Background task cancelled", task_id=task_id)
            return True
        return False


# Global instance
task_manager = BackgroundTaskManager()
```

### Step 5: Implement FastAPI Application (Days 3-5)

**File**: `src/api/main.py`

```python
"""FastAPI application for AI Co-Scientist"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.api.models import (
    SubmitGoalRequest, SubmitFeedbackRequest,
    GoalStatusResponse, HypothesisListResponse,
    HypothesisDetailResponse, StatisticsResponse
)
from src.api.background import task_manager
from src.storage.factory import get_storage
from src.agents.supervisor import SupervisorAgent
from src.supervisor.statistics import SupervisorStatistics
from src.utils.ids import generate_id
from schemas import ResearchGoal, ScientistFeedback
import structlog

# Setup logging
from src.utils.logging_config import setup_logging
setup_logging("INFO")
logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="AI Co-Scientist API",
    description="Multi-agent system for scientific hypothesis generation",
    version="1.0.0"
)

# Enable CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize storage
storage = get_storage()


@app.on_event("startup")
async def startup():
    """Initialize storage on startup"""
    await storage.connect()
    logger.info("API started, storage connected")


@app.on_event("shutdown")
async def shutdown():
    """Close storage on shutdown"""
    await storage.disconnect()
    logger.info("API shutdown, storage disconnected")


# ==================== Endpoints ====================

@app.post("/goals", response_model=GoalStatusResponse)
async def submit_goal(request: SubmitGoalRequest):
    """Submit new research goal and start supervisor

    Args:
        request: Goal submission request

    Returns:
        Goal status with task ID
    """
    logger.info("Received goal submission", description=request.description[:100])

    # Create ResearchGoal
    goal = ResearchGoal(
        id=generate_id("goal"),
        description=request.description,
        constraints=request.constraints,
        preferences=request.preferences,
        prior_publications=request.prior_publications
    )

    # Save to storage
    await storage.add_research_goal(goal)

    # Start supervisor in background
    supervisor = SupervisorAgent(storage)
    task_id = task_manager.start_task(
        goal.id,
        supervisor.execute(goal, max_iterations=20)
    )

    return GoalStatusResponse(
        goal_id=goal.id,
        status="processing",
        progress={"hypotheses_generated": 0},
        current_iteration=0,
        max_iterations=20
    )


@app.get("/goals/{goal_id}", response_model=GoalStatusResponse)
async def get_goal_status(goal_id: str):
    """Get research goal status

    Args:
        goal_id: Research goal ID

    Returns:
        Current status and progress
    """
    # Get goal from storage
    goal = await storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Get statistics
    stats_tracker = SupervisorStatistics(storage)
    stats = await stats_tracker.compute_statistics(goal_id)

    return GoalStatusResponse(
        goal_id=goal_id,
        status="processing",  # TODO: Check if complete
        progress={
            "hypotheses_generated": stats.hypotheses_generated,
            "matches_completed": stats.total_matches
        },
        current_iteration=0,  # TODO: Track iteration
        max_iterations=20
    )


@app.get("/goals/{goal_id}/hypotheses", response_model=HypothesisListResponse)
async def get_hypotheses(
    goal_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("elo", regex="^(elo|created|title)$")
):
    """Get hypotheses for research goal

    Args:
        goal_id: Research goal ID
        page: Page number (1-indexed)
        page_size: Number of results per page
        sort_by: Sort by (elo, created, title)

    Returns:
        Paginated list of hypotheses
    """
    # Get all hypotheses for goal
    all_hypotheses = await storage.get_hypotheses_by_goal(goal_id)

    # Sort
    if sort_by == "elo":
        all_hypotheses.sort(key=lambda h: h.elo_rating, reverse=True)
    elif sort_by == "created":
        all_hypotheses.sort(key=lambda h: h.id, reverse=True)  # ID includes timestamp
    # title sort would be alphabetical

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    page_hypotheses = all_hypotheses[start:end]

    return HypothesisListResponse(
        hypotheses=[h.model_dump() for h in page_hypotheses],
        total_count=len(all_hypotheses),
        page=page,
        page_size=page_size
    )


@app.get("/hypotheses/{hypothesis_id}", response_model=HypothesisDetailResponse)
async def get_hypothesis_detail(hypothesis_id: str):
    """Get detailed hypothesis information

    Args:
        hypothesis_id: Hypothesis ID

    Returns:
        Hypothesis with reviews and tournament record
    """
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

    return HypothesisDetailResponse(
        hypothesis=hypothesis.model_dump(),
        reviews=[r.model_dump() for r in reviews],
        tournament_record={
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_matches": len(matches)
        }
    )


@app.post("/hypotheses/{hypothesis_id}/feedback")
async def submit_feedback(hypothesis_id: str, request: SubmitFeedbackRequest):
    """Submit scientist feedback on hypothesis

    Args:
        hypothesis_id: Hypothesis ID
        request: Feedback request

    Returns:
        Success message
    """
    # Verify hypothesis exists
    hypothesis = await storage.get_hypothesis(hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    # Create feedback object
    feedback = ScientistFeedback(
        id=generate_id("feedback"),
        hypothesis_id=hypothesis_id,
        feedback_text=request.comments,
        suggestions=request.suggested_modifications or ""
    )

    # TODO: Save to storage (add method to BaseStorage)
    logger.info("Feedback received", hypothesis_id=hypothesis_id)

    return {"status": "feedback_received", "hypothesis_id": hypothesis_id}


@app.get("/goals/{goal_id}/overview")
async def get_research_overview(goal_id: str):
    """Get final research overview

    Args:
        goal_id: Research goal ID

    Returns:
        ResearchOverview object
    """
    overview = await storage.get_research_overview(goal_id)
    if not overview:
        raise HTTPException(status_code=404, detail="Research overview not yet generated")

    return overview.model_dump()


@app.get("/goals/{goal_id}/stats", response_model=StatisticsResponse)
async def get_statistics(goal_id: str):
    """Get system statistics for goal

    Args:
        goal_id: Research goal ID

    Returns:
        System statistics
    """
    stats_tracker = SupervisorStatistics(storage)
    stats = await stats_tracker.compute_statistics(goal_id)

    return StatisticsResponse(
        goal_id=goal_id,
        hypotheses_generated=stats.hypotheses_generated,
        hypotheses_pending_review=stats.hypotheses_pending_review,
        hypotheses_in_tournament=stats.hypotheses_in_tournament,
        total_matches=stats.total_matches,
        tournament_convergence=stats.tournament_convergence,
        agent_effectiveness={k.value: v for k, v in stats.agent_effectiveness.items()}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint

    Returns:
        Health status
    """
    storage_healthy = await storage.health_check()

    return {
        "status": "healthy" if storage_healthy else "degraded",
        "storage": "connected" if storage_healthy else "disconnected"
    }
```

### Step 6: Implement Chat Interface (Day 5)

**File**: `src/api/chat.py`

```python
"""Chat interface for scientist interaction"""

from fastapi import APIRouter, HTTPException
from src.api.models import ChatRequest, ChatResponse
from src.storage.factory import get_storage
from src.llm.factory import get_llm_client
from src.config import settings
import structlog

logger = structlog.get_logger()
router = APIRouter()

storage = get_storage()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with system about research goal

    Args:
        request: Chat request with message and context

    Returns:
        AI response with context
    """
    logger.info("Chat request", goal_id=request.goal_id, message=request.message[:100])

    # Get top hypotheses for context
    top_hypotheses = await storage.get_top_hypotheses(n=5, goal_id=request.goal_id)

    # Build context
    context_text = f"""
    You are an AI research assistant helping a scientist explore hypotheses.

    Top Hypotheses (by Elo rating):
    {chr(10).join(f"{i+1}. {h.title} (Elo: {h.elo_rating:.0f})" for i, h in enumerate(top_hypotheses))}

    Scientist's Question: {request.message}

    Provide a helpful, scientific response. Reference specific hypotheses by number.
    """

    # Invoke LLM
    llm_client = get_llm_client(model=settings.supervisor_model, agent_name="chat")
    response = await llm_client.ainvoke(context_text)

    return ChatResponse(
        message=response,
        context_used=[h.id for h in top_hypotheses]
    )
```

**Add to main.py**:
```python
from src.api.chat import router as chat_router
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
```

### Step 7: Create API Tests (Days 6-7)

**File**: `test_api.py`

```python
#!/usr/bin/env python3
"""Test FastAPI endpoints"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_check():
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "degraded"]


def test_submit_goal():
    """Test goal submission"""
    payload = {
        "description": "Test research goal for API testing",
        "constraints": ["in vitro only"],
        "preferences": ["high safety"]
    }

    response = client.post("/goals", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "goal_id" in data
    assert data["status"] == "processing"


def test_get_hypotheses():
    """Test hypothesis retrieval"""
    # First submit goal
    payload = {
        "description": "Test goal",
        "constraints": [],
        "preferences": []
    }
    submit_response = client.post("/goals", json=payload)
    goal_id = submit_response.json()["goal_id"]

    # Get hypotheses
    response = client.get(f"/goals/{goal_id}/hypotheses")
    assert response.status_code == 200

    data = response.json()
    assert "hypotheses" in data
    assert "total_count" in data


def test_get_statistics():
    """Test statistics endpoint"""
    # Submit goal first
    payload = {
        "description": "Test goal",
        "constraints": [],
        "preferences": []
    }
    submit_response = client.post("/goals", json=payload)
    goal_id = submit_response.json()["goal_id"]

    # Get stats
    response = client.get(f"/goals/{goal_id}/stats")
    assert response.status_code == 200

    data = response.json()
    assert "hypotheses_generated" in data
    assert "tournament_convergence" in data


def test_chat():
    """Test chat endpoint"""
    # Submit goal
    payload = {
        "description": "Test goal",
        "constraints": [],
        "preferences": []
    }
    submit_response = client.post("/goals", json=payload)
    goal_id = submit_response.json()["goal_id"]

    # Chat
    chat_payload = {
        "message": "What are the top hypotheses?",
        "goal_id": goal_id
    }

    response = client.post("/api/v1/chat", json=chat_payload)
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
```

### Step 8: Run and Test API (Day 7)

**Start API Server**:
```bash
# Start server
uvicorn src.api.main:app --reload --port 8000

# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

**Test with curl**:
```bash
# Submit goal
curl -X POST http://localhost:8000/goals \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Identify novel drug targets for AML treatment",
    "constraints": ["clinical feasibility"],
    "preferences": ["safety prioritized"]
  }'

# Get hypotheses
curl http://localhost:8000/goals/{goal_id}/hypotheses

# Get statistics
curl http://localhost:8000/goals/{goal_id}/stats
```

---

## Testing Checklist

- [ ] Health check endpoint works
- [ ] Submit goal endpoint creates goal
- [ ] Supervisor starts in background
- [ ] Get hypotheses returns paginated results
- [ ] Get hypothesis detail includes reviews
- [ ] Submit feedback stores feedback
- [ ] Get statistics returns metrics
- [ ] Chat endpoint responds with context
- [ ] API documentation auto-generated (FastAPI /docs)

---

## Success Criteria

**Week 4 Complete When**:

1. ✅ FastAPI application running
2. ✅ All 8+ endpoints functional
3. ✅ Background task management works
4. ✅ Chat interface responds with context
5. ✅ API tests pass
6. ✅ Documentation auto-generated
7. ✅ Committed and pushed to `phase4/api` branch

---

## Git Workflow

```bash
# Daily commits
git add .
git commit -m "feat(api): [description]"
git push origin phase4/api

# Example commits:
# Day 1: "feat(api): create API models and setup"
# Day 2: "feat(api): implement background task manager"
# Day 3: "feat(api): implement goal and hypothesis endpoints"
# Day 4: "feat(api): implement feedback and statistics endpoints"
# Day 5: "feat(api): implement chat interface"
# Day 6: "test(api): add comprehensive endpoint tests"
# Day 7: "docs(api): finalize API and deployment docs"
```

---

## Deployment Notes

**Production Considerations**:
- Use environment variables for secrets
- Configure CORS appropriately
- Add authentication/authorization
- Use HTTPS
- Add rate limiting
- Monitor with logging/metrics

**Docker Deployment** (optional):
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

Your mission: Build the interface that brings AI Co-Scientist to the world! 🌐
