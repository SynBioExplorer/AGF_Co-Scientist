# Phase 5F: Observability with LangSmith

## Overview

Integrate LangSmith for LLM tracing, debugging, and cost monitoring. LangSmith provides visibility into all LangChain operations including agent executions, prompt/response pairs, and token usage.

**Dependencies:** None (standalone)
**Documentation:** https://docs.smith.langchain.com/

## Why LangSmith

| Feature | Benefit |
|---------|---------|
| Trace Visualization | See full agent execution flow |
| Prompt Debugging | View exact prompts sent to LLMs |
| Response Analysis | Analyze model outputs |
| Cost Tracking | Monitor token usage and costs |
| Latency Metrics | Identify slow operations |
| Error Debugging | Pinpoint failures in agent chains |

## Setup

### 1. Create LangSmith Account

1. Go to https://smith.langchain.com/
2. Create account / sign in
3. Create a new project (e.g., "ai-co-scientist")
4. Copy your API key

### 2. Environment Variables

Add to `03_architecture/.env`:

```bash
# LangSmith Configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=ai-co-scientist
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 3. Install Dependencies

Add to `environment.yml`:

```yaml
dependencies:
  - langsmith>=0.1.0
```

Or install directly:

```bash
pip install langsmith
```

## Implementation

### Files to Create/Modify

```
src/
├── llm/
│   ├── base.py         # Add tracing callbacks
│   ├── google.py       # Enable tracing
│   └── openai.py       # Enable tracing
└── observability/
    └── tracing.py      # LangSmith utilities
```

### 1. Tracing Utilities (`src/observability/tracing.py`)

```python
"""LangSmith tracing utilities for the AI Co-Scientist system."""

import os
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager

# Check if LangSmith is enabled
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

if LANGSMITH_ENABLED:
    from langsmith import Client
    from langsmith.run_trees import RunTree
    from langchain.callbacks import LangChainTracer

    # Initialize LangSmith client
    langsmith_client = Client()
else:
    langsmith_client = None


def get_tracer(project_name: Optional[str] = None) -> Optional["LangChainTracer"]:
    """Get a LangChain tracer for LangSmith integration.

    Args:
        project_name: Optional project name override

    Returns:
        LangChainTracer if LangSmith is enabled, None otherwise
    """
    if not LANGSMITH_ENABLED:
        return None

    return LangChainTracer(
        project_name=project_name or os.getenv("LANGCHAIN_PROJECT", "ai-co-scientist")
    )


@contextmanager
def trace_run(
    name: str,
    run_type: str = "chain",
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
):
    """Context manager for tracing a run in LangSmith.

    Args:
        name: Name of the run (e.g., "generation_agent")
        run_type: Type of run ("chain", "llm", "tool", etc.)
        metadata: Additional metadata to attach
        tags: Tags for filtering in LangSmith UI

    Example:
        with trace_run("hypothesis_generation", metadata={"goal_id": goal.id}):
            hypothesis = await agent.execute(goal)
    """
    if not LANGSMITH_ENABLED:
        yield None
        return

    run_tree = RunTree(
        name=name,
        run_type=run_type,
        extra={"metadata": metadata or {}},
        tags=tags or [],
    )

    try:
        yield run_tree
        run_tree.end()
    except Exception as e:
        run_tree.end(error=str(e))
        raise
    finally:
        run_tree.post()


