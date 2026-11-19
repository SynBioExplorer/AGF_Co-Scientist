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
    semantic_scholar_api_key: str | None = None  # free tier 1 r/s; key just gives a dedicated lane

    # LangSmith Observability (Phase 5F)
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "ai-coscientist"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # LLM Provider Selection (change this to switch providers globally)
    llm_provider: Literal["google", "openai", "bedrock"] = "google"

    # AWS Bedrock Configuration
    # Per-model Application Inference Profiles arrive as the
    # BEDROCK_INFERENCE_PROFILE_ARNS JSON map, read in src/llm/bedrock.py.
    bedrock_region: str = "ap-southeast-2"

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
    google_generation_model: str = "gemini-4-argon"
    google_reflection_model: str = "gemini-3.8-flash"
    google_ranking_model: str = "gemini-3.8-flash"
    google_evolution_model: str = "gemini-4-argon"
    google_meta_review_model: str = "gemini-3.8-flash"
    google_supervisor_model: str = "gemini-3.8-flash"

    # OpenAI Model Configuration
    openai_generation_model: str = "gpt-5.1"
    openai_reflection_model: str = "gpt-5-mini"
    openai_ranking_model: str = "gpt-5-mini"
    openai_evolution_model: str = "gpt-5.1"
    openai_meta_review_model: str = "gpt-5"
    openai_supervisor_model: str = "gpt-5-nano"

    # AWS Bedrock Model Configuration
    # ----------------------------------------------------------------
    # Mirrors the Gemini per-agent tiering: Pro-tier model for high-reasoning
    # work (generation, evolution, meta-review), Flash-tier for screening /
    # ranking / orchestration (reflection, ranking, supervisor).
    #
    # Defaults below are Anthropic Claude (Bedrock variant "anthropic"):
    #   Pro tier  -> Opus 4.8
    #   Flash tier-> Sonnet 5  (no Haiku per AGF policy)
    # Not Opus 5.5: its built-in Bedrock content filter blocked the real
    # generation prompt on 6/6 benign biotech goals (2026-10-16), and there is
    # no way to relax it on Bedrock. Opus 4.8 and Sonnet 5 passed 6/6 each.
    #
    # Model IDs verified 2026-10-16 with list-foundation-models in
    # ap-southeast-2 plus a real Converse call per model (listing alone does
    # not prove the account can invoke a model). All of them are
    # INFERENCE_PROFILE-only; src/llm/bedrock.py maps each ID to its profile.
    #
    # When the user picks a different Bedrock variant in the AGF Co-Scientist
    # submission UI, the website API overrides these via ECS task env vars
    # (BEDROCK_GENERATION_MODEL etc.) following the same Pro/Flash tiering;
    # pydantic_settings auto-reads the env vars:
    #
    #   variant     | Pro tier (gen/evolution/meta_review) | Flash tier (reflection/ranking/supervisor)
    #   ------------|--------------------------------------|---------------------------------------------
    #   anthropic   | anthropic.claude-opus-4-8            | anthropic.claude-sonnet-5
    #   openai      | openai.gpt-6-astra                   | openai.gpt-6-luna
    #   kimi        | moonshotai.kimi-k3                   | moonshotai.kimi-k3 (single model)
    bedrock_generation_model: str = "anthropic.claude-opus-4-8"
    bedrock_reflection_model: str = "anthropic.claude-sonnet-5"
    bedrock_ranking_model: str = "anthropic.claude-sonnet-5"
    bedrock_evolution_model: str = "anthropic.claude-opus-4-8"
    bedrock_meta_review_model: str = "anthropic.claude-opus-4-8"
    bedrock_supervisor_model: str = "anthropic.claude-sonnet-5"

    # ----------------------------------------------------------------
    # Per-Agent Provider/Model Overrides (Phase 7 - AGF Website)
    # ----------------------------------------------------------------
    # When set, these override BOTH the global llm_provider AND the
    # corresponding provider-specific model field for that agent.
    # Allows mixing providers within a single run, e.g. Anthropic Opus for
    # generation while GPT-6 Luna does reflection. Set via ECS RunTask env
    # vars (e.g. GENERATION_PROVIDER_OVERRIDE=bedrock,
    # GENERATION_MODEL_OVERRIDE=anthropic.claude-opus-4-8). Pydantic
    # auto-reads env vars matching field names.
    generation_provider_override: Literal["google", "openai", "bedrock"] | None = None
    generation_model_override: str | None = None
    reflection_provider_override: Literal["google", "openai", "bedrock"] | None = None
    reflection_model_override: str | None = None
    ranking_provider_override: Literal["google", "openai", "bedrock"] | None = None
    ranking_model_override: str | None = None
    evolution_provider_override: Literal["google", "openai", "bedrock"] | None = None
    evolution_model_override: str | None = None
    meta_review_provider_override: Literal["google", "openai", "bedrock"] | None = None
    meta_review_model_override: str | None = None
    supervisor_provider_override: Literal["google", "openai", "bedrock"] | None = None
    supervisor_model_override: str | None = None

    # System Configuration
    budget_aud: float = 50.0
    max_workers: int = 4
    # Share of budget_aud the iteration loop leaves for the final meta-review,
    # research overview and report: the loop stops at the rest, the final
    # synthesis may use the whole budget.
    finalization_reserve_fraction: float = 0.05

    # Run options from the website's form (hypothesis.yaml; aws_entrypoint.py
    # sets them). enable_web_search off: no literature retrieval, refutation
    # search or DOI checks, so citations stay not_checked.
    enable_web_search: bool = True
    enable_evolution: bool = True

    # Reviews the meta-review prompt shows: the newest of each hypothesis and
    # review type, failed ones first (meta_review.py).
    meta_review_max_reviews: int = 40

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
    supervisor_max_execution_seconds: int = 21600  # 6 hours total workflow time

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

    # B16 fix: self-regulating pool cap. The supervisor stops scheduling new
    # GENERATION tasks once the hypothesis pool reaches this size, so ranking
    # can catch up. Default 40 hypotheses; tune empirically after the live run.
    generation_pool_cap: int = 40

    # B3 fix: time-aware drain phase. When elapsed/budget crosses
    # drain_phase_start_fraction, the supervisor schedules only RANKING to
    # cover unmatched hypotheses before terminating. Capped at
    # drain_max_iterations to avoid runaway tails.
    drain_phase_start_fraction: float = 0.85
    drain_max_iterations: int = 5

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
