# Task: task-reflection-refutation

## Objective
Integrate RefutationSearchTool into ReflectionAgent.

## Context
You are working in a git worktree for this task. The Phase 6 features exist:
- `src/tools/refutation_search.py` - RefutationSearchTool
- `src/literature/limitations_extractor.py` - LimitationsExtractor

The contract is defined in `contracts/evidence_quality_interface.py`.
Tests are in `05_tests/phase6_reflection_integration_test.py`.

## Requirements

Modify `src/agents/reflection.py` to add:

### 1. New Imports (at top of file)
```python
from src.tools.refutation_search import RefutationSearchTool
from src.literature.limitations_extractor import LimitationsExtractor
from src.tools.registry import initialize_tools
from src.config import settings
from typing import Tuple, List, Optional
```

### 2. Update __init__ Method
Add after existing initializations:
```python
# Phase 6: Refutation search integration
self.tool_registry = initialize_tools()

# Initialize refutation tool with PubMed and Semantic Scholar
pubmed_tool = self.tool_registry.get("pubmed")
semantic_tool = self.tool_registry.get("semantic_scholar")

self.refutation_tool = RefutationSearchTool(
    pubmed_tool=pubmed_tool,
    semantic_scholar_tool=semantic_tool,
    max_results=settings.refutation_max_results,
    min_quality_score=settings.refutation_min_quality_score
)

self.limitations_extractor = LimitationsExtractor(
    min_confidence=settings.limitations_min_confidence
)
```

### 3. Add async _search_for_refutation Method
```python
async def _search_for_refutation(
    self,
    hypothesis: "Hypothesis"
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Search for evidence that contradicts the hypothesis.

    Args:
        hypothesis: Hypothesis object to find refutations for

    Returns:
        Tuple of (contradictions list, retraction_status dict)
    """
    if not settings.enable_refutation_search:
        return [], {}

    # Extract core claim from hypothesis statement
    core_claim = hypothesis.hypothesis_statement[:200]  # First 200 chars as core claim

    # Search for contradictions
    contradictions = await self.refutation_tool.search_contradictions(
        hypothesis_statement=hypothesis.hypothesis_statement,
        core_claim=core_claim
    )

    # Check retractions for each contradiction
    retraction_status = {}
    if settings.refutation_check_retractions:
        for paper in contradictions:
            if paper.get('pmid'):
                status = await self.refutation_tool.check_retractions(paper)
                retraction_status[paper.get('title', 'Unknown')] = status

    self.logger.info(
        "Refutation search complete",
        hypothesis_id=hypothesis.id,
        contradictions_found=len(contradictions),
        retractions_checked=len(retraction_status)
    )

    return contradictions, retraction_status
```

### 4. Add async _check_citation_retractions Method
```python
async def _check_citation_retractions(
    self,
    hypothesis: "Hypothesis"
) -> Dict[str, Dict[str, Any]]:
    """
    Check if any supporting citations have been retracted.

    Args:
        hypothesis: Hypothesis with literature_citations

    Returns:
        Dict mapping citation title to retraction status
    """
    if not settings.refutation_check_retractions:
        return {}

    retraction_status = {}

    for citation in hypothesis.literature_citations:
        # Need PMID to check retractions - try to extract from DOI
        paper_dict = {
            'title': citation.title,
            'doi': citation.doi,
            'pmid': None  # Would need lookup to get PMID from DOI
        }

        # Only check if we have some identifier
        if citation.doi:
            try:
                status = await self.refutation_tool.check_retractions(paper_dict)
                retraction_status[citation.title] = status
            except Exception as e:
                self.logger.warning(
                    "Retraction check failed",
                    citation=citation.title,
                    error=str(e)
                )

    return retraction_status
```

### 5. Add _format_refutation_context Method
```python
def _format_refutation_context(
    self,
    contradictions: List[Dict[str, Any]],
    retraction_status: Dict[str, Dict[str, Any]],
    citation_retractions: Dict[str, Dict[str, Any]]
) -> str:
    """
    Format all refutation evidence for LLM review context.

    Args:
        contradictions: Found contradictory papers
        retraction_status: Retraction info for contradictions
        citation_retractions: Retraction info for hypothesis citations

    Returns:
        Formatted warning string for LLM prompt
    """
    parts = []

    # Format contradictions
    contradiction_context = self.refutation_tool.format_contradictions_for_context(
        contradictions,
        retraction_status
    )
    if contradiction_context:
        parts.append(contradiction_context)

    # Add warnings for retracted supporting citations
    retracted_citations = [
        title for title, status in citation_retractions.items()
        if status.get('is_retracted')
    ]

    if retracted_citations:
        parts.append(
            f"\nWARNING: {len(retracted_citations)} supporting citation(s) have been RETRACTED:\n" +
            "\n".join(f"  - {title}" for title in retracted_citations)
        )

    return "\n\n".join(parts) if parts else ""
```

### 6. Convert execute Method to Async
Change `def execute(` to `async def execute(` and add refutation search:

After the existing prompt creation and before LLM invocation:

```python
# Phase 6: Search for refutation evidence
refutation_context = ""
if settings.enable_refutation_search:
    contradictions, retraction_status = await self._search_for_refutation(hypothesis)
    citation_retractions = await self._check_citation_retractions(hypothesis)

    refutation_context = self._format_refutation_context(
        contradictions,
        retraction_status,
        citation_retractions
    )

# Add refutation context to prompt if found
if refutation_context:
    structured_prompt = f"""{prompt}

COUNTER-EVIDENCE TO CONSIDER:
{refutation_context}

When scoring, account for any contradictory evidence or retracted citations above.

{structured_output_instruction}"""
else:
    structured_prompt = f"""{prompt}

{structured_output_instruction}"""
```

Where `structured_output_instruction` is the existing JSON schema instruction.

### 7. Update Callers (if needed)
Note: If `execute()` becomes async, callers must use `await`. Check:
- `src/graphs/workflow.py`
- Any tests calling `execute()`

## Verification Commands
After modifying, run:
```bash
python -c "from src.agents.reflection import ReflectionAgent; r = ReflectionAgent(); print('Init OK')"
python -m py_compile src/agents/reflection.py
python -m pytest 05_tests/phase6_reflection_integration_test.py -v --tb=short
```

## Important
- Maintain backward compatibility - existing functionality must still work
- Use `settings.enable_*` flags to control features
- Handle async properly throughout
- Log all refutation-related operations
- Handle edge cases (empty citations, API failures)

When complete, commit your changes to this worktree branch.
