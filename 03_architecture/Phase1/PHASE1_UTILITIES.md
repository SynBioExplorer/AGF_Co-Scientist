# Phase 1: Utility Modules

## Overview

Core utility modules providing ID generation, structured logging, and custom exception handling across the entire system.

**Location:** `src/utils/`
**Status:** ✅ Complete

## Components

### 1. ID Generation (`src/utils/ids.py`)

Generates unique, sortable IDs for all system entities.

```python
import uuid
from datetime import datetime

def generate_id(prefix: str) -> str:
    """Generate unique ID with format: prefix_YYYYMMDD_random"""
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = uuid.uuid4().hex[:8]
    return f"{prefix}_{date_str}_{random_str}"

# Convenience functions
def generate_hypothesis_id() -> str:
    return generate_id("hyp")

def generate_review_id() -> str:
    return generate_id("rev")

def generate_match_id() -> str:
    return generate_id("match")

def generate_task_id() -> str:
    return generate_id("task")
```

**Format:** `{prefix}_{YYYYMMDD}_{random8}`

**Examples:**
- `hyp_20260122_a1b2c3d4` - Hypothesis
- `rev_20260122_e5f6g7h8` - Review
- `match_20260122_i9j0k1l2` - Tournament match

### 2. Structured Logging (`src/utils/logging_config.py`)

JSON-formatted structured logging via structlog.

```python
import structlog
import logging

def configure_logging(level: str = "INFO"):
    """Configure structured logging"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper())
    )

def get_logger(name: str = None):
    """Get configured logger"""
    return structlog.get_logger(name)
```

**Usage:**
```python
from src.utils.logging_config import get_logger

logger = get_logger("generation_agent")
logger.info("Hypothesis generated", hypothesis_id="hyp_123", elo=1200.0)
```

**Output:**
```json
{
    "event": "Hypothesis generated",
    "hypothesis_id": "hyp_123",
    "elo": 1200.0,
    "timestamp": "2026-01-22T10:30:00Z",
    "level": "info",
    "logger": "generation_agent"
}
```

### 3. Custom Exceptions (`src/utils/errors.py`)

Hierarchy of custom exceptions for error handling.

```python
class CoScientistError(Exception):
    """Base exception for all co-scientist errors"""
    pass

class BudgetExceededError(CoScientistError):
    """Raised when API budget is exhausted"""
    def __init__(self, spent: float, budget: float):
        self.spent = spent
        self.budget = budget
        super().__init__(f"Budget exceeded: ${spent:.2f} of ${budget:.2f}")

class ValidationError(CoScientistError):
    """Raised when data validation fails"""
    pass

class LLMResponseError(CoScientistError):
    """Raised when LLM returns invalid response"""
    pass

class PromptLoadError(CoScientistError):
    """Raised when prompt file cannot be loaded"""
    pass

class StorageError(CoScientistError):
    """Raised when storage operation fails"""
    pass

class AgentExecutionError(CoScientistError):
    """Raised when agent execution fails"""
    pass
```

**Usage:**
```python
from src.utils.errors import BudgetExceededError

if tracker.spent > tracker.budget:
    raise BudgetExceededError(tracker.spent, tracker.budget)
```

## File Structure

```
src/utils/
├── __init__.py           # Package exports
├── ids.py                # ID generation
├── logging_config.py     # Structured logging
└── errors.py             # Custom exceptions
```

## Dependencies

- `structlog>=24.0.0` - Structured logging

## Package Exports

```python
# src/utils/__init__.py
from .ids import (
    generate_id,
    generate_hypothesis_id,
    generate_review_id,
    generate_match_id,
    generate_task_id
)
from .logging_config import configure_logging, get_logger
from .errors import (
    CoScientistError,
    BudgetExceededError,
    ValidationError,
    LLMResponseError,
    PromptLoadError,
    StorageError,
    AgentExecutionError
)
```

## Testing

```python
def test_id_generation():
    """Test ID format"""
    hyp_id = generate_hypothesis_id()
    assert hyp_id.startswith("hyp_")
    assert len(hyp_id) == 21  # hyp_ + 8 date + _ + 8 random

def test_unique_ids():
    """Test IDs are unique"""
    ids = [generate_hypothesis_id() for _ in range(1000)]
    assert len(set(ids)) == 1000

def test_budget_error():
    """Test budget exception"""
    with pytest.raises(BudgetExceededError) as exc:
        raise BudgetExceededError(spent=55.0, budget=50.0)
    assert exc.value.spent == 55.0
```
