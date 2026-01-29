"""Base LLM client interface"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class BaseLLMClient(ABC):
    """Abstract base for LLM clients"""

    def __init__(self, model: str, cost_tracker: Any):
        self.model = model
        self.cost_tracker = cost_tracker
        self._tracer = None

        # Initialize tracer if LangSmith is enabled
        try:
            from src.observability.tracing import get_tracer, LANGSMITH_ENABLED
            if LANGSMITH_ENABLED:
                self._tracer = get_tracer()
        except ImportError:
            pass

    @property
    def callbacks(self) -> List[Any]:
        """Get callback handlers for LangChain.

        Returns:
            List of callback handlers (includes LangSmith tracer if enabled).
        """
        if self._tracer:
            return [self._tracer]
        return []

    @abstractmethod
    def invoke(self, prompt: str) -> str:
        """Synchronous invocation"""
        pass

    @abstractmethod
    async def ainvoke(self, prompt: str) -> str:
        """Async invocation for parallel execution"""
        pass
