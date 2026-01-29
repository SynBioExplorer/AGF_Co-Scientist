"""Google embedding client using text-embedding-004"""

import os
from typing import List
from google import genai
from google.genai import types

from src.embeddings.base import BaseEmbeddingClient
from src.utils.errors import CoScientistError


class GoogleEmbeddingClient(BaseEmbeddingClient):
    """Google Generative AI embedding client

    Uses text-embedding-004 model with 768 dimensions.
    Supports both sync and async operations.
    """

    def __init__(self, model: str = "text-embedding-004"):
        """Initialize Google embedding client

        Args:
            model: Model name (default: text-embedding-004)
        """
        self._model_name = model
        self._dimension = 768  # text-embedding-004 dimension

        # Configure API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise CoScientistError(
                "GOOGLE_API_KEY environment variable not set. "
                "Required for Google embedding client."
            )

        self._client = genai.Client(api_key=api_key)

    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            result = self._client.models.embed_content(
                model=self._model_name,
                contents=types.EmbedContentConfig(
                    content=types.Content(parts=[types.Part(text=text)]),
                    task_type="retrieval_document"
                )
            )
            return list(result.embeddings[0].values)
        except Exception as e:
            raise CoScientistError(f"Google embedding failed: {str(e)}")

    async def aembed(self, text: str) -> List[float]:
        """Async version of embed

        Note: Google SDK doesn't have native async support,
        so this wraps the sync version. For true async,
        consider using httpx with the REST API.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        return self.embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            # Process each text individually and collect results
            embeddings = []
            for text in texts:
                result = self._client.models.embed_content(
                    model=self._model_name,
                    contents=types.EmbedContentConfig(
                        content=types.Content(parts=[types.Part(text=text)]),
                        task_type="retrieval_document"
                    )
                )
                embeddings.append(list(result.embeddings[0].values))
            return embeddings
        except Exception as e:
            raise CoScientistError(f"Google batch embedding failed: {str(e)}")

    async def aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """Async version of embed_batch

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        return self.embed_batch(texts)

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors (768 for text-embedding-004)"""
        return self._dimension

    @property
    def model_name(self) -> str:
        """Name of the embedding model"""
        return self._model_name
