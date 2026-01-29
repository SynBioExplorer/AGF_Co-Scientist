"""Abstract base class for embedding clients"""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingClient(ABC):
    """Abstract base class for embedding generation"""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    async def aembed(self, text: str) -> List[float]:
        """Async version of embed for parallel processing

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    async def aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """Async version of embed_batch

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the embedding model"""
        pass
