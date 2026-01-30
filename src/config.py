"""Configuration management for AI Co-Scientist system"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Literal, List


class Settings(BaseSettings):
    """System settings loaded from environment variables"""

    # API Keys
    google_api_key: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    tavily_api_key: str | None = None
    pubmed_api_key: str | None = None

    # LangSmith Observability (Phase 5F)
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "ai-coscientist"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # LLM Provider Selection (change this to switch providers globally)
    llm_provider: Literal["google", "openai"] = "google"

    # Storage Configuration (Phase 4 - Database Agent)
    # Options: "memory" (development), "postgres" (production), "cached" (production + Redis)
    storage_backend: Literal["memory", "postgres", "cached"] = "memory"

    # PostgreSQL Configuration
    database_url: str = "postgresql://localhost:5432/coscientist"

    # Redis Configuration (for caching)
    redis_url: str = "redis://localhost:6379/0"

    # Vector Storage Configuration (Phase 5A - Vector Storage)
    # Options: "chroma" (local), "pgvector" (PostgreSQL with pgvector extension)
    vector_store_type: Literal["chroma", "pgvector"] = "chroma"
    chroma_persist_directory: str = "./chroma_db"

    # Embedding Provider Configuration (Phase 5A)
    # Options: "google" (text-embedding-004), "openai" (text-embedding-3-small)
    embedding_provider: Literal["google", "openai"] = "google"
    google_embedding_model: str = "text-embedding-004"
    openai_embedding_model: str = "text-embedding-3-small"

    # API Server Configuration (Phase 4 - API Agent)
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    api_cors_origins: List[str] = ["*"]
    api_debug: bool = False

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

    # Tool Configuration (Phase 5B - Literature Tools)
    tool_timeout_seconds: int = 30
    tool_max_results: int = 10

    # Tournament Pairing Configuration (Phase 5 Enhancement - Proximity-Aware Matching)
    proximity_aware_pairing: bool = True  # Enable proximity-based tournament pairing
    proximity_pairing_weight: float = 0.7  # Proportion of within-cluster matches (70%)
    diversity_pairing_weight: float = 0.2  # Proportion of cross-cluster matches (20%)
    proximity_graph_refresh_frequency: int = 3  # Refresh proximity graph every N iterations
    min_cluster_size_for_pairing: int = 2  # Minimum hypotheses per cluster for pairing

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
