# Phase 6: Refutation Search - Implementation Summary

**Status**: 📋 **PLANNED**

**Date**: February 2, 2026

**Alignment**: Scientific method (Popperian falsification) - Critical gap in current system

---

## Overview

Implement literature search capabilities to find **contradictory evidence** and **negative results** that challenge generated hypotheses. Currently, the system only searches for **supporting** literature, creating a confirmation bias that undermines scientific rigor.

**Problem**: The Google paper requires "contradictions with literature must be justified" - but you can't justify contradictions you don't search for. Science advances through **falsification**, not just confirmation.

**Current System Finds**:
- Papers that **support** the hypothesis
- Papers **cited by** supporting papers (backward expansion)
- Papers **citing** supporting papers (forward expansion)

**Current System Does NOT Find**:
- Papers with **opposing conclusions**
- **Failed replication** attempts
- **Corrections** or retractions of supporting evidence

---

## Implementation

### New File: `src/tools/refutation_search.py`

```python
class RefutationSearchTool:
    """
    Search for papers that contradict a hypothesis or show negative results.

    Three core capabilities:
    1. Contradiction search - Find papers with opposing conclusions
    2. Failed replication search - Find replication failures
    3. Retraction detection - Check PubMed for retractions/corrections
    """

    def search_contradictions(
        self,
        hypothesis_statement: str,
        core_claim: str
    ) -> List[CitationNode]:
        """
        Search for papers contradicting the hypothesis.

        Strategy:
        1. Generate negation queries ("NOT", "no effect", "failed to")
        2. Search Semantic Scholar + PubMed
        3. Filter by contradiction keywords in abstract
        4. Rank by quality score
        5. Return top 10 contradictions
        """

    def search_failed_replications(
        self,
        target_paper: CitationNode
    ) -> List[CitationNode]:
        """
        Find papers that failed to replicate the target paper.

        Strategy:
        1. Get papers citing the target (forward expansion)
        2. Filter for replication keywords
        3. Return failed replication attempts
        """

    def check_retractions(
        self,
        paper: CitationNode
    ) -> Dict[str, any]:
        """
        Check PubMed for retraction notices or corrections.

        Returns:
            {
                "is_retracted": bool,
                "has_correction": bool,
                "notices": List[str]
            }
        """
```

### Negation Query Generation

```python
def _generate_negation_queries(self, claim: str) -> List[str]:
    """
    Examples:
    - "Protein A inhibits Gene B" →
      ["Protein A does not inhibit Gene B",
       "Protein A activates Gene B",  # opposite effect
       "no effect Protein A Gene B",
       "contradicts Protein A Gene B",
       "failed to replicate Protein A Gene B"]
    """
    negation_templates = [
        f"{claim} NOT",
        f"{claim} does not",
        f"no effect {claim}",
        f"contradicts {claim}",
        f"inconsistent with {claim}",
        f"failed to replicate {claim}",
        f"could not reproduce {claim}",
    ]
    return negation_templates
```

### Contradiction Filtering

```python
def _filter_contradictions(
    self,
    papers: List[CitationNode],
    original_claim: str
) -> List[CitationNode]:
    """
    Filter papers that actually contradict the claim.

    Checks abstract for contradiction keywords:
    - "not", "no effect", "no significant"
    - "contradicts", "inconsistent", "contrary"
    - "failed to", "unable to", "did not"
    - "opposite", "conflicting"
    """
```

---

## Files Modified

### 1. **[src/agents/reflection.py](../../src/agents/reflection.py)** - Integrate refutation search in full_review()

**Current**: Reviews hypothesis using only supporting literature

**New**: Reviews hypothesis using BOTH supporting AND contradictory literature

```python
from src.tools.refutation_search import RefutationSearchTool

async def full_review(self, hypothesis: Hypothesis) -> Review:
    # ... existing code ...

    # NEW: Search for contradictory evidence
    refutation_tool = RefutationSearchTool()

    # Extract core claim from hypothesis
    core_claim = self._extract_core_claim(hypothesis)

    # Search for contradictions
    contradictions = refutation_tool.search_contradictions(
        hypothesis_statement=hypothesis.statement,
        core_claim=core_claim
    )

    # Check if supporting citations have been retracted
    retraction_status = {}
    for citation in hypothesis.citations:
        if citation.pmid:
            retraction_status[citation.title] = refutation_tool.check_retractions(citation)

    # Include in review context for LLM
    review_context = f"""
    SUPPORTING EVIDENCE:
    {format_citations(hypothesis.citations)}

    CONTRADICTORY EVIDENCE FOUND ({len(contradictions)} papers):
    {format_citations(contradictions)}

    RETRACTION NOTICES:
    {format_retraction_status(retraction_status)}

    CRITICAL REVIEW TASK:
    Evaluate whether this hypothesis is plausible given BOTH supporting
    and contradictory evidence. If contradictions exist, assess:
    1. Are contradictions from high-quality sources?
    2. Does hypothesis address/explain contradictions?
    3. Are supporting papers retracted or corrected?
    """

    # ... continue with LLM review generation ...
```

### 2. **[src/agents/generation.py](../../src/agents/generation.py)** - Preemptive contradiction handling

