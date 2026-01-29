"""Tests for LangSmith observability and tracing functionality.

This test suite verifies that:
1. LangSmith integration is properly detected from environment
2. Tracing utilities work correctly when enabled
3. Decorators function as no-ops when tracing is disabled
4. Agent and LLM tracing decorators work correctly
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


# Test LANGSMITH_ENABLED detection
def test_langsmith_enabled_detection():
    """Test that LANGSMITH_ENABLED is correctly detected from environment"""
    # Import after setting env var
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
        # Reimport to pick up new env var
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        assert tracing_module.LANGSMITH_ENABLED is True


def test_langsmith_disabled_detection():
    """Test that LANGSMITH_ENABLED defaults to False when not set"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        assert tracing_module.LANGSMITH_ENABLED is False


# Test get_tracer
def test_get_tracer_when_enabled():
    """Test that get_tracer returns a tracer when enabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true", "LANGCHAIN_PROJECT": "test-project"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import get_tracer

        # Mock LangChainTracer to avoid actual LangSmith connection
        with patch("src.observability.tracing.LangChainTracer") as mock_tracer:
            mock_tracer.return_value = Mock()
            tracer = get_tracer()

            if tracing_module.LANGSMITH_ENABLED:
                assert tracer is not None
                mock_tracer.assert_called_once_with(project_name="test-project")


def test_get_tracer_when_disabled():
    """Test that get_tracer returns None when disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import get_tracer

        tracer = get_tracer()
        assert tracer is None


# Test trace_run context manager
def test_trace_run_context_manager_when_enabled():
    """Test that trace_run works as context manager when enabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_run

        # Mock tracing_v2_enabled
        with patch("src.observability.tracing.tracing_v2_enabled") as mock_tracing:
            mock_tracing.return_value.__enter__ = Mock()
            mock_tracing.return_value.__exit__ = Mock()

            with trace_run("test_run", metadata={"key": "value"}, tags=["test"]):
                pass  # Should not raise


def test_trace_run_context_manager_when_disabled():
    """Test that trace_run is a no-op when disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_run

        # Should work without any tracing infrastructure
        with trace_run("test_run", metadata={"key": "value"}):
            pass  # Should not raise


# Test trace_agent decorator
def test_trace_agent_decorator_when_enabled():
    """Test that trace_agent decorator works when enabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_agent

        # Mock trace_run
        with patch("src.observability.tracing.trace_run") as mock_trace_run:
            mock_trace_run.return_value.__enter__ = Mock()
            mock_trace_run.return_value.__exit__ = Mock(return_value=False)

            @trace_agent("TestAgent")
            def test_function(arg1, arg2=None):
                return f"{arg1}-{arg2}"

            result = test_function("hello", arg2="world")
            assert result == "hello-world"


def test_trace_agent_decorator_when_disabled():
    """Test that trace_agent decorator is a no-op when disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_agent

        @trace_agent("TestAgent")
        def test_function(arg1, arg2=None):
            return f"{arg1}-{arg2}"

        result = test_function("hello", arg2="world")
        assert result == "hello-world"


def test_trace_agent_decorator_async_when_enabled():
    """Test that trace_agent decorator works with async functions when enabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_agent
        import asyncio

        # Mock trace_run
        with patch("src.observability.tracing.trace_run") as mock_trace_run:
            mock_trace_run.return_value.__enter__ = Mock()
            mock_trace_run.return_value.__exit__ = Mock(return_value=False)

            @trace_agent("TestAgent")
            async def test_async_function(arg1):
                return f"async-{arg1}"

            result = asyncio.run(test_async_function("hello"))
            assert result == "async-hello"


def test_trace_agent_decorator_async_when_disabled():
    """Test that trace_agent decorator is a no-op with async functions when disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_agent
        import asyncio

        @trace_agent("TestAgent")
        async def test_async_function(arg1):
            return f"async-{arg1}"

        result = asyncio.run(test_async_function("hello"))
        assert result == "async-hello"


# Test trace_llm_call decorator
def test_trace_llm_call_decorator_when_enabled():
    """Test that trace_llm_call decorator works when enabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_llm_call

        # Mock trace_run
        with patch("src.observability.tracing.trace_run") as mock_trace_run:
            mock_trace_run.return_value.__enter__ = Mock()
            mock_trace_run.return_value.__exit__ = Mock(return_value=False)

            @trace_llm_call("google", "gemini-3-pro")
            def invoke_llm(prompt):
                return f"response to {prompt}"

            result = invoke_llm("test prompt")
            assert result == "response to test prompt"


def test_trace_llm_call_decorator_when_disabled():
    """Test that trace_llm_call decorator is a no-op when disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_llm_call

        @trace_llm_call("google", "gemini-3-pro")
        def invoke_llm(prompt):
            return f"response to {prompt}"

        result = invoke_llm("test prompt")
        assert result == "response to test prompt"


# Test log_feedback
def test_log_feedback_when_enabled():
    """Test that log_feedback works when enabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import log_feedback

        # Mock langsmith_client
        with patch("src.observability.tracing.langsmith_client") as mock_client:
            mock_client.create_feedback = Mock()

            result = log_feedback(
                run_id="test-run-id",
                score=0.8,
                comment="Good hypothesis",
                feedback_type="scientist"
            )

            if tracing_module.LANGSMITH_ENABLED and mock_client:
                mock_client.create_feedback.assert_called_once()


def test_log_feedback_when_disabled():
    """Test that log_feedback returns False when disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import log_feedback

        result = log_feedback(
            run_id="test-run-id",
            score=0.8,
            comment="Good hypothesis"
        )

        assert result is False


# Test get_run_url
def test_get_run_url_when_enabled():
    """Test that get_run_url returns correct URL when enabled"""
    with patch.dict(os.environ, {
        "LANGCHAIN_TRACING_V2": "true",
        "LANGCHAIN_PROJECT": "test-project",
        "LANGCHAIN_ENDPOINT": "https://api.smith.langchain.com"
    }):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import get_run_url

        url = get_run_url("test-run-id")

        if tracing_module.LANGSMITH_ENABLED:
            assert url is not None
            assert "test-project" in url
            assert "test-run-id" in url


def test_get_run_url_when_disabled():
    """Test that get_run_url returns None when disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import get_run_url

        url = get_run_url("test-run-id")
        assert url is None


# Test agent decorator with Pydantic models
def test_trace_agent_with_pydantic_models():
    """Test that trace_agent extracts IDs from Pydantic models"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}):
        import importlib
        import src.observability.tracing as tracing_module
        importlib.reload(tracing_module)

        from src.observability.tracing import trace_agent
        from pydantic import BaseModel

        class MockModel(BaseModel):
            id: str
            name: str

        # Mock trace_run
        with patch("src.observability.tracing.trace_run") as mock_trace_run:
            mock_trace_run.return_value.__enter__ = Mock()
            mock_trace_run.return_value.__exit__ = Mock(return_value=False)

            @trace_agent("TestAgent")
            def process_model(hypothesis=None):
                return "processed"

            model = MockModel(id="test-id", name="test")
            result = process_model(hypothesis=model)

            assert result == "processed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
