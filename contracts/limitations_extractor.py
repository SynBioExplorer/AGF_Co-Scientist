"""
Contract: LimitationsExtractorProtocol
Version: 31f3178 (commit hash when contract was created)
Generated: 2026-02-02T10:00:00Z

Extract limitations, caveats, and negative results from scientific papers.
Addresses publication bias by surfacing what didn't work.
"""
from typing import Protocol, Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.literature.citation_graph import CitationNode


class LimitationsExtractorProtocol(Protocol):
    """
    Protocol for extracting limitations and negative results from papers.

    Where Negative Results Hide:
        - "Limitations" section - What didn't work, what's uncertain
        - "Discussion" section - Caveats and alternative explanations
        - "Future Work" section - What needs fixing before progress
        - "Conclusion" section - Boundaries of current knowledge

    Section Headers to Match:
        - Limitations, Limitation
        - Caveats, Caveat
        - Future Work, Future Directions, Future Research
        - Open Questions, Unresolved
        - Discussion
        - Conclusions, Conclusion

    Negative Phrases to Detect:
        - "did not", "no significant", "no effect"
        - "unable to", "failed to", "could not"
        - "limitation", "caveat", "however", "although"
        - "remains unclear", "future work", "further research needed"
    """

    def extract_limitations(
        self,
        paper: "CitationNode",
        full_text: str
    ) -> Dict[str, Any]:
        """
        Extract limitation statements from paper full text.

        Args:
            paper: CitationNode for context (title, year, etc.)
            full_text: Full text of the paper

        Returns:
            Dictionary with:
                - limitations: List[str] - Extracted limitation sentences
                - section_text: str - Full text of limitations section(s)
                - confidence: float - Confidence score 0.0-1.0

        Notes:
            - Confidence is based on number of negative phrases found
            - confidence = min(1.0, len(limitations) / 5.0)
            - Returns empty result if no limitations found

        Example:
            >>> extractor = LimitationsExtractor()
            >>> data = extractor.extract_limitations(paper, full_text)
            >>> print(data["limitations"])
            ['Editing efficiency was low (<10%) in resting T cells',
             'Off-target effects were detected at 3 genomic loci']
        """
        ...

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
            Formatted string suitable for LLM prompt, or empty string if no limitations

        Format:
            Paper: {title} ({year})
            [KNOWN LIMITATIONS]
            - Limitation 1
            - Limitation 2
            ...

        Example:
            >>> context = extractor.format_for_context(paper, data)
            >>> print(context)
            Paper: CRISPR editing in T cells (2023)
            [KNOWN LIMITATIONS]
            - Editing efficiency was low (<10%) in resting T cells
            - Off-target effects detected at 3 loci
        """
        ...

    def parse_sections(self, full_text: str) -> Dict[str, str]:
        """
        Parse paper into sections by header.

        Args:
            full_text: Full text of the paper

        Returns:
            Dictionary mapping section headers to section text

        Header Patterns Matched:
            - "## Limitations"
            - "4. Discussion"
            - "LIMITATIONS"
            - Any line matching: number + header text

        Example:
            >>> sections = extractor.parse_sections(full_text)
            >>> print(sections.keys())
            dict_keys(['Introduction', 'Methods', 'Results', 'Discussion', 'Limitations'])
        """
        ...


# Type alias for implementations
LimitationsExtractor = LimitationsExtractorProtocol
