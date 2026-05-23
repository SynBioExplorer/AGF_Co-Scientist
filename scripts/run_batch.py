"""Sequential batch runner for the AI Co-Scientist.

Reads goals from a YAML file and runs them one after another, sharing a single
budget pool (cost tracker singleton). Each goal gets its own AsyncStorageAdapter
instance and dumps its own run_<ts>_<goal_id>.json + matching .html into data/runs/.

Usage:
    conda activate coscientist
    python scripts/run_batch.py                     # uses config/batch_goals.yaml
    python scripts/run_batch.py path/to/other.yaml
"""

import sys
import os
from pathlib import Path

# Repo root on path BEFORE other imports
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "03_architecture"))
sys.path.insert(0, str(REPO_ROOT / "04_Scripts"))  # cost_tracker lives here

# Load .env BEFORE importing src.* — LangSmith reads env at import time
from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "03_architecture" / ".env")

import asyncio
import json
import re
import yaml
from datetime import datetime

from src.config import settings
from src.storage.async_adapter import AsyncStorageAdapter
from src.agents.supervisor import SupervisorAgent
from src.utils.html_report import generate_html_report
from src.utils.ids import generate_id
from schemas import ResearchGoal


def _slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    s = re.sub(r"[\s_-]+", "_", s).strip("_")
    return s[:max_len].rstrip("_") or "untitled"


def _rename_outputs(json_paths: list[Path]) -> None:
    """Rename produced run_*.json and run_*.html pairs to include the
    top-Elo hypothesis title as a slug. Idempotent: skips if already renamed."""
    for json_path in json_paths:
        if not json_path.exists():
            continue
        try:
            with open(json_path) as f:
                data = json.load(f)
            hyps = data.get("hypotheses", []) or []
            if not hyps:
                continue
            top = max(hyps, key=lambda h: h.get("elo_rating", 0))
            slug = _slugify(top.get("title", ""))
            stem = json_path.stem  # run_<ts>_<goal_id>
            new_stem = f"{stem}_{slug}"
            new_json = json_path.with_name(new_stem + ".json")
            old_html = json_path.with_suffix(".html")
            new_html = json_path.with_name(new_stem + ".html")
            if new_json != json_path:
                json_path.rename(new_json)
                print(f"[batch] renamed {json_path.name} -> {new_json.name}")
            if old_html.exists() and new_html != old_html:
                old_html.rename(new_html)
                print(f"[batch] renamed {old_html.name} -> {new_html.name}")
        except Exception as e:
            print(f"[batch] WARN: rename failed for {json_path}: {e}", file=sys.stderr)


def _model_to_dict(obj):
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


async def _dump_run(storage: AsyncStorageAdapter, goal: ResearchGoal, result: str) -> Path:
    hyps = await storage.get_hypotheses_by_goal(goal.id)
    reviews = await storage.get_all_reviews(goal_id=goal.id)
    matches = await storage.get_all_matches(goal_id=goal.id)
    overview = await storage.get_research_overview(goal.id)
    meta = await storage.get_meta_review(goal.id)
    checkpoint = await storage.get_latest_checkpoint(goal.id)

    payload = {
        "goal": _model_to_dict(goal),
        "result": result,
        "run_timestamp": datetime.now().isoformat(),
        "total_hypotheses": len(hyps),
        "total_reviews": len(reviews),
        "total_matches": len(matches),
        "hypotheses": [_model_to_dict(h) for h in hyps],
        "reviews": [_model_to_dict(r) for r in reviews],
        "matches": [_model_to_dict(m) for m in matches],
        "research_overview": _model_to_dict(overview),
        "meta_review": _model_to_dict(meta),
        "context_memory": _model_to_dict(checkpoint),
    }

    runs_dir = REPO_ROOT / "data" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = runs_dir / f"run_{ts}_{goal.id}.json"
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    try:
        generate_html_report(str(json_path))
    except Exception as e:
        print(f"[batch] WARN: HTML report generation failed for {goal.id}: {e}", file=sys.stderr)

    return json_path


async def run_one(goal_cfg: dict, max_iters: int, lab_context: str) -> Path:
    storage = AsyncStorageAdapter()
    goal = ResearchGoal(
        id=generate_id("goal"),
        description=goal_cfg["description"].rstrip(),
        constraints=goal_cfg.get("constraints", []) or [],
        preferences=goal_cfg.get("preferences", []) or [],
        laboratory_context=lab_context.rstrip() if lab_context else None,
    )
    supervisor = SupervisorAgent(storage)
    result = await supervisor.execute(goal, max_iterations=max_iters)
    return await _dump_run(storage, goal, result)


async def main(cfg_path: Path):
    cfg = yaml.safe_load(cfg_path.read_text())
    settings.budget_aud = float(cfg.get("budget_aud", settings.budget_aud))
    max_iters = int(cfg.get("max_iterations", 20))
    lab_context = cfg.get("laboratory_context", "") or ""
    goals = cfg["goals"]

    print(f"[batch] {len(goals)} goals, budget=${settings.budget_aud:.2f} AUD shared, "
          f"max_iterations={max_iters}")

    produced_paths: list[Path] = []
    for i, goal_cfg in enumerate(goals, 1):
        print(f"\n[batch] === goal {i}/{len(goals)} ===")
        print(f"[batch] description: {goal_cfg['description'].strip()[:120]}...")
        try:
            out = await run_one(goal_cfg, max_iters, lab_context)
            produced_paths.append(out)
            print(f"[batch] goal {i} -> {out}")
        except Exception as e:
            print(f"[batch] goal {i} FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    print("\n[batch] all goals processed; renaming outputs by top-Elo title")
    _rename_outputs(produced_paths)
    print("[batch] done")


if __name__ == "__main__":
    cfg_arg = sys.argv[1] if len(sys.argv) > 1 else "config/batch_goals.yaml"
    cfg_path = Path(cfg_arg)
    if not cfg_path.is_absolute():
        cfg_path = REPO_ROOT / cfg_arg
    if not cfg_path.exists():
        print(f"config not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(cfg_path))
