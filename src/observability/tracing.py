"""LangSmith tracing utilities for LLM observability.

This module provides decorators and context managers for tracing agent
executions and LLM calls. Tracing is automatically enabled when
LANGSMITH_TRACING=true (or legacy LANGCHAIN_TRACING_V2=true) is set.
"""

import os
import functools
from contextlib import contextmanager
from typing import Any, Dict, Optional, List, Callable
from datetime import datetime
import structlog

logger = structlog.get_logger()

# Check if LangSmith is enabled via environment variable (new or legacy)
LANGSMITH_ENABLED = (
    os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    or os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
)

# Sync legacy env vars from new LANGSMITH_ vars so langchain internals see them
if LANGSMITH_ENABLED:
    if os.getenv("LANGSMITH_API_KEY") and not os.getenv("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_API_KEY"] = os.environ["LANGSMITH_API_KEY"]
    if os.getenv("LANGSMITH_ENDPOINT") and not os.getenv("LANGCHAIN_ENDPOINT"):
        os.environ["LANGCHAIN_ENDPOINT"] = os.environ["LANGSMITH_ENDPOINT"]
    if os.getenv("LANGSMITH_PROJECT") and not os.getenv("LANGCHAIN_PROJECT"):
        os.environ["LANGCHAIN_PROJECT"] = os.environ["LANGSMITH_PROJECT"]
    # Ensure LANGCHAIN_TRACING_V2 is set for langchain internals
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

# Import LangSmith only if enabled to avoid import errors
if LANGSMITH_ENABLED:
    try:
        from langsmith import Client
        from langsmith import trace as langsmith_trace
        from langchain_core.tracers.langchain import LangChainTracer

        # Initialize LangSmith client
        langsmith_client = Client()
        logger.info("langsmith_enabled", project=os.getenv("LANGSMITH_PROJECT", os.getenv("LANGCHAIN_PROJECT", "ai-coscientist")))
    except ImportError as e:
        logger.warning(
            "langsmith_import_failed",
            error=str(e),
            message="Install langsmith: pip install langsmith"
        )
        LANGSMITH_ENABLED = False
        langsmith_client = None
        langsmith_trace = None
else:
    langsmith_client = None
    langsmith_trace = None
    logger.info("langsmith_disabled")


def get_tracer(project_name: Optional[str] = None) -> Optional[Any]:
    """Get a LangChain tracer for the given project.

    Args:
        project_name: Optional project name override. Defaults to env var.

    Returns:
        LangChainTracer instance if enabled, None otherwise.
    """
    if not LANGSMITH_ENABLED:
        return None

    try:
        project = project_name or os.getenv("LANGCHAIN_PROJECT", "ai-coscientist")
        return LangChainTracer(project_name=project)
    except Exception as e:
        logger.warning("tracer_creation_failed", error=str(e))
        return None


@contextmanager
def trace_run(
    name: str,
    run_type: str = "chain",
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
):
    """Context manager for tracing a logical run.

    Args:
        name: Name of the run (e.g., "hypothesis_generation")
        run_type: Type of run ("chain", "llm", "tool", "retriever")
        metadata: Additional metadata to attach to the run
        tags: Tags for filtering and organization

    Example:
        with trace_run("generate_hypothesis", metadata={"goal_id": "abc"}):
            result = generate_hypothesis(goal)
    """
    if not LANGSMITH_ENABLED or langsmith_trace is None:
        # No-op when tracing is disabled or langsmith unavailable
        yield None
        return

    try:
        # langsmith.trace is sync/async-safe (contextvar-based, not an async
        # context manager) — unlike tracing_v2_enabled which crashes when
        # entered from sync code inside an async event loop. LangChainTracer
        # callbacks on LLM clients pick up this parent span automatically
        # via contextvars, restoring per-agent hierarchy in the UI.
        with langsmith_trace(
            name=name,
            run_type=run_type,
            metadata=metadata or {},
            tags=tags or [],
        ):
            yield None
    except Exception as e:
        # A @contextmanager generator must yield exactly once. If an exception
        # propagates into our `yield` via .throw(), we log and re-raise so the
        # caller sees the original error (e.g. parse_llm_json truncation).
        # Yielding a second time here would raise "generator didn't stop after
        # throw()" and mask the real exception.
        logger.warning("trace_run_failed", name=name, error=str(e))
        raise


