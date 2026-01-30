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
from src.utils.errors import LLMClientError
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

        if not settings.openai_api_key:
            raise LLMClientError("OpenAI API key not configured in .env")

        self.llm = ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=8192,
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
        """Estimate token count for text.

        Uses a conservative multiplier for scientific/technical content.
        For more accurate counting, consider using tiktoken library.

        Args:
            text: Text to estimate tokens for.

        Returns:
            Estimated token count.
        """
        # Use 1.5x multiplier for scientific content (more conservative than 1.3x)
        word_count = len(text.split())
        return int(word_count * 1.5)

    def _do_invoke(self, prompt: str) -> str:
        """Internal sync invoke without retry (for use with retry wrapper).

        Args:
            prompt: The prompt to send.

        Returns:
            Response content.
        """
        response = self.llm.invoke(prompt)
        return response.content

    async def _do_ainvoke(self, prompt: str) -> str:
        """Internal async invoke without retry (for use with retry wrapper).

        Args:
            prompt: The prompt to send.

        Returns:
            Response content.
        """
        response = await self.llm.ainvoke(prompt)
        return response.content

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
        # Check budget before attempting (fail fast)
        self.cost_tracker.check_budget()

        try:
            # Use sync retry wrapper
            content = sync_retry(
                self._do_invoke,
                prompt,
                operation_name=f"OpenAI invoke ({self.agent_name})"
            )

            # Track usage after successful call
            input_tokens = self._estimate_tokens(prompt)
            output_tokens = self._estimate_tokens(content)

            self.cost_tracker.add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            logger.debug(
                "openai_invoke_success",
                agent=self.agent_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            return content

        except BudgetExceededError:
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
        # Check budget before attempting (fail fast)
        self.cost_tracker.check_budget()

        try:
            # Use async retry wrapper with timeout
            content = await retry_async(
                self._do_ainvoke,
                prompt,
                timeout=settings.llm_timeout_seconds,
                operation_name=f"OpenAI ainvoke ({self.agent_name})"
            )

            # Track usage after successful call
            input_tokens = self._estimate_tokens(prompt)
            output_tokens = self._estimate_tokens(content)

            self.cost_tracker.add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            logger.debug(
                "openai_ainvoke_success",
                agent=self.agent_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

            return content

        except BudgetExceededError:
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
