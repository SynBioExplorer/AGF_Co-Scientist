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
"""

from src.storage.base import BaseStorage

# Export base class for type hints
__all__ = [
    "BaseStorage",
]
