"""
Limitations Extractor - Phase 6 Feature

Extract limitations, caveats, and negative results from scientific papers.
Addresses publication bias by surfacing what didn't work.

Where Negative Results Hide:
    - "Limitations" section - What didn't work, what's uncertain
    - "Discussion" section - Caveats and alternative explanations
    - "Future Work" section - What needs fixing before progress
    - "Conclusion" section - Boundaries of current knowledge

Reference: 03_architecture/Phase6/phase6_limitations_extraction.md
"""

import re
from typing import Dict, List, Any, Optional, TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from src.literature.citation_graph import CitationNode

logger = structlog.get_logger()


# Section headers indicating limitations/caveats
LIMITATION_HEADERS = [
    r"\bLimitations?\b",
    r"\bCaveats?\b",
    r"\bFuture\s+Work\b",
    r"\bFuture\s+Directions?\b",
    r"\bFuture\s+Research\b",
    r"\bOpen\s+Questions?\b",
    r"\bUnresolved\b",
    r"\bDiscussion\b",
    r"\bConclusions?\b",
    r"\bWeaknesses?\b",
    r"\bChallenges?\b"
]

# Phrases indicating negative/null findings
NEGATIVE_PHRASES = [
    "did not",
    "no significant",
    "no effect",
    "unable to",
    "failed to",
    "could not",
    "limitation",
    "caveat",
    "however",
    "although",
    "remains unclear",
    "future work",
    "further research needed",
    "requires additional",
    "not possible",
    "insufficient",
    "beyond the scope",
    "was not",
    "were not",
    "cannot",
    "should be interpreted with caution",
    "may not generalize",
    "small sample size",
    "potential bias"
]


