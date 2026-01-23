"""Configuration management for AI Co-Scientist system"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    """System settings loaded from environment variables"""

    # API Keys
    google_api_key: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    tavily_api_key: str | None = None

    # LLM Provider Selection (change this to switch providers globally)
    llm_provider: Literal["google", "openai"] = "google"

    # Google Model Configuration
    google_generation_model: str = "gemini-3-pro-preview"
    google_reflection_model: str = "gemini-2.5-flash"
    google_ranking_model: str = "gemini-3-flash-preview"
    google_evolution_model: str = "gemini-3-pro-preview"
    google_meta_review_model: str = "gemini-3-flash-preview"
    google_supervisor_model: str = "gemini-2.0-flash"

    # OpenAI Model Configuration
    openai_generation_model: str = "gpt-5.1"
    openai_reflection_model: str = "gpt-5-mini"
    openai_ranking_model: str = "gpt-5-mini"
    openai_evolution_model: str = "gpt-5.1"
    openai_meta_review_model: str = "gpt-5"
    openai_supervisor_model: str = "gpt-5-nano"

    # System Configuration
    budget_aud: float = 50.0
    max_workers: int = 4

    # Paths
    project_root: Path = Path(__file__).parent.parent
    prompts_dir: Path = project_root / "02_Prompts"
    architecture_dir: Path = project_root / "03_architecture"
    data_dir: Path = project_root / "data"

    class Config:
        env_file = "03_architecture/.env"
        extra = "ignore"

    # Dynamic model properties based on provider
    @property
    def generation_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_generation_model")

    @property
    def reflection_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_reflection_model")

    @property
    def ranking_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_ranking_model")

    @property
    def evolution_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_evolution_model")

    @property
    def meta_review_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_meta_review_model")

    @property
    def supervisor_model(self) -> str:
        return getattr(self, f"{self.llm_provider}_supervisor_model")


# Global settings instance
settings = Settings()
