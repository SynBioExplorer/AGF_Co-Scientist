"""
Contract: LiteratureProtocol
Version: 3f65fb4 (current commit)
Generated: 2025-01-29
Purpose: Define interfaces for literature processing (PDF, citations, repository)
Consumers: task-literature-processing, task-frontend
"""
from typing import Protocol, List, Optional
from pydantic import BaseModel


class PDFMetadata(BaseModel):
    """Extracted PDF metadata."""

    title: Optional[str] = None
    authors: List[str] = []
    abstract: Optional[str] = None
    doi: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    keywords: List[str] = []


class PDFSection(BaseModel):
    """Extracted section from PDF."""

    title: str
    content: str
    page_numbers: List[int] = []


class ParsedPDF(BaseModel):
    """Complete parsed PDF document."""

    filename: str
    metadata: PDFMetadata
    sections: List[PDFSection] = []
    full_text: str
    references: List[str] = []
    page_count: int


class PDFParserProtocol(Protocol):
    """Abstract PDF parser interface."""

    async def parse(self, file_path: str) -> ParsedPDF:
        """Parse PDF file and extract content.

        Args:
            file_path: Path to PDF file

        Returns:
            ParsedPDF with extracted content
        """
        ...

    async def parse_bytes(self, content: bytes, filename: str) -> ParsedPDF:
        """Parse PDF from bytes (for file uploads).

        Args:
            content: PDF content as bytes
            filename: Original filename

        Returns:
            ParsedPDF with extracted content
        """
        ...


class RepositoryDocument(BaseModel):
    """Document in private repository."""

    id: str
    filename: str
    title: Optional[str] = None
    authors: List[str] = []
    abstract: Optional[str] = None
    full_text: str
    chunk_ids: List[str] = []
    metadata: dict = {}


class LiteratureRepositoryProtocol(Protocol):
    """Abstract literature repository interface."""

    async def add_document(self, file_path: str) -> RepositoryDocument:
        """Add single document to repository.

        Args:
            file_path: Path to PDF file

        Returns:
            RepositoryDocument with chunk IDs
        """
        ...

    async def search(
        self,
        query: str,
        k: int = 5,
        return_chunks: bool = False
    ) -> List[dict]:
        """Search repository for relevant content.

        Args:
            query: Search query
            k: Number of results
            return_chunks: Whether to return chunks or documents

        Returns:
            List of search results
        """
        ...

    async def get_document(self, doc_id: str) -> Optional[RepositoryDocument]:
        """Get document by ID.

        Args:
            doc_id: Document ID

        Returns:
            RepositoryDocument if found
        """
        ...

    def list_documents(self) -> List[RepositoryDocument]:
        """List all indexed documents.

        Returns:
            List of all documents
        """
        ...
