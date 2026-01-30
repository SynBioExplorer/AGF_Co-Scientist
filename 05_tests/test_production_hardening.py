"""Tests for production hardening fixes.

This module tests the reliability improvements made for production deployment:
- LLM retry logic with exponential backoff
- Budget tracking race condition fixes
- Memory cleanup mechanisms
- Safety agent integration
- Timeout handling
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from threading import Thread
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_architecture"))


class TestRetryLogic:
    """Test LLM retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Verify retry occurs on 429 rate limit errors."""
        from src.utils.retry import retry_async, is_retryable_error
        from src.utils.errors import LLMRateLimitError

        # Mock function that fails twice then succeeds
        call_count = 0

        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("429 Too Many Requests")
            return "success"

        result = await retry_async(
            flaky_function,
            max_retries=3,
            base_delay=0.01,  # Fast for testing
            timeout=5.0
        )

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded third time

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self):
        """Verify timeout triggers retry."""
        from src.utils.retry import retry_async
        from src.utils.errors import LLMTimeoutError

        call_count = 0

        async def slow_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                await asyncio.sleep(10)  # Will timeout
            return "success"

        result = await retry_async(
            slow_function,
            max_retries=2,
            base_delay=0.01,
            timeout=0.1  # Short timeout
        )

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Verify proper exception after all retries exhausted."""
        from src.utils.retry import retry_async
        from src.utils.errors import LLMRateLimitError

        async def always_fails():
            raise Exception("429 Rate Limited")

        with pytest.raises(Exception) as exc_info:
            await retry_async(
                always_fails,
                max_retries=2,
                base_delay=0.01,
                timeout=1.0
            )

        # Should have tried 3 times (initial + 2 retries)

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self):
        """Verify non-retryable errors are raised immediately."""
        from src.utils.retry import retry_async

        call_count = 0

        async def auth_error():
            nonlocal call_count
            call_count += 1
            raise Exception("Invalid API key")

        with pytest.raises(Exception):
            await retry_async(
                auth_error,
                max_retries=3,
                base_delay=0.01,
                timeout=1.0
            )

        # Should only try once for non-retryable error
        assert call_count == 1

    def test_is_retryable_error(self):
        """Test error classification."""
        from src.utils.retry import is_retryable_error

        # Retryable errors
        assert is_retryable_error(Exception("429 Too Many Requests"))
        assert is_retryable_error(Exception("Rate limit exceeded"))
        assert is_retryable_error(Exception("timeout error"))
        assert is_retryable_error(Exception("503 Service Unavailable"))
        assert is_retryable_error(Exception("Connection reset"))

        # Non-retryable errors
        assert not is_retryable_error(Exception("Invalid API key"))
        assert not is_retryable_error(Exception("Malformed request"))
        assert not is_retryable_error(ValueError("Bad value"))


