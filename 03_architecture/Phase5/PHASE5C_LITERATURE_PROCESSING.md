# Phase 5C: Advanced Literature Processing

## Overview

Implement advanced literature processing capabilities including PDF parsing, citation graph extraction, and private repository indexing to improve hypothesis grounding.

**Branch:** `phase5/literature`
**Worktree:** `worktree-5c-literature`
**Dependencies:** Phase 5A (Vector Storage) for embeddings
**Estimated Duration:** 1 week

## Motivation

From the Google paper (Section 3.5):
> "The co-scientist can also index and search a private repository of publications specified by the scientist."

Scientists often have private collections of papers, preprints, and internal documents that should inform hypothesis generation. This phase enables:
- Upload and process PDF papers
- Extract citations and build reference graphs
- Index private document repositories
- Semantic search across literature

## Deliverables

### Files to Create

```
src/
├── literature/
│   ├── __init__.py
│   ├── pdf_parser.py          # PDF text extraction
│   ├── citation_extractor.py  # Citation parsing
│   ├── citation_graph.py      # Build citation networks
│   ├── repository.py          # Private repo indexing
│   └── chunker.py             # Text chunking for embeddings

tests/
└── test_literature.py         # Literature processing tests
```

### 1. PDF Parser (`src/literature/pdf_parser.py`)

