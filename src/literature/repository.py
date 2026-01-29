"""
Private Repository

Index and search a private collection of scientific PDFs.
Integrates with vector storage from Phase 5A for semantic search.
"""

import hashlib
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field
import structlog

from src.literature.pdf_parser import PDFParser
from src.literature.chunker import TextChunker

logger = structlog.get_logger()


class RepositoryDocument(BaseModel):
    """A document in the private repository."""

    id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    title: str = Field(..., description="Document title")
    authors: list[str] = Field(default_factory=list, description="Authors")
    abstract: Optional[str] = Field(None, description="Abstract")
    full_text: str = Field(..., description="Full document text")
    chunk_ids: list[str] = Field(
        default_factory=list,
        description="IDs of embedded chunks"
    )
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    indexed_at: datetime = Field(
        default_factory=datetime.now,
        description="When document was indexed"
    )


class PrivateRepository:
    """Repository for private scientific document collection."""

    def __init__(
        self,
        vector_store: Optional[Any] = None,
        embedding_client: Optional[Any] = None
    ):
        """Initialize repository.

        Args:
            vector_store: Vector store instance (from Phase 5A)
            embedding_client: Embedding client (from Phase 5A)

        Note:
            vector_store and embedding_client are optional to allow
            implementation before Phase 5A is complete. When both are
            available, semantic search will be enabled.
        """
        self.vector_store = vector_store
        self.embedding_client = embedding_client

        self.pdf_parser = PDFParser()
        self.chunker = TextChunker()

        # In-memory document storage (would be DB in production)
        self.documents: dict[str, RepositoryDocument] = {}

        logger.info(
            "PrivateRepository initialized",
            has_vector_store=vector_store is not None,
            has_embeddings=embedding_client is not None
        )

    async def index_directory(
        self,
        directory: str,
        pattern: str = "*.pdf"
    ) -> dict[str, str]:
        """Index all PDFs in a directory.

        Args:
            directory: Path to directory
            pattern: Glob pattern for files to index

        Returns:
            Dict mapping filenames to document IDs
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        indexed = {}
        pdf_files = list(dir_path.glob(pattern))

        logger.info(
            "Starting batch indexing",
            directory=directory,
            file_count=len(pdf_files)
        )

        for pdf_file in pdf_files:
            try:
                doc_id = await self.add_document(str(pdf_file))
                indexed[pdf_file.name] = doc_id
                logger.info("Indexed document", filename=pdf_file.name, doc_id=doc_id)

            except Exception as e:
                logger.error(
                    "Failed to index document",
                    filename=pdf_file.name,
                    error=str(e)
                )

        logger.info(
            "Batch indexing complete",
            successful=len(indexed),
            total=len(pdf_files)
        )

        return indexed

    async def add_document(self, file_path: str) -> str:
        """Add a single document to the repository.

        Args:
            file_path: Path to PDF file

        Returns:
            Document ID
        """
        # Parse PDF
        parsed_pdf = await self.pdf_parser.parse(file_path)

        # Generate document ID from content hash
        content_hash = hashlib.sha256(
            parsed_pdf.full_text.encode()
        ).hexdigest()
        doc_id = f"doc_{content_hash[:16]}"

        # Check if already indexed
        if doc_id in self.documents:
            logger.info("Document already indexed", doc_id=doc_id)
            return doc_id

        # Chunk document for embeddings
        chunk_ids = []
        if self.vector_store and self.embedding_client:
            chunk_ids = await self._embed_chunks(parsed_pdf, doc_id)

        # Create document record
        document = RepositoryDocument(
            id=doc_id,
            filename=parsed_pdf.filename,
            title=parsed_pdf.metadata.title or parsed_pdf.filename,
            authors=parsed_pdf.metadata.authors,
            abstract=parsed_pdf.metadata.abstract,
            full_text=parsed_pdf.full_text,
            chunk_ids=chunk_ids,
            metadata={
                'doi': parsed_pdf.metadata.doi,
                'year': parsed_pdf.metadata.year,
                'journal': parsed_pdf.metadata.journal,
                'keywords': parsed_pdf.metadata.keywords,
                'page_count': parsed_pdf.page_count,
                'reference_count': len(parsed_pdf.references)
            }
        )

        self.documents[doc_id] = document

        logger.info(
            "Document added to repository",
            doc_id=doc_id,
            title=document.title,
            chunks=len(chunk_ids)
        )

        return doc_id

    async def add_document_bytes(
        self,
        content: bytes,
        filename: str
    ) -> str:
        """Add document from bytes (e.g., uploaded file).

        Args:
            content: PDF file bytes
            filename: Original filename

        Returns:
            Document ID
        """
        # Parse PDF from bytes
        parsed_pdf = await self.pdf_parser.parse_bytes(content, filename)

        # Generate document ID
        content_hash = hashlib.sha256(content).hexdigest()
        doc_id = f"doc_{content_hash[:16]}"

        # Check if already indexed
        if doc_id in self.documents:
            logger.info("Document already indexed", doc_id=doc_id)
            return doc_id

        # Chunk and embed
        chunk_ids = []
        if self.vector_store and self.embedding_client:
            chunk_ids = await self._embed_chunks(parsed_pdf, doc_id)

        # Create document record
        document = RepositoryDocument(
            id=doc_id,
            filename=filename,
            title=parsed_pdf.metadata.title or filename,
            authors=parsed_pdf.metadata.authors,
            abstract=parsed_pdf.metadata.abstract,
            full_text=parsed_pdf.full_text,
            chunk_ids=chunk_ids,
            metadata={
                'doi': parsed_pdf.metadata.doi,
                'year': parsed_pdf.metadata.year,
                'journal': parsed_pdf.metadata.journal,
                'keywords': parsed_pdf.metadata.keywords,
                'page_count': parsed_pdf.page_count
            }
        )

        self.documents[doc_id] = document

        logger.info(
            "Document added from bytes",
            doc_id=doc_id,
            filename=filename,
            chunks=len(chunk_ids)
        )

        return doc_id

    async def _embed_chunks(self, parsed_pdf, doc_id: str) -> list[str]:
        """Chunk document and create embeddings.

        Args:
            parsed_pdf: Parsed PDF document
            doc_id: Document ID

        Returns:
            List of chunk IDs
        """
        # Convert sections to dict format
        sections = [
            {
                'title': section.title,
                'content': section.content,
                'page_numbers': section.page_numbers
            }
            for section in parsed_pdf.sections
        ]

        # Chunk sections
        if sections:
            chunks = self.chunker.chunk_sections(
                sections,
                chunk_size=500,
                overlap=50
            )
        else:
            # Fallback to chunking full text
            chunks = self.chunker.chunk_text(
                parsed_pdf.full_text,
                chunk_size=500,
                overlap=50
            )

        chunk_ids = []

        # Store chunks in vector store
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"

            # Prepare metadata
            chunk_metadata = {
                'document_id': doc_id,
                'chunk_index': i,
                'section_title': chunk.metadata.get('section_title'),
                'start_idx': chunk.start_idx,
                'end_idx': chunk.end_idx,
                'title': parsed_pdf.metadata.title,
                'authors': parsed_pdf.metadata.authors,
            }

            # Add to vector store (when available)
            # This will be implemented when Phase 5A is complete
            # await self.vector_store.add(
            #     chunk_id=chunk_id,
            #     text=chunk.text,
            #     metadata=chunk_metadata
            # )

            chunk_ids.append(chunk_id)

        return chunk_ids

    async def search(
        self,
        query: str,
        k: int = 5,
        return_chunks: bool = False
    ) -> list[dict]:
        """Search repository using semantic similarity.

        Args:
            query: Search query
            k: Number of results to return
            return_chunks: If True, return chunks; if False, return documents

        Returns:
            List of search results with scores
        """
        if not self.vector_store or not self.embedding_client:
            logger.warning(
                "Semantic search not available - vector store not configured"
            )
            # Fallback to basic keyword search
            return self._keyword_search(query, k)

        # Semantic search using vector store
        # This will be implemented when Phase 5A is complete
        # results = await self.vector_store.search(query, k=k * 3)

        # For now, use keyword search as fallback
        results = self._keyword_search(query, k)

        if return_chunks:
            return results
        else:
            # Group chunks by document and aggregate scores
            return self._aggregate_to_documents(results, k)

    def _keyword_search(self, query: str, k: int) -> list[dict]:
        """Fallback keyword-based search.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of matching documents
        """
        query_lower = query.lower()
        results = []

        for doc in self.documents.values():
            score = 0.0

            # Check title
            if query_lower in doc.title.lower():
                score += 2.0

            # Check abstract
            if doc.abstract and query_lower in doc.abstract.lower():
                score += 1.5

            # Check full text
            if query_lower in doc.full_text.lower():
                score += 0.5

            if score > 0:
                results.append({
                    'document_id': doc.id,
                    'title': doc.title,
                    'authors': doc.authors,
                    'abstract': doc.abstract,
                    'score': score,
                    'metadata': doc.metadata
                })

        # Sort by score and return top k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:k]

    def _aggregate_to_documents(self, chunk_results: list[dict], k: int) -> list[dict]:
        """Aggregate chunk results to document-level results.

        Args:
            chunk_results: List of chunk matches
            k: Number of documents to return

        Returns:
            List of document-level results
        """
        doc_scores = {}

        for result in chunk_results:
            doc_id = result.get('document_id') or result.get('metadata', {}).get('document_id')
            if not doc_id:
                continue

            score = result.get('score', 0.0)

            if doc_id not in doc_scores:
                doc_scores[doc_id] = []

            doc_scores[doc_id].append(score)

        # Aggregate scores (use max score)
        aggregated = []
        for doc_id, scores in doc_scores.items():
            doc = self.documents.get(doc_id)
            if doc:
                aggregated.append({
                    'document_id': doc.id,
                    'title': doc.title,
                    'authors': doc.authors,
                    'abstract': doc.abstract,
                    'score': max(scores),
                    'metadata': doc.metadata
                })

        # Sort and return top k
        aggregated.sort(key=lambda x: x['score'], reverse=True)
        return aggregated[:k]

    def get_document(self, doc_id: str) -> Optional[RepositoryDocument]:
        """Get document by ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document or None if not found
        """
        return self.documents.get(doc_id)

    def list_documents(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> list[dict]:
        """List all documents in repository.

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of document summaries
        """
        docs = list(self.documents.values())

        # Sort by indexed time (most recent first)
        docs.sort(key=lambda d: d.indexed_at, reverse=True)

        # Apply pagination
        if limit:
            docs = docs[offset:offset + limit]
        else:
            docs = docs[offset:]

        # Return summaries
        return [
            {
                'id': doc.id,
                'filename': doc.filename,
                'title': doc.title,
                'authors': doc.authors,
                'abstract': doc.abstract[:200] if doc.abstract else None,
                'metadata': doc.metadata,
                'indexed_at': doc.indexed_at.isoformat()
            }
            for doc in docs
        ]

    def get_statistics(self) -> dict:
        """Get repository statistics.

        Returns:
            Dictionary with statistics
        """
        total_docs = len(self.documents)
        total_chunks = sum(len(doc.chunk_ids) for doc in self.documents.values())

        return {
            'total_documents': total_docs,
            'total_chunks': total_chunks,
            'avg_chunks_per_doc': total_chunks / total_docs if total_docs > 0 else 0,
            'has_semantic_search': self.vector_store is not None
        }
