# Task: task-generation-quality

## Objective
Integrate PaperQualityScorer and LimitationsExtractor into GenerationAgent.

## Context
You are working in a git worktree for this task. The Phase 6 features exist:
- `src/literature/quality_scorer.py` - PaperQualityScorer
- `src/literature/limitations_extractor.py` - LimitationsExtractor

The contract is defined in `contracts/evidence_quality_interface.py`.
Tests are in `05_tests/phase6_generation_integration_test.py`.

## Requirements

Modify `src/agents/generation.py` to add:

### 1. New Imports (at top of file)
```python
from src.literature.quality_scorer import PaperQualityScorer
from src.literature.limitations_extractor import LimitationsExtractor
```

### 2. Update __init__ Method
Add after existing initializations:
```python
# Phase 6: Evidence quality enhancement
self.quality_scorer = PaperQualityScorer(
    citation_weight=settings.quality_citation_weight,
    recency_weight=settings.quality_recency_weight,
    journal_weight=settings.quality_journal_weight,
    min_threshold=settings.quality_min_threshold,
    recency_halflife_years=settings.quality_recency_halflife_years
)
self.limitations_extractor = LimitationsExtractor(
    min_confidence=settings.limitations_min_confidence
)
```

### 3. Add _enrich_papers_with_quality Method
```python
def _enrich_papers_with_quality(
    self,
    papers: List[Any]
) -> List[Any]:
    """
    Score papers and filter by quality threshold.

    Args:
        papers: List of CitationNode objects from search

    Returns:
        Filtered and ranked list of papers
    """
    if not settings.enable_quality_scoring or not papers:
        return papers

    # Score each paper
    for paper in papers:
        paper.quality_score = self.quality_scorer.compute_quality_score(paper)

    # Filter by threshold
    filtered = self.quality_scorer.filter_by_quality(papers)

    # Rank by quality (highest first)
    ranked = self.quality_scorer.rank_papers_by_quality(filtered, top_k=len(filtered))

    self.logger.info(
        "Papers enriched with quality scores",
        total=len(papers),
        passed_filter=len(ranked)
    )

    return ranked
```

### 4. Add _extract_paper_limitations Method
```python
def _extract_paper_limitations(
    self,
    papers: List[Any]
) -> str:
    """
    Extract limitations from papers for LLM context.

    Args:
        papers: List of CitationNode objects

    Returns:
        Formatted limitations string or empty if disabled
    """
    if not settings.enable_limitations_extraction or not papers:
        return ""

    # Batch extract from abstracts (full text not available in this pipeline)
    limitations_data = self.limitations_extractor.batch_extract(papers)

    # Format for context
    context = self.limitations_extractor.format_batch_for_context(
        papers,
        limitations_data,
        min_confidence=settings.limitations_min_confidence
    )

    if context:
        self.logger.info(
            "Limitations extracted",
            papers_with_limitations=sum(1 for d in limitations_data.values() if d.get("limitations"))
        )

    return context
```

### 5. Update _format_citation_graph_context Method
Modify to include quality labels and skip retracted papers:

After the existing header line, modify the paper formatting loop:
```python
for i, paper in enumerate(papers):
    # Skip retracted papers
    if getattr(paper, 'is_retracted', False):
        self.logger.warning("Skipping retracted paper", title=paper.title)
        continue

    # Get quality label
    quality_score = getattr(paper, 'quality_score', None)
    if quality_score is not None:
        quality_label = self.quality_scorer.get_quality_label(quality_score)
    else:
        quality_label = "UNKNOWN"

    # Get citations this paper makes
    citations = graph.get_citations(paper.id)
    cited_by = graph.get_cited_by(paper.id)

    context_parts.append(
        f"\n**Paper {i+1}:** {paper.title}\n"
        f"[QUALITY: {quality_label}]\n"
        f"Authors: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}\n"
        f"Year: {paper.year or 'N/A'}\n"
        f"DOI: {paper.doi or 'N/A'}\n"
        f"Citations: {paper.citation_count} | References: {paper.reference_count}\n"
        f"Graph connections: Cites {len(citations)} papers, Cited by {len(cited_by)} papers\n"
    )
```

### 6. Update execute Method
After the citation graph expansion and before formatting the context:

```python
# Phase 6: Enrich papers with quality scores
if search_results:
    # Get papers from graph nodes
    graph_papers = list(citation_graph.nodes.values())

    # Enrich with quality scores and filter
    quality_papers = self._enrich_papers_with_quality(graph_papers)

    # Extract limitations
    limitations_context = self._extract_paper_limitations(quality_papers)

    # Format quality-enriched context
    literature_context = self._format_citation_graph_context(
        citation_graph,
        max_papers=20
    )

    # Append limitations if available
    if limitations_context:
        literature_context = f"{literature_context}\n\n{limitations_context}"
```

## Verification Commands
After modifying, run:
```bash
python -c "from src.agents.generation import GenerationAgent; g = GenerationAgent(); print('Init OK')"
python -m py_compile src/agents/generation.py
python -m pytest 05_tests/phase6_generation_integration_test.py -v --tb=short
```

## Important
- Maintain backward compatibility - existing functionality must still work
- Use `settings.enable_*` flags to control features
- Log all quality-related operations
- Handle edge cases (empty lists, missing attributes)

When complete, commit your changes to this worktree branch.
