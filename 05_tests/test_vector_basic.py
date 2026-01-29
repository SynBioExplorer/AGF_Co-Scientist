"""
Basic tests for Phase 5A: Vector Storage (no API keys required)

This test suite verifies core vector functionality without requiring
external API calls.
"""

import asyncio
import sys
from pathlib import Path

# Add paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_architecture"))

from src.storage.vector import (
    VectorDocument,
    VectorSearchResult,
    BaseVectorStore,
    ChromaVectorStore
)


def test_cosine_similarity():
    """Test cosine similarity calculation"""
    print("\n" + "=" * 70)
    print("TEST: Cosine Similarity")
    print("=" * 70)

    vec_a = [1.0, 0.0, 0.0]
    vec_b = [1.0, 0.0, 0.0]
    vec_c = [0.0, 1.0, 0.0]

    # Identical vectors should have similarity 1.0
    sim_identical = BaseVectorStore.cosine_similarity(vec_a, vec_b)
    assert abs(sim_identical - 1.0) < 0.001, f"Expected 1.0, got {sim_identical}"

    # Orthogonal vectors should have similarity 0.0
    sim_orthogonal = BaseVectorStore.cosine_similarity(vec_a, vec_c)
    assert abs(sim_orthogonal) < 0.001, f"Expected 0.0, got {sim_orthogonal}"

    # Similar vectors
    vec_d = [0.8, 0.2, 0.0]
    sim_similar = BaseVectorStore.cosine_similarity(vec_a, vec_d)
    assert 0.5 < sim_similar < 1.0, f"Expected 0.5-1.0, got {sim_similar}"

    print(f"✓ Identical vectors similarity: {sim_identical:.3f}")
    print(f"✓ Orthogonal vectors similarity: {sim_orthogonal:.3f}")
    print(f"✓ Similar vectors similarity: {sim_similar:.3f}")
    print("PASS: Cosine similarity working correctly\n")


async def test_chroma_basic():
    """Test ChromaDB basic operations"""
    print("=" * 70)
    print("TEST: ChromaDB Basic Operations")
    print("=" * 70)

    try:
        import chromadb

        store = ChromaVectorStore(persist_directory="./test_chroma_db")
        await store.connect()
        print("✓ ChromaDB connection established")

        # Create test documents
        docs = [
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
                metadata={"hypothesis_id": "hyp_3", "goal_id": "goal_2"}
            ),
        ]

        # Test: Add documents
        await store.add_documents(docs, collection_name="test_hypotheses")
        print(f"✓ Added {len(docs)} documents to ChromaDB")

        # Test: Search for similar documents
        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        results = await store.search(
            query_embedding=query_embedding,
            collection_name="test_hypotheses",
            limit=3
        )

        assert len(results) > 0, "No results found"
        assert results[0].document.id == "doc1", "Expected doc1 as top result"
        print(f"✓ Search found {len(results)} similar documents")
        print(f"  Top result: {results[0].document.id} (similarity: {results[0].similarity:.3f})")

        # Test: Search with metadata filter
        results_filtered = await store.search(
            query_embedding=query_embedding,
            collection_name="test_hypotheses",
            limit=10,
            filters={"goal_id": "goal_1"}
        )

        assert all(r.document.metadata.get("goal_id") == "goal_1" for r in results_filtered)
        print(f"✓ Filtered search found {len(results_filtered)} documents with goal_id=goal_1")

        # Test: Get document by ID
        doc = await store.get("doc1", collection_name="test_hypotheses")
        assert doc is not None, "Document not found"
        assert doc.id == "doc1", "Wrong document retrieved"
        print(f"✓ Retrieved document by ID: {doc.id}")

        # Test: Delete document
        deleted_count = await store.delete(["doc1"], collection_name="test_hypotheses")
        assert deleted_count == 1, "Document not deleted"

        doc_after_delete = await store.get("doc1", collection_name="test_hypotheses")
        assert doc_after_delete is None, "Document still exists after deletion"
        print(f"✓ Deleted document: doc1")

        # Test: Search with minimum similarity threshold
        results_threshold = await store.search(
            query_embedding=query_embedding,
            collection_name="test_hypotheses",
            limit=10,
            min_similarity=0.95
        )
        print(f"✓ Search with min_similarity=0.95 found {len(results_threshold)} documents")

        # Cleanup
        await store.clear_collection("test_hypotheses")
        await store.disconnect()
        print("✓ Cleaned up test collection")
        print("PASS: ChromaDB basic operations working correctly\n")

    except ImportError:
        print("SKIP: ChromaDB not installed")
        print("Install with: pip install chromadb\n")


async def test_chroma_persistence():
    """Test that ChromaDB persists data to disk"""
    print("=" * 70)
    print("TEST: ChromaDB Persistence")
    print("=" * 70)

    try:
        import chromadb

        # Create and add document
        store1 = ChromaVectorStore(persist_directory="./test_persist_db")
        await store1.connect()

        doc = VectorDocument(
            id="persist_test",
            content="Test persistence",
            embedding=[0.5, 0.5, 0.5],
            metadata={"test": "persistence"}
        )

        await store1.add_documents([doc], collection_name="persist_test")
        await store1.disconnect()
        print("✓ Created document and closed connection")

        # Reopen and verify document exists
        store2 = ChromaVectorStore(persist_directory="./test_persist_db")
        await store2.connect()

        retrieved = await store2.get("persist_test", collection_name="persist_test")
        assert retrieved is not None, "Document not persisted"
        assert retrieved.id == "persist_test", "Wrong document retrieved"
        print("✓ Document persisted and retrieved after reconnect")

        # Cleanup
        await store2.clear_collection("persist_test")
        await store2.disconnect()
        print("PASS: ChromaDB persistence working correctly\n")

    except ImportError:
        print("SKIP: ChromaDB not installed\n")


def main():
    """Run all basic vector tests"""
    print("\n" + "=" * 70)
    print("PHASE 5A: VECTOR STORAGE - BASIC TEST SUITE")
    print("=" * 70)
    print("\nThese tests verify core vector functionality without API keys.\n")

    # Test 1: Cosine similarity (pure Python, no dependencies)
    try:
        test_cosine_similarity()
    except Exception as e:
        print(f"FAIL: Cosine similarity test failed: {e}\n")

    # Test 2: ChromaDB basic operations
    try:
        asyncio.run(test_chroma_basic())
    except Exception as e:
        print(f"FAIL: ChromaDB basic test failed: {e}\n")

    # Test 3: ChromaDB persistence
    try:
        asyncio.run(test_chroma_persistence())
    except Exception as e:
        print(f"FAIL: ChromaDB persistence test failed: {e}\n")

    print("=" * 70)
    print("BASIC VECTOR TESTS COMPLETE")
    print("=" * 70)
    print("\nTo test embedding generation, ensure API keys are configured:")
    print("  - GOOGLE_API_KEY for Google embeddings")
    print("  - OPENAI_API_KEY for OpenAI embeddings")
    print("\nThen run: python 05_tests/test_vector.py")
    print()


if __name__ == "__main__":
    main()
