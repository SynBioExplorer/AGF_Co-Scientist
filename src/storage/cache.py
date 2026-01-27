"""Redis caching layer for AI Co-Scientist.

This module provides caching for frequently accessed data:
- Top hypotheses by Elo rating
- Elo rankings for tournament
- System statistics

Cache invalidation is automatic on writes via the CachedStorage wrapper.
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import sys
from pathlib import Path
import structlog

try:
    import redis.asyncio as redis
except ImportError:
    redis = None  # Will raise error on connect if not installed

# Add architecture directory to path for schemas
sys.path.append(str(Path(__file__).parent.parent.parent / "03_Architecture"))
from schemas import (
    Hypothesis,
    Review,
    TournamentMatch,
    SystemStatistics,
    HypothesisStatus,
    GenerationMethod,
    ExperimentalProtocol,
    Citation,
    Assumption,
)

logger = structlog.get_logger()


class RedisCache:
    """Redis caching layer for frequently accessed data.

    Provides caching with configurable TTL for:
    - Top hypotheses (invalidated on Elo changes)
    - Hypothesis counts
    - Win rates
    - System statistics

    Keys follow the pattern: coscientist:{data_type}:{identifier}
    """

    # Default TTL values (in seconds)
    DEFAULT_TTL = 300  # 5 minutes
    TOP_HYPOTHESES_TTL = 60  # 1 minute (changes frequently during tournaments)
    STATISTICS_TTL = 120  # 2 minutes
    WIN_RATE_TTL = 180  # 3 minutes

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis cache.

        Args:
            redis_url: Redis connection URL.
                Format: redis://host:port/db
                If not provided, will use settings.redis_url on connect.
        """
        self._redis_url = redis_url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if redis is None:
            raise ImportError("redis is required for caching. Install with: pip install redis")

        if self._redis_url is None:
            from src.config import settings
            self._redis_url = settings.redis_url

        try:
            self._client = await redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            logger.info("Redis cache connected", url=self._redis_url.split("@")[-1])
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis cache disconnected")

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False

    # =========================================================================
    # Key Generation
    # =========================================================================

    def _key(self, data_type: str, *parts: str) -> str:
        """Generate a cache key."""
        return f"coscientist:{data_type}:{':'.join(parts)}"

    # =========================================================================
    # Top Hypotheses Caching
    # =========================================================================

    async def get_top_hypotheses(
        self,
        goal_id: str,
        n: int
    ) -> Optional[List[Hypothesis]]:
        """Get cached top hypotheses.

        Args:
            goal_id: Research goal ID.
            n: Number of hypotheses.

        Returns:
            List of hypotheses if cached, None otherwise.
        """
        key = self._key("top_hypotheses", goal_id, str(n))
        try:
            cached = await self._client.get(key)
            if cached:
                data = json.loads(cached)
                hypotheses = [self._dict_to_hypothesis(h) for h in data]
                logger.debug("Cache hit", key=key)
                return hypotheses
            logger.debug("Cache miss", key=key)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set_top_hypotheses(
        self,
        goal_id: str,
        n: int,
        hypotheses: List[Hypothesis],
        ttl: Optional[int] = None
    ) -> None:
        """Cache top hypotheses.

        Args:
            goal_id: Research goal ID.
            n: Number of hypotheses.
            hypotheses: List of hypotheses to cache.
            ttl: Time-to-live in seconds (default: TOP_HYPOTHESES_TTL).
        """
        key = self._key("top_hypotheses", goal_id, str(n))
        ttl = ttl or self.TOP_HYPOTHESES_TTL
        try:
            data = [self._hypothesis_to_dict(h) for h in hypotheses]
            await self._client.setex(key, ttl, json.dumps(data))
            logger.debug("Cache set", key=key, ttl=ttl)
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))

    async def invalidate_top_hypotheses(self, goal_id: str) -> None:
        """Invalidate all top hypotheses caches for a goal.

        Called when Elo ratings change.

        Args:
            goal_id: Research goal ID.
        """
        pattern = self._key("top_hypotheses", goal_id, "*")
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._client.delete(*keys)
                logger.debug("Cache invalidated", pattern=pattern, count=len(keys))
        except Exception as e:
            logger.warning("Cache invalidation failed", pattern=pattern, error=str(e))

    # =========================================================================
    # Hypothesis Caching
    # =========================================================================

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get cached hypothesis."""
        key = self._key("hypothesis", hypothesis_id)
        try:
            cached = await self._client.get(key)
            if cached:
                return self._dict_to_hypothesis(json.loads(cached))
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set_hypothesis(
        self,
        hypothesis: Hypothesis,
        ttl: Optional[int] = None
    ) -> None:
        """Cache a hypothesis."""
        key = self._key("hypothesis", hypothesis.id)
        ttl = ttl or self.DEFAULT_TTL
        try:
            data = self._hypothesis_to_dict(hypothesis)
            await self._client.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))

    async def invalidate_hypothesis(self, hypothesis_id: str) -> None:
        """Invalidate cached hypothesis."""
        key = self._key("hypothesis", hypothesis_id)
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))

    # =========================================================================
    # Win Rate Caching
    # =========================================================================

    async def get_win_rate(self, hypothesis_id: str) -> Optional[float]:
        """Get cached win rate."""
        key = self._key("win_rate", hypothesis_id)
        try:
            cached = await self._client.get(key)
            if cached:
                return float(cached)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set_win_rate(
        self,
        hypothesis_id: str,
        win_rate: float,
        ttl: Optional[int] = None
    ) -> None:
        """Cache win rate."""
        key = self._key("win_rate", hypothesis_id)
        ttl = ttl or self.WIN_RATE_TTL
        try:
            await self._client.setex(key, ttl, str(win_rate))
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))

    async def invalidate_win_rate(self, hypothesis_id: str) -> None:
        """Invalidate cached win rate."""
        key = self._key("win_rate", hypothesis_id)
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))

    # =========================================================================
    # Statistics Caching
    # =========================================================================

    async def get_statistics(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Get cached statistics."""
        key = self._key("statistics", goal_id)
        try:
            cached = await self._client.get(key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set_statistics(
        self,
        goal_id: str,
        stats: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """Cache statistics."""
        key = self._key("statistics", goal_id)
        ttl = ttl or self.STATISTICS_TTL
        try:
            await self._client.setex(key, ttl, json.dumps(stats))
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))

    async def invalidate_statistics(self, goal_id: str) -> None:
        """Invalidate cached statistics."""
        key = self._key("statistics", goal_id)
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))

    # =========================================================================
    # Hypothesis Count Caching
    # =========================================================================

    async def get_hypothesis_count(self, goal_id: Optional[str] = None) -> Optional[int]:
        """Get cached hypothesis count."""
        key = self._key("count", goal_id or "all")
        try:
            cached = await self._client.get(key)
            if cached:
                return int(cached)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set_hypothesis_count(
        self,
        count: int,
        goal_id: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> None:
        """Cache hypothesis count."""
        key = self._key("count", goal_id or "all")
        ttl = ttl or self.DEFAULT_TTL
        try:
            await self._client.setex(key, ttl, str(count))
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))

    async def invalidate_counts(self, goal_id: Optional[str] = None) -> None:
        """Invalidate hypothesis counts."""
        try:
            if goal_id:
                await self._client.delete(self._key("count", goal_id))
            # Always invalidate the "all" count
            await self._client.delete(self._key("count", "all"))
        except Exception as e:
            logger.warning("Cache delete failed", error=str(e))

    # =========================================================================
    # Bulk Invalidation
    # =========================================================================

    async def invalidate_goal(self, goal_id: str) -> None:
        """Invalidate all caches for a research goal.

        Called when significant changes occur.

        Args:
            goal_id: Research goal ID.
        """
        patterns = [
            self._key("top_hypotheses", goal_id, "*"),
            self._key("statistics", goal_id),
            self._key("count", goal_id),
        ]
        try:
            for pattern in patterns:
                if "*" in pattern:
                    async for key in self._client.scan_iter(match=pattern):
                        await self._client.delete(key)
                else:
                    await self._client.delete(pattern)
            logger.info("Goal cache invalidated", goal_id=goal_id)
        except Exception as e:
            logger.warning("Goal cache invalidation failed", goal_id=goal_id, error=str(e))

    async def clear_all(self) -> None:
        """Clear all cached data.

        Use with caution - clears all coscientist keys.
        """
        pattern = "coscientist:*"
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._client.delete(*keys)
            logger.warning("All cache cleared", count=len(keys))
        except Exception as e:
            logger.error("Cache clear failed", error=str(e))

    # =========================================================================
    # Serialization Helpers
    # =========================================================================

    def _hypothesis_to_dict(self, hypothesis: Hypothesis) -> Dict[str, Any]:
        """Convert Hypothesis to JSON-serializable dict."""
        return {
            "id": hypothesis.id,
            "research_goal_id": hypothesis.research_goal_id,
            "title": hypothesis.title,
            "summary": hypothesis.summary,
            "hypothesis_statement": hypothesis.hypothesis_statement,
            "rationale": hypothesis.rationale,
            "mechanism": hypothesis.mechanism,
            "experimental_protocol": hypothesis.experimental_protocol.model_dump() if hypothesis.experimental_protocol else None,
            "literature_citations": [c.model_dump() for c in hypothesis.literature_citations],
            "assumptions": [a.model_dump() for a in hypothesis.assumptions],
            "category": hypothesis.category,
            "status": hypothesis.status.value,
            "generation_method": hypothesis.generation_method.value,
            "parent_hypothesis_ids": hypothesis.parent_hypothesis_ids,
            "elo_rating": hypothesis.elo_rating,
            "created_at": hypothesis.created_at.isoformat(),
            "updated_at": hypothesis.updated_at.isoformat(),
        }

    def _dict_to_hypothesis(self, data: Dict[str, Any]) -> Hypothesis:
        """Convert dict to Hypothesis."""
        return Hypothesis(
            id=data["id"],
            research_goal_id=data["research_goal_id"],
            title=data["title"],
            summary=data["summary"],
            hypothesis_statement=data["hypothesis_statement"],
            rationale=data["rationale"],
            mechanism=data["mechanism"],
            experimental_protocol=ExperimentalProtocol(**data["experimental_protocol"]) if data.get("experimental_protocol") else None,
            literature_citations=[Citation(**c) for c in data.get("literature_citations", [])],
            assumptions=[Assumption(**a) for a in data.get("assumptions", [])],
            category=data.get("category"),
            status=HypothesisStatus(data["status"]),
            generation_method=GenerationMethod(data["generation_method"]),
            parent_hypothesis_ids=data.get("parent_hypothesis_ids", []),
            elo_rating=data["elo_rating"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class CachedStorage:
    """Wrapper that adds Redis caching to any BaseStorage implementation.

    Usage:
        from src.storage.postgres import PostgreSQLStorage
        from src.storage.cache import RedisCache, CachedStorage

        pg_storage = PostgreSQLStorage()
        cache = RedisCache()
        storage = CachedStorage(pg_storage, cache)

        await storage.connect()
        # Now all operations go through cache when applicable
    """

    def __init__(self, storage, cache: RedisCache):
        """Initialize cached storage.

        Args:
            storage: Underlying storage implementation (PostgreSQLStorage, etc.)
            cache: Redis cache instance.
        """
        self._storage = storage
        self._cache = cache

    async def connect(self) -> None:
        """Connect both storage and cache."""
        await self._storage.connect()
        await self._cache.connect()

    async def disconnect(self) -> None:
        """Disconnect both storage and cache."""
        await self._cache.disconnect()
        await self._storage.disconnect()

    async def health_check(self) -> bool:
        """Check both storage and cache health."""
        storage_ok = await self._storage.health_check()
        cache_ok = await self._cache.health_check()
        return storage_ok and cache_ok

    # =========================================================================
    # Cached Operations
    # =========================================================================

    async def get_top_hypotheses(self, n: int = 10, goal_id: Optional[str] = None) -> List[Hypothesis]:
        """Get top hypotheses with caching."""
        if goal_id:
            # Try cache first
            cached = await self._cache.get_top_hypotheses(goal_id, n)
            if cached is not None:
                return cached

        # Fetch from storage
        hypotheses = await self._storage.get_top_hypotheses(n, goal_id)

        # Cache the result
        if goal_id:
            await self._cache.set_top_hypotheses(goal_id, n, hypotheses)

        return hypotheses

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get hypothesis with caching."""
        # Try cache first
        cached = await self._cache.get_hypothesis(hypothesis_id)
        if cached is not None:
            return cached

        # Fetch from storage
        hypothesis = await self._storage.get_hypothesis(hypothesis_id)

        # Cache if found
        if hypothesis:
            await self._cache.set_hypothesis(hypothesis)

        return hypothesis

    async def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Update hypothesis and invalidate caches."""
        result = await self._storage.update_hypothesis(hypothesis)

        # Invalidate related caches
        await self._cache.invalidate_hypothesis(hypothesis.id)
        await self._cache.invalidate_top_hypotheses(hypothesis.research_goal_id)
        await self._cache.invalidate_win_rate(hypothesis.id)

        return result

    async def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Get win rate with caching."""
        # Try cache first
        cached = await self._cache.get_win_rate(hypothesis_id)
        if cached is not None:
            return cached

        # Calculate from storage
        win_rate = await self._storage.get_hypothesis_win_rate(hypothesis_id)

        # Cache the result
        await self._cache.set_win_rate(hypothesis_id, win_rate)

        return win_rate

    async def add_match(self, match) -> Any:
        """Add match and invalidate related caches."""
        result = await self._storage.add_match(match)

        # Invalidate win rates for both hypotheses
        await self._cache.invalidate_win_rate(match.hypothesis_a_id)
        await self._cache.invalidate_win_rate(match.hypothesis_b_id)

        return result

    async def get_hypothesis_count(self, goal_id: Optional[str] = None) -> int:
        """Get hypothesis count with caching."""
        # Try cache first
        cached = await self._cache.get_hypothesis_count(goal_id)
        if cached is not None:
            return cached

        # Fetch from storage
        count = await self._storage.get_hypothesis_count(goal_id)

        # Cache the result
        await self._cache.set_hypothesis_count(count, goal_id)

        return count

    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Add hypothesis and invalidate counts."""
        result = await self._storage.add_hypothesis(hypothesis)

        # Invalidate counts
        await self._cache.invalidate_counts(hypothesis.research_goal_id)

        return result

    async def delete_hypothesis(self, hypothesis_id: str) -> bool:
        """Delete hypothesis and invalidate caches."""
        # Get hypothesis first to know its goal_id
        hypothesis = await self._storage.get_hypothesis(hypothesis_id)
        if not hypothesis:
            return False

        result = await self._storage.delete_hypothesis(hypothesis_id)

        if result:
            await self._cache.invalidate_hypothesis(hypothesis_id)
            await self._cache.invalidate_top_hypotheses(hypothesis.research_goal_id)
            await self._cache.invalidate_counts(hypothesis.research_goal_id)

        return result

    async def clear_all(self, goal_id: Optional[str] = None) -> None:
        """Clear storage and cache."""
        await self._storage.clear_all(goal_id)
        if goal_id:
            await self._cache.invalidate_goal(goal_id)
        else:
            await self._cache.clear_all()

    # =========================================================================
    # Passthrough Operations (no caching)
    # =========================================================================

    def __getattr__(self, name: str):
        """Forward all other operations to underlying storage."""
        return getattr(self._storage, name)
