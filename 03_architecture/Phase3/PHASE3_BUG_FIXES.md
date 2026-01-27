# Phase 3: Bug Fixes & Schema Alignment

## Overview

Documentation of critical bugs identified and fixed during Phase 3 development, ensuring system stability and correctness.

**Status:** ✅ All Fixed

## Bug Summary

| Bug | File | Impact | Status |
|-----|------|--------|--------|
| Elo Rating Mismatch | `src/agents/generation.py` | Wrong initial rating | ✅ Fixed |
| Prompt Template Typo | `02_Prompts/05_*.txt` | KeyError in debates | ✅ Fixed |
| Missing Transcript Param | `src/prompts/loader.py` | KeyError in debates | ✅ Fixed |
| Invalid JSON Escapes | Multiple agents | Parse failures | ✅ Fixed |
| ResearchOverview Schema | `src/agents/meta_review.py` | Validation errors | ✅ Fixed |

---

## Bug 1: Elo Rating Mismatch

### Problem
Code used initial Elo rating of 1500.0, but Google paper specifies 1200.0.

### Location
`src/agents/generation.py:141`

### Google Paper Reference
Section 3.3.3, page 11:
> "We set the initial Elo rating of 1200 for the newly added hypothesis"

### Fix
```python
# Before
return Hypothesis(
    ...
    elo_rating=1500.0,  # WRONG
    ...
)

# After
return Hypothesis(
    ...
    elo_rating=1200.0,  # Google paper specification (p.11)
    ...
)
```

---

## Bug 2: Prompt Template Typo

### Problem
Ranking debate prompt used `{review1}` instead of `{review 1}` (with space).

### Location
`02_Prompts/05_Ranking_Agent_Hypothesis_Comparison_Scientific_Debate.txt:22`

### Impact
Would cause `KeyError` when using debate ranking method since the loader uses keys with spaces.

### Fix
```
# Before
{review1}

# After
{review 1}
```

---

## Bug 3: Missing Transcript Parameter

### Problem
Debate generation prompt uses `{transcript}` variable but loader didn't provide it.

### Location
`src/prompts/loader.py:38-52`

### Impact
Would cause `KeyError` when using debate generation method.

### Fix
```python
# Before
def get_generation_debate_prompt(
    self,
    goal: str,
    preferences: str,
    notes: str
) -> str:

# After
def get_generation_debate_prompt(
    self,
    goal: str,
    preferences: str,
    notes: str,
    transcript: str = ""  # New parameter
) -> str:
    if not transcript:
        transcript = "No prior debate transcript available."
    # ...
```

---

## Bug 4: Invalid JSON Escape Sequences

### Problem
LLM responses sometimes contain invalid escape sequences (e.g., `\e`, `\K`) causing `json.JSONDecodeError`.

### Impact
Hypothesis generation would fail with "Invalid \escape" error.

### Solution
Created `src/utils/json_parser.py` with `parse_llm_json()` function that:
1. Extracts JSON from markdown code blocks
2. Attempts standard parsing first
3. Falls back to regex-based escape sequence cleanup if needed

### Implementation
```python
def _fix_escape_sequences(text: str) -> str:
    """Fix invalid JSON escape sequences"""
    # Pattern matches backslash NOT followed by valid escape chars
    pattern = r'\\(?!["\\/bfnrtu])'
    return re.sub(pattern, r'\\\\', text)
```

See [PHASE3_JSON_PARSER.md](PHASE3_JSON_PARSER.md) for full details.

---

## Bug 5: ResearchOverview Schema Alignment

### Problem
`ResearchOverview` constructor was missing required fields, causing Pydantic validation errors.

### Missing Fields
- `id` - Not generated
- `research_goal_id` - Not passed
- `executive_summary` - Prompt used `summary` instead
- `current_knowledge_boundary` - Not in prompt

### Location
`src/agents/meta_review.py:119-236`

### Fix

1. **Updated LLM prompt to use exact field names:**
```python
prompt = f"""
...
Return JSON:
{{
    "executive_summary": "Overview paragraph",
    "current_knowledge_boundary": "What is known and gaps",
    ...
}}
"""
```

2. **Added ID generation:**
```python
from src.utils.ids import generate_id

overview = ResearchOverview(
    id=generate_id("overview"),
    research_goal_id=research_goal_id,
    ...
)
```

3. **Updated method signature:**
```python
async def generate_research_overview(
    self,
    hypotheses: List[Hypothesis],
    reviews: List[Review],
    research_goal: ResearchGoal,
    research_goal_id: str  # New parameter
) -> ResearchOverview:
```

4. **Updated workflow and tests** to pass `research_goal_id`.

---

## Verification

All fixes verified through:

1. **Code inspection** - Manual review of changed files
2. **Grep verification** - Search for old patterns to ensure removal
3. **Test execution** - `test_phase3.py` passes
4. **Pydantic validation** - All schemas validate correctly

## Lessons Learned

1. **Match paper specifications exactly** - Elo rating of 1200, not arbitrary values
2. **Template variables need exact naming** - `{review 1}` not `{review1}`
3. **LLM output is unpredictable** - Need robust parsing with fallbacks
4. **Schema alignment is critical** - Pydantic field names must match exactly
5. **Default parameters prevent errors** - Provide sensible defaults for optional fields
