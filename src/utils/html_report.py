"""Generate a self-contained interactive HTML report from a Co-Scientist run JSON.

The report is styled as a light asymmetric **bento grid** with the Australian
Genome Foundry brand identity: AGF logo (top-left, base64-inlined), AGF teal
``#05A5B0`` / green ``#B9D432`` / navy ``#101B34`` / peach ``#EE5F69`` accent
palette, and Raleway + JetBrains Mono typography.

Output is a single HTML file (~1 MB) carrying its own CSS, JavaScript, and
data, plus the AGF logo as a ``data:image/png;base64,...`` URI. Plotly + Google
Fonts come from CDNs.

Public API
----------
``generate_html_report(run_json_path, output_path=None) -> str``
    Read the run JSON, write the HTML file, return the output path.
    Signature preserved for callers in ``scripts/run_batch.py`` and
    ``src/api/export.py``.

Logo discovery
--------------
The logo is loaded from the first path that exists:

    1. ``src/utils/assets/AusGenome_LOGO_MAIN.png`` (bundled location — drop the
       PNG here)
    2. ``<repo_root>/AusGenome_LOGO_MAIN.png`` (legacy convenience)

If neither exists or Pillow is not installed, the brand row degrades
gracefully to a text-only label (no broken image icon).
"""

from __future__ import annotations

import base64
import io
import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Optional


_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent.parent
_LOGO_SEARCH_PATHS = (
    _MODULE_DIR / "assets" / "AusGenome_LOGO_MAIN.png",
    _REPO_ROOT / "AusGenome_LOGO_MAIN.png",
)