def trace_agent(agent_name: str):
    """Decorator to trace agent executions in LangSmith.

    Args:
        agent_name: Name of the agent for tracing

    Example:
        @trace_agent("generation")
        async def execute(self, goal: ResearchGoal) -> Hypothesis:
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not LANGSMITH_ENABLED:
                return await func(*args, **kwargs)

            # Extract metadata from args if available
            metadata = {}
            if args and hasattr(args[0], '__class__'):
                metadata["agent_class"] = args[0].__class__.__name__

            # Look for research_goal in args/kwargs
            for arg in args[1:]:
                if hasattr(arg, 'id'):
                    metadata["goal_id"] = arg.id
                    break

            with trace_run(
                name=f"{agent_name}_agent",
                run_type="chain",
                metadata=metadata,
                tags=[agent_name, "agent"],
            ):
                return await func(*args, **kwargs)

        return wrapper
    return decorator


def trace_llm_call(provider: str, model: str):
    """Decorator to trace individual LLM calls.

    Args:
        provider: LLM provider (google, openai)
        model: Model name

    Example:
        @trace_llm_call("google", "gemini-1.5-pro")
        async def invoke(self, prompt: str) -> str:
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not LANGSMITH_ENABLED:
                return await func(*args, **kwargs)

            # Get prompt from args
            prompt = args[1] if len(args) > 1 else kwargs.get("prompt", "")

            with trace_run(
                name=f"{provider}_{model}",
                run_type="llm",
                metadata={
                    "provider": provider,
                    "model": model,
                    "prompt_length": len(prompt),
                },
                tags=[provider, model, "llm"],
            ) as run:
                result = await func(*args, **kwargs)

                if run:
                    run.outputs = {"response_length": len(result)}

                return result

        return wrapper
    return decorator


def log_feedback(
    run_id: str,
    score: float,
    comment: Optional[str] = None,
    feedback_type: str = "user",
):
    """Log feedback for a run in LangSmith.

    Useful for logging scientist ratings of hypothesis quality.

    Args:
        run_id: The run ID to attach feedback to
        score: Numeric score (e.g., 1-5)
        comment: Optional text feedback
        feedback_type: Type of feedback (user, auto, etc.)
    """
    if not LANGSMITH_ENABLED or not langsmith_client:
        return

    langsmith_client.create_feedback(
        run_id=run_id,
        key=feedback_type,
        score=score,
        comment=comment,
    )


def get_run_url(run_id: str) -> Optional[str]:
    """Get the LangSmith URL for a run.

    Args:
        run_id: The run ID

    Returns:
        URL to view the run in LangSmith UI
    """
    if not LANGSMITH_ENABLED:
        return None

    project = os.getenv("LANGCHAIN_PROJECT", "ai-co-scientist")
    return f"https://smith.langchain.com/projects/{project}/runs/{run_id}"
```

### 2. Update LLM Base Client (`src/llm/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Any, Optional, List
import os

# Import tracing utilities
from src.observability.tracing import get_tracer, LANGSMITH_ENABLED

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients with LangSmith tracing."""

    def __init__(self, model: str, cost_tracker: Any = None):
        self.model = model
        self.cost_tracker = cost_tracker

        # Get LangSmith tracer if enabled
        self.tracer = get_tracer() if LANGSMITH_ENABLED else None

    @property
    def callbacks(self) -> List:
        """Get callbacks for LangChain, including tracer if enabled."""
        if self.tracer:
            return [self.tracer]
        return []

    @abstractmethod
    def invoke(self, prompt: str) -> str:
        """Invoke the LLM synchronously."""
        pass

    @abstractmethod
    async def ainvoke(self, prompt: str) -> str:
        """Invoke the LLM asynchronously."""
        pass
```

### 3. Update Google Client (`src/llm/google.py`)

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from .base import BaseLLMClient
from src.observability.tracing import trace_llm_call

class GoogleGeminiClient(BaseLLMClient):
    """Google Gemini LLM client with LangSmith tracing."""

    def __init__(self, model: str, cost_tracker: Any = None):
        super().__init__(model, cost_tracker)

        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=0.7,
            max_output_tokens=8192,
            callbacks=self.callbacks,  # Add tracing callbacks
        )

    def invoke(self, prompt: str) -> str:
        """Invoke Gemini synchronously with tracing."""
        response = self.llm.invoke(prompt)
        return response.content

    @trace_llm_call("google", "gemini")
    async def ainvoke(self, prompt: str) -> str:
        """Invoke Gemini asynchronously with tracing."""
        response = await self.llm.ainvoke(prompt)

        # Track cost if tracker available
        if self.cost_tracker:
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(response.content.split()) * 1.3
            self.cost_tracker.track_usage(
                model=self.model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )

        return response.content
```

### 4. Update OpenAI Client (`src/llm/openai.py`)

```python
from langchain_openai import ChatOpenAI
from .base import BaseLLMClient
from src.observability.tracing import trace_llm_call

class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client with LangSmith tracing."""

    def __init__(self, model: str, cost_tracker: Any = None):
        super().__init__(model, cost_tracker)

        self.llm = ChatOpenAI(
            model=model,
            temperature=0.7,
            max_tokens=8192,
            callbacks=self.callbacks,  # Add tracing callbacks
        )

    def invoke(self, prompt: str) -> str:
        """Invoke OpenAI synchronously with tracing."""
        response = self.llm.invoke(prompt)
        return response.content

    @trace_llm_call("openai", "gpt")
    async def ainvoke(self, prompt: str) -> str:
        """Invoke OpenAI asynchronously with tracing."""
        response = await self.llm.ainvoke(prompt)

        if self.cost_tracker:
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(response.content.split()) * 1.3
            self.cost_tracker.track_usage(
                model=self.model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
            )

        return response.content
