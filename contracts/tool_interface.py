"""
Contract: ToolProtocol
Version: 3f65fb4 (current commit)
Generated: 2025-01-29
Purpose: Define the interface for external tools (PubMed, etc.)
Consumers: task-tool-integration, task-literature-processing
"""
from typing import Protocol, List, Optional, Any
from pydantic import BaseModel


class ToolResult(BaseModel):
    """Result from a tool execution."""

    success: bool
    data: Any
    error: Optional[str] = None
    source: str  # Tool name that produced the result
    query: str  # Original query


class ArticleResult(BaseModel):
    """Article result from literature search."""

    pmid: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    authors: List[str] = []
    journal: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None


class ToolProtocol(Protocol):
    """Abstract tool interface.

    All tools must implement this protocol to enable registration
    in the tool registry and consistent invocation.
    """

    @property
    def name(self) -> str:
        """Return the tool name."""
        ...

    @property
    def description(self) -> str:
        """Return a description of what the tool does."""
        ...

    @property
    def domains(self) -> List[str]:
        """Return list of domains this tool is relevant for."""
        ...

    async def execute(
        self,
        query: str,
        max_results: int = 10,
        **kwargs
    ) -> ToolResult:
        """Execute the tool with given query.

        Args:
            query: Search query or input
            max_results: Maximum number of results
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with success status and data/error
        """
        ...
