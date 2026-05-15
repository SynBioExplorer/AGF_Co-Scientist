# Build pipeline

This directory contains everything needed to package the AGF Co-Scientist
desktop application from source.

## Pipeline overview

```
frontend/  --(vite build)-->  frontend/dist/
src/api/   --(PyInstaller)-->  desktop/resources/sidecar/agf-coscientist-backend[.exe]
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
# 1. Frontend bundle
cd frontend && npm ci && npm run build && cd ..

# 2. Python sidecar (produces a universal-2 binary if running on Apple Silicon
#    with the universal2 Python build).
bash build/build-sidecar.sh

# 3. .dmg
npx electron-builder --config build/electron-builder.yml --mac
```

Output: `dist/AGF Co-Scientist-<version>-universal.dmg`.

### Windows

```powershell
cd frontend; npm ci; npm run build; cd ..
powershell -File build/build-sidecar.ps1
npx electron-builder --config build/electron-builder.yml --win
```

Output: `dist\AGF Co-Scientist-<version>-setup.exe` (NSIS one-click installer).

### Linux

```bash
cd frontend && npm ci && npm run build && cd ..
bash build/build-sidecar.sh
npx electron-builder --config build/electron-builder.yml --linux
```

Output: `dist/AGF Co-Scientist-<version>.AppImage`.

## CI

GitHub Actions (`.github/workflows/release.yml`) runs the same pipeline on
`macos-latest`, `windows-latest`, and `ubuntu-latest` whenever a `v*.*.*`
git tag is pushed. The resulting artefacts are uploaded to the matching
GitHub Release; electron-updater consumes them for auto-update on launch.

## Signing / notarisation

**Not enabled for v1.** Installers are unsigned, so users will see a
one-time:

* macOS — "“AGF Co-Scientist” cannot be opened because the developer
  cannot be verified." Right-click → Open → Open.
* Windows — SmartScreen "Windows protected your PC". Click "More info"
  → "Run anyway".
* Linux — `chmod +x AGF*.AppImage && ./AGF*.AppImage`. No warning.

When signing certificates are obtained, populate the standard
`electron-builder` environment variables (`CSC_LINK`, `CSC_KEY_PASSWORD`,
`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, etc.) in the CI secrets.
