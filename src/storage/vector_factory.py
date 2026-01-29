"""Factory for creating vector stores and embedding clients"""

from typing import Literal, Optional

from src.storage.vector import BaseVectorStore, ChromaVectorStore, PgVectorStore
from src.embeddings.base import BaseEmbeddingClient
from src.embeddings.google import GoogleEmbeddingClient
from src.embeddings.openai import OpenAIEmbeddingClient
from src.utils.errors import CoScientistError


VectorStoreType = Literal["chroma", "pgvector"]
EmbeddingProvider = Literal["google", "openai"]


def create_vector_store(
    store_type: VectorStoreType,
    chroma_persist_directory: Optional[str] = "./chroma_db",
    database_url: Optional[str] = None
) -> BaseVectorStore:
    """Create a vector store instance

    Args:
        store_type: Type of vector store ("chroma" or "pgvector")
        chroma_persist_directory: Directory for ChromaDB persistence
        database_url: PostgreSQL connection URL for pgvector

    Returns:
        Vector store instance

    Raises:
        CoScientistError: If store type is not supported or config is invalid
    """
    if store_type == "chroma":
        return ChromaVectorStore(persist_directory=chroma_persist_directory)

    elif store_type == "pgvector":
        if not database_url:
            raise CoScientistError(
                "database_url is required for pgvector store type"
            )
        return PgVectorStore(database_url=database_url)

    else:
        raise CoScientistError(
            f"Unsupported vector store type: {store_type}. "
            f"Supported types: 'chroma', 'pgvector'"
        )


def create_embedding_client(
    provider: EmbeddingProvider,
    model: Optional[str] = None
) -> BaseEmbeddingClient:
    """Create an embedding client instance

    Args:
        provider: Embedding provider ("google" or "openai")
        model: Optional model name override

    Returns:
        Embedding client instance

    Raises:
        CoScientistError: If provider is not supported
    """
    if provider == "google":
        model = model or "text-embedding-004"
        return GoogleEmbeddingClient(model=model)

    elif provider == "openai":
        model = model or "text-embedding-3-small"
        return OpenAIEmbeddingClient(model=model)

    else:
        raise CoScientistError(
            f"Unsupported embedding provider: {provider}. "
            f"Supported providers: 'google', 'openai'"
        )


def get_vector_store_from_config() -> BaseVectorStore:
    """Create vector store using settings from config

    Returns:
        Vector store instance based on config
    """
    from src.config import settings

    return create_vector_store(
        store_type=settings.vector_store_type,
        chroma_persist_directory=settings.chroma_persist_directory,
        database_url=settings.database_url if settings.vector_store_type == "pgvector" else None
    )


def get_embedding_client_from_config() -> BaseEmbeddingClient:
    """Create embedding client using settings from config

    Returns:
        Embedding client instance based on config
    """
    from src.config import settings

    return create_embedding_client(
        provider=settings.embedding_provider,
        model=getattr(settings, f"{settings.embedding_provider}_embedding_model", None)
    )
