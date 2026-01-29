"""Base tool interface for external data sources"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result from a tool execution"""

    success: bool = Field(..., description="Whether the tool execution succeeded")
    data: Any = Field(None, description="Result data from the tool")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    metadata: dict = Field(default_factory=dict, description="Additional metadata about the execution")

    @classmethod
    def success_result(cls, data: Any, metadata: dict = None) -> "ToolResult":
        """Create a successful result"""
        return cls(
            success=True,
            data=data,
            error=None,
            metadata=metadata or {}
        )

    @classmethod
    def error_result(cls, error: str, metadata: dict = None) -> "ToolResult":
        """Create an error result"""
        return cls(
            success=False,
            data=None,
            error=error,
            metadata=metadata or {}
        )


class BaseTool(ABC):
    """Abstract base class for external tools"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (unique identifier)"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does"""
        pass

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain this tool is relevant for (e.g., biomedical, drug_discovery, chemistry)"""
        pass

    @abstractmethod
    async def execute(self, query: str, **kwargs) -> ToolResult:
        """
        Execute the tool with the given query.

        Args:
            query: The search query or input for the tool
            **kwargs: Additional tool-specific parameters

        Returns:
            ToolResult containing the execution result
        """
        pass

    def to_dict(self) -> dict:
        """Convert tool to dictionary representation"""
        return {
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
        }
