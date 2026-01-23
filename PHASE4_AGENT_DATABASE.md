# Phase 4 Agent: Database Layer Implementation

**Branch**: `phase4/database`
**Timeline**: Week 1 (7 days)
**Dependencies**: None (standalone component)
**Priority**: HIGHEST (blocks all other agents)

---

## Mission

Implement the database persistence layer for the AI Co-Scientist system, replacing in-memory storage with PostgreSQL and Redis caching. Create a clean abstraction that allows switching between storage backends via configuration.

---

## Context

You are working in a **git worktree** on branch `phase4/database`. This is part of a parallel development effort where 4 Claude instances are building Phase 4 simultaneously.

**Current System State**:
- Phases 1-3 complete with in-memory storage
- All agents working (Generation, Reflection, Ranking, Evolution, Proximity, Meta-review)
- Current storage: `src/storage/memory.py` (no abstraction, direct implementation)
- Data models: Defined in `03_architecture/schemas.py` (Pydantic)

**Your Goal**:
- Create storage abstraction layer (`BaseStorage`)
- Implement PostgreSQL backend with async operations
- Add Redis caching for performance
- Maintain backward compatibility with existing code
- Publish `BaseStorage` interface **by Day 1** for other agents

---

## Deliverables

### Files to Create

1. **src/storage/base.py** - Abstract storage interface
2. **src/storage/postgres.py** - PostgreSQL implementation
3. **src/storage/cache.py** - Redis caching layer
4. **src/storage/factory.py** - Storage backend factory
5. **src/storage/schema.sql** - PostgreSQL schema definition
6. **scripts/migrate_db.py** - Database migration script
7. **test_storage.py** - Storage implementation tests

### Files to Modify

1. **src/storage/memory.py** - Refactor to inherit from `BaseStorage`
2. **src/config.py** - Add database configuration settings
3. **src/storage/__init__.py** - Export storage classes
4. **03_architecture/environment.yml** - Add database dependencies

---

## Implementation Guide

### Step 1: Install Dependencies (Day 1)

```bash
# Activate conda environment
conda activate coscientist

# Install database packages
conda install -c conda-forge asyncpg redis-py psycopg2

# Verify installation
python -c "import asyncpg, redis; print('✓ Dependencies installed')"
```

Update `03_architecture/environment.yml`:
```yaml
dependencies:
  # ... existing deps
  - asyncpg>=0.29.0
  - redis-py>=5.0.0
  - psycopg2>=2.9.0
```

### Step 2: Create Database Schema (Day 1)

**File**: `src/storage/schema.sql`

Map all Pydantic models from `03_architecture/schemas.py` to PostgreSQL tables:

**Tables to Create** (13 total):
1. `research_goals` - ResearchGoal model
2. `hypotheses` - Hypothesis model
3. `reviews` - Review model
4. `tournament_matches` - TournamentMatch model
5. `proximity_edges` - ProximityEdge model
6. `hypothesis_clusters` - HypothesisCluster model
7. `proximity_graphs` - ProximityGraph model (links to edges/clusters)
8. `meta_reviews` - MetaReviewCritique model
9. `research_overviews` - ResearchOverview model
10. `research_directions` - ResearchDirection model (nested in overview)
11. `research_contacts` - ResearchContact model (nested in overview)
12. `agent_tasks` - AgentTask model (for supervisor)
13. `context_memory` - ContextMemory model (for checkpoints)

**Schema Design Principles**:
- VARCHAR(255) for IDs (e.g., `hyp_20260123_abc123`)
- TEXT for long strings (statement, rationale, mechanism)
- JSONB for complex nested objects (citations, experimental_protocol)
- FLOAT for Elo ratings
- TIMESTAMP for created_at/updated_at
- Foreign keys with ON DELETE CASCADE
- Indexes on frequently queried fields

