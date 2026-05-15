# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the AGF Co-Scientist Python sidecar.

Bundles `src/api/main.py` (wrapped in `build/sidecar_entrypoint.py`) plus
the agent code, prompts, schemas, and `.env.example` template into a
single executable named `agf-coscientist-backend`.

Invoke via:
    pyinstaller build/pyinstaller.spec --distpath desktop/resources/sidecar --clean

Hidden imports cover the dynamic-import surface of FastAPI/uvicorn and the
LangGraph agent modules that are loaded by string name.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Spec files run with __file__ undefined under some PyInstaller versions —
# fall back to the CWD which is the repo root when invoked correctly.
try:
    SPEC_DIR = Path(__file__).parent.resolve()
except NameError:
    SPEC_DIR = Path.cwd() / "build"

REPO_ROOT = SPEC_DIR.parent

block_cipher = None

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hidden_imports = []
hidden_imports += collect_submodules("src.agents")
hidden_imports += collect_submodules("src.api")
hidden_imports += collect_submodules("src.graphs")
hidden_imports += collect_submodules("src.llm")
hidden_imports += collect_submodules("src.storage")
hidden_imports += collect_submodules("src.supervisor")
hidden_imports += collect_submodules("src.tournament")
hidden_imports += collect_submodules("src.utils")
hidden_imports += collect_submodules("src.prompts")

# FastAPI / Starlette / uvicorn dynamic imports
hidden_imports += [
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.loops.uvloop",
    "uvicorn.logging",
    "anyio._backends._asyncio",
    "email.mime.multipart",
    "email.mime.text",
]

# ---------------------------------------------------------------------------
# Data files — prompts, schemas, .env template
# ---------------------------------------------------------------------------
datas = []
datas += [(str(REPO_ROOT / "02_Prompts"), "02_Prompts")]
datas += [(str(REPO_ROOT / "03_architecture" / "schemas.py"), "03_architecture")]

env_example = REPO_ROOT / "03_architecture" / ".env.example"
if env_example.exists():
    datas += [(str(env_example), "03_architecture")]

# Best-effort collect of langchain/langgraph/google generative-ai package data
for pkg in ("langchain", "langchain_core", "langgraph", "google", "anthropic"):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Analysis / build graph
# ---------------------------------------------------------------------------
a = Analysis(
    [str(REPO_ROOT / "build" / "sidecar_entrypoint.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="agf-coscientist-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