Optional enhancement: Generation agent can search for contradictions early and address them in the hypothesis rationale.

```python
# After generating initial hypothesis, check for obvious contradictions
contradictions = refutation_tool.search_contradictions(
    hypothesis_statement=draft_hypothesis.statement,
    core_claim=extracted_claim
)

if len(contradictions) > 0:
    # Refine hypothesis to acknowledge contradictions
    refined_hypothesis = self._refine_with_contradictions(
        draft_hypothesis,
        contradictions
    )
```

### 3. **[src/config.py](../../src/config.py)** - Configuration

```python
# Refutation Search (Phase 6)
enable_refutation_search: bool = True
refutation_max_results: int = 10
refutation_min_quality_score: float = 0.4  # Only use high-quality contradictions
refutation_check_retractions: bool = True
```

---

## PubMed Retraction Detection

Uses PubMed publication types:
- `retracted[pt]` - Paper has been retracted
- `retraction[pt]` - This is a retraction notice
- `correction[pt]` - Correction/erratum published
- `erratum[pt]` - Erratum notice

```python
# Query PubMed for retraction notices
query = f"{paper.pmid}[PMID] AND (retracted[pt] OR retraction[pt])"
results = self.pubmed_tool.search(query, max_results=5)

is_retracted = len(results) > 0
```

---

## Testing

### Test File: `05_tests/phase6_refutation_test.py`

**Test Cases**:

| Test | Purpose | Expected Result |
|------|---------|----------------|
| `test_negation_query_generation()` | Verify query templates | "Protein A inhibits B" → "Protein A does NOT inhibit B" |
| `test_contradiction_filtering()` | Filter papers with opposing results | Papers with "no effect" in abstract returned |
| `test_hydroxychloroquine_covid()` | Real-world controversial hypothesis | Find contradictory RCTs showing no effect |
| `test_retraction_detection()` | Detect retracted papers | Identify known retracted papers (e.g., Wakefield MMR) |
| `test_failed_replication_search()` | Find replication failures | Detect papers saying "failed to replicate" |
| `test_reflection_integration()` | End-to-end review with contradictions | Review mentions contradictory evidence |

### Real-World Test Case: Hydroxychloroquine for COVID-19

**Hypothesis**: "Hydroxychloroquine is effective for treating COVID-19"

**Expected Contradictions Found**:
- RECOVERY trial (2020) - No benefit, potential harm
- SOLIDARITY trial (2020) - No mortality benefit
- Multiple RCTs showing null results
- Retraction of early positive observational studies (Lancet retraction)

**Verification**:
- [ ] Refutation search finds ≥5 contradictory RCTs
- [ ] Retraction detection identifies Lancet retraction
- [ ] Reflection agent review flags hypothesis as "contradicted by high-quality evidence"

---

## Success Criteria

✅ **Contradiction Detection**:
- System finds contradictory papers for 80%+ of test hypotheses
- Contradictions include papers with opposing conclusions
- Quality-filtered (only high-quality contradictions, score > 0.4)

✅ **Retraction Detection**:
- Correctly identifies known retracted papers (100% accuracy on test set)
- Checks PubMed for corrections/errata
- Flags supporting citations that have been retracted

✅ **Reflection Integration**:
- Reflection agent reviews include contradictory evidence section
- Reviews explicitly assess contradiction severity
- Hypotheses contradicted by high-quality evidence receive lower scores

✅ **Backward Compatible**:
- Feature can be disabled via configuration
- System works if refutation search fails (graceful degradation)

---

## Benefits

1. **Scientific Rigor**: Forces hypotheses to confront counter-evidence
2. **Prevents Hallucination**: Catches hypotheses contradicting established findings
3. **Addresses Publication Bias**: Finds negative results that support papers miss
4. **Protects Against Retractions**: Flags supporting citations that have been retracted

---

## Edge Cases & Limitations

**Edge Cases**:
- Hypotheses without clear testable claims (hard to generate negation queries)
- Novel hypotheses with no prior work (no contradictions to find)
- Contradictions from low-quality sources (filtered by quality score)

**Limitations**:
- Negation query generation is heuristic-based (may miss nuanced contradictions)
- PubMed retraction detection only works for papers with PMIDs
- False positives: Papers may mention "no effect" for unrelated sub-claims

**Mitigations**:
- Use quality scoring to filter low-quality contradictions
- LLM-based claim extraction for better negation queries
- Human review of flagged contradictions

---

## Future Enhancements

- **LLM-based contradiction detection**: Use LLM to assess if papers truly contradict
- **Citation network analysis**: Find contradiction cascades (Paper A contradicts B, B contradicts hypothesis)
- **Temporal contradiction tracking**: Track if contradictions emerge over time
- **Field-specific contradiction patterns**: Different fields have different contradiction styles

---

## References

- Popper, K. (1959). *The Logic of Scientific Discovery* - Falsificationism
- Ioannidis, J. P. A. (2005). "Why Most Published Research Findings Are False" - Publication bias
- Open Science Collaboration (2015). "Estimating the reproducibility of psychological science" - Replication crisis
- PubMed Publication Types: https://www.nlm.nih.gov/mesh/pubtypes.html