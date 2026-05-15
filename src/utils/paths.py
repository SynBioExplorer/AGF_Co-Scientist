"""OS-appropriate path resolution for the AGF Co-Scientist desktop app.

Provides cross-platform locations for app data, exports, and DB files.
All functions create the target directory on demand and return ``Path`` objects.

Environment overrides:
    AGF_DATA_DIR     - overrides the app-data directory (used by tests).
    AGF_EXPORT_DIR   - overrides the default export directory.

Default locations:
    macOS:   ~/Library/Application Support/AGF Co-Scientist
    Windows: %APPDATA%/AGF Co-Scientist
    Linux:   ~/.local/share/AGF Co-Scientist
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "AGF Co-Scientist"


def _detect_platform() -> str:
    """Return one of 'mac', 'windows', 'linux'."""
    if sys.platform == "darwin":
        return "mac"
    if sys.platform.startswith("win") or os.name == "nt":
        return "windows"
    return "linux"


def get_app_data_dir() -> Path:
    """Return the OS-appropriate application data directory.

    Honors ``AGF_DATA_DIR`` override (used by tests). The directory is
    created on demand. The result is always an absolute ``Path``.
    """
    override = os.environ.get("AGF_DATA_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    platform = _detect_platform()
    if platform == "mac":
        base = Path.home() / "Library" / "Application Support"
    elif platform == "windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
    else:  # linux + everything else
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            base = Path(xdg)
        else:
            base = Path.home() / ".local" / "share"

    path = (base / APP_NAME).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_export_dir() -> Path:
    """Return the default export directory under the user's Documents folder.

    Honors ``AGF_EXPORT_DIR`` override.
    """
    override = os.environ.get("AGF_EXPORT_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    documents = Path.home() / "Documents"
    path = (documents / APP_NAME).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_sqlite_db_path() -> Path:
    """Return the canonical SQLite DB file path."""
    return get_app_data_dir() / "coscientist.db"


def get_secrets_db_path() -> Path:
    """Return the SQLite file used for the encrypted secret fallback store."""
    return get_app_data_dir() / "secrets.db"
