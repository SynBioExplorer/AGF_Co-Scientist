"""Generate a single self-contained bento-grid HTML report from a Co-Scientist run JSON.

The report is a light asymmetric bento grid with the AGF brand logo embedded inline.
No external file dependencies beyond Plotly and Google Fonts CDNs.
"""
from __future__ import annotations

import base64
import io
import json
import sys
from collections import Counter
from html import escape
from pathlib import Path


# Repo-relative default logo location (Google co-scientist/assets/AusGenome_LOGO_MAIN.png).
# Falls back gracefully to empty string if missing or Pillow unavailable.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOGO_PATH = _PROJECT_ROOT / "assets" / "AusGenome_LOGO_MAIN.png"


def _logo_data_uri(logo_path: Path = DEFAULT_LOGO_PATH, target_height_px: int = 96) -> str:
    """Load the AGF logo, resize to target height (preserving aspect), return data URI.

    target_height_px is 2-3x the intended display height for retina sharpness.
    Returns an empty string if Pillow is missing or the file isn't found.
    """
    try:
        from PIL import Image
    except ImportError:
        return ""
    if not logo_path.exists():
        return ""
    img = Image.open(logo_path).convert("RGBA")
    w, h = img.size
    new_h = target_height_px
    new_w = int(round(w * new_h / h))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def detect_theme(title: str) -> str:
    """Classify a hypothesis by keyword matching on its title."""
    t = title.lower()
    if any(k in t for k in ["nif", "nitrogen", "ammonia", "diazotrop"]):
        return "Nitrogen Fixation"
    if any(k in t for k in ["eps", "biofilm", "scaffold", "extracellular matrix", "capsul", "mineral"]):
        return "EPS/Biofilm"
    if any(k in t for k in ["redox", "rex", "nadh", "butanediol", "bdo", "nox", "metabolic valve", "capacitor"]):
        return "Redox/BDO"
    if any(k in t for k in ["resistance", "phage", "stress", "guardian", "firewall"]):
        return "Stress/Defense"
    if any(k in t for k in ["symbios", "consorti", "communit"]):
        return "Community"
    if any(k in t for k in ["isoprene", "volatile", "terpene", "mva", "xpk", "gas-phase", "sink"]):
        return "Volatile Metabolite"
    return "Other"


def prepare_data(run_json_path: Path) -> dict:
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
            "theme": detect_theme(h["title"]),
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


SHARED_LOGIC_JS = r"""
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


def render_v2_bento(p: dict, logo_path: Path = DEFAULT_LOGO_PATH) -> str:
    goal = p["goal"]
    goal_desc = escape(goal.get("description", ""))
    timestamp = escape(p["run_timestamp"])
    logo_uri = _logo_data_uri(logo_path=logo_path, target_height_px=96)
    data_js = (
        f"const DATA = {json.dumps(p['hyp_cards'], default=str)};\n"
        f"const THEMES = {json.dumps(p['theme_counts'])};\n"
        f"const METHODS = {json.dumps(p['method_counts'])};\n"
        f"const STATUSES = {json.dumps(p['status_counts'])};\n"
        f"const INSIGHTS = {json.dumps(p['insights'])};\n"
    )
    strongest_theme = max(p["theme_counts"], key=p["theme_counts"].get) if p["theme_counts"] else "—"
    strongest_count = max(p["theme_counts"].values()) if p["theme_counts"] else 0
    above_baseline = sum(1 for h in p["hyp_cards"] if h["elo"] > 1200)

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
.sect h4 {{ font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-dim); font-weight: 700; margin-bottom: 6px; }}
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
    <img class="agf-logo" src="{logo_uri}" alt="Australian Genome Foundry">
    <div class="sep"></div>
    <div class="label">AI Co-Scientist · Hypothesis Report
      <small>{timestamp}</small>
    </div>
  </div>
  <div style="font-family:var(--mono);font-size:11px;color:var(--ink-dim);">Macquarie University</div>
</div>

<section class="hero">
  <div>
    <div class="eyebrow">Research Goal · {timestamp[:10]}</div>
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
{SHARED_LOGIC_JS}

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

// Themes — explicit inline layout with categorical y-axis.
// Plotly mutates the layout object between newPlot calls, so the shared
// baseLight.yaxis gets a numeric range from the chart-elo call above; passing
// our own yaxis with type:'category' here keeps the bars rendering correctly.
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


def generate_html_report(run_json_path: str, output_path: str = None) -> str:
    """Read a run JSON and produce a self-contained interactive HTML file.

    Args:
        run_json_path: Path to run_*.json
        output_path: Optional output path. Defaults to same dir with .html extension.

    Returns:
        Path to generated HTML file.
    """
    src = Path(run_json_path)
    out = Path(output_path) if output_path else src.with_suffix(".html")
    prepared = prepare_data(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_v2_bento(prepared))
    return str(out)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m src.utils.html_report <run.json> [<out.html>]", file=sys.stderr)
        return 1
    src = Path(argv[1])
    if not src.exists():
        print(f"ERROR: source JSON not found: {src}", file=sys.stderr)
        return 1
    out = generate_html_report(str(src), argv[2] if len(argv) > 2 else None)
    out_path = Path(out)
    print(f"Wrote {out}  ({out_path.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
