# Phase 3: Robust JSON Parser

## Overview

Utility for parsing JSON from LLM responses, handling common issues like markdown code blocks and invalid escape sequences.

**File:** `src/utils/json_parser.py`
**Status:** ✅ Complete

## Problem

LLM responses often contain:
1. JSON wrapped in markdown code blocks
2. Invalid escape sequences (e.g., `\e`, `\K`, `\S`)
3. Trailing commas or other minor syntax issues

Standard `json.loads()` fails on these inputs.

## Implementation

```python
import json
import re
from typing import Any, Dict

def parse_llm_json(response: str) -> Dict[str, Any]:
    """Parse JSON from LLM response with error recovery

    Handles:
    - Markdown code blocks (```json ... ```)
    - Invalid escape sequences
    - Common JSON syntax issues

    Args:
        response: Raw LLM response text

    Returns:
        Parsed JSON as dictionary

    Raises:
        json.JSONDecodeError: If parsing fails after all recovery attempts
    """
    # Step 1: Extract JSON from markdown code blocks
    text = _extract_json_block(response)

    # Step 2: Try standard parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Step 3: Fix invalid escape sequences
    text = _fix_escape_sequences(text)

    # Step 4: Try parsing again
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Log the error for debugging
        import structlog
        logger = structlog.get_logger()
        logger.warning(
            "JSON parsing failed",
            error=str(e),
            text_preview=text[:200]
        )
        raise

def _extract_json_block(text: str) -> str:
    """Extract JSON from markdown code blocks"""
    # Pattern: ```json ... ``` or ``` ... ```
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()

    # No code block found, return as-is
    return text.strip()

def _fix_escape_sequences(text: str) -> str:
    """Fix invalid JSON escape sequences

    JSON only allows: \" \\ \/ \b \f \n \r \t \uXXXX
    Other backslash sequences like \e \K \S are invalid
    """
    # Pattern matches backslash NOT followed by valid escape chars
    # Valid: " \ / b f n r t u
    pattern = r'\\(?!["\\/bfnrtu])'

    # Replace invalid escapes with escaped backslash
    return re.sub(pattern, r'\\\\', text)
```

## Valid JSON Escapes

| Escape | Meaning |
|--------|---------|
| `\"` | Double quote |
| `\\` | Backslash |
| `\/` | Forward slash |
| `\b` | Backspace |
| `\f` | Form feed |
| `\n` | Newline |
| `\r` | Carriage return |
| `\t` | Tab |
| `\uXXXX` | Unicode character |

## Common Invalid Escapes from LLMs

| Invalid | Appears In | Fix |
|---------|-----------|-----|
| `\e` | Scientific notation | `\\e` |
| `\K` | Regex patterns | `\\K` |
| `\S` | Regex patterns | `\\S` |
| `\d` | Regex/digits | `\\d` |

## Usage

```python
from src.utils.json_parser import parse_llm_json

# Raw LLM response with code block
response = '''
Here's my analysis:

```json
{
    "title": "Test Hypothesis",
    "mechanism": "Uses \\Kras pathway"
}
```

This hypothesis focuses on...
'''

# Parse successfully despite invalid \K escape
data = parse_llm_json(response)
print(data["title"])  # "Test Hypothesis"
```

## Integration

Used throughout the agent codebase:

```python
# In src/agents/generation.py
from src.utils.json_parser import parse_llm_json

response = await self.llm_client.generate(prompt)
data = parse_llm_json(response)  # Safe parsing

hypothesis = Hypothesis(
    title=data.get("title", ""),
    # ...
)
```

## Error Handling

If parsing still fails after recovery attempts:

```python
try:
    data = parse_llm_json(response)
except json.JSONDecodeError as e:
    # Log and handle gracefully
    logger.error("Failed to parse LLM response", error=str(e))
    # Return default or raise custom exception
    raise LLMParseError(f"Could not parse response: {e}")
```

## Testing

```python
def test_parse_markdown_block():
    """Test extraction from markdown"""
    response = '```json\n{"key": "value"}\n```'
    result = parse_llm_json(response)
    assert result == {"key": "value"}

def test_fix_invalid_escapes():
    """Test invalid escape sequence handling"""
    response = '{"regex": "\\\\Kras \\\\S+"}'
    result = parse_llm_json(response)
    assert "regex" in result

def test_nested_json():
    """Test complex nested structures"""
    response = '''```json
    {
        "hypothesis": {
            "title": "Test",
            "protocol": {
                "steps": ["step1", "step2"]
            }
        }
    }
    ```'''
    result = parse_llm_json(response)
    assert result["hypothesis"]["protocol"]["steps"][0] == "step1"
```
