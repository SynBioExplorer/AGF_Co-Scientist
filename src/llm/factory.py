"""LLM Client Factory - Centralized provider selection"""

from typing import Literal, Optional
from src.llm.base import BaseLLMClient
from src.llm.google import GoogleGeminiClient
from src.llm.openai import OpenAIClient
from src.llm.bedrock import BedrockClient
from src.utils.errors import CoScientistError

LLMProvider = Literal["google", "openai", "bedrock"]

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
            provider: "google", "openai", or "bedrock"
            model: Model name or foundation-model ID (Bedrock maps it to its profile)
            agent_name: Name of the agent using this client (for cost tracking)
            thinking_budget: Cap on Gemini reasoning tokens; Bedrock maps 0 to Claude thinking off.

        Returns:
            BaseLLMClient instance.

        Raises:
            CoScientistError: If provider is not supported.
        """
        if provider == "google":
            return GoogleGeminiClient(
                model=model,
                agent_name=agent_name,
                thinking_budget=thinking_budget,
            )
        elif provider == "openai":
            return OpenAIClient(model=model, agent_name=agent_name)
        elif provider == "bedrock":
            return BedrockClient(model=model, agent_name=agent_name, thinking_budget=thinking_budget)
        else:
            raise CoScientistError(
                f"Unsupported LLM provider: {provider}. "
                f"Supported providers: 'google', 'openai', 'bedrock'"
            )


def get_llm_client(model: str, agent_name: str) -> BaseLLMClient:
    """Convenience function to get LLM client using global config.

    Per-agent overrides take precedence over the global settings:
      - settings.{agent}_provider_override → which provider to use
      - settings.{agent}_model_override    → which model to use

    These are populated from env vars on the ECS task (e.g.
    GENERATION_PROVIDER_OVERRIDE=bedrock,
    GENERATION_MODEL_OVERRIDE=anthropic.claude-opus-4-8) so the AGF
    website can mix providers within a single run.

    Args:
        model: Default model from `settings.{agent}_model` (used if no
            agent-level model override is set).
        agent_name: Name of the agent using this client.

    Returns:
        BaseLLMClient instance.
    """
    from src.config import settings

    provider_override = getattr(settings, f"{agent_name}_provider_override", None)
    model_override = getattr(settings, f"{agent_name}_model_override", None)

    provider = provider_override or settings.llm_provider
    effective_model = model_override or model

    # Thinking-budget hint: Gemini takes it as a token budget; BedrockClient
    # maps a budget of 0 to "thinking disabled" for Claude and ignores it for
    # other Bedrock models. The OpenAI client has no equivalent, so drop it.
    thinking_budget = (
        _THINKING_BUDGET_BY_AGENT.get(agent_name) if provider in ("google", "bedrock") else None
    )

    return LLMFactory.create_client(
        provider=provider,
        model=effective_model,
        agent_name=agent_name,
        thinking_budget=thinking_budget,
    )
