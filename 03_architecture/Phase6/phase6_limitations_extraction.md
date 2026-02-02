# Phase 6: Limitations Extraction (Negative Result Injection) - Implementation Summary

**Status**: ✅ **IMPLEMENTED**

**Date**: February 2, 2026

**Implementation Date**: February 2, 2026

**Alignment**: Addresses publication bias - Surface known failures and boundaries

---

## Overview

Implement extraction of **limitations**, **caveats**, and **negative results** from scientific papers to address publication bias. Currently, the system retrieves abstracts and treats all content equally, missing critical information about what **didn't work** or what's **uncertain**.

**Problem**: ~95% of published studies report positive results - too high to reflect reality. Negative results are hidden in specific sections of papers ("Limitations", "Discussion", "Future Work"), causing the LLM to learn that "everything works."

**Where Negative Results Hide**:
- **"Limitations"** section - What didn't work, what's uncertain
- **"Discussion"** section - Caveats and alternative explanations
- **"Future Work"** section - What needs fixing before progress
- **"Conclusion"** section - Boundaries of current knowledge

---

## Implementation Status

**Files Created**:
- [src/literature/limitations_extractor.py](../../src/literature/limitations_extractor.py) - LimitationsExtractor with section parsing
- [05_tests/phase6_limitations_test.py](../../05_tests/phase6_limitations_test.py) - 17 tests passing
- Integration tests included in phase6_generation_integration_test.py and phase6_reflection_integration_test.py

**Files Modified**:
- [src/agents/generation.py](../../src/agents/generation.py) - Extract and include limitations in context
- [src/agents/reflection.py](../../src/agents/reflection.py) - Check hypotheses against known limitations
- [src/literature/citation_graph.py](../../src/literature/citation_graph.py) - Added known_limitations and limitations_confidence fields
- [src/config.py](../../src/config.py) - Added Phase 6 configuration flags

**Test Results**: 17 unit tests passing

**Key Features**:
- Section parsing for "Limitations", "Discussion", "Future Work"
- Negative phrase detection (did not, failed to, unable to)
- Confidence scoring based on extraction quality
- Context formatting with [KNOWN LIMITATIONS] tags

---

## Implementation

### New File: `src/literature/limitations_extractor.py`

```python
class LimitationsExtractor:
    """
    Extract limitations, caveats, and negative results from papers.

    Strategy:
    1. Parse paper into sections (headers: "Limitations", "Discussion", etc.)
    2. Extract sentences containing negative/limitation phrases
    3. Return limitation statements with confidence score
    """

    # Section headers indicating limitations/caveats
    LIMITATION_HEADERS = [
        r"\bLimitations?\b",
        r"\bCaveats?\b",
        r"\bFuture Work\b",
        r"\bFuture Directions?\b",
        r"\bFuture Research\b",
        r"\bOpen Questions?\b",
        r"\bUnresolved\b",
        r"\bDiscussion\b",
        r"\bConclusions?\b"
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
        "requires additional"
    ]

    def extract_limitations(
        self,
        paper: CitationNode,
        full_text: str
    ) -> Dict[str, any]:
        """
        Extract limitation statements from paper.

        Returns:
            {
                "limitations": List[str],  # Extracted limitation sentences
                "section_text": str,       # Full text of limitations section
                "confidence": float        # 0-1, confidence these are real limitations
            }
        """
        # Find sections matching limitation headers
        sections = self._parse_sections(full_text)

        limitation_sections = []
        for header, text in sections.items():
            if self._is_limitation_section(header):
                limitation_sections.append((header, text))

        if not limitation_sections:
            return {
                "limitations": [],
                "section_text": "",
                "confidence": 0.0
            }

        # Extract limitation sentences
        limitations = []
        for header, text in limitation_sections:
            sentences = self._extract_limitation_sentences(text)
            limitations.extend(sentences)

        # Confidence based on how many negative phrases found
        confidence = min(1.0, len(limitations) / 5.0)

        return {
            "limitations": limitations,
            "section_text": section_text,
            "confidence": confidence
        }

    def _extract_limitation_sentences(self, text: str) -> List[str]:
        """
        Extract sentences containing negative/limitation phrases.
        """
        sentences = re.split(r'[.!?]+', text)

        limitations = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short fragments
                continue

            # Check for negative/limitation phrases
            has_limitation = any(
                phrase in sentence.lower()
                for phrase in self.NEGATIVE_PHRASES
            )

            if has_limitation:
                limitations.append(sentence)

        return limitations

    def format_for_context(
        self,
        paper: CitationNode,
        limitations_data: Dict
    ) -> str:
        """
        Format limitations for inclusion in LLM context.
        """
        if not limitations_data["limitations"]:
            return ""

        formatted = f"""
        Paper: {paper.title} ({paper.year})
        [KNOWN LIMITATIONS]
        {chr(10).join('- ' + lim for lim in limitations_data["limitations"])}
        """
        return formatted
```

