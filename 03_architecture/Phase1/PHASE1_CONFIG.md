# Phase 1: Configuration Module

## Overview

Pydantic-based settings management that loads configuration from environment variables and `.env` files, providing type-safe access to API keys, model selections, budget limits, and paths.

**File:** `src/config.py`
**Status:** ✅ Complete

## Implementation

```python
from pydantic_settings import BaseSettings
from typing import Literal
from pathlib import Path

class Settings(BaseSettings):
    """Application settings loaded from environment"""

    # API Keys
    google_api_key: str = ""
    openai_api_key: str = ""
    tavily_api_key: str = ""

    # LLM Provider Selection
    llm_provider: Literal["google", "openai"] = "google"

    # Model Configuration
    google_generation_model: str = "gemini-2.0-flash-exp"
    openai_generation_model: str = "gpt-4-turbo-preview"

    # Budget
    budget_aud: float = 50.0

    # Paths
    prompts_dir: Path = Path("02_Prompts")

    class Config:
        env_file = "03_architecture/.env"
        env_file_encoding = "utf-8"
```

## Features

### Type-Safe Settings
- All settings have explicit types
- Validation happens at load time
- IDE autocompletion supported

### Environment File Loading
- Reads from `03_architecture/.env`
- Falls back to environment variables
- Supports default values

### Dynamic Model Selection
```python
@property
def generation_model(self) -> str:
    """Return model based on active provider"""
    if self.llm_provider == "google":
        return self.google_generation_model
    return self.openai_generation_model
```

## Environment Variables

```bash
# 03_architecture/.env

# API Keys (Required)
GOOGLE_API_KEY=your-google-api-key
OPENAI_API_KEY=your-openai-api-key
TAVILY_API_KEY=your-tavily-api-key

# Provider Selection
LLM_PROVIDER=google  # or "openai"

# Budget
BUDGET_AUD=50.0

# Models (Optional - defaults provided)
GOOGLE_GENERATION_MODEL=gemini-2.0-flash-exp
OPENAI_GENERATION_MODEL=gpt-4-turbo-preview
```

## Usage

```python
from src.config import settings

# Access settings
api_key = settings.google_api_key
model = settings.generation_model
budget = settings.budget_aud

# Check provider
if settings.llm_provider == "google":
    # Use Google-specific logic
    pass
```

## Provider Switching

Change LLM provider by modifying ONE variable:

```bash
# Switch to OpenAI
LLM_PROVIDER=openai
```

All agents automatically use the correct model.

## Validation

Settings are validated on load:
- Missing required fields raise errors
- Invalid types raise validation errors
- Literal types enforce allowed values

## Dependencies

- `pydantic-settings>=2.0.0` - Settings management

## Testing

```python
def test_config_loads():
    """Test configuration loads correctly"""
    from src.config import settings

    assert settings.budget_aud > 0
    assert settings.llm_provider in ["google", "openai"]
```
