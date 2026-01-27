# Phase 5A: Vector Storage & Semantic Search

## Overview

Implement vector embeddings for hypotheses to enable fast semantic similarity search, replacing or augmenting the LLM-based Proximity agent clustering.

**Branch:** `phase5/vector`
**Worktree:** `worktree-5a-vector`
**Dependencies:** Phase 4 complete
**Estimated Duration:** 1 week

## Motivation

The current Proximity agent uses LLM calls to compute pairwise similarity between hypotheses. This is:
- **Expensive:** Each comparison requires an LLM API call
- **Slow:** O(n²) comparisons for n hypotheses
- **Non-scalable:** Cost grows quadratically with hypothesis count

Vector embeddings provide:
- **Fast similarity:** Cosine similarity is O(1) per comparison
- **Scalable:** Millions of hypotheses with sub-second queries
- **Cost-effective:** One embedding per hypothesis (not per pair)

## Deliverables

### Files to Create

```
src/
├── storage/
│   └── vector.py              # Vector store abstraction
├── embeddings/
│   ├── __init__.py
│   ├── base.py                # Abstract embedding client
│   ├── google.py              # Google text-embedding-004
│   ├── openai.py              # OpenAI text-embedding-3-small
│   └── local.py               # Sentence-transformers fallback
└── agents/
    └── proximity.py           # Update to use vector similarity

tests/
└── test_vector.py             # Vector storage tests
```

### 1. Vector Store Abstraction (`src/storage/vector.py`)

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from pydantic import BaseModel

class VectorDocument(BaseModel):
    """Document with embedding."""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: dict = {}

class BaseVectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def add_documents(self, documents: List[VectorDocument]) -> None:
        """Add documents with embeddings."""
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        filter: Optional[dict] = None
    ) -> List[Tuple[VectorDocument, float]]:
        """Search by embedding, return (doc, score) pairs."""
        pass

    @abstractmethod
    async def delete(self, ids: List[str]) -> None:
        """Delete documents by ID."""
        pass

    @abstractmethod
    async def get(self, id: str) -> Optional[VectorDocument]:
        """Get document by ID."""
        pass

class ChromaVectorStore(BaseVectorStore):
    """ChromaDB implementation for development."""

    def __init__(self, collection_name: str = "hypotheses"):
        import chromadb
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(collection_name)

    async def add_documents(self, documents: List[VectorDocument]) -> None:
        self.collection.add(
            ids=[d.id for d in documents],
            embeddings=[d.embedding for d in documents],
            documents=[d.content for d in documents],
            metadatas=[d.metadata for d in documents]
        )

    async def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        filter: Optional[dict] = None
    ) -> List[Tuple[VectorDocument, float]]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter
        )
        # Convert to VectorDocument, score pairs
        docs = []
        for i, id in enumerate(results['ids'][0]):
            doc = VectorDocument(
                id=id,
                content=results['documents'][0][i],
                metadata=results['metadatas'][0][i] if results['metadatas'] else {}
            )
            score = 1 - results['distances'][0][i]  # Convert distance to similarity
            docs.append((doc, score))
        return docs

class PgVectorStore(BaseVectorStore):
    """PostgreSQL pgvector implementation for production."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None

    async def connect(self):
        import asyncpg
        self.pool = await asyncpg.create_pool(self.connection_string)
        # Create extension and table if not exists
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS hypothesis_embeddings (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    embedding vector(768),
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_hypothesis_embedding
                ON hypothesis_embeddings USING ivfflat (embedding vector_cosine_ops)
            """)

    async def add_documents(self, documents: List[VectorDocument]) -> None:
        async with self.pool.acquire() as conn:
            for doc in documents:
                await conn.execute("""
                    INSERT INTO hypothesis_embeddings (id, content, embedding, metadata)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                """, doc.id, doc.content, doc.embedding, doc.metadata)

    async def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        filter: Optional[dict] = None
    ) -> List[Tuple[VectorDocument, float]]:
        async with self.pool.acquire() as conn:
            # Build filter clause if provided
            where_clause = ""
            if filter:
                conditions = [f"metadata->>'{k}' = '{v}'" for k, v in filter.items()]
                where_clause = "WHERE " + " AND ".join(conditions)

            rows = await conn.fetch(f"""
                SELECT id, content, metadata,
                       1 - (embedding <=> $1) as similarity
                FROM hypothesis_embeddings
                {where_clause}
                ORDER BY embedding <=> $1
                LIMIT $2
            """, query_embedding, k)

            return [
                (VectorDocument(id=r['id'], content=r['content'], metadata=r['metadata']),
                 r['similarity'])
                for r in rows
            ]
