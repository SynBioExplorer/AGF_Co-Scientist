"""Embedding clients for vector similarity search"""

from src.embeddings.base import BaseEmbeddingClient
from src.embeddings.google import GoogleEmbeddingClient
from src.embeddings.openai import OpenAIEmbeddingClient

__all__ = [
    "BaseEmbeddingClient",
    "GoogleEmbeddingClient",
    "OpenAIEmbeddingClient",
]
