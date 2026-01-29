"""
Contract: EmbeddingClientProtocol
Version: 3f65fb4 (current commit)
Generated: 2025-01-29
Purpose: Define the interface for embedding clients (Google, OpenAI, Local)
Consumers: task-vector-storage, task-literature-processing
"""
from typing import Protocol, List


class EmbeddingClientProtocol(Protocol):
    """Abstract embedding client interface.

    All embedding clients must implement this protocol to ensure
    interchangeability between providers (Google, OpenAI, local).
    """

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        ...

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        ...

    @property
    def dimension(self) -> int:
        """Return embedding dimension.

        Returns:
            Dimension of embedding vectors (e.g., 768, 1536)
        """
        ...
