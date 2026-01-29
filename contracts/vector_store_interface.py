"""
Contract: VectorStoreProtocol
Version: 3f65fb4 (current commit)
Generated: 2025-01-29
Purpose: Define the interface for vector storage backends (ChromaDB, pgvector)
Consumers: task-vector-storage, task-literature-processing
"""
from typing import Protocol, List, Optional, Tuple
from pydantic import BaseModel


class VectorDocument(BaseModel):
    """Document with embedding for vector storage."""

    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: dict = {}


class VectorStoreProtocol(Protocol):
    """Abstract vector store interface.

    All vector store backends must implement this protocol to ensure
    interchangeability between ChromaDB (local) and pgvector (production).
    """

    async def add_documents(self, documents: List[VectorDocument]) -> None:
        """Add documents with embeddings to the store.

        Args:
            documents: List of VectorDocument objects with embeddings
        """
        ...

    async def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        filter: Optional[dict] = None
    ) -> List[Tuple[VectorDocument, float]]:
        """Search by embedding, return (doc, score) pairs.

        Args:
            query_embedding: Embedding vector for query
            k: Number of results to return
            filter: Optional metadata filter

        Returns:
            List of (document, similarity_score) tuples, sorted by score descending
        """
        ...

    async def delete(self, ids: List[str]) -> None:
        """Delete documents by ID.

        Args:
            ids: List of document IDs to delete
        """
        ...

    async def get(self, id: str) -> Optional[VectorDocument]:
        """Get document by ID.

        Args:
            id: Document ID

        Returns:
            VectorDocument if found, None otherwise
        """
        ...
