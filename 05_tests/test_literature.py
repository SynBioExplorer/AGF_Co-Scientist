"""
Tests for Literature Processing Module

Tests PDF parsing, citation extraction, citation graphs, chunking, and
private repository functionality.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import asyncio

from src.literature.pdf_parser import PDFParser, PDFSection, PDFMetadata
from src.literature.citation_extractor import CitationExtractor, ExtractedCitation
from src.literature.citation_graph import CitationGraph, CitationNode
from src.literature.chunker import TextChunker, TextChunk
from src.literature.repository import PrivateRepository, RepositoryDocument


# ==============================================================================
# PDF Parser Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_pdf_parser_initialization():
    """Test PDF parser initializes correctly."""
    parser = PDFParser()
    assert parser is not None
    assert parser.section_regex is not None


@pytest.mark.asyncio
async def test_pdf_metadata_extraction():
    """Test metadata extraction from text."""
    parser = PDFParser()

    # Mock text with metadata
    text = """
    A Novel Approach to Machine Learning

    John Smith, Jane Doe

    Published in Nature Machine Intelligence, 2023

    DOI: 10.1234/test.2023.001

    Keywords: machine learning, neural networks, deep learning

    Abstract
    This paper presents a novel approach to machine learning...

    Introduction
    Machine learning has revolutionized...
    """

    # Extract metadata components
    doi = parser._extract_doi(text)
    assert doi == "10.1234/test.2023.001"

    year = parser._extract_year(text)
    assert year == 2023

    keywords = parser._extract_keywords(text)
    assert "machine learning" in keywords

    abstract = parser._extract_abstract(text)
    assert abstract is not None
    assert "novel approach" in abstract.lower()


@pytest.mark.asyncio
async def test_pdf_section_extraction():
    """Test section detection and extraction."""
    parser = PDFParser()

    # Test section pattern matching
    assert parser.section_regex.match("Abstract")
    assert parser.section_regex.match("INTRODUCTION")
    assert parser.section_regex.match("Methods")
    assert parser.section_regex.match("Results")
    assert parser.section_regex.match("Discussion")
    assert parser.section_regex.match("References")


# ==============================================================================
# Citation Extractor Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_citation_extractor_initialization():
    """Test citation extractor initializes correctly."""
    extractor = CitationExtractor()
    assert extractor is not None
    assert extractor.author_year_pattern is not None
    assert extractor.numeric_pattern is not None


@pytest.mark.asyncio
async def test_extract_author_year_citations():
    """Test extraction of author-year citations."""
    extractor = CitationExtractor()

    text = """
    Previous research has shown interesting results (Smith et al., 2020).
    This builds on earlier work (Jones, 2019) and recent findings (Brown et al., 2023).
    """

    citations = await extractor.extract_from_text(text)

    # Should find 3 citations
    assert len(citations) >= 3

    # Check first citation
    smith_citation = next(c for c in citations if "Smith" in c.raw_text)
    assert smith_citation.year == 2020
    assert "Smith" in smith_citation.authors[0]


@pytest.mark.asyncio
async def test_extract_numeric_citations():
    """Test extraction of numeric citations."""
    extractor = CitationExtractor()

    text = """
    Several studies support this claim [1, 2, 3].
    Further evidence can be found elsewhere [4-6].
    A single reference is also useful [7].
    """

    citations = await extractor.extract_from_text(text)

    # Should find numeric citations
    assert len(citations) >= 3

    # Check that citations were extracted
    numeric_citations = [c for c in citations if c.raw_text.startswith('[')]
    assert len(numeric_citations) >= 3


@pytest.mark.asyncio
async def test_extract_multi_author_citations():
    """Test extraction of multi-author inline citations."""
    extractor = CitationExtractor()

    text = """
    Smith and Jones (2020) demonstrated this phenomenon.
    Later work by Brown & Wilson (2022) confirmed these findings.
    """

    citations = await extractor.extract_from_text(text)

    # Should find 2 citations
    assert len(citations) >= 2

    # Check multi-author citation
    multi_auth = next(c for c in citations if len(c.authors) == 2)
    assert len(multi_auth.authors) == 2


@pytest.mark.asyncio
async def test_citation_resolution():
    """Test resolving numeric citations with reference list."""
    extractor = CitationExtractor()

    # Create citations with numeric references
    citations = [
        ExtractedCitation(
            raw_text="[1]",
            context="Previous work [1] showed..."
        ),
        ExtractedCitation(
            raw_text="[2]",
            context="Other studies [2] found..."
        )
    ]

    # Reference list
    references = [
        "Smith, J., Jones, A. (2020). A study on machine learning. Nature, 123, 45-67. DOI: 10.1234/nature.2020",
        "Brown, B., Wilson, C. (2021). Deep learning advances. Science, 456, 78-90. PMID: 12345678"
    ]

    # Resolve citations
    resolved = await extractor.resolve_citations(citations, references)

    # Check resolution
    assert len(resolved) == 2

    # First citation should have resolved metadata
    first = resolved[0]
    assert len(first.authors) > 0
    assert first.year == 2020


@pytest.mark.asyncio
async def test_parse_reference_string():
    """Test parsing individual reference strings."""
    extractor = CitationExtractor()

    ref = "Smith, J., Jones, A. (2020). A Novel Approach to Deep Learning. Nature Machine Intelligence, 5(3), 234-256. DOI: 10.1234/nmi.2020.001"

    parsed = extractor._parse_reference(ref)

    assert 'authors' in parsed
    assert len(parsed['authors']) >= 1

    assert 'year' in parsed
    assert parsed['year'] == 2020

    assert 'title' in parsed
    assert 'novel approach' in parsed['title'].lower()

    assert 'doi' in parsed
    assert parsed['doi'] == "10.1234/nmi.2020.001"


# ==============================================================================
# Citation Graph Tests
# ==============================================================================


def test_citation_graph_initialization():
    """Test citation graph initializes correctly."""
    graph = CitationGraph()
    assert graph is not None
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_add_papers_to_graph():
    """Test adding papers to citation graph."""
    graph = CitationGraph()

    # Add papers
    graph.add_paper("paper1", "First Paper", ["Smith, J."], 2020)
    graph.add_paper("paper2", "Second Paper", ["Jones, A."], 2021)
    graph.add_paper("paper3", "Third Paper", ["Brown, B."], 2022)

    assert len(graph.nodes) == 3
    assert "paper1" in graph.nodes
    assert graph.nodes["paper1"].title == "First Paper"


def test_add_citations_to_graph():
    """Test adding citation edges."""
    graph = CitationGraph()

    # Add papers
    graph.add_paper("paper1", "First Paper", ["Smith, J."], 2020)
    graph.add_paper("paper2", "Second Paper", ["Jones, A."], 2021)
    graph.add_paper("paper3", "Third Paper", ["Brown, B."], 2022)

    # Add citations (paper2 cites paper1, paper3 cites paper1 and paper2)
    graph.add_citation("paper2", "paper1")
    graph.add_citation("paper3", "paper1")
    graph.add_citation("paper3", "paper2")

    assert len(graph.edges) == 3

    # Check citation counts
    assert graph.nodes["paper1"].citation_count == 2  # Cited by 2 papers
    assert graph.nodes["paper2"].citation_count == 1  # Cited by 1 paper
    assert graph.nodes["paper3"].reference_count == 2  # Cites 2 papers


def test_get_citations_and_cited_by():
    """Test retrieving citations and cited-by relationships."""
    graph = CitationGraph()

    # Add papers and citations
    graph.add_paper("paper1", "First Paper", ["Smith, J."], 2020)
    graph.add_paper("paper2", "Second Paper", ["Jones, A."], 2021)
    graph.add_paper("paper3", "Third Paper", ["Brown, B."], 2022)

    graph.add_citation("paper2", "paper1")
    graph.add_citation("paper3", "paper1")
    graph.add_citation("paper3", "paper2")

    # Get papers cited by paper3
    citations = graph.get_citations("paper3")
    assert len(citations) == 2
    assert any(c.id == "paper1" for c in citations)
    assert any(c.id == "paper2" for c in citations)

    # Get papers citing paper1
    cited_by = graph.get_cited_by("paper1")
    assert len(cited_by) == 2
    assert any(c.id == "paper2" for c in cited_by)
    assert any(c.id == "paper3" for c in cited_by)


def test_get_most_cited():
    """Test getting most cited papers."""
    graph = CitationGraph()

    # Add papers
    graph.add_paper("paper1", "First Paper", ["Smith, J."], 2020)
    graph.add_paper("paper2", "Second Paper", ["Jones, A."], 2021)
    graph.add_paper("paper3", "Third Paper", ["Brown, B."], 2022)
    graph.add_paper("paper4", "Fourth Paper", ["Wilson, C."], 2023)

    # Create citation pattern (paper1 is most cited)
    graph.add_citation("paper2", "paper1")
    graph.add_citation("paper3", "paper1")
    graph.add_citation("paper4", "paper1")
    graph.add_citation("paper3", "paper2")

    most_cited = graph.get_most_cited(n=2)

    assert len(most_cited) == 2
    assert most_cited[0].id == "paper1"  # 3 citations
    assert most_cited[1].id == "paper2"  # 1 citation


def test_find_citation_paths():
    """Test finding citation paths between papers."""
    graph = CitationGraph()

    # Build citation chain: paper4 -> paper3 -> paper2 -> paper1
    graph.add_paper("paper1", "First Paper", ["Smith, J."], 2020)
    graph.add_paper("paper2", "Second Paper", ["Jones, A."], 2021)
    graph.add_paper("paper3", "Third Paper", ["Brown, B."], 2022)
    graph.add_paper("paper4", "Fourth Paper", ["Wilson, C."], 2023)

    graph.add_citation("paper2", "paper1")
    graph.add_citation("paper3", "paper2")
    graph.add_citation("paper4", "paper3")

    # Find path from paper4 to paper1
    paths = graph.find_citation_paths("paper4", "paper1", max_depth=5)

    assert len(paths) > 0
    # Should find path: paper4 -> paper3 -> paper2 -> paper1
    assert any("paper1" in path and "paper4" in path for path in paths)


def test_co_citation_strength():
    """Test co-citation strength calculation."""
    graph = CitationGraph()

    # Add papers
    for i in range(1, 6):
        graph.add_paper(f"paper{i}", f"Paper {i}", [f"Author {i}"], 2020 + i)

    # Papers 4 and 5 both cite papers 1 and 2
    graph.add_citation("paper4", "paper1")
    graph.add_citation("paper4", "paper2")
    graph.add_citation("paper5", "paper1")
    graph.add_citation("paper5", "paper2")

    # Co-citation strength between paper1 and paper2 should be 2
    strength = graph.get_co_citation_strength("paper1", "paper2")
    assert strength == 2


def test_bibliographic_coupling():
    """Test bibliographic coupling calculation."""
    graph = CitationGraph()

    # Add papers
    for i in range(1, 6):
        graph.add_paper(f"paper{i}", f"Paper {i}", [f"Author {i}"], 2020 + i)

    # Papers 3 and 4 both cite papers 1 and 2
    graph.add_citation("paper3", "paper1")
    graph.add_citation("paper3", "paper2")
    graph.add_citation("paper4", "paper1")
    graph.add_citation("paper4", "paper2")

    # Bibliographic coupling between paper3 and paper4 should be 2
    coupling = graph.get_bibliographic_coupling("paper3", "paper4")
    assert coupling == 2


def test_graph_serialization():
    """Test graph serialization and deserialization."""
    graph = CitationGraph()

    # Build graph
    graph.add_paper("paper1", "First Paper", ["Smith, J."], 2020, doi="10.1234/test")
    graph.add_paper("paper2", "Second Paper", ["Jones, A."], 2021)
    graph.add_citation("paper2", "paper1")

    # Serialize
    data = graph.to_dict()

    assert 'nodes' in data
    assert 'edges' in data
    assert len(data['nodes']) == 2
    assert len(data['edges']) == 1

    # Deserialize
    restored = CitationGraph.from_dict(data)

    assert len(restored.nodes) == 2
    assert len(restored.edges) == 1
    assert "paper1" in restored.nodes
    assert restored.nodes["paper1"].doi == "10.1234/test"


def test_graph_statistics():
    """Test graph statistics calculation."""
    graph = CitationGraph()

    # Add papers and citations
    graph.add_paper("paper1", "First Paper", ["Smith, J."], 2020)
    graph.add_paper("paper2", "Second Paper", ["Jones, A."], 2021)
    graph.add_paper("paper3", "Third Paper", ["Brown, B."], 2022)

    graph.add_citation("paper2", "paper1")
    graph.add_citation("paper3", "paper1")
    graph.add_citation("paper3", "paper2")

    stats = graph.get_statistics()

    assert stats['total_papers'] == 3
    assert stats['total_citations'] == 3
    assert stats['avg_citations_per_paper'] == 1.0  # (2+1+0)/3
    assert stats['max_citations'] == 2  # paper1


# ==============================================================================
# Text Chunker Tests
# ==============================================================================


def test_chunker_initialization():
    """Test text chunker initializes correctly."""
    chunker = TextChunker()
    assert chunker is not None


def test_chunk_by_chars():
    """Test character-based chunking."""
    chunker = TextChunker()

    text = "A" * 1000  # 1000 character text

    chunks = chunker.chunk_text(text, chunk_size=100, overlap=10, respect_sentences=False)

    # Should create ~10 chunks with overlap
    assert len(chunks) >= 9
    assert all(isinstance(c, TextChunk) for c in chunks)

    # Check overlap
    if len(chunks) >= 2:
        # Last 10 chars of first chunk should match first 10 of second
        # (approximately, depending on exact split)
        assert chunks[0].end_idx > chunks[1].start_idx


def test_chunk_by_sentences():
    """Test sentence-aware chunking."""
    chunker = TextChunker()

    text = """
    This is the first sentence. This is the second sentence.
    This is the third sentence. This is the fourth sentence.
    This is the fifth sentence. This is the sixth sentence.
    """

    chunks = chunker.chunk_text(text, chunk_size=100, overlap=20, respect_sentences=True)

    # Should create multiple chunks
    assert len(chunks) >= 2

    # Each chunk should contain complete sentences (ending with period)
    for chunk in chunks:
        # Check that chunk doesn't end mid-sentence (should end with punctuation or whitespace)
        assert chunk.text.rstrip().endswith(('.', '!', '?', ' '))


def test_split_sentences():
    """Test sentence splitting."""
    chunker = TextChunker()

    text = "First sentence. Second sentence! Third sentence? Fourth."

    sentences = chunker._split_sentences(text)

    # Should split into 4 sentences
    assert len(sentences) >= 3


def test_chunk_sections():
    """Test chunking with section metadata."""
    chunker = TextChunker()

    sections = [
        {
            'title': 'Introduction',
            'content': 'This is the introduction section. ' * 50,
            'page_numbers': [1, 2]
        },
        {
            'title': 'Methods',
            'content': 'This describes the methods. ' * 50,
            'page_numbers': [3, 4]
        }
    ]

    chunks = chunker.chunk_sections(sections, chunk_size=200, overlap=20)

    # Should create multiple chunks
    assert len(chunks) >= 2

    # Check that metadata is preserved
    intro_chunks = [c for c in chunks if c.metadata.get('section_title') == 'Introduction']
    assert len(intro_chunks) > 0
    assert intro_chunks[0].metadata['section_pages'] == [1, 2]


def test_merge_small_chunks():
    """Test merging small chunks."""
    chunker = TextChunker()

    # Create chunks with varying sizes
    chunks = [
        TextChunk(text="Small", start_idx=0, end_idx=5),
        TextChunk(text="Another small", start_idx=6, end_idx=19),
        TextChunk(text="This is a much longer chunk that should not be merged", start_idx=20, end_idx=74),
        TextChunk(text="Tiny", start_idx=75, end_idx=79),
    ]

    merged = chunker.merge_small_chunks(chunks, min_size=20)

    # Should merge the small chunks
    assert len(merged) < len(chunks)


# ==============================================================================
# Private Repository Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_repository_initialization():
    """Test repository initializes correctly."""
    repo = PrivateRepository()
    assert repo is not None
    assert repo.pdf_parser is not None
    assert repo.chunker is not None


@pytest.mark.asyncio
async def test_repository_statistics():
    """Test repository statistics."""
    repo = PrivateRepository()

    stats = repo.get_statistics()

    assert 'total_documents' in stats
    assert stats['total_documents'] == 0  # Empty repository
    assert stats['has_semantic_search'] is False  # No vector store


@pytest.mark.asyncio
async def test_repository_list_documents():
    """Test listing documents."""
    repo = PrivateRepository()

    # Empty repository
    docs = repo.list_documents()
    assert docs == []


@pytest.mark.asyncio
async def test_repository_keyword_search():
    """Test keyword search fallback."""
    repo = PrivateRepository()

    # Add a mock document directly
    from datetime import datetime
    repo.documents["test_doc"] = RepositoryDocument(
        id="test_doc",
        filename="test.pdf",
        title="Machine Learning for Scientific Discovery",
        authors=["Smith, J.", "Jones, A."],
        abstract="This paper explores machine learning applications in science.",
        full_text="Machine learning has revolutionized scientific discovery...",
        chunk_ids=[],
        metadata={},
        indexed_at=datetime.now()
    )

    # Search for documents
    results = await repo.search("machine learning", k=5)

    assert len(results) >= 1
    assert results[0]['document_id'] == "test_doc"
    assert results[0]['score'] > 0


# ==============================================================================
# Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_end_to_end_citation_workflow():
    """Test complete workflow: extract citations and build graph."""
    extractor = CitationExtractor()
    graph = CitationGraph()

    # Sample text with citations
    text = """
    Recent work in machine learning (Smith et al., 2020) has shown promising results.
    This builds on earlier studies (Jones, 2019; Brown et al., 2021).
    """

    # Extract citations
    citations = await extractor.extract_from_text(text)

    # Add to graph (simplified)
    graph.add_paper("current_paper", "Current Study", ["Author, X."], 2023)

    for i, citation in enumerate(citations):
        if citation.year:
            paper_id = f"cited_{i}"
            graph.add_paper(
                paper_id,
                f"Paper {i}",
                citation.authors,
                citation.year
            )
            graph.add_citation("current_paper", paper_id)

    # Verify graph was built
    assert len(graph.nodes) >= 2
    assert graph.nodes["current_paper"].reference_count >= 1


def test_chunking_and_metadata_preservation():
    """Test that chunking preserves section metadata."""
    chunker = TextChunker()

    # Create sections with metadata
    sections = [
        {
            'title': 'Abstract',
            'content': 'Short abstract. ' * 10,
            'page_numbers': [1]
        },
        {
            'title': 'Introduction',
            'content': 'Long introduction text. ' * 100,
            'page_numbers': [2, 3, 4]
        }
    ]

    # Chunk with metadata
    chunks = chunker.chunk_sections(sections, chunk_size=200)

    # Verify metadata is preserved
    for chunk in chunks:
        assert 'section_title' in chunk.metadata
        assert 'section_pages' in chunk.metadata

    # Introduction should have more chunks
    intro_chunks = [c for c in chunks if c.metadata['section_title'] == 'Introduction']
    abstract_chunks = [c for c in chunks if c.metadata['section_title'] == 'Abstract']

    assert len(intro_chunks) > len(abstract_chunks)


# ==============================================================================
# Run Tests
# ==============================================================================


if __name__ == "__main__":
    print("Running Literature Processing Tests...")
    print("=" * 70)

    # Run sync tests
    print("\n1. Testing Citation Graph...")
    test_citation_graph_initialization()
    test_add_papers_to_graph()
    test_add_citations_to_graph()
    test_get_citations_and_cited_by()
    test_get_most_cited()
    test_find_citation_paths()
    test_co_citation_strength()
    test_bibliographic_coupling()
    test_graph_serialization()
    test_graph_statistics()
    print("✓ Citation Graph tests passed")

    print("\n2. Testing Text Chunker...")
    test_chunker_initialization()
    test_chunk_by_chars()
    test_chunk_by_sentences()
    test_split_sentences()
    test_chunk_sections()
    test_merge_small_chunks()
    test_chunking_and_metadata_preservation()
    print("✓ Text Chunker tests passed")

    # Run async tests
    print("\n3. Testing PDF Parser...")
    asyncio.run(test_pdf_parser_initialization())
    asyncio.run(test_pdf_metadata_extraction())
    asyncio.run(test_pdf_section_extraction())
    print("✓ PDF Parser tests passed")

    print("\n4. Testing Citation Extractor...")
    asyncio.run(test_citation_extractor_initialization())
    asyncio.run(test_extract_author_year_citations())
    asyncio.run(test_extract_numeric_citations())
    asyncio.run(test_extract_multi_author_citations())
    asyncio.run(test_citation_resolution())
    asyncio.run(test_parse_reference_string())
    print("✓ Citation Extractor tests passed")

    print("\n5. Testing Private Repository...")
    asyncio.run(test_repository_initialization())
    asyncio.run(test_repository_statistics())
    asyncio.run(test_repository_list_documents())
    asyncio.run(test_repository_keyword_search())
    print("✓ Private Repository tests passed")

    print("\n6. Testing Integration Workflows...")
    asyncio.run(test_end_to_end_citation_workflow())
    print("✓ Integration tests passed")

    print("\n" + "=" * 70)
    print("All Literature Processing Tests Passed! ✓")
