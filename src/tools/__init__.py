"""Tool integration for literature research and external data sources"""

from src.tools.base import BaseTool, ToolResult
from src.tools.registry import registry, ToolRegistry
from src.tools.pubmed import PubMedTool, register_pubmed_tool

# Auto-register PubMed tool on import
register_pubmed_tool()

__all__ = [
    "BaseTool",
    "ToolResult",
    "registry",
    "ToolRegistry",
    "PubMedTool",
]