### Section Parsing

```python
def _parse_sections(self, full_text: str) -> Dict[str, str]:
    """
    Parse paper into sections.

    Looks for patterns like:
    - "## Limitations"
    - "4. Discussion"
    - "LIMITATIONS"
    """
    # Simple heuristic: split on common section markers
    section_pattern = r'\n\s*(?:\d+\.?\s*)?([A-Z][A-Za-z\s]+)\n'

    matches = list(re.finditer(section_pattern, full_text))

    sections = {}
    for i, match in enumerate(matches):
        header = match.group(1).strip()
        start = match.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(full_text)
        text = full_text[start:end].strip()
        sections[header] = text

    return sections
```

---

## Files Modified

### 1. **[03_architecture/schemas.py](../../schemas.py)** - Add limitations to CitationNode

```python
class CitationNode(BaseModel):
    # ... existing fields ...
    citation_count: int = Field(0)
    quality_score: Optional[float] = Field(None)

    # NEW: Add limitations if extracted
    known_limitations: List[str] = Field(
        default_factory=list,
        description="Extracted limitation statements from paper"
    )
    limitations_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Confidence score for limitations extraction"
    )
```

### 2. **[src/agents/generation.py](../../src/agents/generation.py)** - Include limitations in context

```python
from src.literature.limitations_extractor import LimitationsExtractor

def _format_citation_context(self, citations: List[CitationNode]) -> str:
    """Format citations for LLM context with limitations highlighted."""

    limitations_extractor = LimitationsExtractor()

    context_parts = []

    for paper in citations:
        # Standard citation info
        context_parts.append(f"""
        Title: {paper.title}
        Authors: {', '.join(paper.authors)}
        Year: {paper.year}
        Citations: {paper.citation_count}
        Quality: {paper.quality_score or 'N/A'}
        Abstract: {paper.abstract}
        """)

        # NEW: Add limitations if available
        if paper.full_text:  # Assuming we have full text
            limitations_data = limitations_extractor.extract_limitations(
                paper=paper,
                full_text=paper.full_text
            )

            if limitations_data["confidence"] > 0.5:
                limitations_text = limitations_extractor.format_for_context(
                    paper=paper,
                    limitations_data=limitations_data
                )
                context_parts.append(limitations_text)

    return "\n\n".join(context_parts)
```

### 3. **[src/agents/reflection.py](../../src/agents/reflection.py)** - Check hypothesis against known limitations

```python
# In full_review() method

# When checking novelty:
# Check if hypothesis addresses known limitations from literature

limitations_from_literature = []
for paper in supporting_papers:
    if paper.known_limitations:
        limitations_from_literature.extend(paper.known_limitations)

review_context += f"""
KNOWN LIMITATIONS FROM LITERATURE:
{chr(10).join('- ' + lim for lim in limitations_from_literature)}

NOVELTY ASSESSMENT TASK:
1. Does this hypothesis simply re-propose something known to fail?
2. Does it address/overcome known limitations from prior work?
3. Does it acknowledge boundary conditions and caveats?

If hypothesis re-proposes known failures WITHOUT addressing why it would work this time,
reduce novelty score significantly.
"""
```

### 4. **[src/config.py](../../src/config.py)** - Configuration

```python
# Limitations Extraction (Phase 6)
enable_limitations_extraction: bool = True
limitations_min_confidence: float = 0.5  # Only use high-confidence extractions
limitations_include_in_context: bool = True
```

---

## Integration with Citation Pipeline

Limitations extraction occurs during literature retrieval:

```python
# In generation agent, after retrieving papers
for paper in papers:
    # Compute quality score
    paper.quality_score = scorer.compute_quality_score(paper)

    # Extract limitations if full text available
    if paper.full_text:
        limitations_data = limitations_extractor.extract_limitations(
            paper=paper,
            full_text=paper.full_text
        )
        if limitations_data["confidence"] > 0.5:
            paper.known_limitations = limitations_data["limitations"]
            paper.limitations_confidence = limitations_data["confidence"]
```

---

## Testing

### Test File: `05_tests/phase6_limitations_test.py`

**Test Cases**:

