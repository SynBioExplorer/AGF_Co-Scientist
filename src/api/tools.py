"""API endpoints for tool integration"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field

from src.tools.registry import registry
from src.tools.base import ToolResult
import structlog

logger = structlog.get_logger()

router = APIRouter()


class ToolListResponse(BaseModel):
    """Response for listing available tools"""
    tools: list[dict] = Field(..., description="List of available tools")
    total_count: int = Field(..., description="Total number of tools")


class ToolSearchRequest(BaseModel):
    """Request for tool search"""
    query: str = Field(..., description="Search query")
    max_results: Optional[int] = Field(None, description="Maximum number of results")


class ToolSearchResponse(BaseModel):
    """Response for tool search"""
    success: bool = Field(..., description="Whether the search succeeded")
    data: list = Field(default_factory=list, description="Search results")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


# ==============================================================================
# Tool Registry Endpoints
# ==============================================================================


@router.get("/tools", response_model=ToolListResponse, tags=["Tools"])
async def list_tools():
    """List all available tools"""
    tools = registry.list_all_tools()

    return ToolListResponse(
        tools=tools,
        total_count=len(tools)
    )


@router.get("/tools/{tool_name}", tags=["Tools"])
async def get_tool_info(tool_name: str):
    """Get information about a specific tool"""
    tool = registry.get(tool_name)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return tool.to_dict()


@router.get("/tools/domain/{domain}", response_model=ToolListResponse, tags=["Tools"])
async def get_tools_by_domain(domain: str):
    """Get all tools for a specific domain"""
    tools = registry.get_tools_for_domain(domain)

    return ToolListResponse(
        tools=[tool.to_dict() for tool in tools],
        total_count=len(tools)
    )


# ==============================================================================
# PubMed Tool Endpoints
# ==============================================================================


@router.get("/tools/pubmed/search", response_model=ToolSearchResponse, tags=["Tools", "PubMed"])
async def search_pubmed(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Search PubMed for biomedical literature.

    This endpoint searches the PubMed database using the NCBI E-utilities API
    and returns article metadata including titles, abstracts, and author information.
    """
    logger.info(
        "PubMed search request",
        query=query[:100],
        max_results=max_results
    )

    # Get PubMed tool from registry
    pubmed_tool = registry.get("pubmed")

    if not pubmed_tool:
        raise HTTPException(
            status_code=500,
            detail="PubMed tool not available"
        )

    # Execute search
    result: ToolResult = await pubmed_tool.execute(query, max_results=max_results)

    return ToolSearchResponse(
        success=result.success,
        data=result.data or [],
        error=result.error,
        metadata=result.metadata
    )


@router.post("/tools/pubmed/search", response_model=ToolSearchResponse, tags=["Tools", "PubMed"])
async def search_pubmed_post(request: ToolSearchRequest):
    """
    Search PubMed for biomedical literature (POST version).

    This endpoint is identical to the GET version but accepts a JSON body.
    Useful for complex queries that might exceed URL length limits.
    """
    max_results = request.max_results or 10

    logger.info(
        "PubMed search request (POST)",
        query=request.query[:100],
        max_results=max_results
    )

    # Get PubMed tool from registry
    pubmed_tool = registry.get("pubmed")

    if not pubmed_tool:
        raise HTTPException(
            status_code=500,
            detail="PubMed tool not available"
        )

    # Execute search
    result: ToolResult = await pubmed_tool.execute(request.query, max_results=max_results)

    return ToolSearchResponse(
        success=result.success,
        data=result.data or [],
        error=result.error,
        metadata=result.metadata
    )