**Example Table**:
```sql
-- Hypotheses table (most critical)
CREATE TABLE hypotheses (
    id VARCHAR(255) PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    statement TEXT NOT NULL,
    rationale TEXT NOT NULL,
    mechanism TEXT,
    experimental_protocol JSONB,  -- ExperimentalProtocol as JSON
    citations JSONB,  -- List[Citation] as JSON array
    elo_rating FLOAT DEFAULT 1200.0,
    status VARCHAR(50) DEFAULT 'generated',
    generation_method VARCHAR(50),
    parent_hypothesis_id VARCHAR(255) REFERENCES hypotheses(id),
    evolution_strategy VARCHAR(50),
    evolution_rationale TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_hypotheses_elo ON hypotheses(elo_rating DESC);
CREATE INDEX idx_hypotheses_status ON hypotheses(status);
CREATE INDEX idx_hypotheses_goal ON hypotheses(research_goal_id);
CREATE INDEX idx_hypotheses_created ON hypotheses(created_at DESC);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_hypotheses_updated_at
    BEFORE UPDATE ON hypotheses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Repeat for all 13 tables** (see `03_architecture/schemas.py` for field definitions).

### Step 3: Create Abstract Storage Interface (Day 1) ⚠️ PRIORITY

**File**: `src/storage/base.py`

**CRITICAL**: Publish this interface **by end of Day 1** so Supervisor Agent can begin work.

```python
"""Abstract storage interface for data persistence"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import (
    ResearchGoal, Hypothesis, Review, TournamentMatch,
    ProximityGraph, ProximityEdge, HypothesisCluster,
    MetaReviewCritique, ResearchOverview, AgentTask,
    SystemStatistics, ContextMemory, ScientistFeedback
)


class BaseStorage(ABC):
    """Abstract base class for all storage implementations"""

    # ==================== Research Goals ====================

    @abstractmethod
    async def add_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Add new research goal"""
        pass

    @abstractmethod
    async def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Retrieve research goal by ID"""
        pass

    @abstractmethod
    async def get_all_research_goals(self) -> List[ResearchGoal]:
        """Get all research goals"""
        pass

    # ==================== Hypotheses ====================

    @abstractmethod
    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Add new hypothesis"""
        pass

    @abstractmethod
    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve hypothesis by ID"""
        pass

    @abstractmethod
    async def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Update existing hypothesis (e.g., Elo rating)"""
        pass

    @abstractmethod
    async def get_hypotheses_by_goal(self, goal_id: str, status: Optional[str] = None) -> List[Hypothesis]:
        """Get all hypotheses for a research goal, optionally filtered by status"""
        pass

    @abstractmethod
    async def get_top_hypotheses(self, n: int = 10, goal_id: Optional[str] = None) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating"""
        pass

    @abstractmethod
    async def get_all_hypotheses(self) -> List[Hypothesis]:
        """Get all hypotheses across all goals"""
        pass

    # ==================== Reviews ====================

    @abstractmethod
    async def add_review(self, review: Review) -> Review:
        """Add new review"""
        pass

    @abstractmethod
    async def get_reviews_for_hypothesis(self, hypothesis_id: str) -> List[Review]:
        """Get all reviews for a hypothesis"""
        pass

    @abstractmethod
    async def get_review(self, review_id: str) -> Optional[Review]:
        """Get review by ID"""
        pass

    # ==================== Tournament ====================

    @abstractmethod
    async def add_match(self, match: TournamentMatch) -> TournamentMatch:
        """Add tournament match"""
        pass

    @abstractmethod
    async def get_matches_for_hypothesis(self, hypothesis_id: str) -> List[TournamentMatch]:
        """Get all matches involving a hypothesis"""
        pass

    @abstractmethod
    async def get_all_matches(self, goal_id: Optional[str] = None) -> List[TournamentMatch]:
        """Get all tournament matches"""
        pass

    @abstractmethod
    async def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for hypothesis"""
        pass

    # ==================== Proximity Graph ====================

    @abstractmethod
    async def save_proximity_graph(self, graph: ProximityGraph) -> ProximityGraph:
        """Save proximity graph (edges + clusters)"""
        pass

    @abstractmethod
    async def get_proximity_graph(self, goal_id: str) -> Optional[ProximityGraph]:
        """Get proximity graph for research goal"""
        pass

    # ==================== Meta-Review ====================

    @abstractmethod
    async def save_meta_review(self, meta_review: MetaReviewCritique) -> MetaReviewCritique:
        """Save meta-review critique"""
        pass

    @abstractmethod
    async def get_meta_review(self, goal_id: str) -> Optional[MetaReviewCritique]:
        """Get meta-review for research goal"""
        pass

    @abstractmethod
    async def save_research_overview(self, overview: ResearchOverview) -> ResearchOverview:
        """Save research overview"""
        pass

    @abstractmethod
    async def get_research_overview(self, goal_id: str) -> Optional[ResearchOverview]:
        """Get research overview for research goal"""
        pass

    # ==================== Tasks & Statistics ====================

    @abstractmethod
    async def add_task(self, task: AgentTask) -> AgentTask:
        """Add agent task to queue"""
        pass

    @abstractmethod
    async def get_pending_tasks(self, agent_type: Optional[str] = None) -> List[AgentTask]:
        """Get pending tasks, optionally filtered by agent type"""
        pass

    @abstractmethod
    async def update_task_status(self, task_id: str, status: str, result: Optional[str] = None) -> AgentTask:
        """Update task status"""
        pass

    # ==================== Checkpoints ====================

    @abstractmethod
    async def save_checkpoint(self, checkpoint: ContextMemory) -> ContextMemory:
        """Save workflow checkpoint"""
        pass

    @abstractmethod
    async def get_latest_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Get most recent checkpoint for research goal"""
        pass

    # ==================== Connection Management ====================

    @abstractmethod
    async def connect(self):
        """Initialize connection pool"""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection pool"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if storage is healthy"""
        pass
