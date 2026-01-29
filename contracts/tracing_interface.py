"""
Contract: TracingProtocol
Version: 3f65fb4 (current commit)
Generated: 2025-01-29
Purpose: Define the interface for LangSmith tracing integration
Consumers: task-observability, all LLM client tasks
"""
from typing import Protocol, Optional, Dict, Any, List, ContextManager


class TracingProtocol(Protocol):
    """Abstract tracing interface for LangSmith integration.

    Provides utilities for tracing LLM calls, agent executions,
    and workflow steps.
    """

    def get_tracer(self, project_name: Optional[str] = None) -> Optional[Any]:
        """Get a LangChain tracer for callbacks.

        Args:
            project_name: Optional project name override

        Returns:
            LangChainTracer if LangSmith is enabled, None otherwise
        """
        ...

    def trace_run(
        self,
        name: str,
        run_type: str = "chain",
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> ContextManager:
        """Context manager for tracing a run.

        Args:
            name: Name of the run
            run_type: Type of run ("chain", "llm", "tool", etc.)
            metadata: Additional metadata
            tags: Tags for filtering

        Returns:
            Context manager that traces the run
        """
        ...

    def log_feedback(
        self,
        run_id: str,
        score: float,
        comment: Optional[str] = None,
        feedback_type: str = "user"
    ) -> None:
        """Log feedback for a run.

        Args:
            run_id: The run ID to attach feedback to
            score: Numeric score
            comment: Optional text feedback
            feedback_type: Type of feedback
        """
        ...


# Module-level flag to check if LangSmith is enabled
LANGSMITH_ENABLED: bool = False