```

### 2. Embedding Client (`src/embeddings/base.py`)

```python
from abc import ABC, abstractmethod
from typing import List

class BaseEmbeddingClient(ABC):
    """Abstract embedding client."""

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for batch of texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension."""
        pass
```

### 3. Google Embedding Client (`src/embeddings/google.py`)

```python
from typing import List
from .base import BaseEmbeddingClient

class GoogleEmbeddingClient(BaseEmbeddingClient):
    """Google text-embedding-004 client."""

    def __init__(self, api_key: str, model: str = "text-embedding-004"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = model
        self._dimension = 768

    async def embed(self, text: str) -> List[float]:
        import google.generativeai as genai
        result = genai.embed_content(
            model=f"models/{self.model}",
            content=text,
            task_type="SEMANTIC_SIMILARITY"
        )
        return result['embedding']

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # Google supports batch embedding
        import google.generativeai as genai
        results = []
        for text in texts:
            result = await self.embed(text)
            results.append(result)
        return results

    @property
    def dimension(self) -> int:
        return self._dimension
```

### 4. OpenAI Embedding Client (`src/embeddings/openai.py`)

```python
from typing import List
from .base import BaseEmbeddingClient

class OpenAIEmbeddingClient(BaseEmbeddingClient):
    """OpenAI text-embedding-3-small client."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._dimension = 1536

    async def embed(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension
```

### 5. Update Proximity Agent (`src/agents/proximity.py`)

Add vector-based similarity as primary method:

```python
class ProximityAgent(BaseAgent):
    """Proximity agent with vector similarity support."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        vector_store: Optional[BaseVectorStore] = None,
        embedding_client: Optional[BaseEmbeddingClient] = None,
        use_vectors: bool = True
    ):
        super().__init__(llm_client)
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.use_vectors = use_vectors and vector_store and embedding_client

    async def compute_similarity(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis
    ) -> float:
        """Compute similarity between two hypotheses."""
        if self.use_vectors:
            return await self._vector_similarity(hypothesis_a, hypothesis_b)
        else:
            return await self._llm_similarity(hypothesis_a, hypothesis_b)

    async def _vector_similarity(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis
    ) -> float:
        """Fast vector-based similarity."""
        import numpy as np

        # Get or compute embeddings
        emb_a = await self._get_embedding(hypothesis_a)
        emb_b = await self._get_embedding(hypothesis_b)

        # Cosine similarity
        similarity = np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b))
        return float(similarity)

    async def _get_embedding(self, hypothesis: Hypothesis) -> List[float]:
        """Get embedding for hypothesis, computing if needed."""
        # Check cache first
        doc = await self.vector_store.get(hypothesis.id)
        if doc and doc.embedding:
            return doc.embedding

        # Compute embedding
        text = f"{hypothesis.title}\n{hypothesis.hypothesis_statement}\n{hypothesis.rationale}"
        embedding = await self.embedding_client.embed(text)

        # Store for future use
        doc = VectorDocument(
            id=hypothesis.id,
            content=text,
            embedding=embedding,
            metadata={"research_goal_id": hypothesis.research_goal_id}
        )
        await self.vector_store.add_documents([doc])

        return embedding

    async def find_similar(
        self,
        hypothesis: Hypothesis,
        candidates: List[Hypothesis],
        k: int = 5
    ) -> List[Tuple[Hypothesis, float]]:
        """Find k most similar hypotheses."""
        if self.use_vectors:
            embedding = await self._get_embedding(hypothesis)
            results = await self.vector_store.search(
                embedding,
                k=k,
                filter={"research_goal_id": hypothesis.research_goal_id}
            )
            # Map back to Hypothesis objects
            candidate_map = {h.id: h for h in candidates}
            return [
                (candidate_map[doc.id], score)
                for doc, score in results
                if doc.id in candidate_map and doc.id != hypothesis.id
            ]
        else:
            # Fallback to LLM-based (expensive)
            return await self._llm_find_similar(hypothesis, candidates, k)
```

### 6. Configuration Updates (`src/config.py`)

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Vector storage
    vector_store_type: Literal["chroma", "pgvector"] = "chroma"
    chroma_persist_directory: str = "./chroma_data"

    # Embeddings
    embedding_provider: Literal["google", "openai", "local"] = "google"
    google_embedding_model: str = "text-embedding-004"
    openai_embedding_model: str = "text-embedding-3-small"
```

### 7. Factory for Vector Components (`src/storage/vector_factory.py`)

```python
from .vector import BaseVectorStore, ChromaVectorStore, PgVectorStore
from ..embeddings.base import BaseEmbeddingClient
from ..embeddings.google import GoogleEmbeddingClient
from ..embeddings.openai import OpenAIEmbeddingClient
from ..config import get_settings

def create_vector_store() -> BaseVectorStore:
    """Create vector store based on config."""
    settings = get_settings()

    if settings.vector_store_type == "chroma":
        return ChromaVectorStore(
            persist_directory=settings.chroma_persist_directory
        )
    elif settings.vector_store_type == "pgvector":
        return PgVectorStore(settings.database_url)
    else:
        raise ValueError(f"Unknown vector store type: {settings.vector_store_type}")

def create_embedding_client() -> BaseEmbeddingClient:
    """Create embedding client based on config."""
    settings = get_settings()

    if settings.embedding_provider == "google":
        return GoogleEmbeddingClient(
            api_key=settings.google_api_key,
            model=settings.google_embedding_model
        )
    elif settings.embedding_provider == "openai":
        return OpenAIEmbeddingClient(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model
        )
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
```

## Database Schema (pgvector)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Hypothesis embeddings table
CREATE TABLE hypothesis_embeddings (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(768),  -- Adjust dimension based on model
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- IVFFlat index for fast similarity search
CREATE INDEX idx_hypothesis_embedding_ivfflat
ON hypothesis_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Index on research_goal_id in metadata for filtering
CREATE INDEX idx_hypothesis_metadata_goal
ON hypothesis_embeddings
USING GIN ((metadata->'research_goal_id'));
```

## Test Cases (`tests/test_vector.py`)

```python
import pytest
from src.storage.vector import ChromaVectorStore, VectorDocument
from src.embeddings.google import GoogleEmbeddingClient

@pytest.fixture
async def vector_store():
    store = ChromaVectorStore(collection_name="test_hypotheses")
    yield store
    # Cleanup

@pytest.fixture
async def embedding_client():
    return GoogleEmbeddingClient(api_key="test_key")

async def test_add_and_search(vector_store, embedding_client):
    """Test adding documents and searching."""
    # Create test documents
    docs = [
        VectorDocument(
            id="hyp_001",
            content="KIRA6 inhibits IRE1α and shows promise for AML treatment",
            embedding=await embedding_client.embed("KIRA6 inhibits IRE1α..."),
            metadata={"research_goal_id": "goal_001"}
        ),
        VectorDocument(
            id="hyp_002",
            content="Disulfiram targets NPL4 for cancer therapy",
            embedding=await embedding_client.embed("Disulfiram targets NPL4..."),
            metadata={"research_goal_id": "goal_001"}
        )
    ]

    await vector_store.add_documents(docs)

    # Search for similar
    query_embedding = await embedding_client.embed("IRE1α inhibition for leukemia")
    results = await vector_store.search(query_embedding, k=2)

    assert len(results) == 2
    assert results[0][0].id == "hyp_001"  # Most similar
    assert results[0][1] > 0.7  # High similarity

async def test_filter_by_goal(vector_store):
    """Test filtering search by research goal."""
    # Add docs with different goals
    # Search with filter
    # Verify only matching goal returned
    pass

async def test_cosine_similarity():
    """Test cosine similarity calculation."""
    import numpy as np

    a = [1, 0, 0]
    b = [1, 0, 0]
    c = [0, 1, 0]

    # Same vectors = similarity 1.0
    sim_ab = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    assert sim_ab == 1.0

    # Orthogonal vectors = similarity 0.0
    sim_ac = np.dot(a, c) / (np.linalg.norm(a) * np.linalg.norm(c))
    assert sim_ac == 0.0
```

## Success Criteria

- [ ] ChromaDB integration working for development
- [ ] pgvector integration working for production
- [ ] Google and OpenAI embedding clients implemented
- [ ] Proximity agent updated to use vector similarity by default
- [ ] Fallback to LLM-based similarity when vectors unavailable
- [ ] All tests passing
- [ ] Performance: 1000 hypotheses searchable in < 100ms

## Integration Points

### With Existing Code
- `ProximityAgent` - Primary consumer of vector similarity
- `RankingAgent` - Uses Proximity for match pairing
- `Storage` - Embeddings stored alongside hypothesis data

### With Phase 5C (Literature)
- Literature chunks can also be embedded for semantic search
- Citation similarity can use same embedding infrastructure

## Environment Variables

```bash
# Vector storage
VECTOR_STORE_TYPE=chroma  # or pgvector
CHROMA_PERSIST_DIRECTORY=./chroma_data

# Embeddings
EMBEDDING_PROVIDER=google  # or openai
GOOGLE_EMBEDDING_MODEL=text-embedding-004
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```
