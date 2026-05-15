# Build pipeline — v0.1.0

This directory contains everything needed to package the AGF Co-Scientist
desktop application from source.

All build commands assume the **repo root** as the working directory.

## Pipeline overview

```
frontend/    --(vite build)-->     frontend/dist/
src/api/     --(PyInstaller)-->    release/v0.1.0/desktop/resources/sidecar/
                                   agf-coscientist-backend[.exe]
                                       |
                                       v
                                electron-builder
                                       |
                                       v
                          dist/AGF Co-Scientist-<ver>.{dmg,exe,AppImage}
```

## Files

| File | Purpose |
|------|---------|
| `pyinstaller.spec` | PyInstaller bundle definition for the FastAPI sidecar. |
| `sidecar_entrypoint.py` | Standalone uvicorn launcher; writes `port.txt` so Electron can connect. |
| `build-sidecar.sh` / `build-sidecar.ps1` | Wrapper around PyInstaller. |
| `electron-builder.yml` | electron-builder config (mac dmg / win nsis / linux AppImage). |
| `icon.{png,ico,icns}` | Application icons. Until provided, see `icon.png.TODO.txt`. |

## Local builds

### Prerequisites

* Python 3.11 with `pip install -r requirements-api.txt && pip install pyinstaller`.
* Node 20 with the root `package.json` and `frontend/package.json` deps installed (`npm ci`).

### macOS

```bash
# From repo root:
# 1. Frontend bundle
cd frontend && npm ci && npm run build && cd ..

# 2. Python sidecar (produces a universal-2 binary if running on Apple Silicon
#    with the universal2 Python build).
bash release/v0.1.0/build/build-sidecar.sh

# 3. .dmg
npx electron-builder --config release/v0.1.0/build/electron-builder.yml --mac
```

Output: `dist/AGF Co-Scientist-<version>-universal.dmg`.

### Windows

```powershell
# From repo root:
cd frontend; npm ci; npm run build; cd ..
powershell -File release\v0.1.0\build\build-sidecar.ps1
npx electron-builder --config release\v0.1.0\build\electron-builder.yml --win
```

Output: `dist\AGF Co-Scientist-<version>-setup.exe` (NSIS one-click installer).

### Linux

```bash
# From repo root:
cd frontend && npm ci && npm run build && cd ..
bash release/v0.1.0/build/build-sidecar.sh
npx electron-builder --config release/v0.1.0/build/electron-builder.yml --linux
```

Output: `dist/AGF Co-Scientist-<version>.AppImage`.

## CI

GitHub Actions (`.github/workflows/release.yml`) runs the same pipeline on
`macos-latest`, `windows-latest`, and `ubuntu-latest` whenever a `v*.*.*`
git tag is pushed. The resulting artefacts are uploaded to the matching
GitHub Release; electron-updater consumes them for auto-update on launch.

## Signing / notarisation

**Not enabled for v0.1.0.** Installers are unsigned, so users will see a
one-time:

* macOS — "“AGF Co-Scientist” cannot be opened because the developer
  cannot be verified." Right-click → Open → Open.
* Windows — SmartScreen "Windows protected your PC". Click "More info"
  → "Run anyway".
* Linux — `chmod +x AGF*.AppImage && ./AGF*.AppImage`. No warning.

When signing certificates are obtained, populate the standard
`electron-builder` environment variables (`CSC_LINK`, `CSC_KEY_PASSWORD`,
`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, etc.) in the CI secrets.

## Future releases

When a v0.2.0 release is cut, copy this folder to `release/v0.2.0/` and
update version numbers (`package.json`, `release/v0.2.0/desktop/package.json`,
this README, and the workflow paths). Older release directories can be
kept around indefinitely as immutable build recipes.
