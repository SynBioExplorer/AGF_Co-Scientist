# Task: task-reflection-tests

## Objective
Create integration tests for ReflectionAgent Phase 6 features.

## Context
You are working in a git worktree for this task. The Phase 6 features have been implemented:
- `src/tools/refutation_search.py` - RefutationSearchTool
- `src/literature/limitations_extractor.py` - LimitationsExtractor

The contract is defined in `contracts/evidence_quality_interface.py`.

## Requirements

Create `05_tests/phase6_reflection_integration_test.py` that tests:

1. **Refutation Search Integration**
   - Test that `_search_for_refutation()` calls RefutationSearchTool correctly
   - Test that contradictory evidence is found for hypothesis claims
   - Test that results are properly formatted

2. **Citation Retraction Checking**
   - Test that `_check_citation_retractions()` checks each citation with PMID
   - Test that retraction status is properly returned
   - Test handling of citations without PMIDs

3. **Refutation Context Formatting**
   - Test that `_format_refutation_context()` formats warnings correctly
   - Test that "CONTRADICTORY EVIDENCE FOUND" appears when contradictions exist
   - Test that "RETRACTED" warnings appear for retracted citations

4. **Configuration Flags**
   - Test that `enable_refutation_search` flag controls behavior
   - Test that refutation search is skipped when disabled

5. **Async Method Tests**
   - Test async execution of refutation methods
   - Use pytest-asyncio markers

6. **Mock Tests (no LLM/API calls)**
   - Mock the tool registry and tools
   - Mock PubMed and Semantic Scholar responses
   - Focus on testing integration logic

## File to Create
`05_tests/phase6_reflection_integration_test.py`

## Reference Files
- `05_tests/phase6_refutation_test.py` - Refutation search tests (use mock patterns)
- `05_tests/phase6_integration_test.py` - Existing integration tests
- `src/agents/reflection.py` - Current ReflectionAgent implementation
- `src/tools/refutation_search.py` - RefutationSearchTool
- `contracts/evidence_quality_interface.py` - Interface contract

## Verification Commands
After creating the test file, verify:
```bash
python -m py_compile 05_tests/phase6_reflection_integration_test.py
python -m pytest 05_tests/phase6_reflection_integration_test.py --collect-only
```

## Important
- Do NOT modify `src/agents/reflection.py` - that's a different task
- Only create the test file
- Use pytest fixtures and classes similar to existing test files
- Use `@pytest.mark.asyncio` for async tests
- Include a `run_tests()` function at the bottom for standalone execution

When complete, commit your changes to this worktree branch.
