"""OpenAI embedding client using text-embedding-3-small"""

import os
from typing import List
from openai import OpenAI, AsyncOpenAI

from src.embeddings.base import BaseEmbeddingClient
from src.utils.errors import CoScientistError


class OpenAIEmbeddingClient(BaseEmbeddingClient):
    """OpenAI embedding client

    Uses text-embedding-3-small model with 1536 dimensions.
    Supports both sync and async operations.
    """

    def __init__(self, model: str = "text-embedding-3-small"):
        """Initialize OpenAI embedding client

        Args:
            model: Model name (default: text-embedding-3-small)
        """
        self._model_name = model

        # Dimension mapping for OpenAI models
        self._dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

        if model not in self._dimensions:
            raise CoScientistError(
                f"Unknown OpenAI embedding model: {model}. "
                f"Supported models: {list(self._dimensions.keys())}"
            )

        # Configure API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise CoScientistError(
                "OPENAI_API_KEY environment variable not set. "
                "Required for OpenAI embedding client."
            )

        self._client = OpenAI(api_key=api_key)
        self._async_client = AsyncOpenAI(api_key=api_key)

    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self._client.embeddings.create(
                model=self._model_name,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise CoScientistError(f"OpenAI embedding failed: {str(e)}")

    async def aembed(self, text: str) -> List[float]:
        """Async version of embed

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = await self._async_client.embeddings.create(
                model=self._model_name,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise CoScientistError(f"OpenAI async embedding failed: {str(e)}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            response = self._client.embeddings.create(
                model=self._model_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise CoScientistError(f"OpenAI batch embedding failed: {str(e)}")

    async def aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """Async version of embed_batch

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            response = await self._async_client.embeddings.create(
                model=self._model_name,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise CoScientistError(f"OpenAI async batch embedding failed: {str(e)}")

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors"""
        return self._dimensions[self._model_name]

    @property
    def model_name(self) -> str:
        """Name of the embedding model"""
        return self._model_name