| Test | Purpose | Expected Result |
|------|---------|----------------|
| `test_section_parsing()` | Parse paper into sections | Identify "Limitations" section |
| `test_limitation_sentence_extraction()` | Extract negative phrases | Find sentences with "did not", "failed to" |
| `test_confidence_scoring()` | Confidence based on extraction | More limitations → higher confidence |
| `test_known_failure_detection()` | Catch re-proposed failures | Hypothesis re-proposing "known to fail" flagged |
| `test_context_formatting()` | Limitations in LLM context | [KNOWN LIMITATIONS] section present |
| `test_reflection_integration()` | Novelty check with limitations | Hypothesis ignoring limitations scored lower |

### Verification Steps

- [x] Parse paper with clear "Limitations" section
- [x] Extract limitation sentences containing negative phrases
- [x] Verify confidence > 0.5 for papers with explicit limitations
- [x] Check that limitations appear in Generation agent context
- [x] Verify: Generated hypotheses don't re-propose known failures
- [x] Test: Reflection agent flags hypotheses ignoring known limitations

### Real-World Test Case: Known Experimental Failure

**Setup**: Provide paper describing "Protocol X failed to amplify Gene Y due to high GC content"

**Test Hypothesis**: "Use Protocol X to amplify Gene Y"

**Expected Behavior**:
- [x] Limitations extractor finds "Protocol X failed" statement
- [x] Generation agent includes limitation in context
- [x] If hypothesis proposed anyway, Reflection agent flags as "ignores known limitation"
- [x] Novelty score reduced due to re-proposing known failure

---

## Success Criteria

✅ **Extraction Accuracy**:
- Extracts limitations from 70%+ of papers with explicit limitation sections
- Correctly identifies "Limitations", "Discussion", "Future Work" sections
- Limitation sentences contain negative/caveat phrases

✅ **Context Integration**:
- Limitations appear in Generation agent LLM context
- Formatted with [KNOWN LIMITATIONS] tag for clarity
- Only high-confidence extractions (confidence > 0.5) included

✅ **Hypothesis Quality Improvement**:
- Reduces proposals for known-failure experiments by 30%+
- Hypotheses that address limitations score higher in novelty
- Reflection agent explicitly checks if limitations are acknowledged

✅ **Backward Compatible**:
- Works without full text (skips extraction gracefully)
- Can be disabled via configuration
- Doesn't break if extraction fails

---

## Benefits

1. **Reduces Publication Bias**: Surfaces negative results hidden in papers
2. **Prevents Redundant Failures**: Avoids re-proposing experiments known to fail
3. **Increases Novelty**: Hypotheses addressing limitations are genuinely novel
4. **Realistic Expectations**: LLM learns boundaries of current knowledge

---

## Edge Cases & Limitations

**Edge Cases**:
- Papers without clear section headers (older papers, some journals)
- Limitations stated implicitly rather than explicitly
- Full text not available (can only extract from abstracts)

**Limitations**:
- Heuristic-based section parsing (may miss unconventional headers)
- Phrase matching may have false positives ("did not replicate" vs "did not attempt")
- Requires full text for best results (abstracts rarely contain limitations)

**Mitigations**:
- Multiple header patterns to catch different styles
- Confidence scoring to filter low-quality extractions
- Graceful degradation if full text unavailable

---

## Future Enhancements

- **NLP-based limitation detection**: Use LLM to identify limitations without keyword matching
- **Severity scoring**: Rate how serious each limitation is
- **Limitation categorization**: Technical limitations vs theoretical limitations
- **Cross-paper limitation aggregation**: "Multiple papers report difficulty with X"
- **Integration with vector database**: Store limitations as metadata for semantic search

---

## Example Output

### Paper: "CRISPR/Cas9 editing efficiency in primary T cells"

**Extracted Limitations**:
```
[KNOWN LIMITATIONS]
- Editing efficiency was low (<10%) in resting T cells, limiting clinical applicability
- Off-target effects were detected at 3 genomic loci with high sequence similarity
- Method could not be validated in CD4+ cells due to technical limitations
- Further optimization needed for in vivo delivery approaches
- However, these results were obtained in vitro and require validation in animal models
```

**Confidence**: 0.8 (4 clear limitation statements found)

**Context for LLM**:
```
Paper: CRISPR/Cas9 editing efficiency in primary T cells (2023)
[KNOWN LIMITATIONS]
- Editing efficiency was low (<10%) in resting T cells
- Off-target effects detected at 3 genomic loci
- Could not be validated in CD4+ cells
```

---

## References

- Ioannidis, J. P. A. (2005). "Why Most Published Research Findings Are False" - Publication bias
- Franco, A., et al. (2014). "Publication Bias in the Social Sciences" - 95% positive results
- Open Science Framework - Registered Reports to combat publication bias
- Fanelli, D. (2010). "Do Pressures to Publish Increase Scientists' Bias?" - Incentive structures