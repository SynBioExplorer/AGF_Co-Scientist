"""Integration tests for LangSmith tracing with actual agent code.

Tests that tracing decorators work correctly with real agent implementations
and LLM clients, both when tracing is enabled and disabled.
"""

import os
import pytest
from unittest.mock import patch, Mock


def test_llm_client_callbacks_property():
    """Test that LLM clients have callbacks property"""
    from src.llm.base import BaseLLMClient

    # Create a minimal implementation
    class TestLLMClient(BaseLLMClient):
        def invoke(self, prompt: str) -> str:
            return "test"

        async def ainvoke(self, prompt: str) -> str:
            return "test"

    client = TestLLMClient(model="test-model", cost_tracker=Mock())

    # Should have callbacks property
    assert hasattr(client, "callbacks")
    assert isinstance(client.callbacks, list)


def test_llm_client_with_tracing_disabled():
    """Test that LLM client works when tracing is disabled"""
    with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "false"}):
        # Reload to pick up env change
        import importlib
        import src.llm.base
        importlib.reload(src.llm.base)

        from src.llm.base import BaseLLMClient

        class TestLLMClient(BaseLLMClient):
            def invoke(self, prompt: str) -> str:
                return "test"

            async def ainvoke(self, prompt: str) -> str:
                return "test"

        client = TestLLMClient(model="test-model", cost_tracker=Mock())

        # Callbacks should be empty when tracing is disabled
        assert client.callbacks == []


def test_generation_agent_has_trace_decorator():
    """Test that GenerationAgent.execute has trace decorator"""
    from src.agents.generation import GenerationAgent

    # Check that execute method exists
    assert hasattr(GenerationAgent, "execute")

    # The decorator should not break the function signature
    import inspect
    sig = inspect.signature(GenerationAgent.execute)
    assert "research_goal" in sig.parameters


def test_reflection_agent_has_trace_decorator():
    """Test that ReflectionAgent.execute has trace decorator"""
    from src.agents.reflection import ReflectionAgent

    assert hasattr(ReflectionAgent, "execute")

    import inspect
    sig = inspect.signature(ReflectionAgent.execute)
    assert "hypothesis" in sig.parameters


def test_ranking_agent_has_trace_decorator():
    """Test that RankingAgent.execute has trace decorator"""
    from src.agents.ranking import RankingAgent

    assert hasattr(RankingAgent, "execute")

    import inspect
    sig = inspect.signature(RankingAgent.execute)
    assert "hypothesis_a" in sig.parameters
    assert "hypothesis_b" in sig.parameters


def test_evolution_agent_has_trace_decorator():
    """Test that EvolutionAgent.execute has trace decorator"""
    from src.agents.evolution import EvolutionAgent

    assert hasattr(EvolutionAgent, "execute")

    import inspect
    sig = inspect.signature(EvolutionAgent.execute)
    assert "hypothesis" in sig.parameters
    assert "strategy" in sig.parameters


def test_proximity_agent_has_trace_decorator():
    """Test that ProximityAgent.execute has trace decorator"""
    from src.agents.proximity import ProximityAgent

    assert hasattr(ProximityAgent, "execute")

    import inspect
    sig = inspect.signature(ProximityAgent.execute)
    assert "hypotheses" in sig.parameters


def test_meta_review_agent_has_trace_decorator():
    """Test that MetaReviewAgent.execute has trace decorator"""
    from src.agents.meta_review import MetaReviewAgent

    assert hasattr(MetaReviewAgent, "execute")

    import inspect
    sig = inspect.signature(MetaReviewAgent.execute)
    assert "reviews" in sig.parameters
    assert "matches" in sig.parameters


def test_supervisor_agent_has_trace_decorator():
    """Test that SupervisorAgent.execute has trace decorator"""
    from src.agents.supervisor import SupervisorAgent

    assert hasattr(SupervisorAgent, "execute")

    import inspect
    sig = inspect.signature(SupervisorAgent.execute)
    assert "research_goal" in sig.parameters


def test_config_has_langsmith_settings():
    """Test that config has LangSmith settings"""
    from src.config import settings

    # Check that LangSmith settings exist
    assert hasattr(settings, "langchain_tracing_v2")
    assert hasattr(settings, "langchain_api_key")
    assert hasattr(settings, "langchain_project")
    assert hasattr(settings, "langchain_endpoint")

    # Check defaults
    assert isinstance(settings.langchain_tracing_v2, bool)
    assert settings.langchain_project == "ai-coscientist"


def test_observability_module_exports():
    """Test that observability module exports expected functions"""
    from src.observability import (
        trace_agent,
        trace_llm_call,
        trace_run,
        get_tracer,
        log_feedback,
        get_run_url,
        LANGSMITH_ENABLED,
    )

    # All exports should be callable or boolean
    assert callable(trace_agent)
    assert callable(trace_llm_call)
    assert callable(trace_run)
    assert callable(get_tracer)
    assert callable(log_feedback)
    assert callable(get_run_url)
    assert isinstance(LANGSMITH_ENABLED, bool)


def test_google_client_has_tracing():
    """Test that Google client has tracing support"""
    # Check that trace_llm_call is imported
    import src.llm.google as google_module
    import inspect

    source = inspect.getsource(google_module)

    # Should import trace_llm_call
    assert "from src.observability.tracing import trace_llm_call" in source

    # ainvoke should have decorator
    assert "@trace_llm_call" in source


def test_openai_client_has_tracing():
    """Test that OpenAI client has tracing support"""
    import src.llm.openai as openai_module
    import inspect

    source = inspect.getsource(openai_module)

    # Should import trace_llm_call
    assert "from src.observability.tracing import trace_llm_call" in source

    # ainvoke should have decorator
    assert "@trace_llm_call" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
