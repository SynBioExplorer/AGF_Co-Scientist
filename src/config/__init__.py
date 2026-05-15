"""``src.config`` package.

Re-exports :class:`Settings` and the global ``settings`` instance so
``from src.config import settings`` continues to work after the
single-module-to-package conversion.
"""

from src.config._main import Settings, settings  # noqa: F401

__all__ = ["Settings", "settings"]
