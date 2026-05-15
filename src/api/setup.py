"""Setup wizard endpoints.

First-run onboarding for the desktop app:

    GET  /api/setup/status         -- "have we been configured yet?"
    POST /api/setup/validate-key   -- per-provider quick check
    POST /api/setup/complete       -- write secrets + state in one shot

Plus the related settings + export-config endpoints:

    GET    /api/settings/secrets
    PUT    /api/settings/secrets
    DELETE /api/settings/secrets/{provider}
    GET    /api/settings/agent-models
    PUT    /api/settings/agent-models
    GET    /api/settings/available-models?provider=gemini

The "did the user finish setup?" state lives in a small JSON file under
:func:`src.utils.paths.get_app_data_dir`; secrets live in the OS
keychain (with encrypted-SQLite fallback).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from src.config.agent_models import (
    AGENT_NAMES,
    AgentModelConfig,
    AgentModelsState,
    load_all,
    save_all,
)
from src.llm import HARDCODED_MODELS, get_available_models, normalize_provider
from src.utils import keychain
from src.utils.paths import get_app_data_dir, get_default_export_dir

router = APIRouter(prefix="/api", tags=["setup"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


Provider = Literal["gemini", "openai", "deepseek", "anthropic"]


class ValidateKeyRequest(BaseModel):
    provider: Provider
    api_key: str = Field(..., min_length=1)


class ValidateKeyResponse(BaseModel):
    valid: bool
    error: Optional[str] = None
    available_models: List[str] = Field(default_factory=list)


class EmailConfig(BaseModel):
    enabled: bool = False
    recipient: Optional[EmailStr] = None


class OptionalKeys(BaseModel):
    tavily: Optional[str] = None
    ncbi: Optional[str] = None
    semantic_scholar: Optional[bool] = None


class SetupCompleteRequest(BaseModel):
    providers: Dict[Provider, Optional[str]] = Field(default_factory=dict)
    optional: OptionalKeys = Field(default_factory=OptionalKeys)
    export_folder: str
    email: EmailConfig = Field(default_factory=EmailConfig)


class SetupStatusResponse(BaseModel):
    completed: bool
    missing_steps: List[str] = Field(default_factory=list)


class MaskedSecret(BaseModel):
    set: bool
    masked: Optional[str] = None


class SecretsResponse(BaseModel):
    providers: Dict[str, MaskedSecret]
    optional: Dict[str, MaskedSecret]
    email: EmailConfig
    export_folder: str


class AgentModelsResponse(BaseModel):
    default: AgentModelConfig
    agents: Dict[str, Optional[AgentModelConfig]]


class AvailableModelsResponse(BaseModel):
    models: List[str]


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

PROVIDER_SECRET_KEYS = {
    "gemini": "google_api_key",  # underlying env var GOOGLE_API_KEY
    "openai": "openai_api_key",
    "deepseek": "deepseek_api_key",
    "anthropic": "anthropic_api_key",
}

OPTIONAL_SECRET_KEYS = {
    "tavily": "tavily_api_key",
    "ncbi": "pubmed_api_key",
    "semantic_scholar": "semantic_scholar_api_key",
}


def _state_path() -> Path:
    return get_app_data_dir() / "setup_state.json"


def _read_state() -> dict:
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    with open(_state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Provider validation
# ---------------------------------------------------------------------------


def _format_check(provider: str, key: str) -> tuple[bool, Optional[str]]:
    """Cheap, network-free format sanity check."""
    if not key or not isinstance(key, str):
        return False, "empty key"
    key = key.strip()
    if len(key) < 8:
        return False, "key too short"
    # Lightweight format hints -- intentionally lenient. The real test is a
    # call against the provider, which we attempt below when reachable.
    hints = {
        "openai": "sk-",
        "anthropic": "sk-ant-",
        "deepseek": "sk-",
    }
    expected = hints.get(provider)
    if expected and not key.startswith(expected):
        return True, None  # warn-only; accept anyway
    return True, None


async def _live_validate(provider: str, key: str) -> tuple[bool, Optional[str]]:
    """Best-effort live validation. Returns (valid, error)."""
    canonical = normalize_provider(provider)
    try:
        if canonical == "gemini":
            import httpx  # type: ignore

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params={"key": key},
                )
                if r.status_code == 200:
                    return True, None
                return False, f"HTTP {r.status_code}: {r.text[:200]}"

        if canonical == "openai":
            import httpx  # type: ignore

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if r.status_code == 200:
                    return True, None
                return False, f"HTTP {r.status_code}"

        if canonical == "deepseek":
            import httpx  # type: ignore

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.deepseek.com/v1/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
                if r.status_code == 200:
                    return True, None
                return False, f"HTTP {r.status_code}"

        if canonical == "anthropic":
            import httpx  # type: ignore

            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                if r.status_code == 200:
                    return True, None
                return False, f"HTTP {r.status_code}"
    except Exception as e:
        # Treat network failures as inconclusive -- we fall back to format
        # validation, which already passed by the time we get here.
        return True, f"could not reach provider: {e}"
    return False, "unknown provider"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/setup/status", response_model=SetupStatusResponse)
async def setup_status() -> SetupStatusResponse:
    state = _read_state()
    missing: List[str] = []

    # Need at least one provider key.
    any_provider = any(
        keychain.get_secret(slot) for slot in PROVIDER_SECRET_KEYS.values()
    )
    if not any_provider:
        missing.append("providers")

    if not state.get("export_folder"):
        missing.append("folder")

    email = state.get("email") or {}
    if email.get("enabled") and not email.get("recipient"):
        missing.append("email")

    return SetupStatusResponse(
        completed=state.get("completed", False) and not missing,
        missing_steps=missing,
    )


@router.post("/setup/validate-key", response_model=ValidateKeyResponse)
async def validate_key(req: ValidateKeyRequest) -> ValidateKeyResponse:
    ok, err = _format_check(req.provider, req.api_key)
    if not ok:
        return ValidateKeyResponse(valid=False, error=err, available_models=[])
    live_ok, live_err = await _live_validate(req.provider, req.api_key)
    models = get_available_models(req.provider)
    return ValidateKeyResponse(
        valid=bool(live_ok),
        error=live_err,
        available_models=models,
    )


@router.post("/setup/complete")
async def setup_complete(req: SetupCompleteRequest) -> dict:
    # Persist provider secrets.
    for provider, key in req.providers.items():
        slot = PROVIDER_SECRET_KEYS.get(provider)
        if not slot:
            continue
        if key:
            keychain.set_secret(slot, key)
        else:
            keychain.delete_secret(slot)

    # Optional services.
    if req.optional.tavily is not None:
        if req.optional.tavily:
            keychain.set_secret(OPTIONAL_SECRET_KEYS["tavily"], req.optional.tavily)
        else:
            keychain.delete_secret(OPTIONAL_SECRET_KEYS["tavily"])
    if req.optional.ncbi is not None:
        if req.optional.ncbi:
            keychain.set_secret(OPTIONAL_SECRET_KEYS["ncbi"], req.optional.ncbi)
        else:
            keychain.delete_secret(OPTIONAL_SECRET_KEYS["ncbi"])

    # Validate export folder.
    export_path = Path(req.export_folder).expanduser()
    try:
        export_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create export folder {export_path}: {e}",
        )

    state = _read_state()
    state["export_folder"] = str(export_path.resolve())
    state["email"] = req.email.model_dump()
    state["semantic_scholar_enabled"] = bool(req.optional.semantic_scholar)
    state["completed"] = True
    _write_state(state)

    return {"success": True}


# -------- Secrets management ----------------------------------------------


def _build_secrets_response() -> SecretsResponse:
    state = _read_state()
    providers: Dict[str, MaskedSecret] = {}
    for provider, slot in PROVIDER_SECRET_KEYS.items():
        value = keychain.get_secret(slot)
        providers[provider] = MaskedSecret(
            set=bool(value), masked=keychain.mask(value)
        )
    optional: Dict[str, MaskedSecret] = {}
    for name, slot in OPTIONAL_SECRET_KEYS.items():
        if name == "semantic_scholar":
            optional[name] = MaskedSecret(
                set=bool(state.get("semantic_scholar_enabled")),
                masked=None,
            )
        else:
            value = keychain.get_secret(slot)
            optional[name] = MaskedSecret(
                set=bool(value), masked=keychain.mask(value)
            )
    email = EmailConfig(**(state.get("email") or {}))
    return SecretsResponse(
        providers=providers,
        optional=optional,
        email=email,
        export_folder=state.get("export_folder", str(get_default_export_dir())),
    )


@router.get("/settings/secrets", response_model=SecretsResponse)
async def get_secrets() -> SecretsResponse:
    return _build_secrets_response()


@router.put("/settings/secrets", response_model=SecretsResponse)
async def put_secrets(req: SetupCompleteRequest) -> SecretsResponse:
    await setup_complete(req)
    return _build_secrets_response()


@router.delete("/settings/secrets/{provider}")
async def delete_secret(provider: str) -> dict:
    p = provider.strip().lower()
    if p in PROVIDER_SECRET_KEYS:
        keychain.delete_secret(PROVIDER_SECRET_KEYS[p])
    elif p in OPTIONAL_SECRET_KEYS:
        if p == "semantic_scholar":
            state = _read_state()
            state["semantic_scholar_enabled"] = False
            _write_state(state)
        else:
            keychain.delete_secret(OPTIONAL_SECRET_KEYS[p])
    else:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    return {"success": True}


# -------- Agent model config ----------------------------------------------


@router.get("/settings/agent-models", response_model=AgentModelsResponse)
async def get_agent_models() -> AgentModelsResponse:
    state = load_all()
    # Ensure every expected agent appears in the response.
    agents = {name: state.agents.get(name) for name in AGENT_NAMES}
    return AgentModelsResponse(default=state.default, agents=agents)


@router.put("/settings/agent-models", response_model=AgentModelsResponse)
async def put_agent_models(req: AgentModelsResponse) -> AgentModelsResponse:
    new_state = AgentModelsState(
        default=req.default,
        agents={name: req.agents.get(name) for name in AGENT_NAMES},
    )
    saved = save_all(new_state)
    return AgentModelsResponse(
        default=saved.default,
        agents={name: saved.agents.get(name) for name in AGENT_NAMES},
    )


@router.get("/settings/available-models", response_model=AvailableModelsResponse)
async def available_models(
    provider: str = Query(..., description="Provider name"),
) -> AvailableModelsResponse:
    try:
        models = get_available_models(provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AvailableModelsResponse(models=models)


__all__ = ["router"]
