# AGF Co-Scientist — Desktop Release

A polished, cross-platform desktop application that wraps the AGF Co-Scientist FastAPI backend and React frontend in a single downloadable installer per OS. **No Python install, no Node install, no manual `.env` editing.**

| Platform | Installer | First-launch note |
|----------|-----------|--------------------|
| **macOS** | `.dmg` (universal — Intel + Apple Silicon) | First open: right-click → Open (unsigned build, one-time Gatekeeper prompt) |
| **Windows** | `.exe` (NSIS one-click) | First open: SmartScreen → "More info" → "Run anyway" (unsigned build) |
| **Linux** | `.AppImage` | `chmod +x` once, then double-click |

Auto-update is enabled — the app checks GitHub Releases on launch and every 6 hours.

---

## For end users

### Download
Get the latest installer from the [Releases page](https://github.com/SynBioExplorer/AGF_Co-Scientist/releases) and run it.

### First-run setup (5-step wizard)

1. **Welcome** — short pitch.
2. **LLM providers** *(at least one required)* — paste API keys for any of:
   - **Google Gemini** — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
   - **OpenAI GPT** — [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
   - **DeepSeek** — [platform.deepseek.com](https://platform.deepseek.com/api_keys)
   - **Anthropic Claude** — [console.anthropic.com](https://console.anthropic.com/settings/keys)

   Each row has a **Test** button that makes a single cheap call to confirm the key works.

   > **Privacy:** Keys are stored only on your computer (OS keychain — macOS Keychain, Windows Credential Manager, Linux Secret Service). They are never sent anywhere except directly to the provider whose name appears next to them.

3. **Optional services** — toggle/key these on if you want richer literature retrieval:
   - **Tavily** (optional API key) — live web search during reflection
   - **Semantic Scholar** (free, no key) — citation graph + paper quality scoring
   - **NCBI PubMed** (optional API key) — higher PubMed rate limits

4. **Export folder** — pick where run reports (`.html`, `.json`) are saved. Defaults to `~/Documents/AGF Co-Scientist`.

5. **Email reports** *(optional)* — turn on, paste your email address. When a run finishes, the app opens your default mail client (Mail, Outlook, etc.) with the HTML report attached. No SMTP credentials needed.

### Mix-and-match LLM models per agent

Settings → **Models** lets you pick a different provider + model for each of the 8 agents. Example mix:

| Agent | Provider | Model |
|-------|----------|-------|
| Generation | OpenAI | gpt-5 |
| Reflection | Gemini | gemini-2.5-pro |
| Ranking | DeepSeek | deepseek-reasoner |
| Evolution | Anthropic | claude-opus-4-1 |
| Proximity | (default) | |
| Meta-review | Gemini | gemini-2.5-pro |
| Supervisor | (default) | |
| Safety | (default) | |

Any agent set to "Use default" inherits the global default model picked at the top of the tab.

---

## For developers — running from source

### Prerequisites
- **Python 3.11+** with `pip install -r requirements-api.txt`
- **Node.js 20+** and `npm`
- **Conda** *(optional but recommended)*

### Dev mode (hot-reload everywhere)
```bash
# One-time setup
npm install                       # installs Electron toolchain at repo root
cd frontend && npm install && cd ..

# Run all three processes concurrently
npm start
```
This spins up Vite on `:5173`, the FastAPI backend (also picks an ephemeral port in prod), and the Electron shell, all with hot reload.

### Production build
```bash
npm run build                     # frontend + sidecar + installer
```
Output lands in `dist/`. Per-OS targets are configured in `build/electron-builder.yml`.

### Per-OS native build
The sidecar is bundled by PyInstaller per platform:
```bash
# macOS / Linux
bash build/build-sidecar.sh

# Windows
powershell build/build-sidecar.ps1
```
Then `npm run build:electron` to produce the platform installer.

### Release pipeline
Tagging a commit `v*.*.*` triggers `.github/workflows/release.yml`, which builds on `macos-latest`, `windows-latest`, and `ubuntu-latest` in parallel and attaches the installers to a GitHub Release. `electron-updater` picks them up automatically on the next launch of installed clients.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Electron shell (desktop/main.js)                        │
│    • spawns Python sidecar on launch                     │
│    • IPC bridge for folder picker, mailto:, updates      │
│    • electron-updater → GitHub Releases                  │
│  ┌────────────────────────────────────────────────────┐  │
│  │  React 19 renderer (frontend/src/v2)               │  │
│  │    • motion.dev spring animations                  │  │
│  │    • Onboarding, Dashboard, Run, Results, Settings │  │
│  └────────────────────────────────────────────────────┘  │
│                       │                                  │
│                  HTTP loopback                           │
│                       │                                  │
│  ┌────────────────────▼───────────────────────────────┐  │
│  │  Python sidecar (PyInstaller --onefile)            │  │
│  │    • FastAPI, 8 agents, LangGraph                  │  │
│  │    • SQLite store in OS app-data dir               │  │
│  │    • 4 LLM clients: Gemini, OpenAI, DeepSeek, Claude│ │
│  │    • Per-agent model config                        │  │
│  │    • Keychain-backed secrets                       │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Data locations (per OS)
- **macOS:** `~/Library/Application Support/AGF Co-Scientist/`
- **Windows:** `%APPDATA%\AGF Co-Scientist\`
- **Linux:** `~/.local/share/AGF Co-Scientist/`

Contains: `coscientist.db` (SQLite), `port.txt` (current sidecar port), `logs/`.

---

## Tests

```bash
# Phase A — Python backend foundation (49 tests)
PYTHONPATH=03_architecture:04_Scripts:. python -m unittest discover -s 05_tests -p "phase5_*_test.py"

# Phase B — Electron / sidecar / IPC
npm run test:electron

# Phase C — Frontend
cd frontend && npm test          # vitest unit + component
cd frontend && npm run test:e2e  # Playwright E2E
```

CI runs all three on every push (`.github/workflows/ci.yml`).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| macOS: "App can't be opened, unidentified developer" | Right-click the app → Open → Open again. (One-time, per machine.) |
| Windows: SmartScreen blocks | Click "More info" → "Run anyway". (One-time.) |
| Linux: `.AppImage` won't run | `chmod +x AGF-Co-Scientist-*.AppImage` |
| App opens to blank window | Check `~/Library/Application Support/AGF Co-Scientist/logs/` (or equivalent). Most likely the sidecar failed to start. |
| Email button doesn't open mail client | Set a default mail handler in your OS. The HTML report is still saved to your export folder. |
| Key validation says "invalid" but works elsewhere | The provider may rate-limit the validation endpoint. Skip Test, finish setup, and try a real run. |

---

## Open caveats (v0.1.0)

- **Unsigned builds** — Apple notarization and Windows EV signing are deferred. One-time OS warning on first launch.
- **Icons are placeholders** — `build/icon.{icns,ico,png}` are placeholder files. Generate from a 1024×1024 master before the first public release; instructions in `build/README.md`.
- **`mailto:` attachments** are most reliable on macOS Mail and Outlook desktop; Gmail web requires drag-drop from the export folder, so the "Show in folder" button is shown alongside the email button.
- **Auto-update silently no-ops** until a tagged release exists on GitHub.