class LimitationsExtractor:
    """
    Extract limitations, caveats, and negative results from papers.

    Parses paper full text to find limitation sections and extracts
    sentences containing negative/limitation phrases.
    """

    def __init__(self, min_confidence: float = 0.5):
        """
        Initialize the limitations extractor.

        Args:
            min_confidence: Minimum confidence threshold for including limitations
        """
        self.min_confidence = min_confidence
        self.limitation_headers = [re.compile(h, re.IGNORECASE) for h in LIMITATION_HEADERS]

    def parse_sections(self, full_text: str) -> Dict[str, str]:
        """
        Parse paper into sections by header.

        Args:
            full_text: Full text of the paper

        Returns:
            Dictionary mapping section headers to section text
        """
        if not full_text:
            return {}

        # Pattern to match section headers
        # Matches: "## Limitations", "4. Discussion", "LIMITATIONS", etc.
        section_pattern = r'\n\s*(?:#+\s*|\d+\.?\s*)?([A-Z][A-Za-z\s]+?)(?:\n|:)'

        matches = list(re.finditer(section_pattern, full_text))

        if not matches:
            # Try alternative pattern for markdown-style headers
            alt_pattern = r'^#{1,3}\s*(.+?)$'
            matches = list(re.finditer(alt_pattern, full_text, re.MULTILINE))

        sections = {}

        for i, match in enumerate(matches):
            header = match.group(1).strip()
            start = match.end()

            # End is either next section or end of text
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(full_text)

            text = full_text[start:end].strip()
            if text:
                sections[header] = text

        return sections

    def _is_limitation_section(self, header: str) -> bool:
        """
        Check if a section header indicates limitations content.

        Args:
            header: Section header text

        Returns:
            True if header matches a limitation pattern
        """
        for pattern in self.limitation_headers:
            if pattern.search(header):
                return True
        return False

    def _extract_limitation_sentences(self, text: str) -> List[str]:
        """
        Extract sentences containing negative/limitation phrases.

        Args:
            text: Section text to analyze

        Returns:
            List of sentences containing limitation indicators
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)

        limitations = []
        for sentence in sentences:
            sentence = sentence.strip()

            # Skip very short fragments
            if len(sentence) < 20:
                continue

            # Check for negative/limitation phrases
            sentence_lower = sentence.lower()
            has_limitation = any(
                phrase in sentence_lower
                for phrase in NEGATIVE_PHRASES
            )

            if has_limitation:
                limitations.append(sentence)

        return limitations

    def extract_limitations(
        self,
        paper: "CitationNode",
        full_text: str
    ) -> Dict[str, Any]:
        """
        Extract limitation statements from paper full text.

        Args:
            paper: CitationNode for context
            full_text: Full text of the paper

        Returns:
            Dictionary with limitations, section_text, and confidence
        """
        if not full_text:
            return {
                "limitations": [],
                "section_text": "",
                "confidence": 0.0
            }

        # Parse into sections
        sections = self.parse_sections(full_text)

        # Find limitation sections
        limitation_sections = []
        for header, text in sections.items():
            if self._is_limitation_section(header):
                limitation_sections.append((header, text))

        if not limitation_sections:
            # Try extracting from entire text if no clear sections
            all_limitations = self._extract_limitation_sentences(full_text)

            return {
                "limitations": all_limitations[:10],  # Limit to top 10
                "section_text": "",
                "confidence": min(0.3, len(all_limitations) / 10.0)  # Low confidence without section
            }

        # Extract limitation sentences from each section
        all_limitations = []
        section_texts = []

        for header, text in limitation_sections:
            sentences = self._extract_limitation_sentences(text)
            all_limitations.extend(sentences)
            section_texts.append(f"[{header}]\n{text}")

        # Calculate confidence based on quantity and section clarity
        base_confidence = min(1.0, len(all_limitations) / 5.0)
        section_bonus = 0.2 if any(
            'limitation' in h.lower() for h, _ in limitation_sections
        ) else 0.0

        confidence = min(1.0, base_confidence + section_bonus)

        paper_title = getattr(paper, 'title', 'Unknown')
        logger.info(
            "Limitations extracted",
            paper_title=paper_title[:50],
            num_limitations=len(all_limitations),
            confidence=confidence
        )

        return {
            "limitations": all_limitations[:10],  # Limit to top 10
            "section_text": "\n\n".join(section_texts),
            "confidence": confidence
        }

    def extract_from_abstract(
        self,
        paper: "CitationNode"
    ) -> Dict[str, Any]:
        """
        Extract limitations from paper abstract (fallback when no full text).

        Args:
            paper: CitationNode with abstract field

        Returns:
            Dictionary with limitations and confidence
        """
        abstract = getattr(paper, 'abstract', '') or ''

        if not abstract:
            return {
                "limitations": [],
                "section_text": "",
                "confidence": 0.0
            }

        limitations = self._extract_limitation_sentences(abstract)

        # Lower confidence for abstract-only extraction
        confidence = min(0.5, len(limitations) / 3.0)

        return {
            "limitations": limitations,
            "section_text": abstract,
            "confidence": confidence
        }

    def format_for_context(
        self,
        paper: "CitationNode",
        limitations_data: Dict[str, Any]
    ) -> str:
        """
        Format extracted limitations for inclusion in LLM context.

        Args:
            paper: CitationNode for metadata
            limitations_data: Output from extract_limitations()

        Returns:
            Formatted string suitable for LLM prompt
        """
        limitations = limitations_data.get("limitations", [])

        if not limitations:
            return ""

        title = getattr(paper, 'title', 'Unknown')
        year = getattr(paper, 'year', 'N/A')

        formatted_limitations = '\n'.join(f'- {lim}' for lim in limitations)

        return (
            f"Paper: {title} ({year})\n"
            f"[KNOWN LIMITATIONS]\n"
            f"{formatted_limitations}"
        )

    def batch_extract(
        self,
        papers: List["CitationNode"],
        full_texts: Optional[Dict[str, str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract limitations from multiple papers.

        Args:
            papers: List of CitationNode objects
            full_texts: Optional dict mapping paper ID to full text

        Returns:
            Dictionary mapping paper ID to limitations data
        """
        full_texts = full_texts or {}
        results = {}

        for paper in papers:
            paper_id = getattr(paper, 'id', None) or getattr(paper, 'doi', None) or getattr(paper, 'title', 'unknown')

            if paper_id in full_texts:
                # Use full text extraction
                data = self.extract_limitations(paper, full_texts[paper_id])
            else:
                # Fallback to abstract
                data = self.extract_from_abstract(paper)

            results[paper_id] = data

        # Log summary
        papers_with_limitations = sum(
            1 for data in results.values()
            if data.get("limitations")
        )

        logger.info(
            "Batch extraction complete",
            total_papers=len(papers),
            papers_with_limitations=papers_with_limitations
        )

        return results

    def format_batch_for_context(
        self,
        papers: List["CitationNode"],
        limitations_data: Dict[str, Dict[str, Any]],
        min_confidence: Optional[float] = None
    ) -> str:
        """
        Format limitations from multiple papers for LLM context.

        Args:
            papers: List of CitationNode objects
            limitations_data: Output from batch_extract()
            min_confidence: Minimum confidence threshold

        Returns:
            Formatted string for all papers with limitations
        """
        threshold = min_confidence or self.min_confidence

        formatted_parts = []
        for paper in papers:
            paper_id = getattr(paper, 'id', None) or getattr(paper, 'doi', None) or getattr(paper, 'title', 'unknown')

            data = limitations_data.get(paper_id, {})

            if data.get("confidence", 0) >= threshold:
                formatted = self.format_for_context(paper, data)
                if formatted:
                    formatted_parts.append(formatted)

        if not formatted_parts:
            return ""

        return "KNOWN LIMITATIONS FROM LITERATURE:\n\n" + "\n\n".join(formatted_parts)


# Default extractor instance
default_extractor = LimitationsExtractor()
