#!/usr/bin/env bash
# Build the Python sidecar into a single executable using PyInstaller.
#
# Output:
#   release/v0.1.0/desktop/resources/sidecar/agf-coscientist-backend[.exe]
#
# Prerequisites:
#   - Python 3.11
#   - `pip install -r requirements-api.txt && pip install pyinstaller`

set -euo pipefail

# This script lives at release/v0.1.0/build/, so the repo root is 3 levels up.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$RELEASE_DIR/../.." && pwd)"
cd "$REPO_ROOT"

OUT_DIR="$RELEASE_DIR/desktop/resources/sidecar"
mkdir -p "$OUT_DIR"

echo "[build-sidecar] cleaning previous build artefacts..."
rm -rf "$RELEASE_DIR/build/pyinstaller-work" || true

echo "[build-sidecar] running pyinstaller..."
python -m PyInstaller \
  "$RELEASE_DIR/build/pyinstaller.spec" \
  --distpath "$OUT_DIR" \
  --workpath "$RELEASE_DIR/build/pyinstaller-work" \
  --noconfirm \
  --clean

echo "[build-sidecar] sidecar binary written to: $OUT_DIR"
ls -la "$OUT_DIR"
