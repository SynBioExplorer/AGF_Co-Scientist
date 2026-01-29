"""
Literature Processing Module

Advanced literature processing capabilities for the AI Co-Scientist system.
Includes PDF parsing, citation extraction, citation graph analysis, and
private repository indexing.
"""

from src.literature.pdf_parser import PDFParser, ParsedPDF, PDFSection, PDFMetadata
from src.literature.citation_extractor import CitationExtractor, ExtractedCitation
from src.literature.citation_graph import CitationGraph, CitationNode, CitationEdge
from src.literature.chunker import TextChunker
from src.literature.repository import PrivateRepository, RepositoryDocument

__all__ = [
    "PDFParser",
    "ParsedPDF",
    "PDFSection",
    "PDFMetadata",
    "CitationExtractor",
    "ExtractedCitation",
    "CitationGraph",
    "CitationNode",
    "CitationEdge",
    "TextChunker",
    "PrivateRepository",
    "RepositoryDocument",
]
