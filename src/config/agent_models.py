"""Per-agent LLM configuration.

Each of the eight specialized agents may use a different LLM provider /
model / temperature. Config is persisted in a small JSON file inside the
app data directory (so it survives across runs and is decoupled from the
optional SQLite store).

API:
    get_default_config() -> AgentModelConfig
    set_default_config(cfg) -> None
    get_agent_override(agent_name) -> AgentModelConfig | None
    set_agent_override(agent_name, cfg) -> None
    clear_agent_override(agent_name) -> None
    get_agent_runtime_config(agent_name) -> dict | None
        # used by src.llm.factory at LLM-client creation time
    load_all() -> AgentModelsState
    save_all(state) -> None
"""

from __future__ import annotations

import json
import threading
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator

AgentName = Literal[
    "generation",
    "reflection",
    "ranking",
    "evolution",
    "proximity",
    "meta_review",
    "supervisor",
    "safety",
]

AGENT_NAMES: tuple[str, ...] = (
    "generation",
    "reflection",
    "ranking",
    "evolution",
    "proximity",
    "meta_review",
    "supervisor",
    "safety",
)


class AgentModelConfig(BaseModel):
    """Provider + model + sampling parameters for one agent (or the default)."""

    provider: Literal["gemini", "openai", "deepseek", "anthropic"] = "gemini"
    model: str = "gemini-2.5-pro"
    temperature: float = Field(0.7, ge=0.0, le=2.0)

    @field_validator("provider", mode="before")
    @classmethod
    def _normalize(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        v = v.strip().lower()
        return {
            "google": "gemini",
            "gemini": "gemini",
            "openai": "openai",
            "gpt": "openai",
            "deepseek": "deepseek",
            "anthropic": "anthropic",
            "claude": "anthropic",
        }.get(v, v)


class AgentModelsState(BaseModel):
    """Top-level config doc persisted to disk."""

    default: AgentModelConfig = Field(default_factory=AgentModelConfig)
    agents: Dict[str, Optional[AgentModelConfig]] = Field(
        default_factory=lambda: {name: None for name in AGENT_NAMES}
    )

    def ensure_all_agents(self) -> "AgentModelsState":
        for name in AGENT_NAMES:
            self.agents.setdefault(name, None)
        return self


_lock = threading.Lock()
_cache: Optional[AgentModelsState] = None
_cache_path: Optional[str] = None  # bound to the path we cached from


def _config_path() -> str:
    from src.utils.paths import get_app_data_dir

    return str(get_app_data_dir() / "agent_models.json")


def _read_from_disk() -> AgentModelsState:
    path = _config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        state = AgentModelsState.model_validate(raw)
    except FileNotFoundError:
        state = AgentModelsState()
    except Exception:
        # Treat any corruption as "no config" so the app boots.
        state = AgentModelsState()
    return state.ensure_all_agents()


def _write_to_disk(state: AgentModelsState) -> None:
    path = _config_path()
    payload = state.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_all() -> AgentModelsState:
    """Return the in-memory state, loading from disk on first call.

    The cache is invalidated automatically when the resolved config path
    changes (eg. when tests flip ``AGF_DATA_DIR``).
    """
    global _cache, _cache_path
    with _lock:
        path = _config_path()
        if _cache is None or _cache_path != path:
            _cache = _read_from_disk()
            _cache_path = path
        return _cache.model_copy(deep=True)


def save_all(state: AgentModelsState) -> AgentModelsState:
    """Persist ``state`` and refresh the cache."""
    global _cache, _cache_path
    with _lock:
        state = state.ensure_all_agents()
        _write_to_disk(state)
        _cache = state.model_copy(deep=True)
        _cache_path = _config_path()
        return _cache.model_copy(deep=True)


def reset_cache() -> None:
    """Drop the in-memory cache (forces reload from disk)."""
    global _cache, _cache_path
    with _lock:
        _cache = None
        _cache_path = None


def get_default_config() -> AgentModelConfig:
    return load_all().default


def set_default_config(cfg: AgentModelConfig) -> AgentModelConfig:
    state = load_all()
    state.default = cfg
    save_all(state)
    return cfg


def get_agent_override(agent_name: str) -> Optional[AgentModelConfig]:
    if agent_name not in AGENT_NAMES:
        return None
    state = load_all()
    return state.agents.get(agent_name)


def set_agent_override(agent_name: str, cfg: AgentModelConfig) -> AgentModelConfig:
    if agent_name not in AGENT_NAMES:
        raise ValueError(
            f"Unknown agent {agent_name!r}; expected one of {AGENT_NAMES}"
        )
    state = load_all()
    state.agents[agent_name] = cfg
    save_all(state)
    return cfg


def clear_agent_override(agent_name: str) -> None:
    if agent_name not in AGENT_NAMES:
        return
    state = load_all()
    state.agents[agent_name] = None
    save_all(state)


def get_agent_runtime_config(agent_name: str) -> Optional[dict]:
    """Return the resolved (override-or-default) config as a plain dict.

    Returns ``None`` when no config has been saved to disk yet -- the
    caller should then use legacy ``settings.llm_provider`` behavior.
    """
    import os

    path = _config_path()
    # Only honor agent-models config when it has been explicitly written.
    if not os.path.exists(path):
        return None
    state = load_all()
    override = state.agents.get(agent_name)
    if override is not None:
        return override.model_dump()
    return state.default.model_dump()
