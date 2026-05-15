"""Anthropic (Claude) LLM client.

Wraps ``langchain_anthropic.ChatAnthropic`` with the same cost-tracking,
retry, and timeout plumbing as the other clients.

Available models (defaults):
    - claude-opus-4-1
    - claude-sonnet-4-5
    - claude-haiku-4-5

Reads ``ANTHROPIC_API_KEY`` from the environment first, then from
``settings.anthropic_api_key``.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import structlog

from src.config import settings
from src.llm.base import BaseLLMClient
from src.observability.tracing import trace_llm_call
from src.utils.errors import LLMClientError
from src.utils.retry import retry_async, sync_retry

sys.path.append(str(settings.project_root / "04_Scripts"))
from cost_tracker import BudgetExceededError, get_tracker  # noqa: E402

logger = structlog.get_logger()

ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-5"
ANTHROPIC_AVAILABLE_MODELS: list[str] = [
    "claude-opus-4-1",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
]


class AnthropicClient(BaseLLMClient):
    """LLM client targeting Anthropic's Messages API via LangChain."""

    def __init__(
        self,
        model: str = ANTHROPIC_DEFAULT_MODEL,
        agent_name: str = "default",
        temperature: float = 0.7,
        api_key: Optional[str] = None,
    ):
        cost_tracker = get_tracker(budget_aud=settings.budget_aud)
        super().__init__(model, cost_tracker)

        self.agent_name = agent_name
        resolved_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or getattr(settings, "anthropic_api_key", None)
        )
        if not resolved_key:
            raise LLMClientError("Anthropic API key not configured")

        # Import lazily so the module can still be imported when the
        # langchain-anthropic package isn't installed (which is fine for
        # config-only paths and unit tests using mocks).
        try:
            from langchain_anthropic import ChatAnthropic  # type: ignore
        except ImportError as e:
            raise LLMClientError(
                "langchain-anthropic is not installed. "
                "Run: pip install langchain-anthropic"
            ) from e

        self.llm = ChatAnthropic(
            model=model,
            anthropic_api_key=resolved_key,
            temperature=temperature,
            max_tokens=8192,
            callbacks=self.callbacks,
        )
        logger.info(
            "anthropic_client_initialized",
            model=model,
            agent=agent_name,
            timeout=settings.llm_timeout_seconds,
        )

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.5)

    def _extract_usage(self, response, prompt: str, content: str) -> tuple[int, int]:
        in_tok = out_tok = None
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            in_tok = usage.get("input_tokens")
            out_tok = usage.get("output_tokens")
        if in_tok is None or out_tok is None:
            return self._estimate_tokens(prompt), self._estimate_tokens(content)
        return int(in_tok), int(out_tok)

    def _do_invoke(self, prompt: str):
        response = self.llm.invoke(prompt)
        return response.content, response

    async def _do_ainvoke(self, prompt: str):
        response = await self.llm.ainvoke(prompt)
        return response.content, response

    def invoke(self, prompt: str) -> str:
        try:
            content, response = sync_retry(
                self._do_invoke,
                prompt,
                operation_name=f"Anthropic invoke ({self.agent_name})",
            )
            in_tok, out_tok = self._extract_usage(response, prompt, content)
            self.cost_tracker.check_and_add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )
            return content
        except BudgetExceededError:
            raise
        except Exception as e:
            logger.error(
                "anthropic_invoke_failed",
                agent=self.agent_name,
                error=str(e),
            )
            if isinstance(e, LLMClientError):
                raise
            raise LLMClientError(f"Anthropic invocation failed: {e}") from e

    @trace_llm_call("anthropic", "claude")
    async def ainvoke(self, prompt: str) -> str:
        try:
            content, response = await retry_async(
                self._do_ainvoke,
                prompt,
                timeout=settings.llm_timeout_seconds,
                operation_name=f"Anthropic ainvoke ({self.agent_name})",
            )
            in_tok, out_tok = self._extract_usage(response, prompt, content)
            self.cost_tracker.check_and_add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )
            return content
        except BudgetExceededError:
            raise
        except Exception as e:
            logger.error(
                "anthropic_ainvoke_failed",
                agent=self.agent_name,
                error=str(e),
            )
            if isinstance(e, LLMClientError):
                raise
            raise LLMClientError(f"Anthropic async invocation failed: {e}") from e
