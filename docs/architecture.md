# Architecture

How a run proceeds in the current code, with the numbers that govern it. File paths are relative to the repository root. Defaults come from `src/config.py` unless stated otherwise.

## Entry points

- `scripts/run_batch.py` reads a YAML file of goals and runs them one after another. Each goal gets its own in-memory storage; all goals in the file share one cost tracker and therefore one budget. Each run is written to `data/runs/run_<timestamp>_<goal-id>.json` with an HTML report beside it, and both files are then renamed to end with a slug of the highest-rated hypothesis's title.
- `src/api/main.py` starts a run as a background task when a goal is posted to `/goals`. The task is cancelled after 600 seconds per allowed iteration, capped at the run time limit (6 hours).

Both call `SupervisorAgent.execute` in `src/agents/supervisor.py`.

## The run loop

1. The supervisor asks its model to turn the goal into evaluation criteria, domain constraints and a quality threshold. If the reply does not parse, it uses novelty, feasibility and testability.
2. It queues three generation tasks: two literature-exploration tasks and one simulated debate.
3. Each iteration then:
   - stops if the budget is spent;
   - computes statistics and checks the stop conditions (below);
   - recomputes the agent weights;
   - runs the four phases: Generation and Proximity; Reflection and Observation review; Ranking and Evolution; Meta-review;
   - ends the loop if no LLM call has succeeded for too long (below);
   - adds the latest meta-review's strengths, weaknesses and opportunities to the context memory (the last 30 entries are kept) and saves a checkpoint.
4. After the loop, the stored research overview is cleared and rebuilt from the hypotheses that pass the readiness gate, and a final checkpoint records the cost summary.

A run that ends without any hypothesis raises `RunAbortedError` with a plain-language reason instead of producing an empty report.

### Stop conditions

