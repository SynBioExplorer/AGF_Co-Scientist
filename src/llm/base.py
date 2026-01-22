"""Base LLM client interface"""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMClient(ABC):
    """Abstract base for LLM clients"""

    def __init__(self, model: str, cost_tracker: Any):
        self.model = model
        self.cost_tracker = cost_tracker

    @abstractmethod
    def invoke(self, prompt: str) -> str:
        """Synchronous invocation"""
        pass

    @abstractmethod
    async def ainvoke(self, prompt: str) -> str:
        """Async invocation for parallel execution"""
        pass
