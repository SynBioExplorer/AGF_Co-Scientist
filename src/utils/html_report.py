"""Generate an interactive HTML report from a Co-Scientist run JSON."""

import json
from pathlib import Path
from html import escape


def generate_html_report(run_json_path: str, output_path: str = None) -> str:
    """Read a run JSON and produce a self-contained interactive HTML file.

    Args:
        run_json_path: Path to run_*.json
        output_path: Optional output path. Defaults to same dir with .html extension.

    Returns:
        Path to generated HTML file.
    """
    with open(run_json_path) as f:
        data = json.load(f)

    if not output_path:
        output_path = str(Path(run_json_path).with_suffix(".html"))

    hypotheses = data.get("hypotheses", [])
    reviews = data.get("reviews", [])
    matches = data.get("matches", [])
    goal = data.get("goal", {})
    context_memory = data.get("context_memory", {})

    # Build lookup maps
    review_map = {}
    for r in reviews:
        review_map.setdefault(r["hypothesis_id"], []).append(r)

    match_participation = {}
    for m in matches:
        for hid in [m["hypothesis_a_id"], m["hypothesis_b_id"]]:
            match_participation.setdefault(hid, []).append(m)

    # Stats
    total_hyps = len(hypotheses)
    total_reviews = len(reviews)
    total_matches = len(matches)
    elo_values = [h["elo_rating"] for h in hypotheses]
    elo_min = min(elo_values) if elo_values else 0
    elo_max = max(elo_values) if elo_values else 0

    # Theme detection
    def detect_theme(title):
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
        return "Other"

    # Build hypothesis cards JSON
    hyp_cards = []
    for h in hypotheses:
        revs = review_map.get(h["id"], [])
        mats = match_participation.get(h["id"], [])
        wins = sum(1 for m in mats if m.get("winner_id") == h["id"])
        theme = detect_theme(h["title"])
        proto = h.get("experimental_protocol") or {}

        hyp_cards.append({
            "id": h["id"],
            "title": h["title"],
            "elo": h["elo_rating"],
            "status": h["status"],
            "method": h.get("generation_method", "unknown"),
            "theme": theme,
            "statement": h.get("hypothesis_statement", ""),
            "rationale": h.get("rationale", ""),
            "mechanism": h.get("mechanism", ""),
            "summary": h.get("summary", ""),
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
                "strengths": r.get("strengths", []),
                "weaknesses": r.get("weaknesses", []),
                "suggestions": r.get("suggestions", []),
                "rationale": r.get("rationale", ""),
            } for r in revs],
            "matches_played": len(mats),
            "wins": wins,
            "losses": len(mats) - wins,
        })

    # Sort by Elo descending
    hyp_cards.sort(key=lambda x: x["elo"], reverse=True)

    # Theme counts for chart
    from collections import Counter
    theme_counts = Counter(h["theme"] for h in hyp_cards)
    method_counts = Counter(h["method"] for h in hyp_cards)
    status_counts = Counter(h["status"] for h in hyp_cards)

    html = _render_html(
        goal=goal,
        hyp_cards=hyp_cards,
        total_hyps=total_hyps,
        total_reviews=total_reviews,
        total_matches=total_matches,
        elo_min=elo_min,
        elo_max=elo_max,
        theme_counts=dict(theme_counts),
        method_counts=dict(method_counts),
        status_counts=dict(status_counts),
        run_timestamp=data.get("run_timestamp", ""),
        context_memory=context_memory,
        matches=matches,
    )

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def _render_html(*, goal, hyp_cards, total_hyps, total_reviews, total_matches,
                 elo_min, elo_max, theme_counts, method_counts, status_counts,
                 run_timestamp, context_memory, matches):
    """Render the full HTML page."""

    cards_json = json.dumps(hyp_cards, default=str)
    matches_json = json.dumps(matches, default=str)
    theme_json = json.dumps(theme_counts)
    method_json = json.dumps(method_counts)
    status_json = json.dumps(status_counts)
    insights_json = json.dumps(context_memory.get("accumulated_insights", []))

    goal_desc = escape(goal.get("description", ""))
    constraints = goal.get("constraints", [])
    preferences = goal.get("preferences", [])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Co-Scientist Report</title>
<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<style>
:root {{
  --bg: #0f1117;
  --surface: #1a1d27;
  --card: #222635;
  --border: #2d3348;
  --text: #e1e4ed;
  --text-dim: #8b90a0;
  --accent: #6c8cff;
  --green: #4ade80;
  --red: #f87171;
  --yellow: #fbbf24;
  --font: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: var(--font); line-height: 1.6; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 4px; }}
