"""DeepSeek LLM client.

DeepSeek exposes an OpenAI-compatible API at https://api.deepseek.com. We
reuse ``langchain_openai.ChatOpenAI`` and just point ``base_url`` at the
DeepSeek endpoint. Mirrors the structure of :mod:`src.llm.openai`.

Available models:
    - deepseek-chat
    - deepseek-reasoner

Reads ``DEEPSEEK_API_KEY`` from the environment first, then from
``settings.deepseek_api_key``.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import structlog
from langchain_openai import ChatOpenAI

from src.config import settings
from src.llm.base import BaseLLMClient
from src.observability.tracing import trace_llm_call
from src.utils.errors import LLMClientError
from src.utils.retry import retry_async, sync_retry

sys.path.append(str(settings.project_root / "04_Scripts"))
from cost_tracker import BudgetExceededError, get_tracker  # noqa: E402

logger = structlog.get_logger()

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_AVAILABLE_MODELS: list[str] = ["deepseek-chat", "deepseek-reasoner"]


class DeepSeekClient(BaseLLMClient):
    """LLM client targeting the DeepSeek OpenAI-compatible API."""

    def __init__(
        self,
        model: str = DEEPSEEK_DEFAULT_MODEL,
        agent_name: str = "default",
        temperature: float = 0.7,
        api_key: Optional[str] = None,
    ):
        cost_tracker = get_tracker(budget_aud=settings.budget_aud)
        super().__init__(model, cost_tracker)

        self.agent_name = agent_name

        resolved_key = (
            api_key
            or os.environ.get("DEEPSEEK_API_KEY")
            or getattr(settings, "deepseek_api_key", None)
        )
        if not resolved_key:
            raise LLMClientError("DeepSeek API key not configured")

        self.llm = ChatOpenAI(
            model=model,
            api_key=resolved_key,
            base_url=DEEPSEEK_BASE_URL,
            temperature=temperature,
            max_tokens=8192,
            callbacks=self.callbacks,
        )

        logger.info(
            "deepseek_client_initialized",
            model=model,
            agent=agent_name,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )

    # ------------------------------------------------------------------
    # Token accounting -- DeepSeek mirrors OpenAI's response shape.
    # ------------------------------------------------------------------

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.5)

    def _extract_usage(self, response, prompt: str, content: str) -> tuple[int, int]:
        in_tok = out_tok = None
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            in_tok = usage.get("input_tokens") or usage.get("prompt_tokens")
            out_tok = usage.get("output_tokens") or usage.get("completion_tokens")

        meta = getattr(response, "response_metadata", None) or {}
        token_usage = meta.get("token_usage") if isinstance(meta, dict) else None
        if isinstance(token_usage, dict):
            if in_tok is None:
                in_tok = token_usage.get("prompt_tokens")
            if out_tok is None:
                out_tok = token_usage.get("completion_tokens")

        if in_tok is None or out_tok is None:
            return self._estimate_tokens(prompt), self._estimate_tokens(content)
        return int(in_tok), int(out_tok)

    # ------------------------------------------------------------------
    # Sync / async invocation
    # ------------------------------------------------------------------

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
                operation_name=f"DeepSeek invoke ({self.agent_name})",
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
                "deepseek_invoke_failed",
                agent=self.agent_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            if isinstance(e, LLMClientError):
                raise
            raise LLMClientError(f"DeepSeek invocation failed: {e}") from e

    @trace_llm_call("deepseek", "chat")
    async def ainvoke(self, prompt: str) -> str:
        try:
            content, response = await retry_async(
                self._do_ainvoke,
                prompt,
                timeout=settings.llm_timeout_seconds,
                operation_name=f"DeepSeek ainvoke ({self.agent_name})",
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
                "deepseek_ainvoke_failed",
                agent=self.agent_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            if isinstance(e, LLMClientError):
                raise
            raise LLMClientError(f"DeepSeek async invocation failed: {e}") from e
