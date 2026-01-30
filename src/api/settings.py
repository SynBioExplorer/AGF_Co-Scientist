"""
Settings API Router

Provides GET/PUT endpoints for system configuration that persists across restarts.
Settings are stored in .runtime_settings.json (gitignored) to avoid modifying .env.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from src.config import get_settings
import json
import os

router = APIRouter(prefix="/settings", tags=["settings"])

class Settings(BaseModel):
    """System settings matching frontend expectations."""
    llm_provider: str
    default_model: str
    default_temperature: float
    agent_models: Dict[str, str]
    max_iterations: int
    enable_evolution: bool
    enable_web_search: bool

SETTINGS_FILE = "03_architecture/.runtime_settings.json"


@router.get("", response_model=Settings)
async def get_settings():
    """
    Get current system settings.

    Returns settings from .runtime_settings.json if it exists,
    otherwise returns defaults from environment variables.
    """
    # Load from runtime settings file if exists
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return Settings(**json.load(f))

    # Return defaults from .env
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "google"),
        default_model=os.getenv("DEFAULT_MODEL", "gemini-2.0-flash-exp"),
        default_temperature=float(os.getenv("DEFAULT_TEMPERATURE", "0.7")),
        agent_models={},  # Empty = use default_model for all agents
        max_iterations=int(os.getenv("MAX_ITERATIONS", "50")),
        enable_evolution=os.getenv("ENABLE_EVOLUTION", "true").lower() == "true",
        enable_web_search=os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true"
    )


@router.put("", response_model=Settings)
async def update_settings(new_settings: Settings):
    """
    Update system settings.

    Settings are persisted to .runtime_settings.json (gitignored).
    This allows settings to persist across server restarts without modifying .env.

    Args:
        new_settings: New settings to save

    Returns:
        The saved settings

    Raises:
        HTTPException: If provider is invalid
    """
    # Validate provider
    if new_settings.llm_provider not in ["google", "openai"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {new_settings.llm_provider}. Must be 'google' or 'openai'"
        )

    # Save to runtime settings file
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(new_settings.dict(), f, indent=2)

    return new_settings
