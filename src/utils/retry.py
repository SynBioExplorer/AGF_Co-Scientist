"""Retry utilities with exponential backoff for LLM calls.

This module provides retry mechanisms for handling transient failures
in LLM API calls, including:
- Rate limiting (HTTP 429)
- Timeouts
- Transient server errors (5xx)
- Network connectivity issues

The retry logic uses exponential backoff with jitter to prevent
thundering herd problems when multiple clients retry simultaneously.
"""

import asyncio
import random
import time
from typing import TypeVar, Callable, Any, Optional
import structlog
from botocore.exceptions import (
    ClientError,
    ConnectionError as BotoConnectionError,
    HTTPClientError,
)

from src.utils.errors import (
    ContentFilteredError,
    RetryableError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMClientError,
    RunTimeLimitError,
)

logger = structlog.get_logger()
T = TypeVar('T')

_RETRYABLE_AWS_ERROR_CODES = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "InternalServerException",
    "ModelTimeoutException",
    "ModelNotReadyException",
}
# botocore's standard mode retried 500/502/503/504 whatever the code; 429 is
# retried here in addition. A response without x-amzn-errortype (edge, proxy)
# carries only the status.
_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable.

    Checks the error message for common indicators of transient failures
    that are likely to succeed on retry.

    Args:
        error: The exception to check.

    Returns:
        True if the error is retryable, False otherwise.
    """
    # Already classified as retryable
    if isinstance(error, RetryableError):
        return True

    # A safety-filter block is deterministic for the prompt. Checked by type,
    # before the substring checks, so a model ID or agent name in the message
    # can never make it look transient.
    if isinstance(error, (ContentFilteredError, RunTimeLimitError)):
        return False

    # AWS errors by type, code and HTTP status. botocore's own retries are off
    # for Bedrock (one retry layer), so this covers what its standard mode
    # retried for Converse (500/502/503/504 by status, ThrottlingException,
    # ModelNotReadyException, connection and read failures) and also retries a
    # bare 429 and ModelTimeoutException. The substring checks below miss e.g.
    # InternalServerException, an unmodelled 503, and a ThrottlingException
    # worded "Too many tokens".
    # BotoConnectionError covers endpoint, connect-timeout, SSL and proxy
    # failures; HTTPClientError covers read timeouts and closed connections.
    if isinstance(error, (BotoConnectionError, HTTPClientError)):
        return True
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code", "")
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return code in _RETRYABLE_AWS_ERROR_CODES or status in _RETRYABLE_HTTP_STATUS

    error_str = str(error).lower()

    # Rate limit indicators
    rate_limit_indicators = [
        '429',
        'rate limit',
        'rate_limit',
        'quota',
        'too many requests',
        'resource exhausted',
        'resourceexhausted',
    ]
    if any(x in error_str for x in rate_limit_indicators):
        return True

    # Timeout indicators
    timeout_indicators = [
        'timeout',
        'timed out',
        'deadline',
        'deadline exceeded',
        'context deadline',
    ]
    if any(x in error_str for x in timeout_indicators):
        return True

    # Transient server errors
    server_error_indicators = [
        '503',
        '502',
        '500',
        '504',
        'service unavailable',
        'internal error',
        'internal server error',
        'bad gateway',
        'gateway timeout',
        'temporarily unavailable',
    ]
    if any(x in error_str for x in server_error_indicators):
        return True

    # Network errors
    network_error_indicators = [
        'connection',
        'network',
        'reset',
        'refused',
        'unreachable',
        'eof',
        'broken pipe',
    ]
    if any(x in error_str for x in network_error_indicators):
        return True

    return False


def classify_error(error: Exception) -> Exception:
    """Classify an error into a more specific exception type.

    Args:
        error: The original exception.

    Returns:
        A more specific exception type if applicable.
    """
    # Kept as is, as in is_retryable_error: the message names the model, and a
    # date-stamped model ID (e.g. ...-20250429-v1:0) contains "429".
    if isinstance(error, (ContentFilteredError, RunTimeLimitError)):
        return error
    # A permanent AWS error keeps its own type; "429" in an ARN or "timeout"
    # in a validation message must not make it look like a rate limit.
    if isinstance(error, ClientError) and not is_retryable_error(error):
        return error

    error_str = str(error).lower()

    if '429' in error_str or 'rate limit' in error_str:
        return LLMRateLimitError(str(error))

    if 'timeout' in error_str or 'timed out' in error_str:
        return LLMTimeoutError(str(error))

    if is_retryable_error(error):
        return RetryableError(str(error))

    return error


async def retry_async(
    func: Callable[..., Any],
    *args,
    max_retries: int = -1,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    timeout: Optional[float] = None,
    operation_name: str = "LLM call",
    **kwargs
) -> Any:
    """Execute async function with retry and timeout.

    Implements exponential backoff with jitter for robust retry behavior.
    Each attempt has an independent timeout, and retries occur only for
    transient/retryable errors.

    Args:
        func: Async function to call.
        *args: Positional arguments for the function.
        max_retries: Maximum retry attempts (must be >= 0). Defaults to settings.llm_max_retries.
            IMPORTANT: None is not allowed to prevent infinite retry loops.
        base_delay: Initial delay between retries in seconds.
            Defaults to settings.llm_retry_base_delay.
        max_delay: Maximum delay between retries in seconds.
            Defaults to settings.llm_retry_max_delay.
        timeout: Timeout per attempt in seconds.
            Defaults to settings.llm_timeout_seconds.
        operation_name: Name for logging purposes.
        **kwargs: Keyword arguments for the function.

    Returns:
        Function result.

    Raises:
        ValueError: If max_retries < 0.
        LLMTimeoutError: If all attempts timeout.
        LLMRateLimitError: If rate limited after all retries.
        LLMClientError: If a non-retryable error occurs.
    """
    # Import settings here to avoid circular imports
    from src.config import settings

    # Use settings default if sentinel value provided
    if max_retries == -1:
        max_retries = settings.llm_max_retries

    # Validate max_retries
    if max_retries < 0:
        raise ValueError(f"max_retries must be non-negative, got {max_retries}")

    # Warn if suspiciously high
    if max_retries > 10:
        logger.warning(
            "high_max_retries",
            max_retries=max_retries,
            operation=operation_name,
            message="max_retries > 10 may indicate a configuration issue"
        )

    base_delay = base_delay if base_delay is not None else settings.llm_retry_base_delay
    max_delay = max_delay if max_delay is not None else settings.llm_retry_max_delay
    timeout = timeout if timeout is not None else settings.llm_timeout_seconds

    last_error: Optional[Exception] = None
    total_attempts = max_retries + 1

    for attempt in range(total_attempts):
        try:
            # Apply timeout to each attempt
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout
            )

        except asyncio.TimeoutError:
            last_error = LLMTimeoutError(
                f"{operation_name} timed out after {timeout}s "
                f"(attempt {attempt + 1}/{total_attempts})"
            )
            logger.warning(
                "llm_timeout",
                operation=operation_name,
                attempt=attempt + 1,
                max_attempts=total_attempts,
                timeout_seconds=timeout
            )

        except asyncio.CancelledError:
            # Don't retry on cancellation - propagate immediately
            raise

        except Exception as e:
            # Classify the error
            classified_error = classify_error(e)
            last_error = classified_error

            if not is_retryable_error(e):
                # Non-retryable error, raise immediately
                logger.error(
                    "llm_non_retryable_error",
                    operation=operation_name,
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise classified_error from e

            logger.warning(
                "llm_retryable_error",
                operation=operation_name,
                attempt=attempt + 1,
                max_attempts=total_attempts,
                error=str(e),
                error_type=type(e).__name__
            )

        # Don't sleep after last attempt
        if attempt < max_retries:
            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            actual_delay = delay + jitter

            logger.info(
                "llm_retry_backoff",
                operation=operation_name,
                attempt=attempt + 1,
                next_attempt=attempt + 2,
                delay_seconds=round(actual_delay, 2)
            )

            await asyncio.sleep(actual_delay)

    # All retries exhausted
    logger.error(
        "llm_all_retries_exhausted",
        operation=operation_name,
        total_attempts=total_attempts,
        final_error=str(last_error)
    )

    if last_error is not None:
        raise last_error
    else:
        raise LLMClientError(f"{operation_name} failed after {total_attempts} attempts")


def sync_retry(
    func: Callable[..., Any],
    *args,
    max_retries: int = -1,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    operation_name: str = "LLM call",
    remaining_time: Optional[Callable[[], Optional[float]]] = None,
    **kwargs
) -> Any:
    """Execute sync function with retry.

    Note: This does not include timeout handling since Python sync code
    cannot be easily interrupted. Use for quick operations or when the
    underlying library handles its own timeouts.

    Args:
        func: Sync function to call.
        *args: Positional arguments for the function.
        max_retries: Maximum retry attempts (must be >= 0). Defaults to settings.llm_max_retries.
            IMPORTANT: None is not allowed to prevent infinite retry loops.
        base_delay: Initial delay between retries in seconds.
            Defaults to settings.llm_retry_base_delay.
        max_delay: Maximum delay between retries in seconds.
            Defaults to settings.llm_retry_max_delay.
        operation_name: Name for logging purposes.
        **kwargs: Keyword arguments for the function.

    Returns:
        Function result.

    Raises:
        ValueError: If max_retries < 0.
        LLMTimeoutError: If timeout errors occur.
        LLMRateLimitError: If rate limited after all retries.
        LLMClientError: If a non-retryable error occurs.
    """
    # Import settings here to avoid circular imports
    from src.config import settings

    # Use settings default if sentinel value provided
    if max_retries == -1:
        max_retries = settings.llm_max_retries

    # Validate max_retries
    if max_retries < 0:
        raise ValueError(f"max_retries must be non-negative, got {max_retries}")

    # Warn if suspiciously high
    if max_retries > 10:
        logger.warning(
            "high_max_retries",
            max_retries=max_retries,
            operation=operation_name,
            message="max_retries > 10 may indicate a configuration issue"
        )

    base_delay = base_delay if base_delay is not None else settings.llm_retry_base_delay
    max_delay = max_delay if max_delay is not None else settings.llm_retry_max_delay

    last_error: Optional[Exception] = None
    total_attempts = max_retries + 1

    for attempt in range(total_attempts):
        remaining = remaining_time() if remaining_time else None
        if remaining is not None and remaining <= 0:
            raise RunTimeLimitError("Run time limit reached before a model retry")
        try:
            return func(*args, **kwargs)

        except Exception as e:
            # Classify the error
            classified_error = classify_error(e)
            last_error = classified_error

            if not is_retryable_error(e):
                # Non-retryable error, raise immediately
                logger.error(
                    "sync_non_retryable_error",
                    operation=operation_name,
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise classified_error from e

            logger.warning(
                "sync_retryable_error",
                operation=operation_name,
                attempt=attempt + 1,
                max_attempts=total_attempts,
                error=str(e),
                error_type=type(e).__name__
            )

        # Don't sleep after last attempt
        if attempt < max_retries:
            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            actual_delay = delay + jitter

            logger.info(
                "sync_retry_backoff",
                operation=operation_name,
                attempt=attempt + 1,
                next_attempt=attempt + 2,
                delay_seconds=round(actual_delay, 2)
            )

            remaining = remaining_time() if remaining_time else None
            if remaining is not None and actual_delay >= remaining:
                time.sleep(max(0, remaining))
                raise RunTimeLimitError("Run time limit reached during retry backoff")
            time.sleep(actual_delay)

    # All retries exhausted
    logger.error(
        "sync_all_retries_exhausted",
        operation=operation_name,
        total_attempts=total_attempts,
        final_error=str(last_error)
    )

    if last_error is not None:
        raise last_error
    else:
        raise LLMClientError(f"{operation_name} failed after {total_attempts} attempts")