```

### 5. Update Agents with Tracing

Example for Generation Agent (`src/agents/generation.py`):

```python
from src.observability.tracing import trace_agent

class GenerationAgent(BaseAgent):
    """Generation agent with LangSmith tracing."""

    @trace_agent("generation")
    async def execute(
        self,
        research_goal: ResearchGoal,
        method: str = "literature",
        **kwargs
    ) -> Hypothesis:
        """Generate a hypothesis with full tracing."""
        # ... existing implementation ...
        pass
```

## Viewing Traces

### LangSmith Dashboard

1. Go to https://smith.langchain.com/
2. Select your project ("ai-co-scientist")
3. View runs in the "Runs" tab

### What You'll See

- **Run Tree**: Full hierarchy of agent calls
- **Inputs/Outputs**: Exact prompts and responses
- **Latency**: Time taken for each step
- **Token Counts**: Input/output tokens per call
- **Errors**: Stack traces for failures
- **Metadata**: Custom tags and metadata

### Filtering Runs

Use tags to filter runs:
- `generation` - Generation agent runs
- `reflection` - Reflection agent runs
- `ranking` - Ranking/tournament runs
- `llm` - Raw LLM calls

## Cost Tracking

LangSmith automatically tracks token usage. View in the dashboard:

1. Go to project settings
2. View "Usage" tab
3. See breakdown by model, run type, and time

## Testing Tracing

```python
# tests/test_tracing.py
import pytest
import os

# Enable tracing for tests
os.environ["LANGCHAIN_TRACING_V2"] = "true"

from src.observability.tracing import (
    LANGSMITH_ENABLED,
    get_tracer,
    trace_run,
    trace_agent,
)


def test_langsmith_enabled():
    """Test LangSmith is properly configured."""
    assert LANGSMITH_ENABLED == True


def test_get_tracer():
    """Test tracer creation."""
    tracer = get_tracer()
    assert tracer is not None


@pytest.mark.asyncio
async def test_trace_run():
    """Test trace_run context manager."""
    with trace_run("test_run", metadata={"test": True}) as run:
        assert run is not None


@pytest.mark.asyncio
async def test_trace_agent_decorator():
    """Test trace_agent decorator."""

    @trace_agent("test")
    async def mock_agent_execute():
        return "result"

    result = await mock_agent_execute()
    assert result == "result"
```

## Success Criteria

- [ ] LangSmith API key configured
- [ ] Traces appearing in LangSmith dashboard
- [ ] Agent executions showing full call hierarchy
- [ ] LLM calls showing prompts and responses
- [ ] Token usage tracked per call
- [ ] Errors captured with stack traces
- [ ] Tests passing with tracing enabled

## Troubleshooting

### Traces Not Appearing

1. Check `LANGCHAIN_TRACING_V2=true` is set
2. Verify `LANGCHAIN_API_KEY` is valid
3. Check project name matches in UI
4. Ensure callbacks are passed to LangChain objects

### Performance Impact

LangSmith tracing adds minimal overhead (~10-50ms per trace). For production, you can:

1. Disable tracing: `LANGCHAIN_TRACING_V2=false`
2. Use sampling: Only trace a percentage of requests
3. Use async posting: Traces are posted asynchronously by default

## Next Steps

After enabling LangSmith:

1. Create custom dashboards for monitoring
2. Set up alerts for errors or high latency
3. Use feedback to improve prompts
4. Compare model performance across runs