```python
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
import io

class PDFSection(BaseModel):
    """Extracted section from PDF."""
    title: str
    content: str
    page_numbers: List[int]

class PDFMetadata(BaseModel):
    """Extracted PDF metadata."""
    title: Optional[str]
    authors: List[str]
    abstract: Optional[str]
    doi: Optional[str]
    year: Optional[int]
    journal: Optional[str]
    keywords: List[str]

class ParsedPDF(BaseModel):
    """Complete parsed PDF document."""
    filename: str
    metadata: PDFMetadata
    sections: List[PDFSection]
    full_text: str
    references: List[str]
    page_count: int

class PDFParser:
    """Parse scientific PDFs and extract structured content."""

    def __init__(self):
        self._check_dependencies()

    def _check_dependencies(self):
        """Check required libraries are installed."""
        try:
            import pymupdf  # PyMuPDF
        except ImportError:
            raise ImportError("Install PyMuPDF: pip install pymupdf")

    async def parse(self, file_path: str | Path) -> ParsedPDF:
        """Parse PDF file and extract content."""
        import pymupdf

        doc = pymupdf.open(str(file_path))

        # Extract full text
        full_text = ""
        for page in doc:
            full_text += page.get_text()

        # Extract metadata
        metadata = self._extract_metadata(doc, full_text)

        # Extract sections
        sections = self._extract_sections(doc)

        # Extract references
        references = self._extract_references(full_text)

        return ParsedPDF(
            filename=Path(file_path).name,
            metadata=metadata,
            sections=sections,
            full_text=full_text,
            references=references,
            page_count=len(doc)
        )

    async def parse_bytes(self, content: bytes, filename: str) -> ParsedPDF:
        """Parse PDF from bytes (for file uploads)."""
        import pymupdf

        doc = pymupdf.open(stream=content, filetype="pdf")

        full_text = ""
        for page in doc:
            full_text += page.get_text()

        metadata = self._extract_metadata(doc, full_text)
        sections = self._extract_sections(doc)
        references = self._extract_references(full_text)

        return ParsedPDF(
            filename=filename,
            metadata=metadata,
            sections=sections,
            full_text=full_text,
            references=references,
            page_count=len(doc)
        )

    def _extract_metadata(self, doc, full_text: str) -> PDFMetadata:
        """Extract metadata from PDF."""
        import re

        # Get PDF metadata
        pdf_meta = doc.metadata

        # Extract title (from metadata or first lines)
        title = pdf_meta.get("title") or self._extract_title_from_text(full_text)

        # Extract authors
        authors = self._extract_authors(pdf_meta.get("author", ""), full_text)

        # Extract abstract
        abstract = self._extract_abstract(full_text)

        # Extract DOI
        doi_match = re.search(r'10\.\d{4,}/[^\s]+', full_text)
        doi = doi_match.group(0) if doi_match else None

        # Extract year
        year = None
        if pdf_meta.get("creationDate"):
            year_match = re.search(r'20\d{2}|19\d{2}', pdf_meta["creationDate"])
            if year_match:
                year = int(year_match.group(0))

        # Extract keywords
        keywords = self._extract_keywords(full_text)

        return PDFMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            year=year,
            journal=None,  # Hard to extract reliably
            keywords=keywords
        )

    def _extract_title_from_text(self, text: str) -> Optional[str]:
        """Extract title from beginning of text."""
        lines = text.strip().split('\n')
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 20 and len(line) < 200:
                return line
        return None

    def _extract_authors(self, meta_author: str, text: str) -> List[str]:
        """Extract author names."""
        if meta_author:
            # Split by common separators
            return [a.strip() for a in meta_author.replace(';', ',').split(',') if a.strip()]
        return []

    def _extract_abstract(self, text: str) -> Optional[str]:
        """Extract abstract section."""
        import re

        # Look for Abstract section
        abstract_match = re.search(
            r'Abstract[:\s]*\n(.+?)(?=\n\s*(?:Introduction|Keywords|1\.|Background))',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if abstract_match:
            return abstract_match.group(1).strip()[:2000]  # Limit length
        return None

    def _extract_sections(self, doc) -> List[PDFSection]:
        """Extract document sections."""
        sections = []
        current_section = None
        current_content = []
        current_pages = []

        for page_num, page in enumerate(doc):
            text = page.get_text()
            lines = text.split('\n')

            for line in lines:
                # Detect section headers (simplified heuristic)
                if self._is_section_header(line):
                    if current_section:
                        sections.append(PDFSection(
                            title=current_section,
                            content='\n'.join(current_content),
                            page_numbers=current_pages
                        ))
                    current_section = line.strip()
                    current_content = []
                    current_pages = [page_num + 1]
                else:
                    current_content.append(line)
                    if page_num + 1 not in current_pages:
                        current_pages.append(page_num + 1)

        # Add final section
        if current_section:
            sections.append(PDFSection(
                title=current_section,
                content='\n'.join(current_content),
                page_numbers=current_pages
            ))

        return sections

    def _is_section_header(self, line: str) -> bool:
        """Detect if line is a section header."""
        import re

        line = line.strip()
        if not line or len(line) > 100:
            return False

        # Common section patterns
        patterns = [
            r'^\d+\.?\s+[A-Z]',           # "1. Introduction" or "1 Introduction"
            r'^(Abstract|Introduction|Methods|Results|Discussion|Conclusion|References)',
            r'^[A-Z][A-Za-z\s]+$',         # All caps or title case short line
        ]

        return any(re.match(p, line) for p in patterns)

    def _extract_references(self, text: str) -> List[str]:
        """Extract reference list."""
        import re

        # Find references section
        ref_match = re.search(
            r'References\s*\n(.+?)(?:\n\s*(?:Appendix|Supplementary)|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not ref_match:
            return []

        ref_text = ref_match.group(1)

        # Split by reference numbers or bullet points
        refs = re.split(r'\n\s*\[?\d+\]?\s*\.?\s*', ref_text)
        return [r.strip() for r in refs if r.strip() and len(r) > 20]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords if present."""
        import re

        kw_match = re.search(
            r'Keywords?[:\s]*([^\n]+)',
            text,
            re.IGNORECASE
        )

        if kw_match:
            keywords_text = kw_match.group(1)
            return [k.strip() for k in keywords_text.split(',') if k.strip()]
        return []
```

### 2. Citation Extractor (`src/literature/citation_extractor.py`)