h2 {{ font-size: 1.3rem; font-weight: 600; margin: 32px 0 16px; color: var(--accent); }}
h3 {{ font-size: 1rem; font-weight: 600; margin: 16px 0 8px; }}

/* Header */
.header {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 24px; }}
.header-meta {{ display: flex; gap: 24px; flex-wrap: wrap; margin-top: 12px; }}
.stat {{ background: var(--card); border-radius: 8px; padding: 12px 20px; text-align: center; min-width: 120px; }}
.stat-value {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
.stat-label {{ font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }}

/* Controls */
.controls {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 24px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }}
.controls input, .controls select {{ background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px; font-size: 0.9rem; }}
.controls input {{ flex: 1; min-width: 200px; }}
.controls select {{ min-width: 140px; }}

/* Charts */
.charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.chart-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }}

/* Cards */
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 12px; overflow: hidden; transition: border-color 0.2s; }}
.card:hover {{ border-color: var(--accent); }}
.card-header {{ padding: 16px 20px; cursor: pointer; display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }}
.card-title {{ font-weight: 600; flex: 1; }}
.card-badges {{ display: flex; gap: 6px; flex-shrink: 0; flex-wrap: wrap; }}
.badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
.badge-elo {{ background: var(--card); color: var(--accent); font-size: 0.85rem; }}
.badge-elo.above {{ color: var(--green); }}
.badge-elo.below {{ color: var(--red); }}
.badge-method {{ background: #1e293b; color: #93c5fd; }}
.badge-theme {{ background: #1e2937; color: #6ee7b7; }}
.badge-status {{ background: #27233b; color: #c4b5fd; }}
.badge-wl {{ background: var(--card); color: var(--text-dim); }}

.card-body {{ display: none; padding: 0 20px 20px; }}
.card-body.open {{ display: block; }}
.section {{ margin-bottom: 16px; }}
.section-title {{ font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
.section-content {{ color: var(--text); font-size: 0.9rem; white-space: pre-wrap; }}
.tag {{ display: inline-block; background: var(--card); padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; margin: 2px; }}
.review-box {{ background: var(--card); border-radius: 8px; padding: 12px; margin-bottom: 8px; }}
.review-scores {{ display: flex; gap: 16px; margin-bottom: 8px; }}
.review-score {{ font-size: 0.8rem; }}
.review-score span {{ font-weight: 700; color: var(--accent); }}
ul {{ padding-left: 20px; }}
li {{ font-size: 0.85rem; margin-bottom: 2px; }}

/* Rank number */
.rank {{ font-size: 1.1rem; font-weight: 700; color: var(--text-dim); min-width: 30px; }}

/* Footer */
.footer {{ margin-top: 40px; padding: 20px; text-align: center; color: var(--text-dim); font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
  <h1>AI Co-Scientist Report</h1>
  <p style="color:var(--text-dim); margin-top:4px;">Run: {escape(run_timestamp)}</p>
  <p style="margin-top:8px;">{goal_desc}</p>
  <div class="header-meta">
    <div class="stat"><div class="stat-value">{total_hyps}</div><div class="stat-label">Hypotheses</div></div>
    <div class="stat"><div class="stat-value">{total_reviews}</div><div class="stat-label">Reviews</div></div>
    <div class="stat"><div class="stat-value">{total_matches}</div><div class="stat-label">Matches</div></div>
    <div class="stat"><div class="stat-value">{elo_min:.0f}-{elo_max:.0f}</div><div class="stat-label">Elo Range</div></div>
  </div>
</div>

<!-- Controls -->
<div class="controls">
  <input type="text" id="search" placeholder="Search hypotheses..." oninput="filterCards()">
  <select id="filterTheme" onchange="filterCards()">
    <option value="">All Themes</option>
  </select>
  <select id="filterMethod" onchange="filterCards()">
    <option value="">All Methods</option>
  </select>
  <select id="filterStatus" onchange="filterCards()">
    <option value="">All Statuses</option>
  </select>
  <select id="sortBy" onchange="sortCards()">
    <option value="elo">Sort by Elo</option>
    <option value="quality">Sort by Quality</option>
    <option value="novelty">Sort by Novelty</option>
    <option value="wins">Sort by Wins</option>
  </select>
</div>

<!-- Charts -->
<div class="charts">
  <div class="chart-box"><div id="chart-themes"></div></div>
  <div class="chart-box"><div id="chart-elo"></div></div>
  <div class="chart-box"><div id="chart-methods"></div></div>
</div>

<!-- Hypothesis Cards -->
<h2>Hypotheses</h2>
<div id="cards-container"></div>

<!-- Context Memory -->
<h2>Context Memory Insights</h2>
<div id="insights-container" style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;"></div>

<div class="footer">
  Generated by AI Co-Scientist | Australian Genome Foundry, Macquarie University
</div>
</div>

<script>
const DATA = {cards_json};
const MATCHES = {matches_json};
const THEMES = {theme_json};
const METHODS = {method_json};
const STATUSES = {status_json};
const INSIGHTS = {insights_json};

// Populate filter dropdowns
const themeSelect = document.getElementById('filterTheme');
Object.keys(THEMES).sort().forEach(t => {{
  const o = document.createElement('option'); o.value = t; o.textContent = t + ' (' + THEMES[t] + ')';
  themeSelect.appendChild(o);
}});
const methodSelect = document.getElementById('filterMethod');
Object.keys(METHODS).sort().forEach(m => {{
  const o = document.createElement('option'); o.value = m; o.textContent = m.replace(/_/g,' ') + ' (' + METHODS[m] + ')';
  methodSelect.appendChild(o);
}});
const statusSelect = document.getElementById('filterStatus');
Object.keys(STATUSES).sort().forEach(s => {{
  const o = document.createElement('option'); o.value = s; o.textContent = s.replace(/_/g,' ') + ' (' + STATUSES[s] + ')';
  statusSelect.appendChild(o);
}});

function eloClass(elo) {{ return elo > 1200 ? 'above' : elo < 1200 ? 'below' : ''; }}

function renderCard(h, rank) {{
  const avgQ = h.reviews.length ? (h.reviews.reduce((s,r) => s + (r.quality||0), 0) / h.reviews.length).toFixed(2) : '-';
  const avgN = h.reviews.length ? (h.reviews.reduce((s,r) => s + (r.novelty||0), 0) / h.reviews.length).toFixed(2) : '-';

  let reviewsHtml = '';
  h.reviews.forEach(r => {{
    reviewsHtml += `<div class="review-box">
      <div class="review-scores">
        <div class="review-score">Quality: <span>${{r.quality||'-'}}</span></div>
        <div class="review-score">Novelty: <span>${{r.novelty||'-'}}</span></div>
        <div class="review-score">Type: ${{r.type}}</div>
      </div>
      ${{r.strengths.length ? '<b>Strengths:</b><ul>' + r.strengths.map(s=>'<li>'+s+'</li>').join('') + '</ul>' : ''}}
      ${{r.weaknesses.length ? '<b>Weaknesses:</b><ul>' + r.weaknesses.map(s=>'<li>'+s+'</li>').join('') + '</ul>' : ''}}
      ${{r.suggestions.length ? '<b>Suggestions:</b><ul>' + r.suggestions.map(s=>'<li>'+s+'</li>').join('') + '</ul>' : ''}}
    </div>`;
  }});

  const proto = h.protocol;
  const citationsHtml = h.citations.map(c =>
    `<div class="tag">${{c.title || c.doi || 'Citation'}}</div>`
  ).join('');

  return `<div class="card" data-theme="${{h.theme}}" data-method="${{h.method}}" data-status="${{h.status}}"
               data-elo="${{h.elo}}" data-quality="${{avgQ}}" data-novelty="${{avgN}}" data-wins="${{h.wins}}">
    <div class="card-header" onclick="this.nextElementSibling.classList.toggle('open')">
      <span class="rank">#${{rank}}</span>
      <span class="card-title">${{h.title}}</span>
      <div class="card-badges">
        <span class="badge badge-elo ${{eloClass(h.elo)}}">${{h.elo.toFixed(0)}}</span>
        <span class="badge badge-theme">${{h.theme}}</span>
        <span class="badge badge-method">${{h.method.replace(/_/g,' ')}}</span>
        <span class="badge badge-wl">${{h.wins}}W/${{h.losses}}L</span>
      </div>
    </div>
    <div class="card-body">
      ${{h.summary ? '<div class="section"><div class="section-title">Summary</div><div class="section-content">' + h.summary + '</div></div>' : ''}}
      <div class="section"><div class="section-title">Hypothesis Statement</div><div class="section-content">${{h.statement}}</div></div>
      <div class="section"><div class="section-title">Rationale</div><div class="section-content">${{h.rationale}}</div></div>
      <div class="section"><div class="section-title">Mechanism</div><div class="section-content">${{h.mechanism}}</div></div>
      <div class="section"><div class="section-title">Experimental Protocol</div>
        <div class="section-content">
          ${{proto.objective ? '<b>Objective:</b> ' + proto.objective + '<br>' : ''}}
          ${{proto.methodology ? '<b>Methodology:</b> ' + proto.methodology + '<br>' : ''}}
          ${{proto.controls && proto.controls.length ? '<b>Controls:</b> ' + proto.controls.join('; ') + '<br>' : ''}}
          ${{proto.expected_outcomes && proto.expected_outcomes.length ? '<b>Expected outcomes:</b> ' + proto.expected_outcomes.join('; ') + '<br>' : ''}}
          ${{proto.success_criteria ? '<b>Success criteria:</b> ' + proto.success_criteria + '<br>' : ''}}
          ${{proto.materials && proto.materials.length ? '<b>Materials:</b> ' + proto.materials.join('; ') + '<br>' : ''}}
          ${{proto.limitations && proto.limitations.length ? '<b>Limitations:</b> ' + proto.limitations.join('; ') + '<br>' : ''}}
          ${{proto.estimated_timeline ? '<b>Timeline:</b> ' + proto.estimated_timeline : ''}}
        </div>
      </div>
      ${{h.citations.length ? '<div class="section"><div class="section-title">Citations</div>' + citationsHtml + '</div>' : ''}}
      ${{h.parent_ids.length ? '<div class="section"><div class="section-title">Evolved from</div><div class="section-content">' + h.parent_ids.join(', ') + '</div></div>' : ''}}
      ${{reviewsHtml ? '<div class="section"><div class="section-title">Reviews (' + h.reviews.length + ')</div>' + reviewsHtml + '</div>' : ''}}
    </div>
  </div>`;
}}

let currentData = [...DATA];
function renderAll() {{
  const container = document.getElementById('cards-container');
  container.innerHTML = currentData.map((h, i) => renderCard(h, i + 1)).join('');
}}

function filterCards() {{
  const q = document.getElementById('search').value.toLowerCase();
  const theme = document.getElementById('filterTheme').value;
  const method = document.getElementById('filterMethod').value;
  const status = document.getElementById('filterStatus').value;
  currentData = DATA.filter(h => {{
    if (q && !h.title.toLowerCase().includes(q) && !h.statement.toLowerCase().includes(q) && !h.mechanism.toLowerCase().includes(q)) return false;
    if (theme && h.theme !== theme) return false;
    if (method && h.method !== method) return false;
    if (status && h.status !== status) return false;
    return true;
  }});
  sortCards();
}}

function sortCards() {{
  const by = document.getElementById('sortBy').value;
  currentData.sort((a, b) => {{
    if (by === 'elo') return b.elo - a.elo;
    if (by === 'wins') return b.wins - a.wins;
    const getAvg = (h, field) => h.reviews.length ? h.reviews.reduce((s,r) => s + (r[field]||0), 0) / h.reviews.length : 0;
    if (by === 'quality') return getAvg(b, 'quality') - getAvg(a, 'quality');
    if (by === 'novelty') return getAvg(b, 'novelty') - getAvg(a, 'novelty');
    return 0;
  }});
  renderAll();
}}

// Charts
const chartLayout = {{ paper_bgcolor: '#1a1d27', plot_bgcolor: '#1a1d27', font: {{ color: '#e1e4ed', size: 12 }}, margin: {{ t: 40, b: 30, l: 40, r: 20 }} }};

Plotly.newPlot('chart-themes', [{{
  x: Object.keys(THEMES), y: Object.values(THEMES), type: 'bar',
  marker: {{ color: '#6c8cff' }}
}}], {{ ...chartLayout, title: 'Themes' }}, {{ responsive: true }});

Plotly.newPlot('chart-elo', [{{
  x: DATA.map((h,i) => i+1), y: DATA.map(h => h.elo), type: 'scatter', mode: 'markers',
  marker: {{ color: DATA.map(h => h.elo > 1200 ? '#4ade80' : h.elo < 1200 ? '#f87171' : '#8b90a0'), size: 8 }},
  text: DATA.map(h => h.title.slice(0,40))
}}], {{ ...chartLayout, title: 'Elo Distribution', xaxis: {{ title: 'Rank' }}, yaxis: {{ title: 'Elo' }} }}, {{ responsive: true }});

Plotly.newPlot('chart-methods', [{{
  labels: Object.keys(METHODS).map(m => m.replace(/_/g,' ')),
  values: Object.values(METHODS), type: 'pie',
  marker: {{ colors: ['#6c8cff', '#4ade80', '#fbbf24', '#f87171'] }},
  textinfo: 'label+value'
}}], {{ ...chartLayout, title: 'Generation Methods' }}, {{ responsive: true }});

// Insights
const insightsContainer = document.getElementById('insights-container');
insightsContainer.innerHTML = INSIGHTS.map(i => '<div style="margin-bottom:6px;font-size:0.85rem;">- ' + i + '</div>').join('');

// Initial render
renderAll();
</script>
</body>
</html>'''
