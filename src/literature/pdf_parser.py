"""
PDF Parser

Extracts text, metadata, and references from scientific PDFs using PyMuPDF.
Handles section detection, metadata extraction, and reference parsing.
"""

import re
from typing import Optional
from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel, Field


class PDFSection(BaseModel):
    """A section within a PDF document."""

    title: str = Field(..., description="Section title/heading")
    content: str = Field(..., description="Section text content")
    page_numbers: list[int] = Field(
        default_factory=list,
        description="Pages this section spans"
    )


class PDFMetadata(BaseModel):
    """Metadata extracted from a PDF."""

    title: Optional[str] = Field(None, description="Document title")
    authors: list[str] = Field(default_factory=list, description="Author names")
    abstract: Optional[str] = Field(None, description="Abstract/summary")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    year: Optional[int] = Field(None, description="Publication year")
    journal: Optional[str] = Field(None, description="Journal/venue name")
    keywords: list[str] = Field(default_factory=list, description="Keywords/tags")


class ParsedPDF(BaseModel):
    """Complete parsed PDF document."""

    filename: str = Field(..., description="Original filename")
    metadata: PDFMetadata = Field(..., description="Extracted metadata")
    sections: list[PDFSection] = Field(
        default_factory=list,
        description="Document sections"
    )
    full_text: str = Field(..., description="Complete document text")
    references: list[str] = Field(
        default_factory=list,
        description="Reference strings"
    )
    page_count: int = Field(..., description="Number of pages")


