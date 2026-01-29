# Phase 5C: Literature Processing - Quick Reference

## Quick Start

### Import Everything
```python
from src.literature import (
    PDFParser, ParsedPDF,
    CitationExtractor, ExtractedCitation,
    CitationGraph, CitationNode,
    TextChunker, TextChunk,
    PrivateRepository, RepositoryDocument
)
```

---

## Common Use Cases

### 1. Parse a PDF Paper

```python
parser = PDFParser()
parsed = await parser.parse("path/to/paper.pdf")

print(f"Title: {parsed.metadata.title}")
print(f"Authors: {', '.join(parsed.metadata.authors)}")
print(f"Year: {parsed.metadata.year}")
print(f"DOI: {parsed.metadata.doi}")
print(f"Pages: {parsed.page_count}")
print(f"Sections: {len(parsed.sections)}")
```

### 2. Extract Citations from Text

```python
extractor = CitationExtractor()
text = """
Recent work (Smith et al., 2020) has shown promising results.
This builds on earlier studies [1,2,3] in the field.
"""

citations = await extractor.extract_from_text(text)
for cit in citations:
    print(f"{cit.raw_text} - Year: {cit.year}")
```

### 3. Build Citation Network

```python
graph = CitationGraph()

# Add papers
graph.add_paper("paper1", "Study A", ["Smith, J."], 2020)
graph.add_paper("paper2", "Study B", ["Jones, A."], 2021)
graph.add_paper("paper3", "Study C", ["Brown, B."], 2022)

# Add citation relationships
graph.add_citation("paper2", "paper1")  # paper2 cites paper1
graph.add_citation("paper3", "paper1")

# Analyze
most_cited = graph.get_most_cited(n=5)
stats = graph.get_statistics()
paths = graph.find_citation_paths("paper3", "paper1")
```

### 4. Chunk Document Text

```python
chunker = TextChunker()

# Chunk by sentences
chunks = chunker.chunk_text(
    text=full_text,
    chunk_size=500,      # characters
    overlap=50,          # overlap between chunks
    respect_sentences=True  # don't split mid-sentence
)

for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {len(chunk.text)} chars")
```

### 5. Index Private PDF Collection

```python
from src.storage.vector import ChromaVectorStore
from src.embeddings.google import GoogleEmbeddingClient

# Setup vector storage (optional, but enables semantic search)
vector_store = ChromaVectorStore(persist_directory="./my_vectors")
await vector_store.connect()

embedding_client = GoogleEmbeddingClient(api_key="your-key")

# Create repository
repo = PrivateRepository(
    vector_store=vector_store,
    embedding_client=embedding_client
)

# Index a directory of PDFs
indexed = await repo.index_directory("./research_papers")
print(f"Indexed {len(indexed)} documents")

# Search semantically
results = await repo.search("CRISPR gene editing", k=5)
for result in results:
    doc = result['document']
    print(f"{doc['title']} (score: {result['score']:.2f})")
```

### 6. Keyword Search (No Embeddings Needed)

```python
# Repository works without vector store
repo = PrivateRepository()

# Manually add documents (or index PDFs)
from src.literature import RepositoryDocument
from datetime import datetime

repo.documents['doc1'] = RepositoryDocument(
    id='doc1',
    filename='paper.pdf',
    title='Machine Learning in Biology',
    authors=['Smith, J.'],
    abstract='This paper explores ML applications...',
    full_text='Full paper text here...',
    chunk_ids=[],
    indexed_at=datetime.now()
)

# Search by keywords
results = await repo.search("machine learning", k=10)
```

---

## Component Overview

### PDFParser
**Purpose:** Extract text and metadata from scientific PDFs

**Key Methods:**
- `parse(file_path)` - Parse from file path
- `parse_bytes(content, filename)` - Parse from bytes

**Returns:** `ParsedPDF` with:
- `metadata` - Title, authors, DOI, year, abstract, keywords
- `sections` - Document sections with titles and content
- `full_text` - Complete text content
- `references` - List of reference strings
- `page_count` - Number of pages

---

### CitationExtractor
**Purpose:** Extract and parse citations from scientific text

**Key Methods:**
- `extract_from_text(text)` - Extract all citations
- `resolve_citations(citations, references)` - Resolve numeric citations

**Supported Formats:**
- Author-year: `(Smith et al., 2020)`
- Numeric: `[1]`, `[1,2,3]`, `[1-5]`
- Inline: `Smith and Jones (2020)`

**Returns:** `List[ExtractedCitation]` with:
- `raw_text` - Original citation text
- `authors` - Author names
- `year` - Publication year
- `title`, `journal`, `doi`, `pmid` - Parsed metadata
- `context` - Surrounding text

---

### CitationGraph
**Purpose:** Build and analyze citation networks

**Key Methods:**
- `add_paper(id, title, authors, year, doi)` - Add paper node
- `add_citation(citing_id, cited_id)` - Add citation edge
- `get_most_cited(n)` - Get top cited papers
- `get_citations(paper_id)` - Get papers this paper cites
- `get_cited_by(paper_id)` - Get papers citing this paper
- `find_citation_paths(source, target)` - Find citation paths
- `get_co_citation_strength(p1, p2)` - Co-citation analysis
- `get_bibliographic_coupling(p1, p2)` - Coupling analysis
- `get_statistics()` - Graph metrics

**Data:** `CitationNode` and `CitationEdge` objects

---

### TextChunker
**Purpose:** Split text into chunks for embedding/processing

