"""OpenAI GPT client with cost tracking, retry logic, and timeouts.

This client wraps the LangChain OpenAI integration with:
- Automatic retry with exponential backoff for transient failures
- Configurable timeout for each LLM call
- Budget tracking and enforcement
- Structured logging for observability
"""

from langchain_openai import ChatOpenAI
from src.llm.base import BaseLLMClient
from src.config import settings
from src.utils.errors import LLMClientError, RunTimeLimitError
from src.utils.retry import retry_async, sync_retry
from src.observability.tracing import trace_llm_call
import structlog
import sys
sys.path.append(str(settings.project_root / "04_Scripts"))
from cost_tracker import get_tracker, BudgetExceededError

logger = structlog.get_logger()


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client with cost tracking, retry, and timeout support.

    Features:
    - Automatic retry with exponential backoff (configurable via settings)
    - Per-call timeout (default 5 minutes for scientific reasoning)
    - Budget tracking with atomic check-and-add
    - Handles both sync and async invocations
    """

    def __init__(self, model: str, agent_name: str):
        """Initialize OpenAI client.

        Args:
            model: Model name (e.g., 'gpt-5.1').
            agent_name: Name of the agent using this client (for cost tracking).

        Raises:
            LLMClientError: If OpenAI API key is not configured.
        """
        cost_tracker = get_tracker(budget_aud=settings.budget_aud)
        super().__init__(model, cost_tracker)

        self.agent_name = agent_name
        self.max_tokens = 8192

        # Prefer env var (set per-request by API middleware) over frozen settings
        import os
        api_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
        if not api_key:
            raise LLMClientError("OpenAI API key not configured")

        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=0.7,
            max_tokens=self.max_tokens,
            max_retries=0,  # retry_async/sync_retry own admission and accounting
            callbacks=self.callbacks  # Add tracing callbacks
        )

        logger.info(
            "openai_client_initialized",
            model=model,
            agent=agent_name,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries
        )

    def _estimate_tokens(self, text: str) -> int:
        # Last-resort fallback only — used when usage_metadata is unavailable.
        word_count = len(text.split())
        return int(word_count * 1.5)

    def _extract_usage(self, response, prompt: str, content: str) -> tuple[int, int]:
        """Return (input_tokens, output_tokens) for billing.

        Prefers SDK-reported counts from response.usage_metadata. For GPT-5,
        output_tokens/completion_tokens include reasoning tokens. The reasoning
        detail is a breakdown, not an additional charge. Falls back to an
        estimator only when metadata is unavailable (the reservation is retained).
        """
        in_tok = out_tok = None

        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            in_tok = self._usage_value(usage, "input_tokens", "prompt_tokens")
            out_tok = self._usage_value(usage, "output_tokens", "completion_tokens")

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

    def _do_invoke(self, prompt: str):
        with self._budgeted_request(prompt, self.max_tokens) as reservation:
            response = self.llm.invoke(prompt, timeout=self._request_timeout(settings.llm_timeout_seconds))
            self._settle_response(reservation, response, prompt, response.content)
            return response.content, response

    async def _do_ainvoke(self, prompt: str):
        with self._budgeted_request(prompt, self.max_tokens) as reservation:
            response = await self.llm.ainvoke(prompt, timeout=self._request_timeout(settings.llm_timeout_seconds))
            self._settle_response(reservation, response, prompt, response.content)
            return response.content, response

    def invoke(self, prompt: str) -> str:
        """Invoke OpenAI synchronously with retry and cost tracking.

        Args:
            prompt: The prompt to send to the model.

        Returns:
            Model response content.

        Raises:
            BudgetExceededError: If budget limit would be exceeded.
            LLMClientError: If invocation fails after all retries.
        """
        try:
            # Refused before the call once the spend limit is reached
            self.cost_tracker.ensure_budget_available()
            # Use sync retry wrapper
            content, response = sync_retry(
                self._do_invoke,
                prompt,
                operation_name=f"OpenAI invoke ({self.agent_name})",
                remaining_time=self.cost_tracker.remaining_run_seconds,
            )

            input_tokens, output_tokens = self._extract_usage(response, prompt, content)


            logger.debug(
                "openai_invoke_success",
                agent=self.agent_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            return content

        except (BudgetExceededError, RunTimeLimitError):
            # Re-raise budget errors without wrapping
            raise

        except Exception as e:
            # Log and wrap any other errors
            logger.error(
                "openai_invoke_failed",
                agent=self.agent_name,
                error=str(e),
                error_type=type(e).__name__
            )

            # If it's already a properly classified error, re-raise
            if isinstance(e, LLMClientError):
                raise

            raise LLMClientError(f"OpenAI invocation failed: {e}") from e

    @trace_llm_call("openai", "gpt")
    async def ainvoke(self, prompt: str) -> str:
        """Invoke OpenAI asynchronously with retry, timeout, and cost tracking.

        This is the preferred method for production use as it:
        - Supports proper timeout handling via asyncio
        - Enables concurrent LLM calls
        - Integrates with async frameworks (FastAPI, etc.)

        Args:
            prompt: The prompt to send to the model.

        Returns:
            Model response content.

        Raises:
            BudgetExceededError: If budget limit would be exceeded.
            LLMTimeoutError: If the call times out after all retries.
            LLMRateLimitError: If rate limited after all retries.
            LLMClientError: If invocation fails for other reasons.
        """
        try:
            # Refused before the call once the spend limit is reached
            self.cost_tracker.ensure_budget_available()
            # Use async retry wrapper with timeout
            content, response = await self._within_run_time(retry_async(
                self._do_ainvoke,
                prompt,
                timeout=settings.llm_timeout_seconds,
                operation_name=f"OpenAI ainvoke ({self.agent_name})"
            ))

            input_tokens, output_tokens = self._extract_usage(response, prompt, content)


            logger.debug(
                "openai_ainvoke_success",
                agent=self.agent_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            return content

        except (BudgetExceededError, RunTimeLimitError):
            # Re-raise budget errors without wrapping
            raise

        except Exception as e:
            # Log and wrap any other errors
            logger.error(
                "openai_ainvoke_failed",
                agent=self.agent_name,
                error=str(e),
                error_type=type(e).__name__
            )

            # If it's already a properly classified error, re-raise
            if isinstance(e, LLMClientError):
                raise

            raise LLMClientError(f"OpenAI async invocation failed: {e}") from e
