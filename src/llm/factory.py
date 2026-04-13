"""LLM Client Factory - Centralized provider selection"""

from typing import Literal, Optional
from src.llm.base import BaseLLMClient
from src.llm.google import GoogleGeminiClient
from src.llm.openai import OpenAIClient
from src.utils.errors import CoScientistError

LLMProvider = Literal["google", "openai"]

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


class LLMFactory:
    """Factory for creating LLM clients based on provider configuration"""

    @staticmethod
    def create_client(
        provider: LLMProvider,
        model: str,
        agent_name: str,
        thinking_budget: Optional[int] = None,
    ) -> BaseLLMClient:
        """Create an LLM client based on provider type

        Args:
            provider: "google" or "openai"
            model: Model name/identifier
            agent_name: Name of the agent using this client (for cost tracking)
            thinking_budget: Cap on Gemini reasoning tokens (Google provider only).

        Returns:
            BaseLLMClient instance (GoogleGeminiClient or OpenAIClient)

        Raises:
            CoScientistError: If provider is not supported
        """
        if provider == "google":
            return GoogleGeminiClient(
                model=model,
                agent_name=agent_name,
                thinking_budget=thinking_budget,
            )
        elif provider == "openai":
            return OpenAIClient(model=model, agent_name=agent_name)
        else:
            raise CoScientistError(
                f"Unsupported LLM provider: {provider}. "
                f"Supported providers: 'google', 'openai'"
            )


def get_llm_client(model: str, agent_name: str) -> BaseLLMClient:
    """Convenience function to get LLM client using global config

    Args:
        model: Model name/identifier
        agent_name: Name of the agent using this client

    Returns:
        BaseLLMClient instance based on settings.llm_provider
    """
    from src.config import settings
    thinking_budget = _THINKING_BUDGET_BY_AGENT.get(agent_name)
    return LLMFactory.create_client(
        provider=settings.llm_provider,
        model=model,
        agent_name=agent_name,
        thinking_budget=thinking_budget,
    )