def trace_agent(agent_name: str) -> Callable:
    """Decorator for tracing agent executions.

    Wraps agent execute/run methods to automatically trace their execution
    in LangSmith. Captures inputs, outputs, duration, and errors.

    Args:
        agent_name: Name of the agent (e.g., "GenerationAgent")

    Example:
        class GenerationAgent:
            @trace_agent("GenerationAgent")
            def execute(self, research_goal):
                ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not LANGSMITH_ENABLED:
                # No-op when disabled
                return func(*args, **kwargs)

            # Extract metadata from kwargs
            metadata = {
                "agent_name": agent_name,
                "function": func.__name__,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Add any IDs from kwargs
            for key in ["research_goal", "hypothesis", "goal_id", "hypothesis_id"]:
                if key in kwargs:
                    value = kwargs[key]
                    # Extract ID if it's a Pydantic model
                    if hasattr(value, "id"):
                        metadata[f"{key}_id"] = value.id
                    elif isinstance(value, str):
                        metadata[key] = value

            tags = [agent_name, func.__name__]

            try:
                with trace_run(
                    name=f"{agent_name}.{func.__name__}",
                    run_type="chain",
                    metadata=metadata,
                    tags=tags
                ):
                    result = func(*args, **kwargs)
                    return result
            except Exception as e:
                logger.error(
                    "agent_execution_error",
                    agent=agent_name,
                    function=func.__name__,
                    error=str(e)
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not LANGSMITH_ENABLED:
                # No-op when disabled
                return await func(*args, **kwargs)

            # Extract metadata from kwargs
            metadata = {
                "agent_name": agent_name,
                "function": func.__name__,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Add any IDs from kwargs
            for key in ["research_goal", "hypothesis", "goal_id", "hypothesis_id"]:
                if key in kwargs:
                    value = kwargs[key]
                    # Extract ID if it's a Pydantic model
                    if hasattr(value, "id"):
                        metadata[f"{key}_id"] = value.id
                    elif isinstance(value, str):
                        metadata[key] = value

            tags = [agent_name, func.__name__]

            try:
                with trace_run(
                    name=f"{agent_name}.{func.__name__}",
                    run_type="chain",
                    metadata=metadata,
                    tags=tags
                ):
                    result = await func(*args, **kwargs)
                    return result
            except Exception as e:
                logger.error(
                    "agent_execution_error",
                    agent=agent_name,
                    function=func.__name__,
                    error=str(e)
                )
                raise

        # Return async or sync wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


def trace_llm_call(provider: str, model: str) -> Callable:
    """Decorator for tracing LLM API calls.

    Wraps LLM client invoke/ainvoke methods to track token usage,
    latency, and costs.

    Args:
        provider: LLM provider (e.g., "google", "openai")
        model: Model name (e.g., "gemini-3-pro-preview")

    Example:
        @trace_llm_call("google", "gemini-3-pro-preview")
        async def ainvoke(self, prompt: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not LANGSMITH_ENABLED:
                return func(*args, **kwargs)

            metadata = {
                "provider": provider,
                "model": model,
                "timestamp": datetime.utcnow().isoformat(),
            }
            tags = [provider, model, "llm_call"]

            with trace_run(
                name=f"llm.{provider}.{model}",
                run_type="llm",
                metadata=metadata,
                tags=tags
            ):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not LANGSMITH_ENABLED:
                return await func(*args, **kwargs)

            metadata = {
                "provider": provider,
                "model": model,
                "timestamp": datetime.utcnow().isoformat(),
            }
            tags = [provider, model, "llm_call"]

            with trace_run(
                name=f"llm.{provider}.{model}",
                run_type="llm",
                metadata=metadata,
                tags=tags
            ):
                return await func(*args, **kwargs)

        # Return async or sync wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


def log_feedback(
    run_id: str,
    score: float,
    comment: Optional[str] = None,
    feedback_type: str = "human"
) -> bool:
    """Log user feedback for a specific run.

    Args:
        run_id: LangSmith run ID to attach feedback to
        score: Numeric score (0.0 to 1.0)
        comment: Optional text feedback
        feedback_type: Type of feedback ("human", "auto", "scientist")

    Returns:
        True if feedback was logged successfully, False otherwise.
    """
    if not LANGSMITH_ENABLED or not langsmith_client:
        return False

    try:
        langsmith_client.create_feedback(
            run_id=run_id,
            key=feedback_type,
            score=score,
            comment=comment,
        )
        logger.info(
            "feedback_logged",
            run_id=run_id,
            score=score,
            type=feedback_type
        )
        return True
    except Exception as e:
        logger.warning("feedback_logging_failed", error=str(e))
        return False


def get_run_url(run_id: str) -> Optional[str]:
    """Get the LangSmith URL for a specific run.

    Args:
        run_id: LangSmith run ID

    Returns:
        URL to view the run in LangSmith, or None if disabled.
    """
    if not LANGSMITH_ENABLED:
        return None

    project = os.getenv("LANGCHAIN_PROJECT", "ai-coscientist")
    endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    # Convert API endpoint to web endpoint
    web_endpoint = endpoint.replace("api.", "")
    return f"{web_endpoint}/public/{project}/r/{run_id}"
