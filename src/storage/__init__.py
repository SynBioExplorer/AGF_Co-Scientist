"""State storage and management for AI Co-Scientist.

This module provides storage abstraction layer with multiple backends:
- InMemoryStorage: For testing and development (Phase 1-3)
- PostgreSQLStorage: For production with persistence (Phase 4+)
- CachedStorage: PostgreSQL + Redis caching layer (Phase 4+)

Usage:
    from src.storage import get_storage, BaseStorage

    # Get storage based on configuration
    storage = get_storage()
    await storage.connect()

    # Use storage operations
    await storage.add_hypothesis(hypothesis)
    top_hyps = await storage.get_top_hypotheses(n=10)

    await storage.disconnect()

    # Or use context manager for automatic cleanup
    from src.storage import StorageContext

    async with StorageContext(backend="postgres") as storage:
        await storage.add_hypothesis(hypothesis)
"""

from src.storage.base import BaseStorage
from src.storage.memory import InMemoryStorage, SyncInMemoryStorage, storage
from src.storage.factory import get_storage, create_and_connect_storage, StorageContext

# Export all public classes and functions
__all__ = [
    # Abstract base
    "BaseStorage",
    # Implementations
    "InMemoryStorage",
    "SyncInMemoryStorage",
    # Factory
    "get_storage",
    "create_and_connect_storage",
    "StorageContext",
    # Global instance for backward compatibility
    "storage",
]

# Lazy imports for optional backends (avoid import errors if deps missing)
def get_postgres_storage():
    """Get PostgreSQLStorage class (lazy import)."""
    from src.storage.postgres import PostgreSQLStorage
    return PostgreSQLStorage

def get_redis_cache():
    """Get RedisCache class (lazy import)."""
    from src.storage.cache import RedisCache
    return RedisCache

def get_cached_storage():
    """Get CachedStorage class (lazy import)."""
    from src.storage.cache import CachedStorage
    return CachedStorage
