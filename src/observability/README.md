# Observability Module

LangSmith integration for LLM tracing, debugging, and cost monitoring in the AI Co-Scientist system.

## Overview

This module provides automatic tracing of all agent executions and LLM calls using [LangSmith](https://smith.langchain.com/). When enabled, every hypothesis generation, review, tournament match, and LLM API call is automatically logged to LangSmith for debugging, monitoring, and analysis.

## Features

- **Automatic LLM Tracing**: All LLM calls (Google Gemini, OpenAI) are automatically traced
- **Agent Execution Tracking**: All agent methods (Generation, Reflection, Ranking, etc.) are traced
- **Token Usage Monitoring**: Track token consumption across all agents
- **Cost Attribution**: See which agents consume the most resources
- **Debugging Support**: View full prompt/response pairs for debugging
- **Graceful Degradation**: Tracing is a no-op when disabled (zero performance impact)
- **Error Tracking**: Capture and analyze agent failures

## Setup

### 1. Get LangSmith API Key

1. Sign up for free at [smith.langchain.com](https://smith.langchain.com/)
2. Create a new project (e.g., "ai-coscientist")
3. Generate an API key from the settings page

### 2. Configure Environment

Add to your `03_architecture/.env`:

```bash
# Enable LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_your_api_key_here
LANGCHAIN_PROJECT=ai-coscientist
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

### 3. Verify Installation

LangSmith should be already installed via `environment.yml`:

```bash
conda activate coscientist
python -c "from src.observability import LANGSMITH_ENABLED; print(f'LangSmith enabled: {LANGSMITH_ENABLED}')"
```

## Usage

### Automatic Tracing

No code changes required! Once configured, all agents and LLM calls are automatically traced:

```python
from src.agents.generation import GenerationAgent
from schemas import ResearchGoal

# This execution will be automatically traced if LANGCHAIN_TRACING_V2=true
agent = GenerationAgent()
hypothesis = agent.execute(
    research_goal=ResearchGoal(
        id="goal-1",
        description="Investigate CRISPR efficiency"
    )
)
```

### Manual Tracing

You can also manually create trace contexts:

```python
from src.observability import trace_run

with trace_run(
    name="custom_analysis",
    run_type="chain",
    metadata={"analysis_type": "clustering"},
    tags=["analysis", "clustering"]
):
    # Your code here
    results = perform_analysis()
```

### Logging User Feedback

Log scientist feedback on hypotheses:

```python
from src.observability import log_feedback

log_feedback(
    run_id="abc123",  # From LangSmith trace
    score=0.9,
    comment="Excellent hypothesis, very testable",
    feedback_type="scientist"
)
```

### Getting Trace URLs

Generate shareable links to specific traces:

```python
from src.observability import get_run_url

url = get_run_url("abc123")
print(f"View trace: {url}")
```

## Architecture

### Decorators

The module provides two main decorators:

#### `@trace_agent(agent_name)`

Wraps agent execution methods to create a trace context. Automatically extracts metadata like hypothesis IDs, goal IDs, etc.

```python
from src.observability import trace_agent

class MyAgent:
    @trace_agent("MyAgent")
    def execute(self, hypothesis, goal_id):
        # Automatically traced with:
        # - agent_name: "MyAgent"
        # - hypothesis_id: extracted from hypothesis.id
        # - goal_id: passed through
        return result
```

#### `@trace_llm_call(provider, model)`

Wraps LLM client invoke/ainvoke methods to track API calls, token usage, and latency.

```python
from src.observability import trace_llm_call

class MyLLMClient:
    @trace_llm_call("google", "gemini-3-pro")
    async def ainvoke(self, prompt: str) -> str:
        # Automatically traced with:
        # - provider: "google"
        # - model: "gemini-3-pro"
        # - latency: computed
        return await self.llm.ainvoke(prompt)
```

### Callbacks

LLM clients automatically use LangChain callbacks when tracing is enabled:

```python
from src.llm.base import BaseLLMClient

class GoogleGeminiClient(BaseLLMClient):
    def __init__(self, model: str, agent_name: str):
        super().__init__(model, cost_tracker)
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            callbacks=self.callbacks  # Automatically includes LangSmith tracer
        )
```

## Viewing Traces

### LangSmith Dashboard

1. Go to [smith.langchain.com](https://smith.langchain.com/)
2. Select your project (e.g., "ai-coscientist")
3. View traces organized by:
   - **Agent type**: Generation, Reflection, Ranking, etc.
   - **Time**: Recent executions
   - **Status**: Success, error, pending
   - **Cost**: Token usage and estimated cost

### Trace Hierarchy

Traces are organized hierarchically:

```
SupervisorAgent.execute
├── GenerationAgent.execute
│   └── llm.google.gemini-3-pro (prompt + response)
├── ReflectionAgent.execute
│   └── llm.google.gemini-2.5-flash (prompt + response)
└── RankingAgent.execute
    ├── llm.google.gemini-3-flash (debate turn 1)
    ├── llm.google.gemini-3-flash (debate turn 2)
    └── llm.google.gemini-3-flash (judge decision)
```

## Performance

### When Enabled

- Minimal overhead (< 5ms per trace)
- Asynchronous logging (non-blocking)
- Network calls to LangSmith API

### When Disabled

- **Zero overhead**: Decorators are true no-ops
- No network calls
- No additional imports

## Debugging Common Issues

### Tracing Not Working

1. **Check environment variables**:
   ```bash
   echo $LANGCHAIN_TRACING_V2
   echo $LANGCHAIN_API_KEY
   ```

2. **Verify imports**:
   ```python
   from src.observability import LANGSMITH_ENABLED
   print(LANGSMITH_ENABLED)  # Should be True
   ```

3. **Check logs**:
   Look for "langsmith_enabled" or "langsmith_disabled" in structured logs

### Missing Traces

- Ensure `LANGCHAIN_TRACING_V2=true` (not "True" or "1")
- Check API key is valid
- Verify network connectivity to smith.langchain.com

### Import Errors

If you see "No module named 'langsmith'":

```bash
conda activate coscientist
pip install langsmith>=0.1.0
```

## Testing

Run the test suite:

```bash
# Unit tests for tracing utilities
pytest 05_tests/test_tracing.py -v

# Integration tests with agents
pytest 05_tests/test_tracing_integration.py -v
```

## Examples

### Example 1: Debugging Failed Hypothesis

1. Run workflow with tracing enabled
2. Note which hypothesis failed review
3. Go to LangSmith and filter by `hypothesis_id`
4. View the full prompt sent to the LLM
5. Analyze the response to understand why it failed

### Example 2: Cost Attribution

1. Run full workflow (20 iterations)
2. Go to LangSmith Analytics
3. Group by `agent_name` tag
4. See that Generation consumes 40% of tokens (as expected)
5. Identify if any agent is over-consuming

### Example 3: Scientist Feedback Loop

1. Scientist reviews top hypotheses in UI
2. Provides feedback scores (0.0 to 1.0)
3. System logs feedback to LangSmith:
   ```python
   log_feedback(
       run_id=hypothesis.langsmith_run_id,
       score=scientist_score,
       comment=scientist_comment,
       feedback_type="scientist"
   )
   ```
4. Feedback appears in LangSmith for analysis

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LANGCHAIN_TRACING_V2` | `false` | Enable/disable tracing |
| `LANGCHAIN_API_KEY` | - | LangSmith API key |
| `LANGCHAIN_PROJECT` | `ai-coscientist` | Project name in LangSmith |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | LangSmith API endpoint |

## API Reference

### `get_tracer(project_name: Optional[str] = None) -> Optional[LangChainTracer]`

Get a LangChain tracer for the given project.

**Returns**: LangChainTracer instance if enabled, None otherwise.

### `trace_run(name: str, run_type: str = "chain", metadata: Optional[Dict] = None, tags: Optional[List[str]] = None)`

Context manager for tracing a logical run.

**Args**:
- `name`: Name of the run
- `run_type`: Type ("chain", "llm", "tool", "retriever")
- `metadata`: Additional metadata
- `tags`: Tags for filtering

### `@trace_agent(agent_name: str)`

Decorator for tracing agent executions.

**Args**:
- `agent_name`: Name of the agent (e.g., "GenerationAgent")

### `@trace_llm_call(provider: str, model: str)`

Decorator for tracing LLM API calls.

**Args**:
- `provider`: LLM provider (e.g., "google", "openai")
- `model`: Model name (e.g., "gemini-3-pro-preview")

### `log_feedback(run_id: str, score: float, comment: Optional[str] = None, feedback_type: str = "human") -> bool`

Log user feedback for a specific run.

**Args**:
- `run_id`: LangSmith run ID
- `score`: Numeric score (0.0 to 1.0)
- `comment`: Optional text feedback
- `feedback_type`: Type of feedback ("human", "auto", "scientist")

**Returns**: True if feedback was logged successfully.

### `get_run_url(run_id: str) -> Optional[str]`

Get the LangSmith URL for a specific run.

**Args**:
- `run_id`: LangSmith run ID

**Returns**: URL to view the run, or None if disabled.

## Best Practices

1. **Use Descriptive Names**: When creating manual traces, use clear names like "cluster_hypotheses" not "process"
2. **Add Metadata**: Include relevant IDs and parameters in metadata for filtering
3. **Tag Appropriately**: Use tags like ["production", "experiment", "debug"] to organize traces
4. **Review Regularly**: Check LangSmith dashboard weekly to identify patterns
5. **Log Feedback**: Capture scientist feedback for continuous improvement
6. **Disable in Tests**: Set `LANGCHAIN_TRACING_V2=false` for unit tests (faster)

## Security

- API keys are loaded from environment variables (never hardcoded)
- Traces may contain sensitive scientific data - use LangSmith privacy settings
- Consider using separate projects for production vs development
- LangSmith offers private deployments for sensitive workloads

## Future Enhancements

Planned features for Phase 6:

- **Custom Metrics**: Track domain-specific metrics (novelty scores, Elo ratings)
- **Automated Alerts**: Notify when agents fail or exceed budget
- **A/B Testing**: Compare different prompt strategies
- **Dataset Creation**: Export successful runs as training datasets
- **Prompt Optimization**: Use LangSmith's prompt playground to refine prompts

## References

- [LangSmith Documentation](https://docs.smith.langchain.com/)
- [LangChain Tracing Guide](https://python.langchain.com/docs/guides/debugging/tracing)
- [LangSmith Python SDK](https://github.com/langchain-ai/langsmith-sdk)