```python
from typing import List, Optional, Tuple
from pydantic import BaseModel
import re

class ExtractedCitation(BaseModel):
    """Extracted citation from text."""
    raw_text: str
    authors: List[str]
    year: Optional[int]
    title: Optional[str]
    journal: Optional[str]
    doi: Optional[str]
    pmid: Optional[str]
    context: str  # Surrounding text where citation appeared

class CitationExtractor:
    """Extract and parse citations from scientific text."""

    # Common citation patterns
    PATTERNS = {
        # (Author et al., 2020)
        "author_year": r'\(([A-Z][a-z]+(?:\s+et\s+al\.)?),?\s*(\d{4})\)',
        # [1], [1,2,3], [1-3]
        "numeric": r'\[(\d+(?:[,\-]\d+)*)\]',
        # (Smith 2020; Jones 2021)
        "multi_author": r'\(([A-Z][a-z]+\s+\d{4}(?:;\s*[A-Z][a-z]+\s+\d{4})*)\)',
    }

    async def extract_from_text(self, text: str) -> List[ExtractedCitation]:
        """Extract all citations from text."""
        citations = []

        for pattern_name, pattern in self.PATTERNS.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                context = self._get_context(text, match.start(), match.end())
                citation = self._parse_citation(match.group(0), pattern_name, context)
                if citation:
                    citations.append(citation)

        return citations

    def _get_context(self, text: str, start: int, end: int, window: int = 200) -> str:
        """Get surrounding context for citation."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def _parse_citation(
        self,
        raw: str,
        pattern_type: str,
        context: str
    ) -> Optional[ExtractedCitation]:
        """Parse citation based on pattern type."""

        if pattern_type == "author_year":
            match = re.match(r'\(([^,]+),?\s*(\d{4})\)', raw)
            if match:
                return ExtractedCitation(
                    raw_text=raw,
                    authors=[match.group(1).strip()],
                    year=int(match.group(2)),
                    title=None,
                    journal=None,
                    doi=None,
                    pmid=None,
                    context=context
                )

        elif pattern_type == "numeric":
            # Numeric citations need reference list lookup
            return ExtractedCitation(
                raw_text=raw,
                authors=[],
                year=None,
                title=None,
                journal=None,
                doi=None,
                pmid=None,
                context=context
            )

        return None

    async def resolve_citations(
        self,
        citations: List[ExtractedCitation],
        references: List[str]
    ) -> List[ExtractedCitation]:
        """Resolve numeric citations using reference list."""
        resolved = []

        for citation in citations:
            if citation.raw_text.startswith('['):
                # Extract reference numbers
                nums = re.findall(r'\d+', citation.raw_text)
                for num in nums:
                    idx = int(num) - 1
                    if 0 <= idx < len(references):
                        ref_text = references[idx]
                        # Parse reference text
                        parsed = self._parse_reference_text(ref_text)
                        resolved.append(ExtractedCitation(
                            raw_text=ref_text,
                            authors=parsed.get("authors", []),
                            year=parsed.get("year"),
                            title=parsed.get("title"),
                            journal=parsed.get("journal"),
                            doi=parsed.get("doi"),
                            pmid=parsed.get("pmid"),
                            context=citation.context
                        ))
            else:
                resolved.append(citation)

        return resolved

    def _parse_reference_text(self, text: str) -> dict:
        """Parse a reference string into components."""
        result = {}

        # Extract DOI
        doi_match = re.search(r'10\.\d{4,}/[^\s]+', text)
        if doi_match:
            result["doi"] = doi_match.group(0)

        # Extract PMID
        pmid_match = re.search(r'PMID:\s*(\d+)', text)
        if pmid_match:
            result["pmid"] = pmid_match.group(1)

        # Extract year
        year_match = re.search(r'\((\d{4})\)|,\s*(\d{4})', text)
        if year_match:
            result["year"] = int(year_match.group(1) or year_match.group(2))

        # Authors (simplified - first part before year/title)
        author_match = re.match(r'^([^(]+?)(?:\(|\d{4})', text)
        if author_match:
            authors_text = author_match.group(1)
            result["authors"] = [a.strip() for a in authors_text.split(',') if a.strip()][:5]

        return result
```

### 3. Citation Graph (`src/literature/citation_graph.py`)