```

**Commit and push this file immediately** so other agents can reference it.

### Step 4: Refactor InMemoryStorage (Day 2)

**File**: `src/storage/memory.py`

Refactor existing `InMemoryStorage` to inherit from `BaseStorage`:

```python
"""In-memory storage implementation (for testing)"""

from typing import List, Optional, Dict
from src.storage.base import BaseStorage
from schemas import (
    ResearchGoal, Hypothesis, Review, TournamentMatch,
    ProximityGraph, MetaReviewCritique, ResearchOverview
)
import structlog

logger = structlog.get_logger()


class InMemoryStorage(BaseStorage):
    """In-memory storage for testing and development"""

    def __init__(self):
        self._research_goals: Dict[str, ResearchGoal] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._reviews: Dict[str, Review] = {}
        self._matches: Dict[str, TournamentMatch] = {}
        self._proximity_graphs: Dict[str, ProximityGraph] = {}
        self._meta_reviews: Dict[str, MetaReviewCritique] = {}
        self._overviews: Dict[str, ResearchOverview] = {}
        self._tasks: Dict[str, AgentTask] = {}
        self._checkpoints: Dict[str, ContextMemory] = {}

    async def connect(self):
        """No-op for in-memory storage"""
        logger.info("InMemoryStorage: connected")

    async def disconnect(self):
        """No-op for in-memory storage"""
        logger.info("InMemoryStorage: disconnected")

    async def health_check(self) -> bool:
        """Always healthy"""
        return True

    # Implement all methods from BaseStorage
    # (Copy existing logic from current memory.py, add async keyword)

    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Add hypothesis to memory"""
        self._hypotheses[hypothesis.id] = hypothesis
        return hypothesis

    # ... implement all other methods
```

**Test that existing code still works** with refactored `InMemoryStorage`.

### Step 5: Implement PostgreSQL Storage (Days 3-4)

**File**: `src/storage/postgres.py`

```python
"""PostgreSQL storage implementation with async operations"""

import asyncpg
import json
from typing import List, Optional, Dict
from src.storage.base import BaseStorage
from src.config import settings
from schemas import (
    ResearchGoal, Hypothesis, Review, TournamentMatch,
    ExperimentalProtocol, Citation, ProximityGraph, ProximityEdge,
    HypothesisCluster, MetaReviewCritique, ResearchOverview
)
import structlog

logger = structlog.get_logger()


class PostgreSQLStorage(BaseStorage):
    """PostgreSQL-backed storage with connection pooling"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or settings.database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("PostgreSQL connection pool created", database=self.database_url)
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL", error=str(e))
            raise

    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return False

    # ==================== Hypotheses ====================

    async def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Insert hypothesis into database"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hypotheses (
                    id, research_goal_id, title, statement, rationale,
                    mechanism, experimental_protocol, citations, elo_rating,
                    status, generation_method, parent_hypothesis_id,
                    evolution_strategy, evolution_rationale
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                hypothesis.id,
                hypothesis.research_goal_id,
                hypothesis.title,
                hypothesis.statement,
                hypothesis.rationale,
                hypothesis.mechanism,
                json.dumps(hypothesis.experimental_protocol.model_dump()) if hypothesis.experimental_protocol else None,
                json.dumps([c.model_dump() for c in hypothesis.citations]),
                hypothesis.elo_rating,
                hypothesis.status.value,
                hypothesis.generation_method.value if hypothesis.generation_method else None,
                hypothesis.parent_hypothesis_id,
                hypothesis.evolution_strategy.value if hypothesis.evolution_strategy else None,
                hypothesis.evolution_rationale
            )
            logger.info("Hypothesis added to database", hypothesis_id=hypothesis.id)
        return hypothesis

    async def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve hypothesis by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM hypotheses WHERE id = $1",
                hypothesis_id
            )
            if not row:
                return None

            # Deserialize JSONB fields
            return self._row_to_hypothesis(row)

    async def get_top_hypotheses(self, n: int = 10, goal_id: Optional[str] = None) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating"""
        async with self.pool.acquire() as conn:
            if goal_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM hypotheses
                    WHERE research_goal_id = $1
                    ORDER BY elo_rating DESC
                    LIMIT $2
                    """,
                    goal_id, n
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM hypotheses ORDER BY elo_rating DESC LIMIT $1",
                    n
                )

            return [self._row_to_hypothesis(row) for row in rows]

    # ==================== Helper Methods ====================

    def _row_to_hypothesis(self, row: asyncpg.Record) -> Hypothesis:
        """Convert database row to Hypothesis object"""
        from schemas import HypothesisStatus, GenerationMethod, EvolutionStrategy

        return Hypothesis(
            id=row['id'],
            research_goal_id=row['research_goal_id'],
            title=row['title'],
            statement=row['statement'],
            rationale=row['rationale'],
            mechanism=row['mechanism'],
            experimental_protocol=ExperimentalProtocol(**json.loads(row['experimental_protocol'])) if row['experimental_protocol'] else None,
            citations=[Citation(**c) for c in json.loads(row['citations'])],
            elo_rating=row['elo_rating'],
            status=HypothesisStatus(row['status']),
            generation_method=GenerationMethod(row['generation_method']) if row['generation_method'] else None,
            parent_hypothesis_id=row['parent_hypothesis_id'],
            evolution_strategy=EvolutionStrategy(row['evolution_strategy']) if row['evolution_strategy'] else None,
            evolution_rationale=row['evolution_rationale']
        )

    # Implement all other methods from BaseStorage
    # Follow same pattern: SQL query → deserialize → return Pydantic model
