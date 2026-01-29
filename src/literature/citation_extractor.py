"""
Citation Extractor

Extracts and resolves citations from scientific text using regex patterns.
Supports multiple citation formats (author-year, numeric, etc.).
"""

import re
from typing import Optional
from pydantic import BaseModel, Field


class ExtractedCitation(BaseModel):
    """A citation extracted from text."""

    raw_text: str = Field(..., description="Original citation text")
    authors: list[str] = Field(default_factory=list, description="Parsed author names")
    year: Optional[int] = Field(None, description="Publication year")
    title: Optional[str] = Field(None, description="Article title")
    journal: Optional[str] = Field(None, description="Journal name")
    doi: Optional[str] = Field(None, description="DOI")
    pmid: Optional[str] = Field(None, description="PubMed ID")
    context: Optional[str] = Field(
        None,
        description="Surrounding text context where citation appears"
    )


class CitationExtractor:
    """Extracts citations from scientific text."""

    def __init__(self):
        """Initialize citation extractor with patterns."""
        # Author-year pattern: (Smith et al., 2020)
        self.author_year_pattern = re.compile(
            r'\(([A-Z][a-z]+(?:\set\sal\.)?),?\s+(\d{4})\)',
            re.MULTILINE
        )

        # Numeric pattern: [1], [2-5]
        self.numeric_pattern = re.compile(
            r'\[(\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)\]'
        )

        # Multi-author inline: Smith and Jones (2020)
        self.multi_author_pattern = re.compile(
            r'([A-Z][a-z]+)\s+(?:and|&)\s+([A-Z][a-z]+)\s+\((\d{4})\)'
        )

        # DOI pattern
        self.doi_pattern = re.compile(r'10\.\d{4,}/[^\s]+')

        # PMID pattern
        self.pmid_pattern = re.compile(r'PMID:\s*(\d+)')

    async def extract_from_text(self, text: str) -> list[ExtractedCitation]:
        """Extract all citations from text.

        Args:
            text: Document text to extract citations from

        Returns:
            List of extracted citations
        """
        citations = []

        # Extract author-year citations
        for match in self.author_year_pattern.finditer(text):
            authors_str = match.group(1)
            year = int(match.group(2))

            # Parse authors
            authors = self._parse_authors(authors_str)

            # Get context
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]

            citations.append(ExtractedCitation(
                raw_text=match.group(0),
                authors=authors,
                year=year,
                context=context
            ))

        # Extract multi-author citations
        for match in self.multi_author_pattern.finditer(text):
            author1 = match.group(1)
            author2 = match.group(2)
            year = int(match.group(3))

            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]

            citations.append(ExtractedCitation(
                raw_text=match.group(0),
                authors=[author1, author2],
                year=year,
                context=context
            ))

        # Extract numeric citations (store for later resolution)
        for match in self.numeric_pattern.finditer(text):
            ref_nums = match.group(1)

            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end]

            citations.append(ExtractedCitation(
                raw_text=match.group(0),
                context=context
            ))

        return citations

    async def resolve_citations(
        self,
        citations: list[ExtractedCitation],
        references: list[str]
    ) -> list[ExtractedCitation]:
        """Resolve numeric citations using reference list.

        Args:
            citations: List of citations to resolve
            references: Reference strings from document

        Returns:
            Citations with resolved metadata
        """
        resolved = []

        for citation in citations:
            # Check if numeric citation
            numeric_match = re.match(r'\[(\d+)\]', citation.raw_text)
            if numeric_match and references:
                ref_num = int(numeric_match.group(1))
                if 1 <= ref_num <= len(references):
                    # Parse reference string
                    ref_str = references[ref_num - 1]
                    parsed = self._parse_reference(ref_str)

                    # Update citation with parsed data
                    citation.authors = parsed.get('authors', [])
                    citation.year = parsed.get('year')
                    citation.title = parsed.get('title')
                    citation.journal = parsed.get('journal')
                    citation.doi = parsed.get('doi')
                    citation.pmid = parsed.get('pmid')

            resolved.append(citation)

        return resolved

    def _parse_authors(self, authors_str: str) -> list[str]:
        """Parse author string into list.

        Args:
            authors_str: String like "Smith et al." or "Smith"

        Returns:
            List of author names
        """
        if 'et al' in authors_str.lower():
            # Extract first author
            first_author = authors_str.split('et al')[0].strip().rstrip(',')
            return [first_author]
        else:
            return [authors_str.strip()]

    def _parse_reference(self, ref_str: str) -> dict:
        """Parse a reference string into components.

        Args:
            ref_str: Reference text

        Returns:
            Dict with parsed components
        """
        result = {}

        # Extract authors (usually at start)
        # Pattern: LastName, F.M., LastName2, F.
        author_pattern = r'^([A-Z][a-z]+(?:,\s*[A-Z]\.?)+(?:,?\s+(?:and|&)\s+[A-Z][a-z]+(?:,\s*[A-Z]\.?)+)*)'
        author_match = re.match(author_pattern, ref_str)
        if author_match:
            authors_str = author_match.group(1)
            # Split by 'and' or '&' or ','
            authors = [
                a.strip()
                for a in re.split(r'(?:,\s*and\s*|,\s*&\s*|,\s+(?=[A-Z]))', authors_str)
                if a.strip() and len(a) > 2
            ]
            result['authors'] = authors[:5]  # Limit to 5

        # Extract year
        year_match = re.search(r'\((\d{4})\)|\b(\d{4})\b', ref_str)
        if year_match:
            year_str = year_match.group(1) or year_match.group(2)
            result['year'] = int(year_str)

        # Extract title (usually in quotes or after authors)
        title_match = re.search(r'["\'](.+?)["\']', ref_str)
        if title_match:
            result['title'] = title_match.group(1)
        else:
            # Try to extract from structure
            # Title often comes after year
            if 'year' in result:
                year_pos = ref_str.find(str(result['year']))
                if year_pos > 0:
                    after_year = ref_str[year_pos + 4:].strip(' .,')
                    # Take up to first period or 100 chars
                    title_end = after_year.find('.')
                    if title_end > 0:
                        result['title'] = after_year[:title_end].strip()
                    else:
                        result['title'] = after_year[:100].strip()

        # Extract journal (often in italics or after title)
        # Common pattern: journal name, volume(issue), pages
        journal_pattern = r'(?:["\'].*?["\']\.?\s+)?([A-Z][A-Za-z\s&]+(?:Journal|Review|Science|Nature|Cell)?),?\s+\d+'
        journal_match = re.search(journal_pattern, ref_str)
        if journal_match:
            result['journal'] = journal_match.group(1).strip()

        # Extract DOI
        doi_match = self.doi_pattern.search(ref_str)
        if doi_match:
            result['doi'] = doi_match.group(0)

        # Extract PMID
        pmid_match = self.pmid_pattern.search(ref_str)
        if pmid_match:
            result['pmid'] = pmid_match.group(1)

        return result