```python
from typing import Dict, List, Set, Optional, Tuple
from pydantic import BaseModel
from collections import defaultdict

class CitationNode(BaseModel):
    """Node in citation graph."""
    id: str
    title: str
    authors: List[str]
    year: Optional[int]
    doi: Optional[str]
    citation_count: int = 0
    reference_count: int = 0

class CitationEdge(BaseModel):
    """Edge in citation graph (citing -> cited)."""
    source_id: str  # Citing paper
    target_id: str  # Cited paper

class CitationGraph:
    """Build and analyze citation networks."""

    def __init__(self):
        self.nodes: Dict[str, CitationNode] = {}
        self.edges: List[CitationEdge] = []
        self._citations: Dict[str, Set[str]] = defaultdict(set)  # paper -> papers it cites
        self._cited_by: Dict[str, Set[str]] = defaultdict(set)   # paper -> papers citing it

    def add_paper(
        self,
        paper_id: str,
        title: str,
        authors: List[str],
        year: Optional[int] = None,
        doi: Optional[str] = None
    ) -> None:
        """Add paper to graph."""
        if paper_id not in self.nodes:
            self.nodes[paper_id] = CitationNode(
                id=paper_id,
                title=title,
                authors=authors,
                year=year,
                doi=doi
            )

    def add_citation(self, citing_id: str, cited_id: str) -> None:
        """Add citation edge."""
        if citing_id in self.nodes and cited_id in self.nodes:
            if cited_id not in self._citations[citing_id]:
                self._citations[citing_id].add(cited_id)
                self._cited_by[cited_id].add(citing_id)

                self.edges.append(CitationEdge(
                    source_id=citing_id,
                    target_id=cited_id
                ))

                # Update counts
                self.nodes[citing_id].reference_count += 1
                self.nodes[cited_id].citation_count += 1

    def get_citations(self, paper_id: str) -> List[CitationNode]:
        """Get papers cited by this paper."""
        return [self.nodes[pid] for pid in self._citations.get(paper_id, [])]

    def get_cited_by(self, paper_id: str) -> List[CitationNode]:
        """Get papers that cite this paper."""
        return [self.nodes[pid] for pid in self._cited_by.get(paper_id, [])]

    def get_most_cited(self, n: int = 10) -> List[CitationNode]:
        """Get most cited papers."""
        sorted_nodes = sorted(
            self.nodes.values(),
            key=lambda x: x.citation_count,
            reverse=True
        )
        return sorted_nodes[:n]

    def get_common_citations(
        self,
        paper_ids: List[str]
    ) -> List[Tuple[CitationNode, int]]:
        """Find papers commonly cited by multiple papers."""
        citation_counts: Dict[str, int] = defaultdict(int)

        for pid in paper_ids:
            for cited_id in self._citations.get(pid, []):
                citation_counts[cited_id] += 1

        # Sort by count
        common = sorted(
            [(self.nodes[k], v) for k, v in citation_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )

        return common

    def find_citation_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3
    ) -> List[List[str]]:
        """Find citation paths between two papers."""
        if source_id not in self.nodes or target_id not in self.nodes:
            return []

        paths = []
        self._dfs_paths(source_id, target_id, [source_id], paths, max_depth)
        return paths

    def _dfs_paths(
        self,
        current: str,
        target: str,
        path: List[str],
        paths: List[List[str]],
        max_depth: int
    ) -> None:
        """DFS to find all paths."""
        if len(path) > max_depth:
            return

        if current == target:
            paths.append(path.copy())
            return

        for cited_id in self._citations.get(current, []):
            if cited_id not in path:
                path.append(cited_id)
                self._dfs_paths(cited_id, target, path, paths, max_depth)
                path.pop()

    def to_dict(self) -> dict:
        """Export graph to dictionary."""
        return {
            "nodes": [n.dict() for n in self.nodes.values()],
            "edges": [e.dict() for e in self.edges]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CitationGraph":
        """Import graph from dictionary."""
        graph = cls()
        for node_data in data.get("nodes", []):
            node = CitationNode(**node_data)
            graph.nodes[node.id] = node

        for edge_data in data.get("edges", []):
            edge = CitationEdge(**edge_data)
            graph._citations[edge.source_id].add(edge.target_id)
            graph._cited_by[edge.target_id].add(edge.source_id)
            graph.edges.append(edge)

        return graph
```

### 4. Private Repository (`src/literature/repository.py`)

