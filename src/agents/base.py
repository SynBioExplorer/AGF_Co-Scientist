"""Base agent class"""

from abc import ABC, abstractmethod
from typing import Any
from src.llm.base import BaseLLMClient
import structlog

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(self, llm_client: BaseLLMClient, name: str):
        self.llm_client = llm_client
        self.name = name
        self.logger = logger.bind(agent=name)

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute agent task"""
        pass

    def log_execution(self, task: str, **metadata):
        """Log agent execution"""
        self.logger.info(
            f"{self.name} executing",
            task=task,
            **metadata
        )
