"""LLM Client Factory - Centralized provider selection"""

from typing import Literal, Optional

from src.llm.base import BaseLLMClient
from src.llm.google import GoogleGeminiClient
from src.llm.openai import OpenAIClient
from src.utils.errors import CoScientistError

# Provider literals -- aliases included so existing code that passes
# "google" still works alongside new "gemini" / "deepseek" / "anthropic" /
# "claude" / "gpt" paths used by per-agent configs.
LLMProvider = Literal[
    "google", "gemini", "openai", "gpt", "deepseek", "anthropic", "claude"
]

# Per-agent thinking-budget overrides for Gemini. Rationale: ranking and
# proximity emit structured JSON only (no reasoning trace is parsed); initial
# reflection is a pass/fail screen. Generation/meta-review benefit from
# unconstrained reasoning so we leave them None.
_THINKING_BUDGET_BY_AGENT = {
    "ranking": 0,
    "proximity": 0,
    "safety": 0,
    "reflection": 512,
    "observation_review": 512,
    "evolution": 1024,
    # generation, meta_review, supervisor: None (unconstrained)
}


def _normalize(provider: str) -> str:
    p = (provider or "").strip().lower()
    mapping = {
        "google": "google",
        "gemini": "google",
        "openai": "openai",
        "gpt": "openai",
        "deepseek": "deepseek",
        "anthropic": "anthropic",
        "claude": "anthropic",
    }
    if p not in mapping:
        raise CoScientistError(
            f"Unsupported LLM provider: {provider!r}. "
            f"Supported: google/gemini, openai/gpt, deepseek, anthropic/claude"
        )
    return mapping[p]


class LLMFactory:
    """Factory for creating LLM clients based on provider configuration"""

    @staticmethod
    def create_client(
        provider: str,
        model: str,
        agent_name: str,
        thinking_budget: Optional[int] = None,
        temperature: float = 0.7,
    ) -> BaseLLMClient:
        canonical = _normalize(provider)

        if canonical == "google":
            return GoogleGeminiClient(
                model=model,
                agent_name=agent_name,
                thinking_budget=thinking_budget,
            )
        if canonical == "openai":
            return OpenAIClient(model=model, agent_name=agent_name)
        if canonical == "deepseek":
            from src.llm.deepseek_client import DeepSeekClient

            return DeepSeekClient(
                model=model,
                agent_name=agent_name,
                temperature=temperature,
            )
        if canonical == "anthropic":
            from src.llm.anthropic_client import AnthropicClient

            return AnthropicClient(
                model=model,
                agent_name=agent_name,
                temperature=temperature,
            )
        raise CoScientistError(f"Unsupported LLM provider: {provider}")


def get_llm_client(model: str, agent_name: str) -> BaseLLMClient:
    """Return an LLM client honoring (in order of priority):

        1. The per-agent configuration stored in ``agent_models`` (Phase A).
        2. The global ``settings.llm_provider``.

    Args:
        model: Model name preferred by the caller. Overridden by per-agent
            config if one is set.
        agent_name: Used for cost tracking and per-agent config lookup.
    """
    from src.config import settings

    # Try per-agent config first (Phase A onboarding).
    try:
        from src.config.agent_models import get_agent_runtime_config

        cfg = get_agent_runtime_config(agent_name)
    except Exception:
        cfg = None

    if cfg:
        provider = cfg.get("provider") or settings.llm_provider
        resolved_model = cfg.get("model") or model
        temperature = float(cfg.get("temperature", 0.7))
    else:
        provider = settings.llm_provider
        resolved_model = model
        temperature = 0.7

    canonical = _normalize(provider)
    thinking_budget = (
        _THINKING_BUDGET_BY_AGENT.get(agent_name) if canonical == "google" else None
    )

    return LLMFactory.create_client(
        provider=provider,
        model=resolved_model,
        agent_name=agent_name,
        thinking_budget=thinking_budget,
        temperature=temperature,
    )