```python
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel
import asyncio

from .pdf_parser import PDFParser, ParsedPDF
from .chunker import TextChunker
from ..storage.vector import BaseVectorStore, VectorDocument
from ..embeddings.base import BaseEmbeddingClient

class RepositoryDocument(BaseModel):
    """Document in private repository."""
    id: str
    filename: str
    title: Optional[str]
    authors: List[str]
    abstract: Optional[str]
    full_text: str
    chunk_ids: List[str]
    metadata: dict = {}

class PrivateRepository:
    """Index and search private document repository."""

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_client: BaseEmbeddingClient,
        storage_path: Optional[Path] = None
    ):
        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.storage_path = storage_path or Path("./private_repo")
        self.pdf_parser = PDFParser()
        self.chunker = TextChunker()
        self.documents: dict[str, RepositoryDocument] = {}

    async def index_directory(self, directory: Path) -> int:
        """Index all PDFs in directory."""
        pdf_files = list(directory.glob("**/*.pdf"))
        indexed = 0

        for pdf_path in pdf_files:
            try:
                await self.add_document(pdf_path)
                indexed += 1
            except Exception as e:
                print(f"Failed to index {pdf_path}: {e}")

        return indexed

    async def add_document(self, file_path: Path) -> RepositoryDocument:
        """Add single document to repository."""
        # Parse PDF
        parsed = await self.pdf_parser.parse(file_path)

        # Generate document ID
        doc_id = f"doc_{hash(file_path.name) % 10**8}"

        # Chunk text for embedding
        chunks = self.chunker.chunk_text(
            parsed.full_text,
            chunk_size=500,
            overlap=50
        )

        # Generate embeddings and store chunks
        chunk_ids = []
        vector_docs = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            embedding = await self.embedding_client.embed(chunk)

            vector_docs.append(VectorDocument(
                id=chunk_id,
                content=chunk,
                embedding=embedding,
                metadata={
                    "document_id": doc_id,
                    "filename": parsed.filename,
                    "chunk_index": i,
                    "title": parsed.metadata.title
                }
            ))
            chunk_ids.append(chunk_id)

        await self.vector_store.add_documents(vector_docs)

        # Create repository document
        repo_doc = RepositoryDocument(
            id=doc_id,
            filename=parsed.filename,
            title=parsed.metadata.title,
            authors=parsed.metadata.authors,
            abstract=parsed.metadata.abstract,
            full_text=parsed.full_text,
            chunk_ids=chunk_ids,
            metadata={
                "doi": parsed.metadata.doi,
                "year": parsed.metadata.year,
                "page_count": parsed.page_count
            }
        )

        self.documents[doc_id] = repo_doc
        return repo_doc

    async def search(
        self,
        query: str,
        k: int = 5,
        return_chunks: bool = False
    ) -> List[dict]:
        """Search repository for relevant content."""
        # Embed query
        query_embedding = await self.embedding_client.embed(query)

        # Search vector store
        results = await self.vector_store.search(query_embedding, k=k * 2)

        if return_chunks:
            return [
                {
                    "chunk": doc.content,
                    "score": score,
                    "document_id": doc.metadata.get("document_id"),
                    "filename": doc.metadata.get("filename")
                }
                for doc, score in results[:k]
            ]

        # Deduplicate by document
        seen_docs = set()
        doc_results = []

        for doc, score in results:
            doc_id = doc.metadata.get("document_id")
            if doc_id and doc_id not in seen_docs:
                seen_docs.add(doc_id)
                repo_doc = self.documents.get(doc_id)
                if repo_doc:
                    doc_results.append({
                        "document": repo_doc.dict(),
                        "score": score,
                        "matching_chunk": doc.content
                    })

                if len(doc_results) >= k:
                    break

        return doc_results

    async def get_document(self, doc_id: str) -> Optional[RepositoryDocument]:
        """Get document by ID."""
        return self.documents.get(doc_id)

    def list_documents(self) -> List[RepositoryDocument]:
        """List all indexed documents."""
        return list(self.documents.values())
```

### 5. Text Chunker (`src/literature/chunker.py`)

