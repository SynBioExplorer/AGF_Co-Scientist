# Task: task-generation-tests

## Objective
Create integration tests for GenerationAgent Phase 6 features.

## Context
You are working in a git worktree for this task. The Phase 6 features have been implemented:
- `src/literature/quality_scorer.py` - PaperQualityScorer
- `src/literature/limitations_extractor.py` - LimitationsExtractor

The contract is defined in `contracts/evidence_quality_interface.py`.

## Requirements

Create `05_tests/phase6_generation_integration_test.py` that tests:

1. **Quality Scoring Integration**
   - Test that `_enrich_papers_with_quality()` scores papers correctly
   - Test that papers below threshold are filtered out
   - Test that papers are ranked by quality (highest first)

2. **Quality Labels in Context**
   - Test that `[QUALITY: HIGH]`, `[QUALITY: MEDIUM]`, `[QUALITY: LOW]` labels appear in formatted context
   - Test that retracted papers are excluded from context

3. **Limitations Extraction Integration**
   - Test that `_extract_paper_limitations()` extracts limitations
   - Test that limitations appear in LLM context when enabled
   - Test that limitations are skipped when `enable_limitations_extraction=False`

4. **Configuration Flags**
   - Test that `enable_quality_scoring` flag controls behavior
   - Test that `quality_min_threshold` is respected

5. **Mock Tests (no LLM calls)**
   - Use MockCitationNode objects (see existing tests for pattern)
   - Mock the LLM client to avoid API calls
   - Focus on testing the integration logic, not the LLM response

## File to Create
`05_tests/phase6_generation_integration_test.py`

## Reference Files
- `05_tests/phase6_quality_scoring_test.py` - Quality scorer tests (use MockCitationNode pattern)
- `05_tests/phase6_limitations_test.py` - Limitations tests
- `05_tests/phase6_integration_test.py` - Existing integration tests
- `src/agents/generation.py` - Current GenerationAgent implementation
- `contracts/evidence_quality_interface.py` - Interface contract

## Verification Commands
After creating the test file, verify:
```bash
python -m py_compile 05_tests/phase6_generation_integration_test.py
python -m pytest 05_tests/phase6_generation_integration_test.py --collect-only
```

## Important
- Do NOT modify `src/agents/generation.py` - that's a different task
- Only create the test file
- Use pytest fixtures and classes similar to existing test files
- Include a `run_tests()` function at the bottom for standalone execution

When complete, commit your changes to this worktree branch.