class TestBudgetRaceCondition:
    """Test budget tracking thread safety."""

    def test_concurrent_budget_check_and_add(self):
        """Verify no race condition with concurrent budget operations."""
        sys.path.append(str(project_root / "04_Scripts"))
        from cost_tracker import CostTracker, BudgetExceededError

        # Create tracker with very small budget to ensure we hit the limit
        tracker = CostTracker(budget_aud=0.01, persist_path=None)

        # Track actual costs added
        costs_added = []
        errors = []

        def add_usage_worker():
            """Worker that tries to add usage."""
            try:
                # Each call costs ~0.02 AUD with this model/tokens
                cost = tracker.check_and_add_usage(
                    agent="test",
                    model="gemini-3-pro-preview",  # Higher cost model
                    input_tokens=5000,
                    output_tokens=1000
                )
                costs_added.append(cost)
            except BudgetExceededError:
                errors.append("budget_exceeded")
            except Exception as e:
                errors.append(str(e))

        # Launch many concurrent threads
        threads = [Thread(target=add_usage_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Budget should not be exceeded significantly
        total_cost = tracker.total_cost_aud
        # With atomic check_and_add, we should never exceed by more than 1 call
        assert total_cost <= tracker.budget_aud + 0.05  # Small margin for single overage

        # At least one call should succeed or fail
        assert len(costs_added) + len(errors) == 10  # All threads completed

    def test_atomic_check_and_add_usage(self):
        """Verify check_and_add_usage is atomic."""
        sys.path.append(str(project_root / "04_Scripts"))
        from cost_tracker import CostTracker, BudgetExceededError

        tracker = CostTracker(budget_aud=0.05, persist_path=None)

        # First call should succeed
        cost1 = tracker.check_and_add_usage(
            agent="test",
            model="gemini-2.0-flash",
            input_tokens=50000,
            output_tokens=50000
        )
        assert cost1 > 0

        # Second call should fail (would exceed budget)
        with pytest.raises(BudgetExceededError):
            tracker.check_and_add_usage(
                agent="test",
                model="gemini-2.0-flash",
                input_tokens=50000,
                output_tokens=50000
            )


class TestMemoryCleanup:
    """Test memory cleanup mechanisms."""

    @pytest.mark.asyncio
    async def test_task_cleanup(self):
        """Verify old tasks are cleaned up."""
        # Import directly to avoid FastAPI dependency from __init__.py
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "background",
            project_root / "src" / "api" / "background.py"
        )
        background_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(background_module)
        BackgroundTaskManager = background_module.BackgroundTaskManager

        manager = BackgroundTaskManager(max_workers=2)

        # Create a task
        task_id = await manager.start_async_task(
            goal_id="test-goal",
            coroutine=asyncio.sleep(0.01)
        )

        # Wait for completion
        await asyncio.sleep(0.1)

        # Verify task exists
        status = manager.get_task_status(task_id)
        assert status is not None
        assert status["status"] == "completed"

        # Cleanup with max_age_hours=0 should remove it
        cleaned = manager.cleanup_completed_tasks(max_age_hours=0)
        assert cleaned == 1

        # Task should be gone
        status = manager.get_task_status(task_id)
        assert status is None

        manager.shutdown()

    def test_chat_history_limit(self):
        """Verify chat history respects per-goal limits."""
        try:
            from src.api.chat import add_chat_message, get_chat_history, _chat_history
            from schemas import ChatMessage
        except ImportError:
            pytest.skip("FastAPI not installed")

        # Clear existing history
        _chat_history.clear()

        goal_id = "test-goal-limit"

        # Add more messages than the limit
        # Note: We'll need to temporarily lower the limit for testing
        with patch('src.config.settings.chat_history_max_messages', 5):
            for i in range(10):
                msg = ChatMessage(
                    id=f"msg-{i}",
                    role="scientist",
                    content=f"Message {i}",
                    hypothesis_references=[],
                )
                add_chat_message(goal_id, msg)

            # Should only have the limit number of messages
            history = get_chat_history(goal_id)
            assert len(history) == 5
            # Should have the most recent messages (5-9)
            assert history[0].content == "Message 5"
            assert history[-1].content == "Message 9"

    def test_chat_cleanup_old_history(self):
        """Verify old chat history is cleaned up."""
        try:
            from src.api.chat import (
                add_chat_message,
                cleanup_old_history,
                _chat_history,
                _chat_timestamps
            )
            from schemas import ChatMessage
        except ImportError:
            pytest.skip("FastAPI not installed")

        # Clear existing data
        _chat_history.clear()
        _chat_timestamps.clear()

        goal_id = "old-goal"

        # Add a message
        msg = ChatMessage(
            id="msg-old",
            role="scientist",
            content="Old message",
            hypothesis_references=[],
        )
        add_chat_message(goal_id, msg)

        # Manually set timestamp to old
        _chat_timestamps[goal_id] = datetime.utcnow() - timedelta(hours=200)

        # Cleanup should remove it
        cleaned = cleanup_old_history(max_age_hours=168)
        assert cleaned == 1
        assert goal_id not in _chat_history


class TestSafetyIntegration:
    """Test safety agent integration."""

    @pytest.mark.asyncio
    async def test_safety_agent_review(self):
        """Verify safety agent can review hypotheses."""
        from src.agents.safety import SafetyAgent
        from schemas import Hypothesis, ExperimentalProtocol, GenerationMethod

        # Create a hypothesis
        hypothesis = Hypothesis(
            id="test-hyp",
            research_goal_id="test-goal",
            title="Test Hypothesis",
            summary="A safe test hypothesis",
            hypothesis_statement="Testing is good for code quality.",
            rationale="Testing catches bugs early.",
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
            experimental_protocol=ExperimentalProtocol(
                objective="Test the code",
                methodology="Write unit tests",
                materials=["pytest", "mock"],
                controls=["Baseline comparison"],
                success_criteria="All tests pass"
            ),
            elo_rating=1200.0
        )

        safety_agent = SafetyAgent()

        # This will actually call the LLM, so we'll mock it
        with patch.object(safety_agent.llm_client, 'ainvoke') as mock_invoke:
            mock_invoke.return_value = '''
            {
                "safety_score": 0.95,
                "risks": [],
                "mitigations": [],
                "requires_special_approval": false,
                "hazard_categories": {
                    "chemical": 0.0,
                    "biological": 0.0,
                    "physical": 0.0,
                    "regulatory": 0.1
                }
            }
            '''

            result = await safety_agent.review_hypothesis(hypothesis)

            assert "safety_score" in result
            assert safety_agent.is_safe(result, threshold=0.5)

    def test_safety_threshold_config(self):
        """Verify safety threshold is configurable."""
        from src.config import settings

        # Should have safety_threshold setting
        assert hasattr(settings, 'safety_threshold')
        assert 0.0 <= settings.safety_threshold <= 1.0


class TestTimeoutHandling:
    """Test timeout handling in various components."""

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Verify health check has timeout protection."""
        # This is a structural test - verifies the code exists
        try:
            from src.storage.postgres import PostgreSQLStorage

            storage = PostgreSQLStorage()

            # Without a connection, health check should fail gracefully
            result = await storage.health_check()
            assert result is False
        except (ImportError, AttributeError):
            # asyncpg not installed - skip this test
            # AttributeError occurs when asyncpg=None and we try to access asyncpg.Pool
            pytest.skip("asyncpg not installed")

    def test_supervisor_timeout_config(self):
        """Verify supervisor timeout is configurable."""
        from src.config import settings

        assert hasattr(settings, 'supervisor_iteration_timeout')
        assert settings.supervisor_iteration_timeout > 0
        assert hasattr(settings, 'llm_timeout_seconds')
        assert settings.llm_timeout_seconds > 0


class TestErrorClassification:
    """Test error exception hierarchy."""

    def test_error_hierarchy(self):
        """Verify error class hierarchy is correct."""
        from src.utils.errors import (
            CoScientistError,
            LLMClientError,
            RetryableError,
            LLMTimeoutError,
            LLMRateLimitError,
        )

        # RetryableError should be subclass of LLMClientError
        assert issubclass(RetryableError, LLMClientError)
        assert issubclass(LLMTimeoutError, RetryableError)
        assert issubclass(LLMRateLimitError, RetryableError)

        # All should be subclass of base error
        assert issubclass(LLMClientError, CoScientistError)

    def test_error_messages(self):
        """Verify error messages are informative."""
        from src.utils.errors import LLMTimeoutError, LLMRateLimitError

        timeout_err = LLMTimeoutError("Request timed out after 300s")
        assert "300s" in str(timeout_err)

        rate_err = LLMRateLimitError("429 Too Many Requests")
        assert "429" in str(rate_err)


class TestConfigurationSettings:
    """Test new configuration settings exist and have valid defaults."""

    def test_llm_settings_exist(self):
        """Verify LLM retry/timeout settings exist."""
        from src.config import settings

        assert hasattr(settings, 'llm_timeout_seconds')
        assert hasattr(settings, 'llm_max_retries')
        assert hasattr(settings, 'llm_retry_base_delay')
        assert hasattr(settings, 'llm_retry_max_delay')

        # Verify reasonable defaults
        assert settings.llm_timeout_seconds >= 60  # At least 1 minute
        assert settings.llm_max_retries >= 1
        assert settings.llm_retry_base_delay > 0
        assert settings.llm_retry_max_delay >= settings.llm_retry_base_delay

    def test_cleanup_settings_exist(self):
        """Verify cleanup settings exist."""
        from src.config import settings

        assert hasattr(settings, 'task_cleanup_interval_hours')
        assert hasattr(settings, 'task_max_age_hours')
        assert hasattr(settings, 'chat_history_max_messages')
        assert hasattr(settings, 'chat_history_max_age_hours')

        # Verify reasonable defaults
        assert settings.task_cleanup_interval_hours >= 1
        assert settings.task_max_age_hours >= 1
        assert settings.chat_history_max_messages >= 100
        assert settings.chat_history_max_age_hours >= 24


class TestHypothesisStatus:
    """Test hypothesis status enum includes safety status."""

    def test_requires_safety_review_status(self):
        """Verify REQUIRES_SAFETY_REVIEW status exists."""
        from schemas import HypothesisStatus

        assert hasattr(HypothesisStatus, 'REQUIRES_SAFETY_REVIEW')
        assert HypothesisStatus.REQUIRES_SAFETY_REVIEW.value == "requires_safety_review"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