```python
from typing import List
import re

class TextChunker:
    """Split text into chunks for embedding."""

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
        respect_sentences: bool = True
    ) -> List[str]:
        """Split text into overlapping chunks."""

        if respect_sentences:
            return self._chunk_by_sentences(text, chunk_size, overlap)
        else:
            return self._chunk_by_chars(text, chunk_size, overlap)

    def _chunk_by_chars(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Simple character-based chunking."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk.strip())
            start = end - overlap

        return [c for c in chunks if c]

    def _chunk_by_sentences(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Chunk respecting sentence boundaries."""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence)

            if current_size + sentence_size > chunk_size and current_chunk:
                # Save current chunk
                chunks.append(' '.join(current_chunk))

                # Keep last sentences for overlap
                overlap_size = 0
                overlap_sentences = []
                for s in reversed(current_chunk):
                    if overlap_size + len(s) <= overlap:
                        overlap_sentences.insert(0, s)
                        overlap_size += len(s)
                    else:
                        break

                current_chunk = overlap_sentences
                current_size = overlap_size

            current_chunk.append(sentence)
            current_size += sentence_size

        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return [c.strip() for c in chunks if c.strip()]

    def chunk_sections(
        self,
        sections: List[dict],
        chunk_size: int = 500
    ) -> List[dict]:
        """Chunk document sections, preserving section metadata."""
        chunked = []

        for section in sections:
            section_chunks = self.chunk_text(
                section.get("content", ""),
                chunk_size=chunk_size
            )

            for i, chunk in enumerate(section_chunks):
                chunked.append({
                    "section_title": section.get("title", ""),
                    "chunk_index": i,
                    "content": chunk,
                    "page_numbers": section.get("page_numbers", [])
                })

        return chunked
```

## API Endpoints

Add to FastAPI (`src/api/main.py`):

```python
from fastapi import UploadFile, File
from src.literature.repository import PrivateRepository

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a PDF document."""
    content = await file.read()
    doc = await repository.add_document_bytes(content, file.filename)
    return {"document_id": doc.id, "title": doc.title}

@app.get("/documents/search")
async def search_documents(query: str, k: int = 5):
    """Search private repository."""
    results = await repository.search(query, k=k)
    return {"results": results}

@app.get("/documents")
async def list_documents():
    """List all indexed documents."""
    docs = repository.list_documents()
    return {"documents": [d.dict() for d in docs]}
```

## Test Cases (`tests/test_literature.py`)

```python
import pytest
from pathlib import Path
from src.literature.pdf_parser import PDFParser
from src.literature.citation_extractor import CitationExtractor
from src.literature.citation_graph import CitationGraph

@pytest.mark.asyncio
async def test_pdf_parsing():
    """Test PDF parsing."""
    parser = PDFParser()
    # Use a test PDF
    result = await parser.parse(Path("tests/fixtures/sample_paper.pdf"))

    assert result.metadata.title is not None
    assert result.page_count > 0
    assert len(result.full_text) > 100

@pytest.mark.asyncio
async def test_citation_extraction():
    """Test citation extraction."""
    extractor = CitationExtractor()

    text = """
    Previous studies (Smith et al., 2020) have shown promising results.
    This aligns with earlier findings [1,2,3] in the field.
    """

    citations = await extractor.extract_from_text(text)
    assert len(citations) >= 2

def test_citation_graph():
    """Test citation graph building."""
    graph = CitationGraph()

    # Add papers
    graph.add_paper("paper1", "Study A", ["Author A"], 2020)
    graph.add_paper("paper2", "Study B", ["Author B"], 2021)
    graph.add_paper("paper3", "Study C", ["Author C"], 2022)

    # Add citations
    graph.add_citation("paper2", "paper1")  # B cites A
    graph.add_citation("paper3", "paper1")  # C cites A
    graph.add_citation("paper3", "paper2")  # C cites B

    # Verify
    assert graph.nodes["paper1"].citation_count == 2
    assert len(graph.get_cited_by("paper1")) == 2

    most_cited = graph.get_most_cited(1)
    assert most_cited[0].id == "paper1"
```

## Success Criteria

- [ ] PDF parsing extracts text, metadata, and references
- [ ] Citation extraction identifies different citation formats
- [ ] Citation graph builds and analyzes reference networks
- [ ] Private repository indexes PDFs with vector embeddings
- [ ] Semantic search returns relevant document chunks
- [ ] API endpoints for upload and search working
- [ ] All tests passing

## Dependencies

```bash
pip install pymupdf  # PDF parsing
pip install aiofiles # Async file operations
```
