"""Base LLM client interface"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
import asyncio
from src.utils.errors import RunTimeLimitError
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

    @contextmanager
    def _budgeted_request(self, prompt: str, max_output_tokens: int):
        self._request_timeout(float("inf"))
        # Plain-text byte count plus a framing allowance is a conservative input
        # token bound. These clients accept text only and set an output cap.
        reservation = self.cost_tracker.reserve_usage(
            agent=self.agent_name, model=self.model,
            max_input_tokens=len(prompt.encode("utf-8")) + 1024,
            max_output_tokens=max_output_tokens,
        )
        try:
            yield reservation
        finally:
            # A settled request was removed. An exception/cancellation or absent
            # usage metadata leaves its possible spend reserved.
            self.cost_tracker.abandon_reservation(reservation)

    def _request_timeout(self, default: float) -> float:
        remaining = self.cost_tracker.remaining_run_seconds()
        if remaining is None:
            return default
        if remaining <= 0:
            raise RunTimeLimitError("Run time limit reached; no further model requests are allowed")
        return min(default, remaining)

    async def _within_run_time(self, awaitable):
        remaining = self.cost_tracker.remaining_run_seconds()
        if remaining is None:
            return await awaitable
        if remaining <= 0:
            awaitable.close()
            raise RunTimeLimitError("Run time limit reached; no further model requests are allowed")
        try:
            return await asyncio.wait_for(awaitable, timeout=remaining)
        except asyncio.TimeoutError as error:
            raise RunTimeLimitError("Run time limit reached during a model request") from error

    @staticmethod
    def _usage_value(source, *keys):
        if isinstance(source, dict):
            for key in keys:
                if source.get(key) is not None:
                    return source[key]
        return None

    @staticmethod
    def _reported_usage(response) -> bool:
        metadata = getattr(response, "response_metadata", None) or {}
        sources = [getattr(response, "usage_metadata", None)]
        if isinstance(metadata, dict):
            sources += [metadata.get(k) for k in ("usage", "token_usage", "usage_metadata")]
        pairs = (("input_tokens", "output_tokens"), ("prompt_tokens", "completion_tokens"),
                 ("prompt_token_count", "candidates_token_count"), ("input_token_count", "output_token_count"))
        return any(isinstance(source, dict) and any(
            all(isinstance(source.get(k), int) and not isinstance(source[k], bool) and source[k] >= 0
                for k in pair) for pair in pairs) for source in sources)

    def _settle_response(self, reservation: str, response, prompt: str, content: str) -> None:
        if self._reported_usage(response):
            input_tokens, output_tokens = self._extract_usage(response, prompt, content)
            self.cost_tracker.settle_usage(reservation, input_tokens=input_tokens, output_tokens=output_tokens)

    @abstractmethod
    def invoke(self, prompt: str) -> str:
        """Synchronous invocation"""
        pass

    @abstractmethod
    async def ainvoke(self, prompt: str) -> str:
        """Async invocation for parallel execution"""
        pass
