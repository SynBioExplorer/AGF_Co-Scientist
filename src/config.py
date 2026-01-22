"""Configuration management for AI Co-Scientist system"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """System settings loaded from environment variables"""

    # API Keys
    google_api_key: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    tavily_api_key: str | None = None

    # Model Configuration
    generation_model: str = "gemini-3-pro-preview"
    reflection_model: str = "gemini-2.5-flash"
    ranking_model: str = "gemini-3-flash-preview"
    evolution_model: str = "gemini-3-pro-preview"
    meta_review_model: str = "gemini-3-flash-preview"
    supervisor_model: str = "gemini-2.0-flash"

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


# Global settings instance
settings = Settings()
