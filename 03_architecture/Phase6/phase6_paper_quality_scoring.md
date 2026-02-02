# Phase 6: Paper Quality Scoring - Implementation Summary

**Status**: 📋 **PLANNED**

**Date**: February 2, 2026

**Alignment**: Scientific rigor enhancement - Prioritize high-quality evidence

---

## Overview

Implement multi-factor quality scoring for literature citations to prioritize high-quality, reliable evidence in hypothesis generation and review. Currently, the system ranks papers by citation count only, which doesn't account for recency, journal impact, or replication status.

**Problem**: Not all papers are equal. A 2024 Nature paper with 500 citations should be weighted higher than a 2005 low-tier journal paper with 10 citations. The current system treats them equally if sorted only by citation count.

**Solution**: Compute a composite quality score (0.0-1.0) based on:
1. **Citation count** (normalized by field/year) - 50% weight
2. **Recency** (exponential decay, half-life = 5 years) - 30% weight
3. **Journal impact** (Scimago SJR if available) - 20% weight
4. **Penalties** for retractions or predatory journals

---

## Implementation

### New File: `src/literature/quality_scorer.py`

```python
class PaperQualityScorer:
    """
    Compute multi-factor quality score for papers.

    Factors:
    1. Citation count (normalized by field/year)
    2. Recency (exponential decay)
    3. Journal impact (if available via API)
    4. Replication status (boosted if replicated)
    5. Negative factors (retraction, predatory journal)
    """

    def compute_quality_score(self, paper: CitationNode) -> float:
        """
        Returns quality score 0.0-1.0

        Formula:
        quality = w1 * citation_score
                + w2 * recency_score
                + w3 * journal_score
                - penalties
        """
        # Citation score (normalized)
        # Top 1% of papers ~1000+ citations, median ~10
        citation_score = min(1.0, paper.citation_count / 500)

        # Recency score (exponential decay, half-life = 5 years)
        years_old = 2026 - (paper.year or 2000)
        recency_score = 0.5 ** (years_old / 5.0)

        # Journal score (placeholder - could integrate Scimago SJR)
        journal_score = 0.5  # Default mid-range

        # Combine (weighted average)
        quality = (
            0.5 * citation_score +
            0.3 * recency_score +
            0.2 * journal_score
        )

        return min(1.0, max(0.0, quality))

    def rank_papers_by_quality(
        self,
        papers: List[CitationNode],
        top_k: int = 20
    ) -> List[CitationNode]:
        """Return top-k highest quality papers."""
        scored = [(self.compute_quality_score(p), p) for p in papers]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [p for (score, p) in scored[:top_k]]
```

---

## Files Modified

### 1. **[03_architecture/schemas.py](../../schemas.py)** - Add quality score to CitationNode

```python
class CitationNode(BaseModel):
    # ... existing fields ...
    citation_count: int = Field(0, description="Number of times cited")
    year: Optional[int] = Field(None, description="Publication year")

    # NEW: Add quality score
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Multi-factor quality score (citation + recency + journal)"
    )
```

### 2. **[src/agents/generation.py:260-280](../../src/agents/generation.py)** - Use quality scoring

**Current**:
```python
papers.sort(key=lambda p: p.citation_count, reverse=True)
```

**New**:
```python
from src.literature.quality_scorer import PaperQualityScorer

scorer = PaperQualityScorer()

# Score papers
for paper in papers:
    paper.quality_score = scorer.compute_quality_score(paper)

# Sort by quality, not just citations
papers.sort(key=lambda p: p.quality_score or 0, reverse=True)
```

### 3. **[src/agents/reflection.py](../../src/agents/reflection.py)** - Prioritize high-quality evidence

- In `full_review()` method, check quality scores when validating novelty
- Flag hypotheses that contradict **high-quality** evidence (quality > 0.7) more severely than low-quality sources

### 4. **[src/agents/observation_review.py](../../src/agents/observation_review.py)** - Filter by quality

- Only extract observations from high-quality papers (quality > 0.6)
- Prevents garbage observations from low-quality sources

---

## Enhancement: Quality Context Indicator

When formatting papers for LLM context, include quality indicator:

```python
# In generation agent context formatting
for paper in top_papers:
    quality = scorer.compute_quality_score(paper)
    context += f"""
    Title: {paper.title}
    Authors: {', '.join(paper.authors)}
    Year: {paper.year}
    Citations: {paper.citation_count}
    [QUALITY: {'HIGH' if quality > 0.7 else 'MEDIUM' if quality > 0.4 else 'LOW'}]
    Abstract: {paper.abstract}
    """
```

This helps the LLM weigh evidence appropriately.

---

## Configuration

Add to `src/config.py`:

```python
# Paper Quality Scoring (Phase 6)
enable_quality_scoring: bool = True
quality_citation_weight: float = 0.5
quality_recency_weight: float = 0.3
quality_journal_weight: float = 0.2
quality_min_threshold: float = 0.3  # Filter papers below this score
quality_recency_halflife_years: int = 5
```

---

## Testing

### Test File: `05_tests/phase6_quality_scoring_test.py`

**Test Cases**:

| Test | Purpose | Expected Result |
|------|---------|----------------|
| `test_citation_score_normalization()` | Verify citation scoring curve | 1000+ citations → 1.0 score |
| `test_recency_scoring()` | Verify exponential decay | Recent papers score higher |
| `test_old_high_citation_papers()` | Balance recency vs citations | 2010 paper with 1000 citations < 2024 paper with 500 |
| `test_quality_filtering()` | Low-quality papers filtered | Papers with score < 0.3 excluded |
| `test_quality_ranking()` | Papers ranked correctly | Nature 2024 > low-tier 2010 |
| `test_llm_context_quality_labels()` | Quality labels in context | HIGH/MEDIUM/LOW tags present |

### Verification Steps

- [ ] Load 100 papers with varying citation counts (10, 50, 100, 500, 1000+)
- [ ] Compute quality scores
- [ ] Verify: High-citation + recent papers score > 0.7
- [ ] Verify: Old papers (pre-2010) score < 0.5 even with high citations
- [ ] Check that low-quality papers (score < 0.3) filtered from context
- [ ] Verify quality labels appear in Generation agent LLM prompts

---

## Success Criteria

✅ **High-quality papers prioritized**:
- Nature/Science/Cell papers with high citations rank top
- Recent papers (2020+) weighted higher than old papers (pre-2010)

✅ **Low-quality sources filtered**:
- Predatory journal papers excluded
- Papers with score < 0.3 not included in LLM context

✅ **Quality indicators visible**:
- LLM context shows [QUALITY: HIGH/MEDIUM/LOW] labels
- Agents can distinguish evidence strength

✅ **Backward compatible**:
- System works without quality scores (fallback to citation count)
- Configuration flag to disable feature

---

## Benefits

1. **Improved Evidence Quality**: Prioritizes reliable, high-impact sources
2. **Recency Bias**: Recent findings weighted appropriately for current research
3. **Transparency**: LLM sees quality indicators, can weigh evidence accordingly
4. **Filtering**: Automatically excludes low-quality/predatory sources

---

## Future Enhancements

- Integrate Scimago Journal Rank (SJR) API for journal impact scores
- Add replication status tracking (papers with successful replications boosted)
- Field-specific normalization (citation norms vary by field)
- Detect predatory journals via Beall's List or similar databases

---

## References

- Citation count distribution: Median ~10 citations, top 1% ~1000+ citations
- Recency decay: Half-life of 5 years based on scientific literature citation patterns
- Quality thresholds: 0.7+ = high quality, 0.4-0.7 = medium, <0.4 = low quality