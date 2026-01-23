"""LLM Client Factory - Centralized provider selection"""

from typing import Literal
from src.llm.base import BaseLLMClient
from src.llm.google import GoogleGeminiClient
from src.llm.openai import OpenAIClient
from src.utils.errors import CoScientistError

LLMProvider = Literal["google", "openai"]


class LLMFactory:
    """Factory for creating LLM clients based on provider configuration"""

    @staticmethod
    def create_client(
        provider: LLMProvider,
        model: str,
        agent_name: str
    ) -> BaseLLMClient:
        """Create an LLM client based on provider type

        Args:
            provider: "google" or "openai"
            model: Model name/identifier
            agent_name: Name of the agent using this client (for cost tracking)

        Returns:
            BaseLLMClient instance (GoogleGeminiClient or OpenAIClient)

        Raises:
            CoScientistError: If provider is not supported
        """
        if provider == "google":
            return GoogleGeminiClient(model=model, agent_name=agent_name)
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
    return LLMFactory.create_client(
        provider=settings.llm_provider,
        model=model,
        agent_name=agent_name
    )
