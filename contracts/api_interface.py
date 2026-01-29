"""
Contract: API Endpoint Contracts
Version: 3f65fb4 (current commit)
Generated: 2025-01-29
Purpose: Define the API response models for new Phase 5 endpoints
Consumers: task-tool-integration, task-literature-processing, task-frontend
"""
from typing import List, Optional, Any
from pydantic import BaseModel


# =============================================================================
# Literature Endpoints
# =============================================================================


class DocumentUploadResponse(BaseModel):
    """Response from document upload endpoint."""

    document_id: str
    filename: str
    title: Optional[str] = None
    page_count: int
    chunk_count: int
    status: str = "indexed"


class DocumentSearchRequest(BaseModel):
    """Request for document search endpoint."""

    query: str
    k: int = 5
    return_chunks: bool = False


class DocumentSearchResponse(BaseModel):
    """Response from document search endpoint."""

    query: str
    results: List[dict]
    total_results: int


class DocumentListResponse(BaseModel):
    """Response from document list endpoint."""

    documents: List[dict]
    total_count: int


# =============================================================================
# PubMed Tool Endpoints
# =============================================================================


class PubMedSearchRequest(BaseModel):
    """Request for PubMed search endpoint."""

    query: str
    max_results: int = 10


class PubMedSearchResponse(BaseModel):
    """Response from PubMed search endpoint."""

    query: str
    articles: List[dict]
    total_results: int


# =============================================================================
# Settings Endpoints
# =============================================================================


class SettingsResponse(BaseModel):
    """Response from settings endpoint."""

    llm_provider: str
    model: str
    temperature: float
    max_iterations: int
    tournament_rounds: int
    elo_k_factor: int
    enable_evolution: bool
    enable_web_search: bool
    enable_literature_search: bool


class SettingsUpdateRequest(BaseModel):
    """Request to update settings."""

    llm_provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_iterations: Optional[int] = None
    tournament_rounds: Optional[int] = None
    elo_k_factor: Optional[int] = None
    enable_evolution: Optional[bool] = None
    enable_web_search: Optional[bool] = None
    enable_literature_search: Optional[bool] = None
