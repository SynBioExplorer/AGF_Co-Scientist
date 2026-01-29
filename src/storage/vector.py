"""Vector storage abstraction for semantic similarity search

This module provides vector database implementations for storing and querying
hypothesis embeddings. Supports both ChromaDB (local) and pgvector (PostgreSQL).
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import numpy as np


class VectorDocument(BaseModel):
    """A document with vector embedding and metadata"""

    id: str = Field(..., description="Unique identifier")
    content: str = Field(..., description="Text content that was embedded")
    embedding: List[float] = Field(..., description="Vector embedding")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., hypothesis_id, goal_id)"
    )


class VectorSearchResult(BaseModel):
    """Result from vector similarity search"""

    document: VectorDocument
    similarity: float = Field(..., description="Similarity score (0.0 to 1.0)")
    distance: float = Field(..., description="Distance metric (cosine, euclidean, etc)")


class BaseVectorStore(ABC):
    """Abstract base class for vector storage implementations"""

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to vector store"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection and cleanup resources"""
        pass

    @abstractmethod
    async def add_documents(
        self,
        documents: List[VectorDocument],
        collection_name: str = "hypotheses"
    ) -> None:
        """Add documents with embeddings to the store

        Args:
            documents: List of documents with embeddings
            collection_name: Name of the collection/table to store in
        """
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "hypotheses",
        limit: int = 10,
        min_similarity: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Search for similar documents by embedding

        Args:
            query_embedding: Query vector to search for
            collection_name: Collection to search in
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0.0 to 1.0)
            filters: Optional metadata filters (e.g., {"goal_id": "xyz"})

        Returns:
            List of search results ordered by similarity (highest first)
        """
        pass

    @abstractmethod
    async def delete(
        self,
        document_ids: List[str],
        collection_name: str = "hypotheses"
    ) -> int:
        """Delete documents by ID

        Args:
            document_ids: List of document IDs to delete
            collection_name: Collection to delete from

        Returns:
            Number of documents deleted
        """
        pass

    @abstractmethod
    async def get(
        self,
        document_id: str,
        collection_name: str = "hypotheses"
    ) -> Optional[VectorDocument]:
        """Retrieve a document by ID

        Args:
            document_id: ID of the document
            collection_name: Collection to retrieve from

        Returns:
            The document if found, None otherwise
        """
        pass

    @abstractmethod
    async def clear_collection(self, collection_name: str = "hypotheses") -> None:
        """Clear all documents from a collection

        Args:
            collection_name: Collection to clear
        """
        pass

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two vectors

        Args:
            vec_a: First vector
            vec_b: Second vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        a = np.array(vec_a)
        b = np.array(vec_b)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB implementation of vector store

    ChromaDB is an in-process vector database optimized for development
    and small-scale deployments. Persists to disk.
    """

    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initialize ChromaDB vector store

        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = persist_directory
        self._client = None
        self._collections: Dict[str, Any] = {}

    async def connect(self) -> None:
        """Initialize ChromaDB client"""
        try:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.Client(
                Settings(
                    persist_directory=self.persist_directory,
                    anonymized_telemetry=False
                )
            )
        except ImportError:
            raise ImportError(
                "ChromaDB not installed. Install with: pip install chromadb"
            )

    async def disconnect(self) -> None:
        """ChromaDB client cleanup (no-op, auto-persists)"""
        self._collections.clear()
        self._client = None

    def _get_collection(self, collection_name: str):
        """Get or create a ChromaDB collection"""
        if collection_name not in self._collections:
            self._collections[collection_name] = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine distance
            )
        return self._collections[collection_name]

    async def add_documents(
        self,
        documents: List[VectorDocument],
        collection_name: str = "hypotheses"
    ) -> None:
        """Add documents to ChromaDB"""
        collection = self._get_collection(collection_name)

        ids = [doc.id for doc in documents]
        embeddings = [doc.embedding for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        documents_text = [doc.content for doc in documents]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents_text
        )

    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "hypotheses",
        limit: int = 10,
        min_similarity: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Search ChromaDB for similar documents"""
        collection = self._get_collection(collection_name)

        # ChromaDB uses distance, not similarity
        # For cosine: distance = 1 - similarity
        # So min_similarity = 0.7 means max_distance = 0.3
        max_distance = 1.0 - min_similarity if min_similarity > 0 else None

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=filters,
            include=["embeddings", "metadatas", "documents", "distances"]
        )

        # Convert to VectorSearchResult
        search_results = []
        if results["ids"] and len(results["ids"]) > 0:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = 1.0 - distance  # Convert distance to similarity

                # Filter by min_similarity if specified
                if max_distance is not None and distance > max_distance:
                    continue

                doc = VectorDocument(
                    id=doc_id,
                    content=results["documents"][0][i],
                    embedding=results["embeddings"][0][i],
                    metadata=results["metadatas"][0][i] or {}
                )

                search_results.append(
                    VectorSearchResult(
                        document=doc,
                        similarity=similarity,
                        distance=distance
                    )
                )

        return search_results

    async def delete(
        self,
        document_ids: List[str],
        collection_name: str = "hypotheses"
    ) -> int:
        """Delete documents from ChromaDB"""
        collection = self._get_collection(collection_name)
        collection.delete(ids=document_ids)
        return len(document_ids)

    async def get(
        self,
        document_id: str,
        collection_name: str = "hypotheses"
    ) -> Optional[VectorDocument]:
        """Retrieve a document from ChromaDB"""
        collection = self._get_collection(collection_name)

        results = collection.get(
            ids=[document_id],
            include=["embeddings", "metadatas", "documents"]
        )

        if not results["ids"] or len(results["ids"]) == 0:
            return None

        return VectorDocument(
            id=results["ids"][0],
            content=results["documents"][0],
            embedding=results["embeddings"][0],
            metadata=results["metadatas"][0] or {}
        )

    async def clear_collection(self, collection_name: str = "hypotheses") -> None:
        """Clear all documents from a ChromaDB collection"""
        if self._client:
            try:
                self._client.delete_collection(name=collection_name)
                if collection_name in self._collections:
                    del self._collections[collection_name]
            except Exception:
                pass  # Collection may not exist


class PgVectorStore(BaseVectorStore):
    """PostgreSQL + pgvector implementation of vector store

    Uses pgvector extension for efficient vector similarity search
    in PostgreSQL. Suitable for production deployments.
    """

    def __init__(self, database_url: str):
        """Initialize pgvector store

        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url
        self._pool = None

    async def connect(self) -> None:
        """Initialize PostgreSQL connection pool with pgvector"""
        try:
            import asyncpg
        except ImportError:
            raise ImportError(
                "asyncpg not installed. Install with: pip install asyncpg"
            )

        self._pool = await asyncpg.create_pool(self.database_url)

        # Create pgvector extension and tables
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    async def disconnect(self) -> None:
        """Close PostgreSQL connection pool"""
        if self._pool:
            await self._pool.close()

    async def _ensure_table(self, collection_name: str, dimension: int = 768) -> None:
        """Ensure collection table exists

        Args:
            collection_name: Name of the collection
            dimension: Dimension of vectors (default 768 for Google embeddings)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {collection_name} (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding vector({dimension}) NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create index for fast similarity search
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {collection_name}_embedding_idx
                ON {collection_name}
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)

    async def add_documents(
        self,
        documents: List[VectorDocument],
        collection_name: str = "hypotheses"
    ) -> None:
        """Add documents to PostgreSQL with pgvector"""
        if not documents:
            return

        # Infer dimension from first document
        dimension = len(documents[0].embedding)
        await self._ensure_table(collection_name, dimension)

        async with self._pool.acquire() as conn:
            for doc in documents:
                await conn.execute(
                    f"""
                    INSERT INTO {collection_name} (id, content, embedding, metadata)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                    """,
                    doc.id,
                    doc.content,
                    doc.embedding,
                    doc.metadata
                )

    async def search(
        self,
        query_embedding: List[float],
        collection_name: str = "hypotheses",
        limit: int = 10,
        min_similarity: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Search PostgreSQL pgvector for similar documents"""
        dimension = len(query_embedding)
        await self._ensure_table(collection_name, dimension)

        # Build WHERE clause for filters
        where_clause = ""
        params = [query_embedding, limit]

        if filters:
            conditions = []
            for key, value in filters.items():
                params.append(value)
                conditions.append(f"metadata->>{repr(key)} = ${len(params)}")
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

        # pgvector cosine distance: <=> operator
        # Similarity = 1 - distance
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, content, embedding, metadata,
                       1 - (embedding <=> $1) AS similarity,
                       embedding <=> $1 AS distance
                FROM {collection_name}
                {where_clause}
                ORDER BY embedding <=> $1
                LIMIT $2
                """,
                *params
            )

        results = []
        for row in rows:
            similarity = float(row["similarity"])

            # Filter by min_similarity
            if similarity < min_similarity:
                continue

            doc = VectorDocument(
                id=row["id"],
                content=row["content"],
                embedding=list(row["embedding"]),
                metadata=dict(row["metadata"]) if row["metadata"] else {}
            )

            results.append(
                VectorSearchResult(
                    document=doc,
                    similarity=similarity,
                    distance=float(row["distance"])
                )
            )

        return results

    async def delete(
        self,
        document_ids: List[str],
        collection_name: str = "hypotheses"
    ) -> int:
        """Delete documents from PostgreSQL"""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {collection_name} WHERE id = ANY($1)",
                document_ids
            )
            # Extract count from result string like "DELETE 5"
            return int(result.split()[-1]) if result else 0

    async def get(
        self,
        document_id: str,
        collection_name: str = "hypotheses"
    ) -> Optional[VectorDocument]:
        """Retrieve a document from PostgreSQL"""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT id, content, embedding, metadata FROM {collection_name} WHERE id = $1",
                document_id
            )

        if not row:
            return None

        return VectorDocument(
            id=row["id"],
            content=row["content"],
            embedding=list(row["embedding"]),
            metadata=dict(row["metadata"]) if row["metadata"] else {}
        )

    async def clear_collection(self, collection_name: str = "hypotheses") -> None:
        """Clear all documents from a PostgreSQL collection"""
        async with self._pool.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {collection_name} CASCADE")
