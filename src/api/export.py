"""Run export endpoints.

The desktop UX expects to email yourself a digest of a completed run.
We don't run an SMTP server locally; instead we build a ``mailto:`` URL
plus a path to the standalone HTML report and let the OS handle it.

    POST /api/runs/{run_id}/export/email
        -> { "mailto_url": "...", "html_report_path": "..." }
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.utils.paths import get_default_export_dir

router = APIRouter(prefix="/api", tags=["export"])

# Run IDs are written by the supervisor and look like `goal_20260413_035527_<hash>`.
# Restrict to a safe character set so a crafted ID can't escape the export dir
# via `..` segments when `_locate_run_artifacts` walks candidate folders.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class EmailExportResponse(BaseModel):
    mailto_url: str
    html_report_path: str


def _read_setup_state() -> dict:
    from src.api.setup import _read_state

    return _read_state()


def _resolve_export_dir() -> Path:
    state = _read_setup_state()
    folder = state.get("export_folder")
    if folder:
        return Path(folder).expanduser()
    return get_default_export_dir()


def _resolve_email() -> Optional[str]:
    state = _read_setup_state()
    email_cfg = state.get("email") or {}
    if email_cfg.get("enabled"):
        return email_cfg.get("recipient")
    return None


def _safe_basename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def _locate_run_artifacts(run_id: str) -> tuple[Optional[Path], Optional[Path]]:
    """Return (html_path, json_path) for the run, if they exist.

    Looks in multiple candidate folders (export dir, ``data/runs``, app data).
    """
    candidate_dirs = [
        _resolve_export_dir(),
        Path("data/runs").resolve(),
    ]
    # Also try the app data directory.
    try:
        from src.utils.paths import get_app_data_dir

        candidate_dirs.append(get_app_data_dir() / "runs")
    except Exception:
        pass

    sanitized = _safe_basename(run_id)
    html: Optional[Path] = None
    js: Optional[Path] = None
    for d in candidate_dirs:
        try:
            d = Path(d)
            if not d.exists():
                continue
        except Exception:
            continue
        for stem in (run_id, sanitized, f"run_{run_id}", f"run_{sanitized}"):
            for ext in (".html", ".htm"):
                p = d / f"{stem}{ext}"
                if p.exists() and html is None:
                    html = p
            p_json = d / f"{stem}.json"
            if p_json.exists() and js is None:
                js = p_json
    return html, js


def _summarize_for_email(json_path: Optional[Path]) -> str:
    if not json_path or not json_path.exists():
        return ""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""
    goal = data.get("goal") or {}
    description = goal.get("description") if isinstance(goal, dict) else None
    hyps = data.get("hypotheses") or []
    top = sorted(
        hyps if isinstance(hyps, list) else [],
        key=lambda h: (h.get("elo_rating") or 0) if isinstance(h, dict) else 0,
        reverse=True,
    )[:3]
    lines = []
    if description:
        lines.append(f"Goal: {description}")
        lines.append("")
    if top:
        lines.append("Top hypotheses:")
        for i, h in enumerate(top, start=1):
            title = (h.get("title") if isinstance(h, dict) else None) or "(untitled)"
            elo = (h.get("elo_rating") if isinstance(h, dict) else 0) or 0
            lines.append(f"  {i}. {title}  (Elo {elo:.0f})")
    return "\n".join(lines)


@router.post(
    "/runs/{run_id}/export/email", response_model=EmailExportResponse
)
async def export_run_email(run_id: str) -> EmailExportResponse:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")
    html_path, json_path = _locate_run_artifacts(run_id)
    if html_path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No HTML report found for run {run_id!r}. "
                f"Expected file named '{run_id}.html' or 'run_{run_id}.html' "
                f"in the export folder or data/runs/."
            ),
        )

    recipient = _resolve_email() or ""
    subject = f"AGF Co-Scientist - run {run_id}"
    body_lines = [
        f"Run ID: {run_id}",
        f"HTML report: {html_path}",
        "",
    ]
    summary = _summarize_for_email(json_path)
    if summary:
        body_lines.append(summary)
    body = "\n".join(body_lines)

    mailto = (
        f"mailto:{quote(recipient)}"
        f"?subject={quote(subject)}&body={quote(body)}"
    )
    return EmailExportResponse(
        mailto_url=mailto,
        html_report_path=str(html_path),
    )


__all__ = ["router"]