class PDFParser:
    """Parser for scientific PDF documents."""

    def __init__(self):
        """Initialize PDF parser."""
        # Common section headings in scientific papers
        self.section_patterns = [
            r'^abstract$',
            r'^introduction$',
            r'^background$',
            r'^methods?$',
            r'^methodology$',
            r'^results?$',
            r'^discussion$',
            r'^conclusion$',
            r'^references?$',
            r'^bibliography$',
            r'^acknowledgements?$',
            r'^appendix',
        ]
        self.section_regex = re.compile(
            '|'.join(self.section_patterns),
            re.IGNORECASE
        )

    async def parse(self, file_path: str) -> ParsedPDF:
        """Parse a PDF file from disk.

        Args:
            file_path: Path to PDF file

        Returns:
            ParsedPDF with extracted content
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        with open(file_path, 'rb') as f:
            content = f.read()

        return await self.parse_bytes(content, path.name)

    async def parse_bytes(self, content: bytes, filename: str) -> ParsedPDF:
        """Parse a PDF from bytes.

        Args:
            content: PDF file bytes
            filename: Original filename

        Returns:
            ParsedPDF with extracted content
        """
        # Open PDF from bytes
        doc = fitz.open(stream=content, filetype="pdf")

        try:
            # Extract full text
            full_text = self._extract_text(doc)

            # Extract metadata
            metadata = self._extract_metadata(doc, full_text)

            # Extract sections
            sections = self._extract_sections(doc, full_text)

            # Extract references
            references = self._extract_references(full_text)

            return ParsedPDF(
                filename=filename,
                metadata=metadata,
                sections=sections,
                full_text=full_text,
                references=references,
                page_count=len(doc)
            )

        finally:
            doc.close()

    def _extract_text(self, doc: fitz.Document) -> str:
        """Extract all text from document."""
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        return "\n\n".join(text_parts)

    def _extract_metadata(self, doc: fitz.Document, full_text: str) -> PDFMetadata:
        """Extract metadata from PDF."""
        # Get PDF metadata dict
        pdf_meta = doc.metadata or {}

        # Extract title
        title = pdf_meta.get('title')
        if not title or len(title) < 10:
            # Try to extract from first page
            title = self._extract_title_from_text(full_text)

        # Extract authors
        authors = []
        author_str = pdf_meta.get('author', '')
        if author_str:
            # Split by common separators
            authors = [
                a.strip()
                for a in re.split(r'[,;]|\sand\s', author_str)
                if a.strip()
            ]

        # Extract DOI
        doi = self._extract_doi(full_text)

        # Extract year
        year = self._extract_year(full_text)

        # Extract abstract
        abstract = self._extract_abstract(full_text)

        # Extract keywords
        keywords = self._extract_keywords(full_text)

        # Extract journal
        journal = self._extract_journal(full_text)

        return PDFMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            year=year,
            journal=journal,
            keywords=keywords
        )

    def _extract_title_from_text(self, text: str) -> Optional[str]:
        """Extract title from first page text."""
        # Take first meaningful line (longer than 20 chars)
        lines = text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if len(line) > 20 and not line.isupper():
                return line
        return None

    def _extract_doi(self, text: str) -> Optional[str]:
        """Extract DOI from text."""
        # DOI pattern: 10.xxxx/xxxxx
        doi_pattern = r'10\.\d{4,}/[^\s]+'
        match = re.search(doi_pattern, text)
        return match.group(0) if match else None

    def _extract_year(self, text: str) -> Optional[int]:
        """Extract publication year."""
        # Look for 4-digit year between 1900-2100
        year_pattern = r'\b(19|20)\d{2}\b'
        matches = re.findall(year_pattern, text[:2000])  # Check first ~2 pages
        if matches:
            # Return most recent year found
            years = [int(y) for y in matches]
            return max(years)
        return None

    def _extract_abstract(self, text: str) -> Optional[str]:
        """Extract abstract section."""
        # Find abstract section
        abstract_pattern = r'(?i)abstract\s*\n\s*(.+?)(?=\n\s*(?:introduction|keywords|1\.|$))'
        match = re.search(abstract_pattern, text[:3000], re.DOTALL)
        if match:
            abstract = match.group(1).strip()
            # Clean up
            abstract = re.sub(r'\s+', ' ', abstract)
            return abstract[:1000]  # Limit length
        return None

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords."""
        # Find keywords section
        keywords_pattern = r'(?i)keywords?\s*:?\s*(.+?)(?=\n\s*(?:introduction|1\.|abstract|$))'
        match = re.search(keywords_pattern, text[:3000], re.DOTALL)
        if match:
            keywords_str = match.group(1).strip()
            # Split by common separators
            keywords = [
                k.strip()
                for k in re.split(r'[,;·•]', keywords_str)
                if k.strip()
            ]
            return keywords[:10]  # Limit to 10
        return []

    def _extract_journal(self, text: str) -> Optional[str]:
        """Extract journal name."""
        # Look for common journal indicators
        journal_patterns = [
            r'(?i)published in\s+(.+?)(?=\n|,|\.|$)',
            r'(?i)journal of\s+(.+?)(?=\n|,|\.|volume)',
        ]
        for pattern in journal_patterns:
            match = re.search(pattern, text[:2000])
            if match:
                journal = match.group(1).strip()
                return journal[:100]  # Limit length
        return None

    def _extract_sections(self, doc: fitz.Document, full_text: str) -> list[PDFSection]:
        """Extract document sections."""
        sections = []
        lines = full_text.split('\n')

        current_section = None
        current_content = []
        current_pages = set()

        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            page_lines = page_text.split('\n')

            for line in page_lines:
                line_stripped = line.strip()

                # Check if this is a section heading
                if self.section_regex.match(line_stripped):
                    # Save previous section
                    if current_section:
                        sections.append(PDFSection(
                            title=current_section,
                            content='\n'.join(current_content).strip(),
                            page_numbers=sorted(list(current_pages))
                        ))

                    # Start new section
                    current_section = line_stripped
                    current_content = []
                    current_pages = {page_num + 1}

                elif current_section:
                    # Add to current section
                    current_content.append(line)
                    current_pages.add(page_num + 1)

        # Save last section
        if current_section and current_content:
            sections.append(PDFSection(
                title=current_section,
                content='\n'.join(current_content).strip(),
                page_numbers=sorted(list(current_pages))
            ))

        return sections

    def _extract_references(self, text: str) -> list[str]:
        """Extract reference list."""
        references = []

        # Find references section
        ref_pattern = r'(?i)references?\s*\n\s*(.+?)(?=\nappendix|\Z)'
        match = re.search(ref_pattern, text, re.DOTALL)

        if match:
            ref_text = match.group(1)

            # Split into individual references
            # Pattern: [1], (1), 1., or start with author name
            ref_lines = re.split(r'\n\s*(?:\[\d+\]|\(\d+\)|\d+\.)', ref_text)

            for ref in ref_lines:
                ref = ref.strip()
                if len(ref) > 20:  # Minimum reference length
                    references.append(ref[:500])  # Limit length

        return references[:100]  # Limit to 100 references
