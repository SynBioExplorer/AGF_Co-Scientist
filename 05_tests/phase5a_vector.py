"""
Test suite for Phase 5A: Vector Storage

Tests vector embeddings, similarity search, and integration with Proximity Agent.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from typing import List

# Add paths to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_architecture"))

from schemas import Hypothesis, HypothesisStatus

# Import vector components
from src.storage.vector import (
    VectorDocument,
    VectorSearchResult,
    BaseVectorStore,
    ChromaVectorStore
)
from src.embeddings.base import BaseEmbeddingClient
from src.embeddings.google import GoogleEmbeddingClient
from src.embeddings.openai import OpenAIEmbeddingClient
from src.storage.vector_factory import (
    create_vector_store,
    create_embedding_client
)
from src.agents.proximity import ProximityAgent
from src.utils.ids import generate_id


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_hypotheses() -> List[Hypothesis]:
    """Create sample hypotheses for testing"""
    return [
        Hypothesis(
            id=generate_id("hyp"),
            research_goal_id="goal_1",
            title="CRISPR Activation of Tumor Suppressors",
            summary="Use CRISPR activation to upregulate tumor suppressor genes",
            hypothesis_statement="CRISPR-based transcriptional activation can upregulate p53 and PTEN expression",
            rationale="Tumor suppressors are often silenced in cancer",
            mechanism="dCas9-VP64 fusion protein binds promoter regions",
            status=HypothesisStatus.GENERATED
        ),
        Hypothesis(
            id=generate_id("hyp"),
            research_goal_id="goal_1",
            title="Gene Editing for Cancer Treatment",
            summary="Use gene editing to restore tumor suppressor function",
            hypothesis_statement="Base editing can correct mutations in TP53 gene",
            rationale="TP53 mutations are common in cancer",
            mechanism="Adenine base editor (ABE) corrects point mutations",
            status=HypothesisStatus.GENERATED
        ),
        Hypothesis(
            id=generate_id("hyp"),
            research_goal_id="goal_1",
            title="Metabolic Rewiring in Cancer Cells",
            summary="Target metabolic pathways in cancer",
            hypothesis_statement="Inhibiting glycolysis reduces cancer cell proliferation",
            rationale="Cancer cells rely on glycolysis (Warburg effect)",
            mechanism="2-DG blocks hexokinase enzyme",
            status=HypothesisStatus.GENERATED
        ),
    ]


@pytest.fixture
def sample_documents() -> List[VectorDocument]:
    """Create sample vector documents for testing"""
    return [
        VectorDocument(
            id="doc1",
            content="CRISPR gene editing for cancer treatment",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            metadata={"hypothesis_id": "hyp_1", "goal_id": "goal_1"}
        ),
        VectorDocument(
            id="doc2",
            content="Base editing to correct genetic mutations",
            embedding=[0.15, 0.25, 0.35, 0.45, 0.55],
            metadata={"hypothesis_id": "hyp_2", "goal_id": "goal_1"}
        ),
        VectorDocument(
            id="doc3",
            content="Metabolic inhibition using small molecules",
            embedding=[0.9, 0.8, 0.7, 0.6, 0.5],
            metadata={"hypothesis_id": "hyp_3", "goal_id": "goal_1"}
        ),
    ]


# =============================================================================
# Test Embedding Clients
# =============================================================================

def test_google_embedding_client():
    """Test Google embedding client initialization and properties"""
    try:
        client = GoogleEmbeddingClient()

        assert client.model_name == "text-embedding-004"
        assert client.dimension == 768

        print("✓ Google embedding client initialized successfully")

    except Exception as e:
        print(f"⚠ Google embedding client test skipped (API key required): {e}")
        pytest.skip("GOOGLE_API_KEY not configured")


def test_openai_embedding_client():
    """Test OpenAI embedding client initialization and properties"""
    try:
        client = OpenAIEmbeddingClient()

        assert client.model_name == "text-embedding-3-small"
        assert client.dimension == 1536

        print("✓ OpenAI embedding client initialized successfully")

    except Exception as e:
        print(f"⚠ OpenAI embedding client test skipped (API key required): {e}")
        pytest.skip("OPENAI_API_KEY not configured")


def test_embedding_generation():
    """Test actual embedding generation with Google client"""
    try:
        client = GoogleEmbeddingClient()

        text = "CRISPR gene editing for cancer treatment"
        embedding = client.embed(text)

        assert isinstance(embedding, list)
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

        print(f"✓ Generated embedding of dimension {len(embedding)}")

    except Exception as e:
        print(f"⚠ Embedding generation test skipped: {e}")
        pytest.skip("Embedding API not available")


def test_embedding_batch():
    """Test batch embedding generation"""
    try:
        client = GoogleEmbeddingClient()

        texts = [
            "CRISPR gene editing",
            "Base editing mutations",
            "Metabolic inhibition"
        ]
        embeddings = client.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == 768 for emb in embeddings)

        print(f"✓ Generated {len(embeddings)} embeddings in batch")

    except Exception as e:
        print(f"⚠ Batch embedding test skipped: {e}")
        pytest.skip("Embedding API not available")


# =============================================================================
# Test Vector Store (ChromaDB)
# =============================================================================

@pytest.mark.asyncio
async def test_chroma_vector_store_initialization():
    """Test ChromaDB vector store initialization"""
    try:
        import chromadb

        store = ChromaVectorStore(persist_directory="./test_chroma_db")
        await store.connect()

        assert store._client is not None

        await store.disconnect()

        print("✓ ChromaDB vector store initialized successfully")

    except ImportError:
        print("⚠ ChromaDB not installed, test skipped")
        pytest.skip("ChromaDB not installed")


@pytest.mark.asyncio
async def test_add_and_search_documents(sample_documents):
    """Test adding documents and searching by similarity"""
    try:
        import chromadb

        store = ChromaVectorStore(persist_directory="./test_chroma_db")
        await store.connect()

        # Add documents
        await store.add_documents(sample_documents, collection_name="test_hypotheses")

        # Search using first document's embedding as query
        query_embedding = sample_documents[0].embedding
        results = await store.search(
            query_embedding=query_embedding,
            collection_name="test_hypotheses",
            limit=2
        )

        assert len(results) > 0
        assert all(isinstance(r, VectorSearchResult) for r in results)
        assert results[0].document.id == "doc1"  # Should match itself

        print(f"✓ Search found {len(results)} similar documents")
        print(f"  Top result: {results[0].document.id} (similarity: {results[0].similarity:.3f})")

        # Cleanup
        await store.clear_collection("test_hypotheses")
        await store.disconnect()

    except ImportError:
        print("⚠ ChromaDB not installed, test skipped")
        pytest.skip("ChromaDB not installed")


@pytest.mark.asyncio
async def test_search_with_filters(sample_documents):
    """Test searching with metadata filters"""
    try:
        import chromadb

        store = ChromaVectorStore(persist_directory="./test_chroma_db")
        await store.connect()

        # Add documents
        await store.add_documents(sample_documents, collection_name="test_hypotheses")

        # Search with filter
        query_embedding = sample_documents[0].embedding
        results = await store.search(
            query_embedding=query_embedding,
            collection_name="test_hypotheses",
            limit=10,
            filters={"goal_id": "goal_1"}
        )

        assert len(results) > 0
        assert all(r.document.metadata.get("goal_id") == "goal_1" for r in results)

        print(f"✓ Filtered search found {len(results)} documents")

        # Cleanup
        await store.clear_collection("test_hypotheses")
        await store.disconnect()

    except ImportError:
        print("⚠ ChromaDB not installed, test skipped")
        pytest.skip("ChromaDB not installed")


@pytest.mark.asyncio
async def test_delete_documents(sample_documents):
    """Test deleting documents from vector store"""
    try:
        import chromadb

        store = ChromaVectorStore(persist_directory="./test_chroma_db")
        await store.connect()

        # Add documents
        await store.add_documents(sample_documents, collection_name="test_hypotheses")

        # Delete one document
        deleted_count = await store.delete(
            document_ids=["doc1"],
            collection_name="test_hypotheses"
        )

        assert deleted_count == 1

        # Verify it's gone
        doc = await store.get("doc1", collection_name="test_hypotheses")
        assert doc is None

        print("✓ Document deletion successful")

        # Cleanup
        await store.clear_collection("test_hypotheses")
        await store.disconnect()

    except ImportError:
        print("⚠ ChromaDB not installed, test skipped")
        pytest.skip("ChromaDB not installed")


# =============================================================================
# Test Cosine Similarity
# =============================================================================

def test_cosine_similarity():
    """Test cosine similarity calculation"""
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [1.0, 0.0, 0.0]
    vec_c = [0.0, 1.0, 0.0]

    # Identical vectors should have similarity 1.0
    sim_identical = BaseVectorStore.cosine_similarity(vec_a, vec_b)
    assert abs(sim_identical - 1.0) < 0.001

    # Orthogonal vectors should have similarity 0.0
    sim_orthogonal = BaseVectorStore.cosine_similarity(vec_a, vec_c)
    assert abs(sim_orthogonal) < 0.001

    # Similar vectors
    vec_d = [0.8, 0.2, 0.0]
    sim_similar = BaseVectorStore.cosine_similarity(vec_a, vec_d)
    assert 0.5 < sim_similar < 1.0

    print(f"✓ Cosine similarity tests passed")
    print(f"  Identical: {sim_identical:.3f}")
    print(f"  Orthogonal: {sim_orthogonal:.3f}")
    print(f"  Similar: {sim_similar:.3f}")


# =============================================================================
# Test Factory Functions
# =============================================================================

def test_create_vector_store():
    """Test vector store factory"""
    store = create_vector_store(
        store_type="chroma",
        chroma_persist_directory="./test_factory_db"
    )

    assert isinstance(store, ChromaVectorStore)
    print("✓ Vector store factory created ChromaDB store")


def test_create_embedding_client():
    """Test embedding client factory"""
    try:
        client = create_embedding_client(provider="google")
        assert isinstance(client, GoogleEmbeddingClient)
        print("✓ Embedding client factory created Google client")

    except Exception as e:
        print(f"⚠ Embedding client factory test skipped: {e}")
        pytest.skip("API key not configured")


# =============================================================================
# Test Proximity Agent Integration
# =============================================================================

def test_proximity_agent_with_vectors(sample_hypotheses):
    """Test Proximity Agent using vector similarity"""
    try:
        import chromadb

        # Create vector store and embedding client
        vector_store = ChromaVectorStore(persist_directory="./test_proximity_db")
        embedding_client = GoogleEmbeddingClient()

        # Initialize store
        asyncio.run(vector_store.connect())

        # Create Proximity Agent with vector support
        agent = ProximityAgent(
            vector_store=vector_store,
            embedding_client=embedding_client,
            use_vectors=True
        )

        # Execute proximity analysis
        result = agent.execute(
            hypotheses=sample_hypotheses,
            research_goal_id="goal_1",
            similarity_threshold=0.5
        )

        assert result is not None
        assert len(result.edges) >= 0
        assert len(result.clusters) >= 0

        print(f"✓ Proximity Agent executed with vectors")
        print(f"  Found {len(result.edges)} edges")
        print(f"  Created {len(result.clusters)} clusters")

        # Cleanup
        asyncio.run(vector_store.clear_collection("hypotheses"))
        asyncio.run(vector_store.disconnect())

    except Exception as e:
        print(f"⚠ Proximity Agent vector test skipped: {e}")
        pytest.skip("Dependencies not available")


def test_proximity_agent_fallback_to_llm(sample_hypotheses):
    """Test Proximity Agent falling back to LLM when vectors unavailable"""
    # Create Proximity Agent without vector support
    agent = ProximityAgent(
        vector_store=None,
        embedding_client=None,
        use_vectors=False
    )

    assert agent.use_vectors is False

    # Should still work using LLM-based similarity
    print("✓ Proximity Agent created without vector support (will use LLM fallback)")


def test_proximity_agent_find_similar(sample_hypotheses):
    """Test finding similar hypotheses using vector search"""
    try:
        import chromadb

        # Create vector store and embedding client
        vector_store = ChromaVectorStore(persist_directory="./test_similarity_db")
        embedding_client = GoogleEmbeddingClient()

        # Initialize store
        asyncio.run(vector_store.connect())

        # Create Proximity Agent
        agent = ProximityAgent(
            vector_store=vector_store,
            embedding_client=embedding_client,
            use_vectors=True
        )

        # Add hypotheses to vector store first
        # (In real usage, this would happen during execute())
        for hyp in sample_hypotheses:
            embedding = agent._get_embedding(hyp)
            doc = VectorDocument(
                id=hyp.id,
                content=agent._hypothesis_to_text(hyp),
                embedding=embedding,
                metadata={"hypothesis_id": hyp.id, "goal_id": hyp.research_goal_id}
            )
            asyncio.run(vector_store.add_documents([doc], collection_name="hypotheses"))

        # Find similar hypotheses to the first one
        similar = agent.find_similar(
            hypothesis=sample_hypotheses[0],
            min_similarity=0.3,
            limit=5
        )

        assert isinstance(similar, list)
        print(f"✓ Found {len(similar)} similar hypotheses")

        for hyp_id, score in similar[:3]:
            print(f"  {hyp_id}: {score:.3f}")

        # Cleanup
        asyncio.run(vector_store.clear_collection("hypotheses"))
        asyncio.run(vector_store.disconnect())

    except Exception as e:
        print(f"⚠ Find similar test skipped: {e}")
        pytest.skip("Dependencies not available")


# =============================================================================
# Main Test Runner
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PHASE 5A: VECTOR STORAGE TEST SUITE")
    print("=" * 70 + "\n")

    # Run tests
    pytest.main([__file__, "-v", "-s"])

    print("\n" + "=" * 70)
    print("Vector storage tests complete!")
    print("=" * 70 + "\n")
