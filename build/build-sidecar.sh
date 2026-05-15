#!/usr/bin/env bash
# Build the Python sidecar into a single executable using PyInstaller.
#
# Output:
#   desktop/resources/sidecar/agf-coscientist-backend[.exe]
#
# Prerequisites:
#   - Python 3.11
#   - `pip install -r requirements-api.txt && pip install pyinstaller`

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OUT_DIR="$REPO_ROOT/desktop/resources/sidecar"
mkdir -p "$OUT_DIR"

echo "[build-sidecar] cleaning previous build artefacts..."
rm -rf "$REPO_ROOT/build/pyinstaller-work" || true

echo "[build-sidecar] running pyinstaller..."
python -m PyInstaller \
  build/pyinstaller.spec \
  --distpath "$OUT_DIR" \
  --workpath "$REPO_ROOT/build/pyinstaller-work" \
  --noconfirm \
  --clean

echo "[build-sidecar] sidecar binary written to: $OUT_DIR"
ls -la "$OUT_DIR"