**Key Methods:**
- `chunk_text(text, chunk_size, overlap, respect_sentences)` - Basic chunking
- `chunk_sections(sections, chunk_size, overlap)` - Chunk with metadata
- `merge_small_chunks(chunks, min_size)` - Merge small chunks

**Returns:** `List[TextChunk]` with:
- `text` - Chunk content
- `start_idx`, `end_idx` - Position in original text
- `chunk_index` - Chunk number
- `metadata` - Section info, page numbers, etc.

---

### PrivateRepository
**Purpose:** Index and search private PDF collections

**Key Methods:**
- `index_directory(directory, pattern)` - Index all PDFs in folder
- `add_document(file_path)` - Index single PDF
- `search(query, k)` - Search for documents
- `get_document(doc_id)` - Retrieve document
- `list_documents()` - List all indexed docs
- `get_statistics()` - Repository stats

**Features:**
- Semantic search (when vector store + embeddings configured)
- Keyword search fallback (always available)
- Batch indexing
- Document management
- Statistics tracking

---

## Configuration

### Enable Semantic Search

Add to `.env`:
```bash
# Vector Storage
VECTOR_STORE_TYPE=chroma
CHROMA_PERSIST_DIRECTORY=./chroma_db

# Embeddings
EMBEDDING_PROVIDER=google
GOOGLE_EMBEDDING_MODEL=text-embedding-004
```

Then in code:
```python
from src.storage.vector_factory import create_vector_store, create_embedding_client

vector_store = create_vector_store()
await vector_store.connect()

embedding_client = create_embedding_client()

repo = PrivateRepository(
    vector_store=vector_store,
    embedding_client=embedding_client
)
```

---

## Testing

### Run All Tests
```bash
python 05_tests/test_literature.py
```

### Run Completion Verification
```bash
python 05_tests/test_literature_completion.py
```

### Quick Test
```python
from src.literature import CitationGraph

graph = CitationGraph()
graph.add_paper("p1", "Test", ["Author"], 2024)
assert len(graph.nodes) == 1
print("✅ Working!")
```

---

## Dependencies

Required:
- `pymupdf` - PDF parsing
- `numpy` - Vector operations
- `structlog` - Logging
- `pydantic` - Data validation

Optional (for semantic search):
- `chromadb` - Vector storage
- `google-generativeai` or `openai` - Embeddings

---

## Common Patterns

### Parse PDF → Extract Citations → Build Graph

```python
# Parse PDF
parser = PDFParser()
parsed = await parser.parse("paper.pdf")

# Extract citations
extractor = CitationExtractor()
citations = await extractor.extract_from_text(parsed.full_text)

# Build graph
graph = CitationGraph()
graph.add_paper(
    "current",
    parsed.metadata.title or "Current Paper",
    parsed.metadata.authors,
    parsed.metadata.year
)

for i, cit in enumerate(citations):
    if cit.year:
        cited_id = f"cited_{i}"
        graph.add_paper(cited_id, "", cit.authors, cit.year)
        graph.add_citation("current", cited_id)

print(f"Graph: {len(graph.nodes)} papers, {len(graph.edges)} citations")
```

### Index + Search with Full Pipeline

```python
# Setup
vector_store = ChromaVectorStore()
await vector_store.connect()

embedding_client = GoogleEmbeddingClient(api_key="...")

repo = PrivateRepository(vector_store, embedding_client)

# Index
indexed = await repo.index_directory("./papers")

# Search
results = await repo.search("neural networks", k=5)

# Process results
for result in results:
    doc = result['document']
    score = result['score']
    chunk = result['matching_chunk']

    print(f"\n{doc['title']} ({score:.2f})")
    print(f"Authors: {', '.join(doc['authors'])}")
    print(f"Match: {chunk[:200]}...")
```

---

## Troubleshooting

### PDF Parsing Fails
- Ensure PyMuPDF installed: `pip install pymupdf`
- Check PDF is valid and not corrupted
- Some PDFs have protection - try removing

### Citations Not Extracted
- Verify text contains citation patterns
- Check citation format matches supported formats
- Use `extractor.author_year_pattern` to test regex

### Vector Search Not Working
- Check vector store connected: `await store.connect()`
- Verify embedding client configured
- Check `repo.get_statistics()['has_semantic_search']`

### Chunks Too Large/Small
- Adjust `chunk_size` parameter
- Use `respect_sentences=True` for better boundaries
- Use `merge_small_chunks()` for cleanup

---

## Performance Tips

1. **PDF Parsing:** Parse once, cache results
2. **Citation Extraction:** Batch process multiple documents
3. **Graph Building:** Add all nodes first, then edges
4. **Chunking:** Tune chunk size based on embedding model limits
5. **Vector Search:** Use filters to narrow search space

---

## API Integration (Planned)

Future FastAPI endpoints:

```python
@app.post("/documents/upload")
async def upload_pdf(file: UploadFile):
    """Upload and index a PDF"""
    content = await file.read()
    doc = await repo.add_document_bytes(content, file.filename)
    return {"document_id": doc.id, "title": doc.title}

@app.get("/documents/search")
async def search_documents(query: str, k: int = 5):
    """Search indexed documents"""
    results = await repo.search(query, k=k)
    return {"results": results}
```

---

## More Information

- **Full Documentation:** `PHASE5C_COMPLETION_REPORT.md`
- **Implementation Status:** `PHASE5_IMPLEMENTATION_STATUS.md`
- **Tests:** `05_tests/test_literature.py`
- **Source Code:** `src/literature/`