| Condition | Rule |
|---|---|
| Budget | Committed spend reaches the budget less the finalisation reserve (5% by default) |
| Time | 6 hours since the run started (`SUPERVISOR_MAX_EXECUTION_SECONDS=21600`); each iteration may take at most 10 minutes (`SUPERVISOR_ITERATION_TIMEOUT=600`) |
| Stalled LLM calls | Three iterations in a row in which no LLM task succeeded and at least one failed. If any of the failures was transient (a timeout, throttling or a 5xx after the client's own retries), the supervisor pauses between iterations (30 s, doubling up to 5 minutes) and ends the loop only once the stall has also lasted 10 minutes |
| Iteration limit | 20 by default (`max_iterations` in the batch file or the API request) |
| Convergence or quality | Elo convergence at least 0.9, or a mean review quality of the five highest-rated hypotheses of at least 0.85. Both count only after max(5, 0.7 × iteration limit) iterations, with at least six hypotheses, and while no hypothesis is still without a match |

The convergence score is computed over the ten highest-rated hypotheses as (1 − σ/100, clamped to 0 to 1) × the fraction of them whose rating has moved off 1200, where σ is the standard deviation of their ratings.

Once 85% of the time limit has passed, an iteration schedules only ranking tasks, for at most five such iterations, so that hypotheses created late still play matches.

## Scheduling

Each phase gives every agent in it `max(1, int(weight × 12))` task slots. A slot is filled from the task queue or, when the queue holds nothing for that agent, by a task the supervisor creates from the current state. Work that is already queued, running or done (the same review of the same hypothesis, the same pair, the proximity graph) is not dispatched twice. At most `MAX_WORKERS` (default 4) tasks run at once.

Base weights (`src/supervisor/statistics.py`):

| Agent | Weight |
|---|---|
| Ranking | 0.30 |
| Reflection | 0.25 |
| Generation | 0.15 |
| Evolution | 0.13 |
| Observation review | 0.08 |
| Proximity | 0.05 |
| Meta-review | 0.04 |

Before each iteration the weights are adjusted and renormalised: generation is halved when fewer than half of the hypotheses have progressed past their initial state, reflection is raised by half when more than five hypotheses await review, ranking is halved when convergence exceeds 0.8, and evolution is halved when fewer than 30% of evolved hypotheses outrank their parent or raised by half when more than 60% do. `ENABLE_EVOLUTION=false` sets the evolution weight to zero.

## Generation

After the seed tasks, each generation task picks a method at random: literature exploration 0.30, simulated debate 0.30, research expansion 0.25, iterative assumptions 0.15 (`src/agents/generation.py`). Research expansion is given the current research overview and meta-review. Every method receives the titles already in the pool and the context memory. The literature-exploration prompt comes from `02_Prompts/`; the other three methods build their prompts in `generation.py`.

- Literature retrieval runs for every generation task while `ENABLE_WEB_SEARCH` is on. It is cached per goal and later serves observation review.
- Generation stops being scheduled once the pool holds 40 hypotheses (`GENERATION_POOL_CAP`).
- A new hypothesis is compared by LLM similarity with the five highest-rated hypotheses and rejected at a score of 0.8 or more.
- With `SAFETY_THRESHOLD` above 0, the safety agent reviews each new and evolved hypothesis, and one that fails is set aside as `requires_safety_review`. At the default of 0 no safety review runs.

## Reviews

| Review | When it is scheduled |
|---|---|
| Initial | For every new or evolved hypothesis |
| Full | After a passed initial review, and each iteration for the five best initial-review scores without one |
| Deep verification | After a passed full review, and for the three highest-rated hypotheses with a passed full review |
| Simulation | For the three highest-rated hypotheses with a passed full review |
| Observation | For each hypothesis without a complete one, once the retrieved literature holds abstracts |

Reviews other than deep verification first run a refutation search on PubMed and Semantic Scholar for papers that contradict the hypothesis, and check its citations for retractions (`src/tools/refutation_search.py`). Deep verification breaks the hypothesis into its assumptions and judges each one, using the observation evidence the supervisor supplies (`src/agents/reflection.py`). Observation review extracts observations from paper abstracts in the retrieved citation graph and asks whether the hypothesis explains them (`src/agents/observation_review.py`).

### Readiness gate

`assess_readiness` in `src/scientific_readiness.py` is shared by the supervisor and the HTML report. A hypothesis is ready when:

- it is not archived or set aside by the safety review;
- its latest full review and its latest deep-verification review both passed;
- it has no failed simulation review;
- it cites at least one paper and every citation has the status `verified`;
- its observation review is complete, covers at least one observation and has a score.

Elo is not an input. The research overview written after each meta-review, and the final one, use up to five ready hypotheses; the final overview takes diversity-sampled candidates first. When no hypothesis is ready, the overview states that none can be recommended and the report lists, for each hypothesis, the checks it still needs.

## Tournament

`src/agents/ranking.py` runs each match as a debate: in each of three turns (the API option `tournament_rounds`, 1 to 10) an advocate for each hypothesis argues for it against the other, and a final prompt that includes the transcript names the winner. A match therefore costs seven LLM calls at the default. The Elo update is the standard one, with expected score 1 / (1 + 10^((R_b − R_a) / 400)) and change K × (result − expected), K = 32 by default (the API option `elo_k_factor`, 8 to 64). All hypotheses, evolved ones included, start at 1200.

A hypothesis can play once it has a review or is an evolved child. Pair selection is in `TournamentRanker.select_match_pairs` (`src/tournament/elo.py`):

- With a proximity graph, the target is max(20, half the pool) pairs, capped at the number of possible pairs. Up to 30% of them pair a hypothesis that has not played yet with an opponent drawn at random from the top half by rating; the rest are split 70% within clusters, 20% across clusters and the remainder among the top-rated. Pairs selected in earlier iterations are excluded.
- Without a proximity graph, the top-rated hypotheses (up to 20) each play their next two neighbours in the ranking, and the rest are paired with neighbours of similar rating.

The supervisor queues only as many of the selected pairs as the ranking agent has slots, but records every selected pair as used.

The proximity graph is rebuilt in phase 1 of every iteration once two hypotheses exist, because the proximity agent always receives one slot. It covers at most ten hypotheses (the first ten that storage returns for the goal) and is scored pair by pair by the LLM (`src/agents/proximity.py`); embedding-based similarity exists in that module but the supervisor does not configure it.

## Evolution

The parent is the first of the five highest-rated hypotheses that was not among the last three parents (`src/agents/evolution.py`). The strategy comes from `src/utils/strategy_selector.py`: with fewer than five hypotheses, out-of-the-box or inspiration at random; otherwise the first strategy whose keywords appear in the parent's reviews, checked in the order grounding, coherence, simplification, feasibility, out-of-the-box, combination, inspiration; otherwise a weighted random choice. The grounding keywords include common words such as "evidence", "research" and "studies", so reviewed parents mostly get the grounding strategy.

The child is a new hypothesis with a new ID, the parent's ID as lineage, a rating of 1200 and its own review cascade. It can cite only papers its parent already cites (the agent also accepts similar hypotheses as sources, but the supervisor does not pass any); any other reference the model writes is dropped. The parent is marked `evolved`.

## Literature tools

| Tool | Use | Rate limit |
|---|---|---|
| PubMed E-utilities (`src/tools/pubmed.py`) | Search and full records during generation; refutation search; retraction checks | 3 requests/s, 10 with `PUBMED_API_KEY` |
| Semantic Scholar (`src/tools/semantic_scholar.py`) | Search, citation-graph expansion, DOI lookups for citation checks | 1 request/s |
| Tavily (`src/utils/web_search.py`) | Fallback when the literature tools return nothing | Needs `TAVILY_API_KEY` |

Retrieved papers are scored as 0.5 × citation score + 0.3 × recency (half-life 5 years) + 0.2 × journal score (`src/literature/quality_scorer.py`); retracted papers are left out of prompts and citations, and limitations are extracted from the retrieved papers for the prompt context (`src/literature/limitations_extractor.py`).

Each citation in a generated hypothesis is checked by DOI, first against the retrieved papers and otherwise through Semantic Scholar. It is `verified` only when the paper found has a matching title; other statuses record a missing identifier (`no_identifier`), a different paper (`title_mismatch`) or no check (`not_checked`).

## Cost control

Prices per million tokens for every supported model are in `MODEL_PRICING` in `04_Scripts/cost_tracker.py`; the two default Gemini models are priced at their introductory rate until the end date recorded there. Before a request is sent, the client reserves its worst-case cost (prompt length in bytes plus 1,024 tokens of input, and the full output cap) and the request is refused if the reservation would pass the spend limit. A model without a price is refused outright. The reservation is settled with the reported token usage; a request that fails or reports no usage keeps its reserved cost. Costs are held in AUD at a fixed 1.55 per USD.

The iteration loop stops at the budget less the finalisation reserve (`FINALIZATION_RESERVE_FRACTION`, 0.05). The final meta-review, overview and report may use the whole budget.

The tracker is a process-wide singleton saved to `data/cost_tracking.json` relative to the working directory. A new process loads that file, including the budget stored in it, so spend carries over between local runs until the file is deleted. The API replaces the tracker's budget for the duration of a run when the request sets `budget_aud`.

## Failure handling

- Each LLM call has a timeout of `LLM_TIMEOUT_SECONDS` (300; at least 900 for Bedrock) and is retried with exponential backoff (`LLM_MAX_RETRIES=3`, base delay 1 s, capped at 30 s) when the error is transient (`src/utils/retry.py`). No other retry layer is active: all three clients switch off the retries of LangChain or botocore, so that every attempt takes its own budget reservation.
- A Bedrock reply stopped by the content filter raises `ContentFilteredError`, which is not retried; if the run ends without hypotheses, the failure reason names it.
- Replies that do not parse fail the task; while the pool is empty they count towards the stall limit, afterwards they do not.

## Storage and checkpoints

`STORAGE_BACKEND` selects `memory` (the default), `postgres`, or `cached` (PostgreSQL with Redis) (`src/storage/`). A `ContextMemory` checkpoint is saved after every iteration and once more at the end. `resume_from_checkpoint` restores the context memory and explored directions but then calls `execute`, which restarts the iteration count and the seed tasks; with the in-memory back end, checkpoints do not outlive the process.

## Relation to the paper

What follows the design of Gottweis et al. (arXiv:2502.18864): the agent set (generation, reflection, ranking, evolution, proximity, meta-review, supervisor), the four generation methods, the initial, full, deep-verification, observation and simulation reviews, the Elo tournament with new hypotheses entering at 1200, the evolution strategies, meta-review feedback added to later prompts, and the research overview.

Where this implementation differs:

- The paper's tournament review is defined as a review type in `03_architecture/schemas.py` but never scheduled.
- Every match is a multi-turn debate. The paper debates top-ranked hypotheses and compares lower-ranked ones in a single turn; `should_use_multi_turn` in `src/tournament/elo.py` implements that rule but is not called.
- There are no tools that call specialised models such as AlphaFold.
- A scientist cannot steer a run once it has started: feedback sent through the API is stored but not read by any agent, and the private document repository behind `src/api/documents.py` is not read by any agent.
- Additions not in the paper's design: the readiness gate, DOI checks on citations, refutation search in reviews, paper quality scoring, the AUD budget with per-request reservation, and the late-run phase that schedules only matches.