```

**Implement all 30+ methods** from `BaseStorage` interface.

### Step 6: Implement Redis Cache (Day 4)

**File**: `src/storage/cache.py`

```python
"""Redis caching layer for frequently accessed data"""

import redis.asyncio as redis
import json
from typing import Optional, List
from schemas import Hypothesis
from src.config import settings
import structlog

logger = structlog.get_logger()


class RedisCache:
    """Redis caching with TTL for top hypotheses and Elo rankings"""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis"""
        self.client = await redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        logger.info("Redis cache connected")

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()

    async def get_top_hypotheses(self, goal_id: str, n: int) -> Optional[List[Hypothesis]]:
        """Get cached top hypotheses"""
        key = f"top_hypotheses:{goal_id}:{n}"
        cached = await self.client.get(key)
        if cached:
            data = json.loads(cached)
            return [Hypothesis(**h) for h in data]
        return None

    async def set_top_hypotheses(self, goal_id: str, n: int, hypotheses: List[Hypothesis], ttl: int = 300):
        """Cache top hypotheses with TTL (default 5 minutes)"""
        key = f"top_hypotheses:{goal_id}:{n}"
        data = [h.model_dump() for h in hypotheses]
        await self.client.setex(key, ttl, json.dumps(data))

    async def invalidate_top_hypotheses(self, goal_id: str):
        """Invalidate cache when Elo ratings change"""
        pattern = f"top_hypotheses:{goal_id}:*"
        keys = await self.client.keys(pattern)
        if keys:
            await self.client.delete(*keys)
```

### Step 7: Create Storage Factory (Day 5)

**File**: `src/storage/factory.py`

```python
"""Storage backend factory"""

from src.storage.base import BaseStorage
from src.storage.memory import InMemoryStorage
from src.storage.postgres import PostgreSQLStorage
from src.config import settings
import structlog

logger = structlog.get_logger()


def get_storage() -> BaseStorage:
    """Get storage implementation based on configuration"""
    backend = settings.storage_backend

    if backend == "postgres":
        logger.info("Using PostgreSQL storage backend")
        return PostgreSQLStorage()
    elif backend == "memory":
        logger.info("Using in-memory storage backend")
        return InMemoryStorage()
    else:
        raise ValueError(f"Unknown storage backend: {backend}")
```

**Update `src/config.py`**:
```python
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # ... existing settings

    # Storage configuration
    storage_backend: Literal["memory", "postgres"] = "memory"
    database_url: str = "postgresql://localhost:5432/coscientist"
    redis_url: str = "redis://localhost:6379/0"

    # ... rest of settings
```

### Step 8: Create Migration Script (Day 5)

**File**: `scripts/migrate_db.py`

```python
#!/usr/bin/env python3
"""Database migration script - creates tables from schema.sql"""

import asyncpg
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
from src.config import settings

async def run_migration():
    """Run database migration"""
    print(f"Connecting to database: {settings.database_url}")

    # Connect to database
    conn = await asyncpg.connect(settings.database_url)

    # Read schema file
    schema_path = Path(__file__).parent.parent / "src" / "storage" / "schema.sql"
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Execute schema
    print("Creating tables...")
    await conn.execute(schema_sql)

    await conn.close()
    print("✓ Migration complete")

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration())
```

### Step 9: Create Tests (Days 6-7)

**File**: `test_storage.py`

```python
#!/usr/bin/env python3
"""Test storage implementations"""

import pytest
import asyncio
from src.storage.factory import get_storage
from src.storage.memory import InMemoryStorage
from src.storage.postgres import PostgreSQLStorage
from schemas import ResearchGoal, Hypothesis
from src.utils.ids import generate_hypothesis_id

@pytest.mark.asyncio
async def test_in_memory_storage():
    """Test in-memory storage implementation"""
    storage = InMemoryStorage()
    await storage.connect()

    # Test add/get hypothesis
    goal = ResearchGoal(
        id="test_goal",
        description="Test research goal",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    hypothesis = Hypothesis(
        id=generate_hypothesis_id(),
        research_goal_id=goal.id,
        title="Test Hypothesis",
        statement="This is a test",
        rationale="For testing",
        mechanism="Test mechanism",
        elo_rating=1200.0
    )
    await storage.add_hypothesis(hypothesis)

    # Retrieve and verify
    retrieved = await storage.get_hypothesis(hypothesis.id)
    assert retrieved.id == hypothesis.id
    assert retrieved.elo_rating == 1200.0

    await storage.disconnect()

@pytest.mark.asyncio
async def test_postgres_storage():
    """Test PostgreSQL storage implementation"""
    # Requires running PostgreSQL instance
    storage = PostgreSQLStorage()
    await storage.connect()

    # Run same tests as in-memory
    # ... (same test logic as above)

    await storage.disconnect()

@pytest.mark.asyncio
async def test_factory_switching():
    """Test storage factory switching"""
    # Test memory backend
    from src.config import settings
    settings.storage_backend = "memory"
    storage = get_storage()
    assert isinstance(storage, InMemoryStorage)

    # Test postgres backend
    settings.storage_backend = "postgres"
    storage = get_storage()
    assert isinstance(storage, PostgreSQLStorage)
```

Run tests:
```bash
pytest test_storage.py -v
```

---

## Testing Checklist

- [ ] schema.sql creates all 13 tables without errors
- [ ] InMemoryStorage passes all tests
- [ ] PostgreSQL connection pool works
- [ ] Can insert and retrieve Hypothesis
- [ ] Can query top hypotheses by Elo
- [ ] JSONB serialization works for citations/experimental_protocol
- [ ] Foreign key cascades work correctly
- [ ] Redis caching stores and retrieves data
- [ ] Storage factory switches backends correctly
- [ ] All existing Phase 1-3 tests still pass with InMemoryStorage

---

## Success Criteria

**Week 1 Complete When**:

1. ✅ `BaseStorage` interface published (Day 1)
2. ✅ PostgreSQL schema created (13 tables)
3. ✅ `InMemoryStorage` refactored to inherit from `BaseStorage`
4. ✅ `PostgreSQLStorage` implements all methods
5. ✅ Redis caching layer functional
6. ✅ Storage factory switches backends via config
7. ✅ Migration script creates tables
8. ✅ All tests pass
9. ✅ Committed and pushed to `phase4/database` branch

---

## Integration with Other Agents

**What Other Agents Need From You**:

1. **Supervisor Agent** (blocking): Needs `BaseStorage` interface by Day 1
2. **Safety Agent**: Will use storage to save safety assessments
3. **API Agent**: Will use storage factory to get backend

**Communication**:
- Commit `src/storage/base.py` **immediately** on Day 1
- Update `PHASE4_STATUS.md` daily with progress
- Flag any Pydantic schema issues in `schemas.py`

---

## Git Workflow

```bash
# Daily commits
git add .
git commit -m "feat(database): [description of work]"
git push origin phase4/database

# Example commits:
# Day 1: "feat(database): add BaseStorage interface and schema.sql"
# Day 2: "feat(database): refactor InMemoryStorage to inherit from BaseStorage"
# Day 3: "feat(database): implement PostgreSQL storage (50%)"
# Day 4: "feat(database): complete PostgreSQL + Redis cache"
# Day 5: "feat(database): add storage factory and migration script"
# Day 6: "test(database): add comprehensive storage tests"
# Day 7: "docs(database): finalize and push database layer"
```

---

## Questions?

Reference:
- Main plan: `/Users/.../PHASE4_PARALLEL_WORKFLOW.md`
- Data models: `03_architecture/schemas.py`
- Existing storage: `src/storage/memory.py`

**Your mission is clear**: Build the database foundation that Phase 4 depends on. Good luck! 🚀
