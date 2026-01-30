"""Tool registry for managing available tools"""

from typing import Dict, List, Optional
from src.tools.base import BaseTool
from src.utils.errors import CoScientistError
import structlog

logger = structlog.get_logger()


class ToolRegistry:
    """Registry for managing external tools"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.

        Args:
            tool: The tool to register

        Raises:
            CoScientistError: If a tool with the same name is already registered
        """
        if tool.name in self._tools:
            raise CoScientistError(f"Tool '{tool.name}' is already registered")

        self._tools[tool.name] = tool
        logger.info(
            "Tool registered",
            tool_name=tool.name,
            domain=tool.domain
        )

    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            name: The tool name

        Returns:
            The tool instance or None if not found
        """
        return self._tools.get(name)

    def get_tools_for_domain(self, domain: str) -> List[BaseTool]:
        """
        Get all tools for a specific domain.

        Args:
            domain: The domain to filter by

        Returns:
            List of tools matching the domain
        """
        return [
            tool for tool in self._tools.values()
            if tool.domain == domain
        ]

    def list_tools(self) -> List[str]:
        """
        Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def list_all_tools(self) -> List[dict]:
        """
        Get detailed information about all registered tools.

        Returns:
            List of tool dictionaries
        """
        return [tool.to_dict() for tool in self._tools.values()]

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.

        Args:
            name: The tool name

        Returns:
            True if tool was removed, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info("Tool unregistered", tool_name=name)
            return True
        return False


# Global registry instance
registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance"""
    return registry


def initialize_tools() -> ToolRegistry:
    """
    Initialize and register all available tools.

    Returns:
        ToolRegistry with all tools registered
    """
    # Import and register PubMed tool
    try:
        from src.tools.pubmed import register_pubmed_tool
        register_pubmed_tool()
    except ImportError as e:
        logger.warning("Could not register PubMed tool", error=str(e))

    # Import and register Semantic Scholar tool
    try:
        from src.tools.semantic_scholar import register_semantic_scholar_tool
        register_semantic_scholar_tool()
    except ImportError as e:
        logger.warning("Could not register Semantic Scholar tool", error=str(e))

    logger.info("Tool registry initialized", num_tools=len(registry.list_tools()))
    return registry
