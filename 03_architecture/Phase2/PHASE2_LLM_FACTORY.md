# Phase 2: LLM Factory Pattern

## Overview

Centralized provider selection enabling one-line switching between Google Gemini and OpenAI GPT across all agents.

**File:** `src/llm/factory.py`
**Status:** ✅ Complete

## Implementation

```python
from typing import Literal
from src.llm.base import BaseLLMClient
from src.llm.google import GoogleLLMClient
from src.llm.openai import OpenAILLMClient
from src.config import settings
import structlog

logger = structlog.get_logger()

class LLMFactory:
    """Factory for creating LLM clients based on provider"""

    @staticmethod
    def create_client(
        provider: Literal["google", "openai"],
        model: str,
        agent_name: str
    ) -> BaseLLMClient:
        """Create LLM client for specified provider

        Args:
            provider: "google" or "openai"
            model: Model name
            agent_name: Name for cost tracking

        Returns:
            Configured LLM client
        """
        if provider == "google":
            return GoogleLLMClient(
                model=model,
                agent_name=agent_name,
                api_key=settings.google_api_key
            )
        elif provider == "openai":
            return OpenAILLMClient(
                model=model,
                agent_name=agent_name,
                api_key=settings.openai_api_key
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")


def get_llm_client(
    model: str = None,
    agent_name: str = "unknown"
) -> BaseLLMClient:
    """Convenience function using global config

    Args:
        model: Optional model override
        agent_name: Name for cost tracking

    Returns:
        LLM client for configured provider
    """
    provider = settings.llm_provider

    # Use provider-specific model if not specified
    if model is None:
        if provider == "google":
            model = settings.google_generation_model
        else:
            model = settings.openai_generation_model

    logger.info(
        "Creating LLM client",
        provider=provider,
        model=model,
        agent=agent_name
    )

    return LLMFactory.create_client(provider, model, agent_name)
```

## Configuration

```python
# src/config.py additions

class Settings(BaseSettings):
    # Provider selection
    llm_provider: Literal["google", "openai"] = "google"

    # Google models
    google_generation_model: str = "gemini-2.0-flash-exp"
    google_reflection_model: str = "gemini-2.0-flash-exp"
    google_ranking_model: str = "gemini-2.0-flash-exp"

    # OpenAI models
    openai_generation_model: str = "gpt-4-turbo-preview"
    openai_reflection_model: str = "gpt-4-turbo-preview"
    openai_ranking_model: str = "gpt-4-turbo-preview"

    @property
    def generation_model(self) -> str:
        """Return model based on active provider"""
        if self.llm_provider == "google":
            return self.google_generation_model
        return self.openai_generation_model

    @property
    def reflection_model(self) -> str:
        if self.llm_provider == "google":
            return self.google_reflection_model
        return self.openai_reflection_model

    @property
    def ranking_model(self) -> str:
        if self.llm_provider == "google":
            return self.google_ranking_model
        return self.openai_ranking_model
```

## Provider Switching

Change ONE environment variable:

```bash
# Switch to OpenAI
LLM_PROVIDER=openai

# Switch to Google
LLM_PROVIDER=google
```

All agents automatically use the correct provider and model.

## Usage in Agents

```python
from src.llm.factory import get_llm_client

class GenerationAgent(BaseAgent):
    def __init__(self):
        # Automatically uses configured provider
        llm_client = get_llm_client(
            model=settings.generation_model,
            agent_name="generation"
        )
        super().__init__(llm_client, "GenerationAgent")

class ReflectionAgent(BaseAgent):
    def __init__(self):
        llm_client = get_llm_client(
            model=settings.reflection_model,
            agent_name="reflection"
        )
        super().__init__(llm_client, "ReflectionAgent")
```

## Benefits

1. **Single Point of Control** - One variable changes all agents
2. **Cost Tracking** - Agent name passed for accurate tracking
3. **Model Flexibility** - Different models per agent if needed
4. **Easy Testing** - Swap providers for comparison testing

## Testing

```python
def test_factory_google():
    """Test Google client creation"""
    from src.config import settings
    settings.llm_provider = "google"

    client = get_llm_client(agent_name="test")
    assert isinstance(client, GoogleLLMClient)

def test_factory_openai():
    """Test OpenAI client creation"""
    from src.config import settings
    settings.llm_provider = "openai"

    client = get_llm_client(agent_name="test")
    assert isinstance(client, OpenAILLMClient)

def test_provider_switch():
    """Test switching providers"""
    # Start with Google
    settings.llm_provider = "google"
    client1 = get_llm_client()
    assert isinstance(client1, GoogleLLMClient)

    # Switch to OpenAI
    settings.llm_provider = "openai"
    client2 = get_llm_client()
    assert isinstance(client2, OpenAILLMClient)
```
