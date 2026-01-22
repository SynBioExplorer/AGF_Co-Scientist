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


class AgentExecutionError(CoScientistError):
    """Raised when agent execution fails"""
    pass


class ValidationError(CoScientistError):
    """Raised when data validation fails"""
    pass
