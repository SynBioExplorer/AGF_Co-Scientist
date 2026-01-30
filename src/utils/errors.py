"""Custom exception classes"""


class CoScientistError(Exception):
    """Base exception for co-scientist system"""
    pass


class BudgetExceededError(CoScientistError):
    """Raised when budget limit exceeded"""
    pass


class PromptLoadError(CoScientistError):
    """Raised when prompt file cannot be loaded"""
    pass


class LLMClientError(CoScientistError):
    """Raised when LLM client fails"""
    pass


class RetryableError(LLMClientError):
    """Raised for transient LLM errors that can be retried.

    These include rate limits, timeouts, and transient server errors.
    The retry mechanism should catch these and attempt again with backoff.
    """
    pass


class LLMTimeoutError(RetryableError):
    """Raised when LLM invocation exceeds the configured timeout.

    This is a retryable error - the request may succeed on retry
    if the API is experiencing temporary slowness.
    """
    pass


class LLMRateLimitError(RetryableError):
    """Raised when API rate limit is exceeded (HTTP 429).

    This is a retryable error - the request should succeed after
    waiting for the rate limit window to reset.
    """
    pass


class AgentExecutionError(CoScientistError):
    """Raised when agent execution fails"""
    pass


class ValidationError(CoScientistError):
    """Raised when data validation fails"""
    pass


class CheckpointError(CoScientistError):
    """Raised when checkpoint save/load fails"""
    pass
