"""Storage backend factory for AI Co-Scientist.

This module provides a factory function to create storage instances
based on configuration. Switch storage backends by changing a single
environment variable.

Usage:
    from src.storage.factory import get_storage

    # Uses STORAGE_BACKEND from .env (default: "memory")
    storage = get_storage()
    await storage.connect()

    # Or specify explicitly
    storage = get_storage(backend="postgres", enable_cache=True)
"""

from typing import Optional, Literal
import structlog

from src.storage.base import BaseStorage

logger = structlog.get_logger()

# Valid storage backends
StorageBackend = Literal["memory", "postgres", "cached"]


def get_storage(
    backend: Optional[StorageBackend] = None,
    enable_cache: bool = False,
    database_url: Optional[str] = None,
    redis_url: Optional[str] = None,
) -> BaseStorage:
    """Get storage implementation based on configuration.

    Args:
        backend: Storage backend to use. If None, uses STORAGE_BACKEND
            from settings. Options:
            - "memory": In-memory storage (for testing/development)
            - "postgres": PostgreSQL storage (for production)
            - "cached": PostgreSQL with Redis caching (for high-performance production)
        enable_cache: If True and backend is "postgres", wrap with Redis cache.
            Ignored if backend is "cached" (cache is always enabled).
        database_url: PostgreSQL connection URL. If None, uses DATABASE_URL
            from settings.
        redis_url: Redis connection URL. If None, uses REDIS_URL from settings.

    Returns:
        Storage instance implementing BaseStorage interface.

    Raises:
        ValueError: If backend is invalid.

    Example:
        # Development (fast, no dependencies)
        storage = get_storage(backend="memory")

        # Production without cache
        storage = get_storage(backend="postgres")

        # Production with cache (recommended)
        storage = get_storage(backend="postgres", enable_cache=True)
        # or
        storage = get_storage(backend="cached")
    """
    # Get backend from settings if not provided
    if backend is None:
        from src.config import settings
        backend = settings.storage_backend

    logger.info("Creating storage", backend=backend, cache_enabled=enable_cache or backend == "cached")

    if backend == "memory":
        from src.storage.memory import InMemoryStorage
        return InMemoryStorage()

    elif backend == "postgres":
        from src.storage.postgres import PostgreSQLStorage

        pg_storage = PostgreSQLStorage(database_url=database_url)

        if enable_cache:
            from src.storage.cache import RedisCache, CachedStorage
            cache = RedisCache(redis_url=redis_url)
            return CachedStorage(pg_storage, cache)

        return pg_storage

    elif backend == "cached":
        from src.storage.postgres import PostgreSQLStorage
        from src.storage.cache import RedisCache, CachedStorage

        pg_storage = PostgreSQLStorage(database_url=database_url)
        cache = RedisCache(redis_url=redis_url)
        return CachedStorage(pg_storage, cache)

    else:
        raise ValueError(f"Unknown storage backend: {backend}. Valid options: memory, postgres, cached")


async def create_and_connect_storage(
    backend: Optional[StorageBackend] = None,
    enable_cache: bool = False,
    database_url: Optional[str] = None,
    redis_url: Optional[str] = None,
) -> BaseStorage:
    """Create storage and connect to backends.

    Convenience function that creates storage and establishes connections.
    Call disconnect() when done to clean up resources.

    Args:
        backend: Storage backend to use (see get_storage).
        enable_cache: Enable Redis caching for postgres backend.
        database_url: PostgreSQL connection URL.
        redis_url: Redis connection URL.

    Returns:
        Connected storage instance.

    Example:
        storage = await create_and_connect_storage(backend="postgres")
        try:
            # Use storage
            await storage.add_hypothesis(hypothesis)
        finally:
            await storage.disconnect()
    """
    storage = get_storage(
        backend=backend,
        enable_cache=enable_cache,
        database_url=database_url,
        redis_url=redis_url,
    )
    await storage.connect()
    return storage


class StorageContext:
    """Async context manager for storage connections.

    Automatically connects on enter and disconnects on exit.

    Usage:
        async with StorageContext(backend="postgres") as storage:
            await storage.add_hypothesis(hypothesis)
            # Automatically disconnects when exiting context
    """

    def __init__(
        self,
        backend: Optional[StorageBackend] = None,
        enable_cache: bool = False,
        database_url: Optional[str] = None,
        redis_url: Optional[str] = None,
    ):
        self._backend = backend
        self._enable_cache = enable_cache
        self._database_url = database_url
        self._redis_url = redis_url
        self._storage: Optional[BaseStorage] = None

    async def __aenter__(self) -> BaseStorage:
        self._storage = await create_and_connect_storage(
            backend=self._backend,
            enable_cache=self._enable_cache,
            database_url=self._database_url,
            redis_url=self._redis_url,
        )
        return self._storage

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._storage:
            await self._storage.disconnect()
        return False  # Don't suppress exceptions
