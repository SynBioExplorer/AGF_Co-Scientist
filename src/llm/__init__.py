"""LLM clients and factory for AGF Co-Scientist.

Exposes ``create_llm_client(provider, model, agent_name, ...)`` which
returns the right client class for one of the four supported providers:

    - "gemini" / "google"       -> :class:`GoogleGeminiClient`
    - "openai" / "gpt"           -> :class:`OpenAIClient`
    - "deepseek"                 -> :class:`DeepSeekClient`
    - "anthropic" / "claude"     -> :class:`AnthropicClient`

The :data:`HARDCODED_MODELS` mapping is used as a fallback when a remote
"list models" call fails. It is also the source of truth for the
``GET /api/settings/available-models`` endpoint.
"""

from __future__ import annotations

from typing import Optional

from src.llm.base import BaseLLMClient

# Canonical provider name -> default model + available models.
HARDCODED_MODELS: dict[str, dict] = {
    "gemini": {
        "default": "gemini-2.5-pro",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash-exp"],
    },
    "openai": {
        "default": "gpt-5",
        "models": ["gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini", "o3-mini"],
    },
    "deepseek": {
        "default": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "anthropic": {
        "default": "claude-sonnet-4-5",
        "models": ["claude-opus-4-1", "claude-sonnet-4-5", "claude-haiku-4-5"],
    },
}

# Aliases accepted by create_llm_client / normalize_provider.
_ALIASES = {
    "gemini": "gemini",
    "google": "gemini",
    "openai": "openai",
    "gpt": "openai",
    "deepseek": "deepseek",
    "anthropic": "anthropic",
    "claude": "anthropic",
}


def normalize_provider(provider: str) -> str:
    """Return the canonical provider name for an alias, or raise."""
    key = (provider or "").strip().lower()
    if key not in _ALIASES:
        raise ValueError(
            f"Unsupported LLM provider: {provider!r}. "
            f"Valid: {sorted(set(_ALIASES.values()))}"
        )
    return _ALIASES[key]


def get_available_models(provider: str) -> list[str]:
    """Return the hardcoded list of models for a provider."""
    return list(HARDCODED_MODELS[normalize_provider(provider)]["models"])


def get_default_model(provider: str) -> str:
    return HARDCODED_MODELS[normalize_provider(provider)]["default"]


def create_llm_client(
    provider: str,
    model: Optional[str] = None,
    agent_name: str = "default",
    temperature: float = 0.7,
    thinking_budget: Optional[int] = None,
    api_key: Optional[str] = None,
) -> BaseLLMClient:
    """Create an LLM client by provider name.

    Args:
        provider: ``"gemini" | "openai" | "deepseek" | "anthropic"`` (aliases
            ``"google"``, ``"gpt"``, ``"claude"`` are also accepted).
        model: Specific model name. If ``None``, uses the provider default.
        agent_name: Used for cost-tracking attribution.
        temperature: Sampling temperature.
        thinking_budget: Gemini-only -- cap on reasoning tokens.
        api_key: Override; otherwise read from env / settings.
    """
    canonical = normalize_provider(provider)
    if model is None:
        model = get_default_model(canonical)

    if canonical == "gemini":
        from src.llm.google import GoogleGeminiClient

        return GoogleGeminiClient(
            model=model,
            agent_name=agent_name,
            thinking_budget=thinking_budget,
        )
    if canonical == "openai":
        from src.llm.openai import OpenAIClient

        return OpenAIClient(model=model, agent_name=agent_name)
    if canonical == "deepseek":
        from src.llm.deepseek_client import DeepSeekClient

        return DeepSeekClient(
            model=model,
            agent_name=agent_name,
            temperature=temperature,
            api_key=api_key,
        )
    if canonical == "anthropic":
        from src.llm.anthropic_client import AnthropicClient

        return AnthropicClient(
            model=model,
            agent_name=agent_name,
            temperature=temperature,
            api_key=api_key,
        )
    raise ValueError(f"Unsupported provider: {canonical}")


__all__ = [
    "BaseLLMClient",
    "HARDCODED_MODELS",
    "normalize_provider",
    "get_available_models",
    "get_default_model",
    "create_llm_client",
]
