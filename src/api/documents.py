"""
Document API Endpoints

REST API for uploading and searching private literature repository.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field
from typing import Optional
import structlog

from src.literature.repository import PrivateRepository

logger = structlog.get_logger()

# Create router
router = APIRouter(prefix="/documents", tags=["Documents"])

# Initialize repository (singleton)
# Note: In production, this would be dependency-injected with
# vector_store and embedding_client from Phase 5A
_repository: Optional[PrivateRepository] = None


def get_repository() -> PrivateRepository:
    """Get or create repository instance."""
    global _repository
    if _repository is None:
        # Initialize without vector store for now
        # Will be updated when Phase 5A is integrated
        _repository = PrivateRepository()
    return _repository


# ==============================================================================
# Request/Response Models
# ==============================================================================


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    title: str = Field(..., description="Extracted title")
    status: str = Field(..., description="Upload status")


class DocumentSearchResponse(BaseModel):
    """Search results response."""

    results: list[dict] = Field(..., description="Search results")
    query: str = Field(..., description="Original query")
    total_results: int = Field(..., description="Number of results")


class DocumentListResponse(BaseModel):
    """Document list response."""

    documents: list[dict] = Field(..., description="Document summaries")
    total: int = Field(..., description="Total documents in repository")
    limit: Optional[int] = Field(None, description="Results per page")
    offset: int = Field(..., description="Offset for pagination")


class DocumentDetailResponse(BaseModel):
    """Detailed document information."""

    id: str
    filename: str
    title: str
    authors: list[str]
    abstract: Optional[str]
    metadata: dict
    chunk_count: int
    indexed_at: str


class RepositoryStatsResponse(BaseModel):
    """Repository statistics."""

    total_documents: int
    total_chunks: int
    avg_chunks_per_doc: float
    has_semantic_search: bool


# ==============================================================================
# Endpoints
# ==============================================================================


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload")
):
    """Upload a PDF document to the private repository.

    The document will be parsed, chunked, and indexed for semantic search.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    logger.info("Uploading document", filename=file.filename)

    try:
        # Read file content
        content = await file.read()

        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty file"
            )

        # Add to repository
        repository = get_repository()
        doc_id = await repository.add_document_bytes(content, file.filename)

        # Get document details
        document = repository.get_document(doc_id)
        if not document:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve indexed document"
            )

        logger.info(
            "Document uploaded successfully",
            doc_id=doc_id,
            filename=file.filename
        )

        return DocumentUploadResponse(
            document_id=doc_id,
            filename=document.filename,
            title=document.title,
            status="indexed"
        )

    except Exception as e:
        logger.error(
            "Document upload failed",
            filename=file.filename,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
    query: str = Query(..., description="Search query"),
    k: int = Query(5, ge=1, le=20, description="Number of results"),
    return_chunks: bool = Query(False, description="Return chunks instead of documents")
):
    """Search the document repository.

    Uses semantic search if vector storage is available, otherwise
    falls back to keyword search.
    """
    logger.info("Searching documents", query=query, k=k)

    try:
        repository = get_repository()
        results = await repository.search(
            query=query,
            k=k,
            return_chunks=return_chunks
        )

        logger.info(
            "Search completed",
            query=query,
            results_count=len(results)
        )

        return DocumentSearchResponse(
            results=results,
            query=query,
            total_results=len(results)
        )

    except Exception as e:
        logger.error(
            "Search failed",
            query=query,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: Optional[int] = Query(None, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """List all documents in the repository.

    Returns document summaries with pagination.
    """
    logger.info("Listing documents", limit=limit, offset=offset)

    try:
        repository = get_repository()
        documents = repository.list_documents(limit=limit, offset=offset)
        stats = repository.get_statistics()

        return DocumentListResponse(
            documents=documents,
            total=stats['total_documents'],
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error("List documents failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: str):
    """Get detailed information about a specific document."""
    logger.info("Getting document", document_id=document_id)

    try:
        repository = get_repository()
        document = repository.get_document(document_id)

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found"
            )

        return DocumentDetailResponse(
            id=document.id,
            filename=document.filename,
            title=document.title,
            authors=document.authors,
            abstract=document.abstract,
            metadata=document.metadata,
            chunk_count=len(document.chunk_ids),
            indexed_at=document.indexed_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Get document failed",
            document_id=document_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get document: {str(e)}"
        )


@router.get("/stats/repository", response_model=RepositoryStatsResponse)
async def get_repository_stats():
    """Get repository statistics."""
    logger.info("Getting repository statistics")

    try:
        repository = get_repository()
        stats = repository.get_statistics()

        return RepositoryStatsResponse(**stats)

    except Exception as e:
        logger.error("Get stats failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document from the repository.

    Note: This is a placeholder. Full implementation would need to:
    1. Remove document from repository
    2. Remove associated chunks from vector store
    3. Clean up any references
    """
    # Not implemented in this phase
    raise HTTPException(
        status_code=501,
        detail="Document deletion not yet implemented"
    )
