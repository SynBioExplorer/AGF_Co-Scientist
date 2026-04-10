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

    # LLM Timeout and Retry Configuration
    # Scientific hypothesis generation can take 60-180 seconds for complex reasoning
    llm_timeout_seconds: int = 300  # 5 minutes for complex scientific tasks
    llm_max_retries: int = 3  # Total attempts = max_retries + 1 = 4
    llm_retry_base_delay: float = 1.0  # Exponential backoff: 1s, 2s, 4s, 8s...
    llm_retry_max_delay: float = 30.0  # Cap backoff at 30 seconds

    # Supervisor execution timeout (entire workflow iteration)
    supervisor_iteration_timeout: int = 600  # 10 minutes per iteration
    supervisor_max_execution_seconds: int = 7200  # 2 hours total workflow time (AGENT-C1 fix)

    # Memory cleanup configuration
    task_cleanup_interval_hours: int = 1  # Run cleanup every hour
    task_max_age_hours: int = 24  # Remove completed tasks after 24 hours
    chat_history_max_messages: int = 1000  # Per goal message limit
    chat_history_max_age_hours: int = 168  # Remove chat history after 7 days

    # Safety configuration
    safety_threshold: float = 0.0  # Set to 0 to disable safety review; 0.5 for production

    # Tournament Pairing Configuration (Phase 5 Enhancement - Proximity-Aware Matching)
    proximity_aware_pairing: bool = True  # Enable proximity-based tournament pairing
    proximity_pairing_weight: float = 0.7  # Proportion of within-cluster matches (70%)
    diversity_pairing_weight: float = 0.2  # Proportion of cross-cluster matches (20%)
    proximity_graph_refresh_frequency: int = 3  # Refresh proximity graph every N iterations
    min_cluster_size_for_pairing: int = 2  # Minimum hypotheses per cluster for pairing

    # Diversity Sampling Configuration (Phase 6B - UX Enhancement)
    diversity_sampling_enabled: bool = True  # Enable diversity sampling feature
    diversity_sampling_for_overview: bool = True  # Use in final overview generation
    diversity_sampling_min_elo: float = 1200.0  # Minimum Elo rating for selection
    diversity_sampling_default_n: int = 10  # Default number of diverse hypotheses

    # Paths
    project_root: Path = Path(__file__).parent.parent
    prompts_dir: Path = project_root / "02_Prompts"
    architecture_dir: Path = project_root / "03_architecture"
    data_dir: Path = project_root / "data"

    # Phase 6 Week 4: Multi-Source Citation Merging
    citation_source_priority: List[str] = ["local", "pubmed", "semantic_scholar"]
    citation_graph_cache_ttl: int = 86400  # 24 hours
    paper_metadata_cache_ttl: int = 604800  # 7 days
    private_repository_path: str | None = None  # Path to local PDF collection
    enable_parallel_expansion: bool = True  # Parallel citation graph expansion
    max_parallel_expansions: int = 5  # Concurrent expansion tasks

    # =========================================================================
    # Phase 6: Evidence Quality Enhancement Configuration
    # =========================================================================

    # Paper Quality Scoring (Phase 6)
    enable_quality_scoring: bool = True  # Enable multi-factor quality scoring
    quality_citation_weight: float = 0.5  # Weight for citation count score
    quality_recency_weight: float = 0.3  # Weight for recency score
    quality_journal_weight: float = 0.2  # Weight for journal impact score
    quality_min_threshold: float = 0.3  # Filter papers below this quality score
    quality_recency_halflife_years: int = 5  # Half-life for recency decay

    # Refutation Search (Phase 6)
    enable_refutation_search: bool = True  # Enable searching for contradictions
    refutation_max_results: int = 10  # Maximum contradictory papers to find
    refutation_min_quality_score: float = 0.4  # Only use high-quality contradictions
    refutation_check_retractions: bool = True  # Check PubMed for retractions

    # Limitations Extraction (Phase 6)
    enable_limitations_extraction: bool = True  # Enable limitations extraction
    limitations_min_confidence: float = 0.5  # Only include high-confidence limitations
    limitations_include_in_context: bool = True  # Include limitations in LLM context

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
