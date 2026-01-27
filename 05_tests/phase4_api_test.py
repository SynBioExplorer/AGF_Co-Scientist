#!/usr/bin/env python3
"""Test FastAPI endpoints for AI Co-Scientist API

This test file validates the API endpoints without making actual LLM calls
by using mocked responses where needed.

Run with: pytest test_api.py -v
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_Architecture"))

from fastapi.testclient import TestClient

# Mock the LLM client before importing the app
mock_llm = MagicMock()
mock_llm.invoke.return_value = "Mock LLM response for testing"

with patch('src.llm.factory.get_llm_client', return_value=mock_llm):
    from src.api.main import app
    from src.storage.memory import storage

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_storage():
    """Clear storage before each test"""
    storage.clear_all()
    yield
    storage.clear_all()


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_returns_healthy(self):
        """Health endpoint should return healthy status"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["storage"] in ["connected", "disconnected"]
        assert "version" in data


class TestGoalEndpoints:
    """Test research goal endpoints"""

    def test_submit_goal_creates_goal(self):
        """Submitting a goal should create it and return processing status"""
        import asyncio
        payload = {
            "description": "Identify novel drug targets for acute myeloid leukemia treatment",
            "constraints": ["FDA-approved compounds only", "in vitro validation required"],
            "preferences": ["safety prioritized", "existing pathway knowledge"]
        }

        with patch('src.api.main.task_manager') as mock_task_manager:
            # Mock the async start_async_task method
            async def mock_start_async_task(*args, **kwargs):
                return "mock-task-id"
            mock_task_manager.start_async_task = MagicMock(side_effect=mock_start_async_task)

            response = client.post("/goals", json=payload)

        assert response.status_code == 200

        data = response.json()
        assert "goal_id" in data
        assert data["status"] == "processing"
        assert data["progress"]["hypotheses_generated"] == 0
        assert data["current_iteration"] == 0

    def test_submit_goal_validates_description_length(self):
        """Goal description must be at least 10 characters"""
        payload = {
            "description": "short",
            "constraints": [],
            "preferences": []
        }

        response = client.post("/goals", json=payload)
        assert response.status_code == 422  # Validation error

    def test_get_goal_status_not_found(self):
        """Getting non-existent goal should return 404"""
        response = client.get("/goals/nonexistent-goal-id")
        assert response.status_code == 404

    def test_get_goal_status_exists(self):
        """Getting existing goal should return status"""
        # First create a goal
        from schemas import ResearchGoal
        from src.utils.ids import generate_id

        goal = ResearchGoal(
            id=generate_id("goal"),
            description="Test research goal for API testing",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        response = client.get(f"/goals/{goal.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["goal_id"] == goal.id


class TestHypothesisEndpoints:
    """Test hypothesis endpoints"""

    def setup_test_data(self):
        """Create test goal and hypotheses"""
        from schemas import ResearchGoal, Hypothesis, GenerationMethod
        from src.utils.ids import generate_id

        goal = ResearchGoal(
            id=generate_id("goal"),
            description="Test research goal",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        # Create test hypotheses
        hypotheses = []
        for i in range(5):
            hyp = Hypothesis(
                id=generate_id("hyp"),
                research_goal_id=goal.id,
                title=f"Test Hypothesis {i+1}",
                summary=f"Summary of hypothesis {i+1}",
                hypothesis_statement=f"Statement for hypothesis {i+1}",
                rationale=f"Rationale for hypothesis {i+1}",
                generation_method=GenerationMethod.LITERATURE_EXPLORATION,
                elo_rating=1200.0 + (i * 50),  # Varying Elo ratings
            )
            storage.add_hypothesis(hyp)
            hypotheses.append(hyp)

        return goal, hypotheses

    def test_get_hypotheses_pagination(self):
        """Hypothesis list should be paginated"""
        goal, hypotheses = self.setup_test_data()

        response = client.get(f"/goals/{goal.id}/hypotheses?page=1&page_size=2")
        assert response.status_code == 200

        data = response.json()
        assert len(data["hypotheses"]) == 2
        assert data["total_count"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_get_hypotheses_sorted_by_elo(self):
        """Hypotheses should be sorted by Elo rating by default"""
        goal, hypotheses = self.setup_test_data()

        response = client.get(f"/goals/{goal.id}/hypotheses?sort_by=elo")
        assert response.status_code == 200

        data = response.json()
        ratings = [h["elo_rating"] for h in data["hypotheses"]]
        assert ratings == sorted(ratings, reverse=True)

    def test_get_hypothesis_detail(self):
        """Should return full hypothesis details"""
        goal, hypotheses = self.setup_test_data()
        hyp = hypotheses[0]

        response = client.get(f"/hypotheses/{hyp.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["hypothesis"]["id"] == hyp.id
        assert data["hypothesis"]["title"] == hyp.title
        assert "reviews" in data
        assert "tournament_record" in data

    def test_get_hypothesis_not_found(self):
        """Non-existent hypothesis should return 404"""
        response = client.get("/hypotheses/nonexistent-id")
        assert response.status_code == 404


class TestFeedbackEndpoints:
    """Test feedback endpoints"""

    def test_submit_feedback(self):
        """Submitting feedback should be accepted"""
        from schemas import ResearchGoal, Hypothesis, GenerationMethod
        from src.utils.ids import generate_id

        # Create test data
        goal = ResearchGoal(
            id=generate_id("goal"),
            description="Test goal",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        hyp = Hypothesis(
            id=generate_id("hyp"),
            research_goal_id=goal.id,
            title="Test Hypothesis",
            summary="Test summary",
            hypothesis_statement="Test statement",
            rationale="Test rationale",
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        )
        storage.add_hypothesis(hyp)

        payload = {
            "hypothesis_id": hyp.id,
            "rating": 4,
            "comments": "This is a promising hypothesis with good experimental design.",
            "suggested_modifications": "Consider adding a control group"
        }

        response = client.post(f"/hypotheses/{hyp.id}/feedback", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "feedback_received"
        assert data["hypothesis_id"] == hyp.id
        assert "feedback_id" in data

    def test_submit_feedback_invalid_hypothesis(self):
        """Feedback for non-existent hypothesis should fail"""
        payload = {
            "hypothesis_id": "nonexistent-id",
            "comments": "Test feedback"
        }

        response = client.post("/hypotheses/nonexistent-id/feedback", json=payload)
        assert response.status_code == 404


class TestStatisticsEndpoints:
    """Test statistics endpoints"""

    def test_get_statistics(self):
        """Should return statistics for a goal"""
        from schemas import ResearchGoal
        from src.utils.ids import generate_id

        goal = ResearchGoal(
            id=generate_id("goal"),
            description="Test goal",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        response = client.get(f"/goals/{goal.id}/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["goal_id"] == goal.id
        assert "hypotheses_generated" in data
        assert "total_matches" in data
        assert "tournament_convergence" in data

    def test_get_statistics_goal_not_found(self):
        """Statistics for non-existent goal should return 404"""
        response = client.get("/goals/nonexistent/stats")
        assert response.status_code == 404


class TestChatEndpoints:
    """Test chat endpoints"""

    def setup_chat_data(self):
        """Create test data for chat"""
        from schemas import ResearchGoal, Hypothesis, GenerationMethod
        from src.utils.ids import generate_id

        goal = ResearchGoal(
            id=generate_id("goal"),
            description="Test research goal for chat",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        hyp = Hypothesis(
            id=generate_id("hyp"),
            research_goal_id=goal.id,
            title="Test Hypothesis",
            summary="Test summary",
            hypothesis_statement="Test statement",
            rationale="Test rationale",
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
            elo_rating=1300.0,
        )
        storage.add_hypothesis(hyp)

        return goal, hyp

    def test_chat_endpoint(self):
        """Chat endpoint should return a response"""
        goal, hyp = self.setup_chat_data()

        payload = {
            "message": "What are the most promising hypotheses?",
            "goal_id": goal.id,
            "context_hypothesis_ids": []
        }

        with patch('src.api.chat.get_llm_client') as mock_get_llm:
            mock_client = MagicMock()
            mock_client.invoke.return_value = "Based on the current rankings, the top hypothesis is..."
            mock_get_llm.return_value = mock_client

            response = client.post("/api/v1/chat", json=payload)

        assert response.status_code == 200

        data = response.json()
        assert "message" in data
        assert "context_used" in data
        assert "timestamp" in data

    def test_chat_goal_not_found(self):
        """Chat for non-existent goal should return 404"""
        payload = {
            "message": "Test message",
            "goal_id": "nonexistent-goal",
            "context_hypothesis_ids": []
        }

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 404

    def test_get_chat_history(self):
        """Should return chat history for a goal"""
        goal, _ = self.setup_chat_data()

        response = client.get(f"/api/v1/chat/{goal.id}/history")
        assert response.status_code == 200

        data = response.json()
        assert data["goal_id"] == goal.id
        assert "messages" in data

    def test_clear_chat_history(self):
        """Should clear chat history for a goal"""
        goal, _ = self.setup_chat_data()

        response = client.delete(f"/api/v1/chat/{goal.id}/history")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "cleared"


class TestTaskEndpoints:
    """Test task management endpoints"""

    def test_get_task_not_found(self):
        """Getting non-existent task should return 404"""
        response = client.get("/tasks/nonexistent-task-id")
        assert response.status_code == 404

    def test_cancel_task_not_found(self):
        """Cancelling non-existent task should return 404"""
        response = client.post("/tasks/nonexistent-task-id/cancel")
        assert response.status_code == 404


class TestOverviewEndpoint:
    """Test research overview endpoint"""

    def test_overview_not_ready(self):
        """Overview should return error when workflow not complete"""
        from schemas import ResearchGoal
        from src.utils.ids import generate_id

        goal = ResearchGoal(
            id=generate_id("goal"),
            description="Test goal",
            constraints=[],
            preferences=[],
        )
        storage.add_research_goal(goal)

        response = client.get(f"/goals/{goal.id}/overview")
        assert response.status_code == 400  # Not yet available

    def test_overview_goal_not_found(self):
        """Overview for non-existent goal should return 404"""
        response = client.get("/goals/nonexistent/overview")
        assert response.status_code == 404


if __name__ == "__main__":
    print("=" * 60)
    print("AI Co-Scientist API Test Suite")
    print("=" * 60)
    print()

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
