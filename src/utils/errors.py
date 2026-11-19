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


class RunTimeLimitError(CoScientistError):
    """The run's absolute model-work deadline has been reached; never retry."""
    pass


class RetryableError(LLMClientError):
    """Raised for transient LLM errors that can be retried.

    These include rate limits, timeouts, and transient server errors.
    The retry mechanism should catch these and attempt again with backoff.
    """
    pass


class ContentFilteredError(LLMClientError):
    """The model's built-in safety filter returned stopReason=content_filtered.

    Deterministic for a given prompt, so it is never retried. agent and model
    name the blocked call for the run's error message.
    """

    def __init__(self, message: str, *, agent: str | None = None, model: str | None = None):
        super().__init__(message)
        self.agent = agent
        self.model = model


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


class RunAbortedError(CoScientistError):
    """Raised when the supervisor ends a run that produced no hypotheses.

    str() is the user-facing reason: aws_entrypoint.py stores it as the run's
    error_message and puts it in the failure email.
    """
    pass
