# CLAUDE.md

Guidance for coding agents working in this repository. The [README](README.md) describes the system; [docs/architecture.md](docs/architecture.md) and [docs/configuration.md](docs/configuration.md) hold the reference detail.

## Where things are

- Run loop: `SupervisorAgent.execute` in `src/agents/supervisor.py`; agent weights and the convergence score in `src/supervisor/statistics.py`.
- Agents: `src/agents/`. Data models: `03_architecture/schemas.py`, imported as `schemas` through `sys.path`.
- LLM clients: `src/llm/`. Prices, budget reservation and the spend record: `04_Scripts/cost_tracker.py`.
- Readiness gate: `src/scientific_readiness.py`, shared by the supervisor and `src/utils/html_report.py`.
- Entry points: `scripts/run_batch.py` (command line, writes `data/runs/`) and `src/api/main.py` (FastAPI).

## Running

- Work from the repository root: `03_architecture/.env` and `data/cost_tracking.json` are resolved against the working directory.
- `src/config.py` needs `GOOGLE_API_KEY` at import, whatever the provider.
- Spend carries over between local runs through `data/cost_tracking.json`; delete it to reset the budget.
- Tests: `python -m pytest 05_tests/`. `phase1_test.py` to `phase3_test.py` call live APIs, and some tests skip without files from the private deployment.

## Conventions

- The notes in `03_architecture/Phase*/` are historical and describe earlier states of the code. Check the code, not those notes.
- Never commit `03_architecture/.env`.
- The deployment worker and its infrastructure are private and do not belong in this repository.
- Documentation uses British spelling and no em dashes.