# ---------------------------------------------------------------------------
# Logo embedding
# ---------------------------------------------------------------------------
def _logo_data_uri(target_height_px: int = 96) -> str:
    """Return ``data:image/png;base64,...`` for the AGF logo, or ``""``.

    Resizes to ``target_height_px`` (2-3x the intended display height) so the
    embedded PNG stays sharp on retina displays. Returns an empty string when
    Pillow is missing or no logo file is found anywhere on the search path.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return ""

    src = next((p for p in _LOGO_SEARCH_PATHS if p.exists()), None)
    if src is None:
        return ""

    img = Image.open(src).convert("RGBA")
    w, h = img.size
    new_h = target_height_px
    new_w = int(round(w * new_h / h))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------
_THEME_KEYWORDS = (
    ("Nitrogen Fixation", ("nif", "nitrogen", "ammonia", "diazotrop")),
    ("EPS/Biofilm", ("eps", "biofilm", "scaffold", "extracellular matrix", "capsul", "mineral")),
    ("Redox/BDO", ("redox", "rex", "nadh", "butanediol", "bdo", "nox", "metabolic valve", "capacitor")),
    ("Stress/Defense", ("resistance", "phage", "stress", "guardian", "firewall")),
    ("Community", ("symbios", "consorti", "communit")),
    ("Volatile Metabolite", ("isoprene", "volatile", "terpene", "mva", "xpk", "gas-phase", "sink")),
)


def _detect_theme(title: str) -> str:
    """Classify a hypothesis by keyword matching on its title."""
    t = title.lower()
    for label, keywords in _THEME_KEYWORDS:
        if any(k in t for k in keywords):
            return label
    return "Other"


def _derive_themes_via_llm(hypotheses: list, goal_text: str) -> Optional[dict]:
    """Ask the meta-review model to bucket hypotheses into 3-6 run-specific themes.

    Returns ``{hypothesis_id: theme_label}`` on success, ``None`` on any
    failure (import error, LLM call failure, JSON parse failure). Callers
    should fall back to ``_detect_theme`` keyword matching when this
    returns ``None``.
    """
    if not hypotheses:
        return {}
    try:
        from src.llm.factory import get_llm_client
        from src.config import settings
    except Exception:
        return None

    indexed = [(i + 1, h.get("id"), h.get("title", "")) for i, h in enumerate(hypotheses)]
    titles_block = "\n".join(f"{i}. {t}" for i, _, t in indexed)
    prompt = (
        "Group these scientific hypotheses into 3-6 themes by shared mechanism, "
        "organism, technique, or approach.\n\n"
        f"GOAL: {goal_text}\n\n"
        f"HYPOTHESES:\n{titles_block}\n\n"
        "Requirements:\n"
        "- Each theme: 1-3 word label SPECIFIC to this goal "
        "(e.g. 'Library SCRaMbLE', 'Synthetic Lethality', 'Reporter Selection')\n"
        "- No 'Other' / 'General' / 'Miscellaneous' bucket\n"
        "- Every hypothesis must appear in exactly one theme\n"
        "- Aim for 2-4 hypotheses per theme; singletons are OK if genuinely unique\n\n"
        "Return ONLY valid JSON in this exact form:\n"
        '{"themes": {"<label>": [<1-based-index>, ...], ...}}'
    )

    try:
        client = get_llm_client(model=settings.meta_review_model, agent_name="meta_review")
        response = client.invoke(prompt)
        import re
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if not match:
            return None
        parsed = json.loads(match.group(0))
        themes_dict = parsed.get("themes", {})
        if not isinstance(themes_dict, dict) or not themes_dict:
            return None

        result: dict = {}
        for label, indices in themes_dict.items():
            if not isinstance(indices, list):
                continue
            for idx in indices:
                if isinstance(idx, int) and 1 <= idx <= len(indexed):
                    hyp_id = indexed[idx - 1][1]
                    if hyp_id:
                        result[hyp_id] = str(label)
        return result or None
    except Exception:
        return None


def _prepare_data(run_json_path: Path) -> dict:
    """Read a run JSON and return a dict of templating-ready fields."""
    with open(run_json_path) as f:
        data = json.load(f)

    hypotheses = data.get("hypotheses", [])
    reviews = data.get("reviews", [])
    matches = data.get("matches", [])
    goal = data.get("goal", {})
    context_memory = data.get("context_memory", {})

    review_map: dict[str, list] = {}
    for r in reviews:
        review_map.setdefault(r["hypothesis_id"], []).append(r)

    match_participation: dict[str, list] = {}
    for m in matches:
        for hid in (m["hypothesis_a_id"], m["hypothesis_b_id"]):
            match_participation.setdefault(hid, []).append(m)

    elo_values = [h["elo_rating"] for h in hypotheses]
    elo_min = min(elo_values) if elo_values else 0
    elo_max = max(elo_values) if elo_values else 0

    goal_text = (
        goal.get("description") or goal.get("text") or goal.get("goal") or ""
        if isinstance(goal, dict) else str(goal)
    )
    theme_overrides = _derive_themes_via_llm(hypotheses, goal_text) or {}

    hyp_cards = []
    for h in hypotheses:
        revs = review_map.get(h["id"], [])
        mats = match_participation.get(h["id"], [])
        wins = sum(1 for m in mats if m.get("winner_id") == h["id"])
        proto = h.get("experimental_protocol") or {}
        hyp_cards.append({
            "id": h["id"],
            "title": h["title"],
            "elo": h["elo_rating"],
            "status": h["status"],
            "method": h.get("generation_method", "unknown"),
            "theme": theme_overrides.get(h["id"]) or _detect_theme(h["title"]),
            "statement": h.get("hypothesis_statement", ""),
            "rationale": h.get("rationale", ""),
            "mechanism": h.get("mechanism", ""),
            "summary": h.get("summary", ""),
            "assumptions": h.get("assumptions", []),
            "parent_ids": h.get("parent_hypothesis_ids", []),
            "protocol": {
                "objective": proto.get("objective", ""),
                "methodology": proto.get("methodology", ""),
                "controls": proto.get("controls", []),
                "expected_outcomes": proto.get("expected_outcomes", []),
                "success_criteria": proto.get("success_criteria", ""),
                "materials": proto.get("materials", []),
                "limitations": proto.get("limitations", []),
                "estimated_timeline": proto.get("estimated_timeline", ""),
            },
            "citations": h.get("literature_citations", []),
            "reviews": [{
                "type": r.get("review_type", ""),
                "quality": r.get("quality_score"),
                "novelty": r.get("novelty_score"),
                "feasibility": r.get("feasibility_score"),
                "testability": r.get("testability_score"),
                "strengths": r.get("strengths", []),
                "weaknesses": r.get("weaknesses", []),
                "suggestions": r.get("suggestions", []),
                "rationale": r.get("rationale", ""),
            } for r in revs],
            "matches_played": len(mats),
            "wins": wins,
            "losses": len(mats) - wins,
        })

    # B4 fix: demote unreviewed hypotheses to the bottom of the leaderboard,
    # then sort by Elo desc within each group. Unreviewed cards (len==0) sort
    # AFTER reviewed cards (len>0) because False < True in Python.
    hyp_cards.sort(key=lambda x: (len(x["reviews"]) == 0, -x["elo"]))

    return {
        "goal": goal,
        "run_timestamp": data.get("run_timestamp", ""),
        "total_hyps": len(hypotheses),
        "total_reviews": len(reviews),
        "total_matches": len(matches),
        "elo_min": elo_min,
        "elo_max": elo_max,
        "hyp_cards": hyp_cards,
        "theme_counts": dict(Counter(h["theme"] for h in hyp_cards)),
        "method_counts": dict(Counter(h["method"] for h in hyp_cards)),
        "status_counts": dict(Counter(h["status"] for h in hyp_cards)),
        "insights": context_memory.get("accumulated_insights", []),
    }


# ---------------------------------------------------------------------------
# Inline JS: filter / sort / expand / render (variant-agnostic helpers)
# ---------------------------------------------------------------------------
_SHARED_LOGIC_JS = r"""
function populateFilters() {
  const ts = document.getElementById('filterTheme');
  Object.keys(THEMES).sort().forEach(t => {
    const o = document.createElement('option'); o.value = t;
    o.textContent = t + ' (' + THEMES[t] + ')'; ts.appendChild(o);
  });
  const ms = document.getElementById('filterMethod');
  Object.keys(METHODS).sort().forEach(m => {
    const o = document.createElement('option'); o.value = m;
    o.textContent = m.replace(/_/g,' ') + ' (' + METHODS[m] + ')'; ms.appendChild(o);
  });
  const ss = document.getElementById('filterStatus');
  Object.keys(STATUSES).sort().forEach(s => {
    const o = document.createElement('option'); o.value = s;
    o.textContent = s.replace(/_/g,' ') + ' (' + STATUSES[s] + ')'; ss.appendChild(o);
  });
}
function eloClass(elo) { return elo > 1200 ? 'above' : elo < 1200 ? 'below' : 'even'; }
function avgScore(reviews, field) {
  if (!reviews.length) return null;
  return reviews.reduce((s,r) => s + (r[field]||0), 0) / reviews.length;
}
let currentData = [...DATA];
function renderAll() {
  document.getElementById('cards-container').innerHTML =
    currentData.map((h, i) => renderCard(h, i + 1)).join('');
}
function filterCards() {
  const q = (document.getElementById('search').value || '').toLowerCase();
  const theme = document.getElementById('filterTheme').value;
  const method = document.getElementById('filterMethod').value;
  const status = document.getElementById('filterStatus').value;
  currentData = DATA.filter(h => {
    if (q) {
      const hay = (h.title + ' ' + h.statement + ' ' + h.mechanism + ' ' + h.summary).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (theme && h.theme !== theme) return false;
    if (method && h.method !== method) return false;
    if (status && h.status !== status) return false;
    return true;
  });
  sortCards();
}
function sortCards() {
  const by = document.getElementById('sortBy').value;
  currentData.sort((a, b) => {
    if (by === 'elo') return b.elo - a.elo;
    if (by === 'wins') return b.wins - a.wins;
    if (by === 'quality') return (avgScore(b.reviews,'quality')||0) - (avgScore(a.reviews,'quality')||0);
    if (by === 'novelty') return (avgScore(b.reviews,'novelty')||0) - (avgScore(a.reviews,'novelty')||0);
    return 0;
  });
  renderAll();
}
function esc(s){ return (s==null?'':String(s)).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function nl2br(s){ return esc(s).replace(/\n/g, '<br>'); }
"""


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------
def _render_html(p: dict) -> str:
    goal = p["goal"]
    goal_desc = escape(goal.get("description", ""))
    timestamp = escape(p["run_timestamp"])
    logo_uri = _logo_data_uri(target_height_px=96)

    # Brand row: include the <img> only when we actually have a logo; degrade
    # to a text-only label otherwise so no broken-image icon is rendered.
    if logo_uri:
        brand_left = (
            f'<img class="agf-logo" src="{logo_uri}" alt="Australian Genome Foundry">'
            f'<div class="sep"></div>'
            f'<div class="label">AI Co-Scientist · Hypothesis Report'
            f'<small>{timestamp}</small></div>'
        )
    else:
        brand_left = (
            f'<div class="label">Australian Genome Foundry'
            f'<small>AI Co-Scientist · Hypothesis Report · {timestamp}</small></div>'
        )

    data_js = (
        f"const DATA = {json.dumps(p['hyp_cards'], default=str)};\n"
        f"const THEMES = {json.dumps(p['theme_counts'])};\n"
        f"const METHODS = {json.dumps(p['method_counts'])};\n"
        f"const STATUSES = {json.dumps(p['status_counts'])};\n"
        f"const INSIGHTS = {json.dumps(p['insights'])};\n"
    )
    strongest_theme = (
        max(p["theme_counts"], key=p["theme_counts"].get) if p["theme_counts"] else "—"
    )
    strongest_count = max(p["theme_counts"].values()) if p["theme_counts"] else 0
    above_baseline = sum(1 for h in p["hyp_cards"] if h["elo"] > 1200)
    date_prefix = timestamp[:10] if timestamp else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Co-Scientist · Bento · {timestamp}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
:root {{
  --bg: oklch(0.985 0.005 90);
  --surface: oklch(1 0 0);
  --surface-2: oklch(0.97 0.008 90);
  --line: oklch(0.92 0.01 90);
  --line-soft: oklch(0.95 0.008 90);
  --ink: oklch(0.18 0.02 260);
  --ink-2: oklch(0.36 0.02 260);
  --ink-dim: oklch(0.52 0.015 260);
  --teal: #05A5B0;
  --teal-50: oklch(0.93 0.04 200);
  --green: #B9D432;
  --green-50: oklch(0.94 0.06 115);
  --peach: #EE5F69;
  --navy: #101B34;
  --sans: 'Raleway', system-ui, sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, monospace;
  --ease: cubic-bezier(0.23, 1, 0.32, 1);
  --r: 14px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: var(--sans); background: var(--bg); color: var(--ink);
  font-size: 15px; line-height: 1.55; -webkit-font-smoothing: antialiased;
}}
button, input, select {{ font: inherit; color: inherit; }}
.shell {{ max-width: 1340px; margin: 0 auto; padding: 32px 28px 80px; }}

.brand-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }}
.brand-id {{ display: flex; align-items: center; gap: 16px; }}
.brand-id .agf-logo {{ height: 40px; width: auto; display: block; flex-shrink: 0; }}
.brand-id .sep {{ width: 1px; height: 28px; background: var(--line); flex-shrink: 0; }}
.brand-id .label {{ font-size: 13px; color: var(--ink-2); font-weight: 600; letter-spacing: 0.01em; }}
.brand-id .label small {{ display: block; color: var(--ink-dim); font-weight: 400; font-size: 11px; font-family: var(--mono); margin-top: 2px; }}

.hero {{
  background: var(--surface); border-radius: 24px; padding: 36px 40px;
  border: 1px solid var(--line);
  display: grid; grid-template-columns: 1.5fr 1fr; gap: 40px;
  align-items: start; margin-bottom: 16px;
}}
.hero .eyebrow {{
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--teal); margin-bottom: 14px;
}}
.hero .eyebrow::before {{ content: ''; width: 16px; height: 1px; background: var(--teal); }}
.hero h1 {{
  font-size: 30px; font-weight: 700; line-height: 1.2;
  letter-spacing: -0.018em; color: var(--ink);
  margin-bottom: 14px; max-width: 38ch;
}}
.hero .meta {{ margin-top: 24px; display: flex; gap: 20px; flex-wrap: wrap; font-size: 12px; color: var(--ink-dim); }}
.hero .meta strong {{ color: var(--ink); font-weight: 600; }}
.hero-stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.stat-tile {{ background: var(--surface-2); border-radius: 14px; padding: 18px; border: 1px solid var(--line-soft); }}
.stat-tile .l {{ font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-dim); }}
.stat-tile .v {{ font-family: var(--mono); font-size: 26px; font-weight: 500; color: var(--ink); margin-top: 6px; line-height: 1; }}
.stat-tile.teal {{ background: var(--teal-50); }}
.stat-tile.teal .v {{ color: var(--teal); }}
.stat-tile.green {{ background: var(--green-50); }}
.stat-tile.green .v {{ color: oklch(0.5 0.12 115); }}

.bento {{
  display: grid; grid-template-columns: repeat(6, 1fr);
  grid-auto-rows: minmax(160px, auto); gap: 12px; margin-bottom: 28px;
}}
.bcard {{
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r);
  padding: 18px; display: flex; flex-direction: column;
  transition: border-color 160ms var(--ease);
}}
.bcard:hover {{ border-color: var(--ink-dim); }}
.bcard h3 {{ font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-dim); font-weight: 600; margin-bottom: 8px; }}
.bcard.span-3 {{ grid-column: span 3; }}
.bcard.span-2 {{ grid-column: span 2; }}
.bcard.tall {{ grid-row: span 2; }}
.bcard.green {{ background: var(--green); color: var(--navy); border-color: var(--green); }}
.bcard.teal {{ background: var(--teal); color: white; border-color: var(--teal); }}
.bcard.teal h3 {{ color: rgba(255,255,255,0.7); }}
.bcard .big {{ font-family: var(--mono); font-size: 42px; line-height: 1; font-weight: 500; margin-top: auto; letter-spacing: -0.01em; }}
.bcard .note {{ font-size: 12px; color: var(--ink-dim); margin-top: 6px; }}
.bcard.teal .note {{ color: rgba(255,255,255,0.65); }}

.controls {{
  display: flex; gap: 10px; flex-wrap: wrap;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: 18px; padding: 12px 14px; margin-bottom: 16px;
  position: sticky; top: 12px; z-index: 10;
  box-shadow: 0 1px 0 oklch(0.92 0.005 90 / 0.4), 0 8px 24px oklch(0.18 0.02 260 / 0.04);
}}
.controls input, .controls select {{
  background: var(--surface-2); border: 1px solid var(--line);
  border-radius: 10px; padding: 9px 12px; font-size: 13px; color: var(--ink);
  transition: border-color 140ms var(--ease);
}}
.controls input {{ flex: 1; min-width: 220px; }}
.controls input::placeholder {{ color: var(--ink-dim); }}
.controls input:focus, .controls select:focus {{ outline: none; border-color: var(--teal); }}

#cards-container {{ display: grid; grid-template-columns: repeat(6, 1fr); grid-auto-flow: dense; gap: 12px; }}
.bh {{
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r);
  padding: 20px 22px; display: flex; flex-direction: column; cursor: pointer; position: relative;
  transition: border-color 200ms var(--ease), transform 200ms var(--ease), box-shadow 200ms var(--ease);
}}
.bh:hover {{ border-color: var(--ink-dim); transform: translateY(-1px); box-shadow: 0 6px 20px oklch(0.18 0.02 260 / 0.06); }}
.bh:active {{ transform: scale(0.997); }}
.bh.open {{ box-shadow: 0 8px 32px oklch(0.18 0.02 260 / 0.10); border-color: var(--teal); }}
.bh.size-xl {{ grid-column: span 6; }}
.bh.size-lg {{ grid-column: span 3; }}
.bh.size-md {{ grid-column: span 2; }}
.bh.size-sm {{ grid-column: span 2; }}
.bh .badge-line {{ display: flex; gap: 8px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }}
.bh .rank {{ font-family: var(--mono); font-size: 11px; color: var(--ink-dim); font-weight: 500; }}
.bh .b {{ font-size: 10px; padding: 3px 8px; border-radius: 100px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600; }}
.bh .b.theme {{ background: var(--teal-50); color: oklch(0.4 0.08 200); }}
.bh .b.method {{ background: var(--surface-2); color: var(--ink-2); border: 1px solid var(--line); }}
.bh .b.status {{ background: var(--green-50); color: oklch(0.4 0.12 115); }}
.bh .elo {{ margin-left: auto; font-family: var(--mono); font-size: 14px; font-weight: 600; }}
.bh .elo.above {{ color: oklch(0.5 0.12 115); }}
.bh .elo.below {{ color: var(--peach); }}
.bh .elo.even {{ color: var(--ink-dim); }}
.bh h2 {{ font-size: 18px; font-weight: 600; line-height: 1.3; letter-spacing: -0.01em; color: var(--ink); }}
.bh.size-xl h2 {{ font-size: 26px; line-height: 1.2; max-width: 30ch; }}
.bh.size-lg h2 {{ font-size: 19px; }}
.bh .smry {{
  font-size: 13px; color: var(--ink-2); margin-top: 10px; line-height: 1.55;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}}
.bh.size-xl .smry {{ -webkit-line-clamp: 4; font-size: 15px; max-width: 70ch; }}
.bh-foot {{ margin-top: auto; padding-top: 12px; display: flex; justify-content: space-between; font-family: var(--mono); font-size: 11px; color: var(--ink-dim); }}

.bh-body {{ display: grid; grid-template-rows: 0fr; transition: grid-template-rows 280ms var(--ease); }}
.bh-body > div {{ overflow: hidden; }}
.bh.open .bh-body {{ grid-template-rows: 1fr; }}
.bh-body-inner {{ padding-top: 18px; border-top: 1px solid var(--line-soft); margin-top: 16px; }}
.sect {{ margin: 14px 0; }}
.sect h4 {{ font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-dim); font-weight: 600; margin-bottom: 6px; }}
.sect .body {{ font-size: 14px; color: var(--ink); line-height: 1.6; white-space: pre-wrap; }}
.sect ul {{ padding-left: 18px; font-size: 13px; }}
.sect li {{ margin: 4px 0; }}
.proto-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.proto-grid .f .k {{ font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--teal); margin-bottom: 4px; font-weight: 600; }}
.proto-grid .f .v {{ font-size: 13px; color: var(--ink-2); white-space: pre-wrap; }}
.cites {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.cite {{ font-size: 11px; padding: 4px 10px; border-radius: 100px; background: var(--surface-2); border: 1px solid var(--line); color: var(--ink-2); }}
.review-tile {{ background: var(--surface-2); border-left: 3px solid var(--teal); border-radius: 0 10px 10px 0; padding: 12px 14px; margin-bottom: 8px; }}
.review-tile .sc {{ display: flex; gap: 12px; font-family: var(--mono); font-size: 11px; color: var(--ink-dim); margin-bottom: 6px; flex-wrap: wrap; }}
.review-tile .sc strong {{ color: var(--ink); margin-left: 4px; }}
.review-tile .sub {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink-dim); margin: 6px 0 3px; font-weight: 600; }}
.review-tile ul {{ padding-left: 16px; font-size: 12px; color: var(--ink-2); }}

.insights {{ background: var(--navy); color: white; border-radius: var(--r); padding: 26px 28px; margin-top: 18px; }}
.insights h3 {{ font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--green); margin-bottom: 12px; font-weight: 600; }}
.insights ul {{ list-style: none; display: grid; gap: 6px; }}
.insights li {{ font-size: 14px; line-height: 1.5; padding-left: 16px; position: relative; color: oklch(0.92 0.005 90); }}
.insights li::before {{ content: '·'; position: absolute; left: 0; color: var(--teal); font-weight: 700; }}
.footer {{ margin-top: 32px; text-align: center; font-size: 12px; color: var(--ink-dim); }}

@media (max-width: 920px) {{
  .hero {{ grid-template-columns: 1fr; }}
  .hero h1 {{ font-size: 28px; }}
  .bento {{ grid-template-columns: repeat(2, 1fr); }}
  .bcard.span-3, .bcard.span-2 {{ grid-column: span 2; }}
  #cards-container {{ grid-template-columns: 1fr; }}
  .bh.size-xl, .bh.size-lg, .bh.size-md, .bh.size-sm {{ grid-column: span 1; }}
}}
</style>
</head>
<body>
<div class="shell">

<div class="brand-row">
  <div class="brand-id">
    {brand_left}
  </div>
  <div style="font-family:var(--mono);font-size:11px;color:var(--ink-dim);">Macquarie University</div>
</div>

<section class="hero">
  <div>
    <div class="eyebrow">Research Goal · {date_prefix}</div>
    <h1>{goal_desc}</h1>
    <div class="meta">
      <span><strong>{p['total_hyps']}</strong> hypotheses generated</span>
      <span><strong>{p['total_reviews']}</strong> structured reviews</span>
      <span><strong>{p['total_matches']}</strong> tournament matches</span>
    </div>
  </div>
  <div class="hero-stats">
    <div class="stat-tile teal"><div class="l">Top Elo</div><div class="v">{p['elo_max']:.0f}</div></div>
    <div class="stat-tile green"><div class="l">Range</div><div class="v">{p['elo_max']-p['elo_min']:.0f}</div></div>
    <div class="stat-tile"><div class="l">Themes</div><div class="v">{len(p['theme_counts'])}</div></div>
    <div class="stat-tile"><div class="l">Methods</div><div class="v">{len(p['method_counts'])}</div></div>
  </div>
</section>

<div class="bento">
  <div class="bcard span-3 tall"><h3>Elo distribution</h3><div id="chart-elo" style="flex:1;min-height:240px"></div></div>
  <div class="bcard span-2"><h3>Themes</h3><div id="chart-themes" style="flex:1;min-height:140px"></div></div>
  <div class="bcard teal">
    <h3>Above baseline</h3>
    <div class="big">{above_baseline}</div>
    <div class="note">hypotheses Elo &gt; 1200</div>
  </div>
  <div class="bcard span-2"><h3>Methods</h3><div id="chart-methods" style="flex:1;min-height:140px"></div></div>
  <div class="bcard green">
    <h3>Strongest theme</h3>
    <div class="big" style="font-size:22px;font-family:var(--sans);font-weight:700;letter-spacing:-0.01em;">{strongest_theme}</div>
    <div class="note">{strongest_count} hypotheses</div>
  </div>
</div>

<div class="controls">
  <input type="text" id="search" placeholder="Search hypotheses..." oninput="filterCards()">
  <select id="filterTheme" onchange="filterCards()"><option value="">All themes</option></select>
  <select id="filterMethod" onchange="filterCards()"><option value="">All methods</option></select>
  <select id="filterStatus" onchange="filterCards()"><option value="">All statuses</option></select>
  <select id="sortBy" onchange="sortCards()">
    <option value="elo">Sort: Elo</option>
    <option value="quality">Sort: Quality</option>
    <option value="novelty">Sort: Novelty</option>
    <option value="wins">Sort: Wins</option>
  </select>
</div>

<div id="cards-container"></div>

<section class="insights">
  <h3>Context memory insights</h3>
  <ul id="insights-list"></ul>
</section>

<div class="footer">Generated by AI Co-Scientist · Australian Genome Foundry · Macquarie University</div>
</div>

<script>
{data_js}
{_SHARED_LOGIC_JS}

function bentoSize(rank) {{
  if (rank === 1) return 'size-xl';
  if (rank <= 3) return 'size-lg';
  if (rank <= 9) return 'size-md';
  return 'size-sm';
}}

function renderCard(h, rank) {{
  const size = bentoSize(rank);
  const proto = h.protocol;
  const protoFields = [
    ['Objective', proto.objective],
    ['Methodology', proto.methodology],
    ['Controls', proto.controls.join(' · ')],
    ['Expected outcomes', proto.expected_outcomes.join(' · ')],
    ['Success criteria', proto.success_criteria],
    ['Materials', proto.materials.join(' · ')],
    ['Limitations', proto.limitations.join(' · ')],
    ['Timeline', proto.estimated_timeline],
  ].filter(([_, v]) => v);

  const reviewsHtml = h.reviews.map(r => `<div class="review-tile">
    <div class="sc">
      <span>Quality<strong>${{r.quality ?? '–'}}</strong></span>
      <span>Novelty<strong>${{r.novelty ?? '–'}}</strong></span>
      <span>Feasibility<strong>${{r.feasibility ?? '–'}}</strong></span>
      <span>Type<strong>${{esc(r.type)}}</strong></span>
    </div>
    ${{r.strengths.length ? `<div class="sub">Strengths</div><ul>${{r.strengths.map(s=>'<li>'+esc(s)+'</li>').join('')}}</ul>` : ''}}
    ${{r.weaknesses.length ? `<div class="sub">Weaknesses</div><ul>${{r.weaknesses.map(s=>'<li>'+esc(s)+'</li>').join('')}}</ul>` : ''}}
    ${{r.suggestions.length ? `<div class="sub">Suggestions</div><ul>${{r.suggestions.map(s=>'<li>'+esc(s)+'</li>').join('')}}</ul>` : ''}}
  </div>`).join('');

  return `<article class="bh ${{size}}" onclick="this.classList.toggle('open')">
    <div class="badge-line">
      <span class="rank">#${{String(rank).padStart(2,'0')}}</span>
      <span class="b theme">${{esc(h.theme)}}</span>
      <span class="b method">${{esc(h.method.replace(/_/g, ' '))}}</span>
      <span class="b status">${{esc(h.status.replace(/_/g, ' '))}}</span>
      <span class="elo ${{eloClass(h.elo)}}">${{h.elo.toFixed(0)}}</span>
    </div>
    <h2>${{esc(h.title)}}</h2>
    ${{h.summary ? `<p class="smry">${{esc(h.summary)}}</p>` : ''}}
    <div class="bh-foot">
      <span>${{h.wins}}W · ${{h.losses}}L · ${{h.citations.length}} cites</span>
      <span>Click to expand →</span>
    </div>
    <div class="bh-body"><div><div class="bh-body-inner">
      ${{h.statement ? `<div class="sect"><h4>Hypothesis statement</h4><div class="body">${{nl2br(h.statement)}}</div></div>` : ''}}
      ${{h.rationale ? `<div class="sect"><h4>Rationale</h4><div class="body">${{nl2br(h.rationale)}}</div></div>` : ''}}
      ${{h.mechanism ? `<div class="sect"><h4>Mechanism</h4><div class="body">${{nl2br(h.mechanism)}}</div></div>` : ''}}
      ${{protoFields.length ? `<div class="sect"><h4>Experimental protocol</h4>
        <div class="proto-grid">${{protoFields.map(([k,v]) => `<div class="f"><div class="k">${{k}}</div><div class="v">${{nl2br(v)}}</div></div>`).join('')}}</div></div>` : ''}}
      ${{h.citations.length ? `<div class="sect"><h4>Citations</h4><div class="cites">${{
        h.citations.map((c,i) => '<span class="cite">[' + (i+1) + '] ' + esc((c.title||c.doi||'').slice(0,80)) + '</span>').join('')
      }}</div></div>` : ''}}
      ${{h.parent_ids.length ? `<div class="sect"><h4>Evolved from</h4><div class="body" style="font-family:var(--mono);font-size:11px;color:var(--ink-dim)">${{h.parent_ids.map(esc).join(', ')}}</div></div>` : ''}}
      ${{reviewsHtml ? `<div class="sect"><h4>Reviews (${{h.reviews.length}})</h4>${{reviewsHtml}}</div>` : ''}}
    </div></div></div>
  </article>`;
}}

populateFilters();
renderAll();

document.getElementById('insights-list').innerHTML =
  INSIGHTS.map(i => '<li>' + esc(i) + '</li>').join('') || '<li>No insights recorded.</li>';

// Plotly — bento (light)
const lightFont = {{ family: 'Raleway', color: '#5a5e6a', size: 11 }};
const baseLight = {{
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: lightFont, margin: {{ t: 4, b: 28, l: 36, r: 8 }},
  xaxis: {{ gridcolor: '#ececec', linecolor: '#cccccc', tickfont: lightFont, zeroline: false }},
  yaxis: {{ gridcolor: '#ececec', linecolor: '#cccccc', tickfont: lightFont, zeroline: false }},
}};

Plotly.newPlot('chart-elo', [{{
  x: DATA.map((h,i)=>i+1), y: DATA.map(h=>h.elo),
  type: 'scatter', mode: 'markers',
  marker: {{
    color: DATA.map(h => h.elo > 1200 ? '#7CB342' : h.elo < 1200 ? '#EE5F69' : '#9aa0aa'),
    size: 9, line: {{ width: 0 }}
  }},
  text: DATA.map(h => h.title.slice(0,60)),
  hovertemplate: '%{{text}}<br>Elo %{{y:.0f}}<extra></extra>'
}}], baseLight, {{ displayModeBar: false, responsive: true }});

// Themes — explicit inline layout with categorical y-axis. Plotly mutates the
// shared layout object between newPlot calls, so the baseLight.yaxis gets a
// numeric range from the chart-elo call above; passing our own yaxis with
// type:'category' here keeps the bars rendering correctly.
Plotly.newPlot('chart-themes', [{{
  x: Object.values(THEMES), y: Object.keys(THEMES),
  type: 'bar', orientation: 'h',
  marker: {{ color: '#05A5B0', line: {{ width: 0 }} }}
}}], {{
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: lightFont,
  margin: {{ t: 4, b: 24, l: 120, r: 6 }},
  xaxis: {{ gridcolor: '#ececec', linecolor: '#cccccc', tickfont: lightFont, zeroline: false }},
  yaxis: {{ type: 'category', tickfont: lightFont, automargin: true, linecolor: '#cccccc' }}
}}, {{ displayModeBar: false, responsive: true }});

Plotly.newPlot('chart-methods', [{{
  labels: Object.keys(METHODS).map(m => m.replace(/_/g,' ')),
  values: Object.values(METHODS), type: 'pie',
  marker: {{ colors: ['#05A5B0', '#B9D432', '#EE5F69', '#101B34', '#9AC9D1'], line: {{ color: '#fff', width: 2 }} }},
  textinfo: 'percent', textfont: {{ family: 'Raleway', color: '#fff', size: 10, weight: 600 }},
  hole: 0.5
}}], {{ ...baseLight, margin: {{ t: 4, b: 4, l: 4, r: 4 }}, showlegend: false }}, {{ displayModeBar: false, responsive: true }});
</script>
</body></html>
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_html_report(run_json_path: str, output_path: Optional[str] = None) -> str:
    """Read a run JSON and produce a self-contained interactive HTML file.

    Args:
        run_json_path: Path to ``run_*.json``.
        output_path: Optional output path. Defaults to the same directory with
            a ``.html`` extension.

    Returns:
        Path to the generated HTML file.
    """
    src = Path(run_json_path)
    out = Path(output_path) if output_path else src.with_suffix(".html")
    prepared = _prepare_data(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render_html(prepared))
    return str(out)
