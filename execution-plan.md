# Execution Plan: Phase 6b Agent Integration

## Request Summary
Integrate Phase 6 evidence quality features (PaperQualityScorer, RefutationSearchTool, LimitationsExtractor) into GenerationAgent and ReflectionAgent.

## Validation Results

| Check | Status | Details |
|-------|--------|---------|
| DAG Validation | PASS | No cycles detected |
| Conflict Detection | PASS | No file/resource conflicts |
| Risk Score | 10 | AUTO-APPROVE (threshold: 25) |

## Execution Waves

### Wave 1 (Parallel - No Dependencies)

| Task ID | Description | Files | Verification |
|---------|-------------|-------|--------------|
| task-generation-tests | Create GenerationAgent integration tests | `05_tests/phase6_generation_integration_test.py` | Syntax check, test collection |
| task-reflection-tests | Create ReflectionAgent integration tests | `05_tests/phase6_reflection_integration_test.py` | Syntax check, test collection |

### Wave 2 (Parallel - After Wave 1)

| Task ID | Description | Files | Verification |
|---------|-------------|-------|--------------|
| task-generation-quality | Integrate quality scoring + limitations into GenerationAgent | `src/agents/generation.py` | Import check, syntax, unit tests |
| task-reflection-refutation | Integrate refutation search into ReflectionAgent | `src/agents/reflection.py` | Import check, syntax, unit tests |

## Contract

**EvidenceQualityEnhancementProtocol** (Version: 31f3178)
- File: `contracts/evidence_quality_interface.py`
- Defines interfaces for both agents to implement

### Key Methods

**GenerationAgent additions:**
- `_enrich_papers_with_quality(papers)` - Score and filter papers
- `_extract_paper_limitations(papers)` - Extract limitations for context

**ReflectionAgent additions:**
- `_search_for_refutation(hypothesis)` - Find contradictory evidence
- `_check_citation_retractions(hypothesis)` - Check for retracted citations
- `_format_refutation_context(...)` - Format counter-evidence for LLM

## Integration Details

### GenerationAgent Changes

```
src/agents/generation.py
+-------------------------------------------+
| NEW IMPORTS:                              |
| - PaperQualityScorer                      |
| - LimitationsExtractor                    |
| - settings (enable_quality_scoring, etc.) |
+-------------------------------------------+
| __init__():                               |
| + self.quality_scorer                     |
| + self.limitations_extractor              |
+-------------------------------------------+
| NEW METHOD: _enrich_papers_with_quality() |
| - Scores papers using quality_scorer      |
| - Filters below threshold                 |
| - Returns ranked list                     |
+-------------------------------------------+
| NEW METHOD: _extract_paper_limitations()  |
| - Batch extracts limitations              |
| - Formats for LLM context                 |
+-------------------------------------------+
| MODIFIED: _format_citation_graph_context()|
| - Adds [QUALITY: HIGH/MEDIUM/LOW] labels  |
| - Skips retracted papers                  |
+-------------------------------------------+
| MODIFIED: execute()                       |
| - Calls enrichment after search           |
| - Includes limitations in context         |
+-------------------------------------------+
```

### ReflectionAgent Changes

```
src/agents/reflection.py
+-------------------------------------------+
| NEW IMPORTS:                              |
| - RefutationSearchTool                    |
| - LimitationsExtractor                    |
| - initialize_tools, settings              |
+-------------------------------------------+
| __init__():                               |
| + self.tool_registry                      |
| + self.refutation_tool                    |
| + self.limitations_extractor              |
+-------------------------------------------+
| NEW METHOD: _search_for_refutation()      |
| - Extracts core claim                     |
| - Searches for contradictions             |
| - Returns (contradictions, retractions)   |
+-------------------------------------------+
| NEW METHOD: _check_citation_retractions() |
| - Checks PubMed for retractions           |
| - Returns status dict by citation         |
+-------------------------------------------+
| NEW METHOD: _format_refutation_context()  |
| - Formats contradictions as warnings      |
| - Includes limitations context            |
+-------------------------------------------+
| MODIFIED: execute() -> async              |
| - Performs refutation search if enabled   |
| - Appends counter-evidence to prompt      |
+-------------------------------------------+
```

## Risk Assessment

**Score: 10 (LOW RISK)**

Risk factors:
- Incomplete test coverage: 50% (mitigated by TDD approach)

Mitigations:
- Tests created BEFORE implementations (Wave 1 before Wave 2)
- Contract defines clear interfaces
- Phase 6 features already implemented and tested
- Configuration flags allow features to be disabled

## Estimated Timeline

| Wave | Tasks | Estimated Duration |
|------|-------|-------------------|
| Wave 1 | 2 test files | ~10 minutes |
| Wave 2 | 2 agent modifications | ~30 minutes |
| **Total** | 4 tasks | ~45 minutes |

## Approval Status

**AUTO-APPROVED** (Risk Score 10 <= Threshold 25)

Ready to proceed with execution.
