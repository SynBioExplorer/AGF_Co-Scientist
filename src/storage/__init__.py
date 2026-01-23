"""State storage and management.

Provides storage backends for the AI Co-Scientist system:
- InMemoryStorage: Synchronous in-memory storage (Phase 2)
- AsyncStorageAdapter: Async-compatible adapter (Phase 4)
"""

from src.storage.memory import InMemoryStorage, storage
from src.storage.async_adapter import AsyncStorageAdapter, async_storage

__all__ = ["InMemoryStorage", "storage", "AsyncStorageAdapter", "async_storage"]
