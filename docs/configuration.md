# Configuration

## Where settings come from

`src/config.py` defines the settings and their defaults. Values come from environment variables and from `03_architecture/.env`; environment variables take precedence, and names are not case sensitive. The `.env` path is relative to the working directory, so start runs from the repository root. [`03_architecture/.env.example`](../03_architecture/.env.example) is the template.

Some values are read straight from the process environment rather than through `src/config.py`: `BEDROCK_INFERENCE_PROFILE_ARNS`, the LangSmith switches (`LANGSMITH_TRACING` or `LANGCHAIN_TRACING_V2`), and AWS credentials. `scripts/run_batch.py` loads `03_architecture/.env` into the process environment before anything else, so these work from the file for batch runs. The API server does not, so export them in the shell before starting `uvicorn`.

## Providers and models

`LLM_PROVIDER` selects `google` (default), `openai` or `bedrock` for every agent. Default models (`src/config.py`):

| Agent | `google` | `openai` | `bedrock` |
|---|---|---|---|
| Generation | `gemini-4-argon` | `gpt-5.1` | `anthropic.claude-opus-4-8` |
| Evolution | `gemini-4-argon` | `gpt-5.1` | `anthropic.claude-opus-4-8` |
| Meta-review | `gemini-3.8-flash` | `gpt-5` | `anthropic.claude-opus-4-8` |
| Reflection | `gemini-3.8-flash` | `gpt-5-mini` | `anthropic.claude-sonnet-5` |
| Ranking | `gemini-3.8-flash` | `gpt-5-mini` | `anthropic.claude-sonnet-5` |
| Supervisor | `gemini-3.8-flash` | `gpt-5-nano` | `anthropic.claude-sonnet-5` |

Change one with `<PROVIDER>_<AGENT>_MODEL`, for example `GOOGLE_GENERATION_MODEL`. Proximity and safety use the supervisor's model, and observation review uses the reflection model. A model needs an entry in `MODEL_PRICING` in `04_Scripts/cost_tracker.py`; requests to a model without a price are refused before they are sent.

To mix providers in one run, set `<AGENT>_PROVIDER_OVERRIDE` and `<AGENT>_MODEL_OVERRIDE` for any of `GENERATION`, `REFLECTION`, `RANKING`, `EVOLUTION`, `META_REVIEW` and `SUPERVISOR`:

```bash
GENERATION_PROVIDER_OVERRIDE=bedrock
GENERATION_MODEL_OVERRIDE=anthropic.claude-opus-4-8
```

Gemini calls carry a reasoning-token budget per agent (no cap for generation, meta-review and supervisor; 1,024 for evolution; 512 for reflection and observation review; 0 for ranking, proximity and safety). On Bedrock a budget of 0 switches Claude's thinking off; OpenAI calls carry no budget (`src/llm/factory.py`).

### Bedrock

- Credentials come from the standard AWS chain (an IAM role, a profile, or `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`); no Bedrock API key is read.
- `BEDROCK_REGION` defaults to `ap-southeast-2`.
- Without further settings, each model is invoked through a system inference profile: `au.` profiles for the Claude models and `global.` profiles for `openai.gpt-6-astra`, `openai.gpt-6-luna` and `moonshotai.kimi-k3` (`src/llm/bedrock.py`). Your account needs access to them in your region.
- To route calls through application inference profiles in your own account, set `BEDROCK_INFERENCE_PROFILE_ARNS` to a JSON object that maps model IDs to profile ARNs. Models missing from the map fall back to the system profiles.
- Bedrock calls have a timeout of at least 900 seconds and an output cap of 16,384 tokens, and send no temperature.

## Keys

| Variable | Needed for |
|---|---|
| `GOOGLE_API_KEY` | Always: `src/config.py` will not load without it, whichever provider you use |
| `OPENAI_API_KEY` | `LLM_PROVIDER=openai` or an OpenAI override |
| `TAVILY_API_KEY` | Web search fallback when PubMed and Semantic Scholar return nothing |
| `PUBMED_API_KEY` | Optional; raises the PubMed rate limit from 3 to 10 requests per second |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional; without it requests are anonymous |
| `LANGCHAIN_API_KEY` | LangSmith tracing, when `LANGCHAIN_TRACING_V2=true` |

`ANTHROPIC_API_KEY` is read into the settings but no client uses it; Claude is available through Bedrock only.

## Run limits

| Variable | Default | Effect |
|---|---|---|
| `BUDGET_AUD` | `50.0` | Spend limit in AUD for the process (a batch file's `budget_aud` replaces it) |
| `FINALIZATION_RESERVE_FRACTION` | `0.05` | Share of the budget the iteration loop leaves for the final synthesis |
| `SUPERVISOR_MAX_EXECUTION_SECONDS` | `21600` | Run time limit |
| `SUPERVISOR_ITERATION_TIMEOUT` | `600` | Time limit per iteration |
| `LLM_TIMEOUT_SECONDS` | `300` | Per-attempt timeout of an LLM call (Bedrock uses at least 900) |
| `LLM_MAX_RETRIES` | `3` | Retries after a transient LLM failure |
| `MAX_WORKERS` | `4` | Tasks running at once |
| `GENERATION_POOL_CAP` | `40` | Pool size at which generation stops being scheduled |
| `DRAIN_PHASE_START_FRACTION` | `0.85` | Share of the time limit after which only matches are scheduled |
| `DRAIN_MAX_ITERATIONS` | `5` | Iterations that may schedule matches in that phase |
| `SAFETY_THRESHOLD` | `0.0` | Minimum safety score for a hypothesis; `0` switches the safety review off |
| `ENABLE_WEB_SEARCH` | `true` | Literature retrieval during generation, which DOI checks and observation review depend on |
| `ENABLE_REFUTATION_SEARCH` | `true` | Search for contradicting papers during reviews; not affected by `ENABLE_WEB_SEARCH` |
| `ENABLE_EVOLUTION` | `true` | `false` gives the evolution agent no tasks |
| `META_REVIEW_MAX_REVIEWS` | `40` | Reviews shown to the meta-review prompt |

The spend record persists in `data/cost_tracking.json` relative to the working directory and is reloaded, budget included, by the next process; delete it to reset the budget.

## Storage

| Variable | Default | Effect |
|---|---|---|
| `STORAGE_BACKEND` | `memory` | `memory`, `postgres`, or `cached` (PostgreSQL with Redis) |
| `DATABASE_URL` | `postgresql://localhost:5432/coscientist` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |

The schema is in `src/storage/schema.sql`, with index migrations in `src/storage/migrations/`.

## Batch files

`scripts/run_batch.py` takes a YAML file (default `config/batch_goals.yaml`):

```yaml
budget_aud: 15.0        # shared by all goals in the file
max_iterations: 3
laboratory_context: |   # optional; given to every goal
  Equipment and methods available to you.
goals:
  - description: >
      The research goal in plain language.
    constraints: []
    preferences: []
```

## API run options

`POST /goals` takes `description`, `constraints`, `preferences`, `prior_publications` and an optional `config` object (`src/api/models.py`):

| Field | Range | Applied |
|---|---|---|
| `max_iterations` | 1 to 100, default 20 | Yes |
| `tournament_rounds` | 1 to 10 | Yes, debate turns per match |
| `elo_k_factor` | 8 to 64 | Yes |
| `budget_aud` | 0 to 10,000 | Yes, for this run |
| `safety_threshold` | 0 to 1 | Yes, for this run |
| `llm_timeout_seconds` | 30 to 900 | Yes, for this run |
| `enable_evolution`, `enable_web_search` | | No; the supervisor reads `ENABLE_EVOLUTION` and `ENABLE_WEB_SEARCH` |
| `llm_provider`, `default_model`, `default_temperature`, `agent_models` | | No |

The `X-LLM-Provider` request header switches the provider for the duration of a request and accepts `google` or `openai`. `PUT /settings` saves the web interface's preferences to `03_architecture/.runtime_settings.json`; only `GET /settings` reads that file back.

## Entries in `.env.example` that the code does not read

`BUDGET_LIMIT_AUD` (the budget variable is `BUDGET_AUD`), `USD_TO_AUD_RATE` (the rate is fixed in `04_Scripts/cost_tracker.py`), `COST_TRACKING_PATH`, `LOG_LEVEL`, `INITIAL_ELO_RATING`, `ELO_K_FACTOR`, `GOOGLE_PROXIMITY_MODEL` and `OPENAI_PROXIMITY_MODEL`.
