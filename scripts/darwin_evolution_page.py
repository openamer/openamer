#!/usr/bin/env python3
"""darwin_evolution_page.py — build the public evolution page (Phase 5).

Reads real Darwin data (history JSONL + latest status JSON) and renders a
STATIC, dependency-free HTML page with inline SVG charts:
  - population fitness over time (line chart from history snapshots)
  - top skills leaderboard
  - autopatch before/after bars
  - trend radar list
Output: docs/darwin-live/index.html (deployed by the existing darwin-pages
workflow on push, live at openamer.github.io/openamer/darwin-live/).

Zero LLM tokens, no JS deps, pure static.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(r"C:\Users\damir\openamer-repo")
HISTORY = REPO / "reports" / "darwin-history.jsonl"
STATUS = REPO / "reports" / "darwin-status-latest.json"
OUT = REPO / "docs" / "darwin-live" / "index.html"
W, H = 760, 260  # chart viewport


def load_history() -> list[dict]:
    if not HISTORY.exists():
        return []
    return [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]


def svg_line(points: list[tuple[float, float]], color: str) -> str:
    if len(points) < 2:
        return "<p class='muted'>Not enough history yet (need ≥2 snapshots).</p>"
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 == x0: x1 = x0 + 1
    if y1 == y0: y1 = y0 + 1
    def px(x): return 40 + (x - x0) / (x1 - x0) * (W - 60)
    def py(y): return H - 30 - (y - y0) / (y1 - y0) * (H - 50)
    poly = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in points)
    grid = "".join(
        f"<line x1='40' y1='{py(y0 + (y1-y0)*i/4):.0f}' x2='{W-20}' y2='{py(y0 + (y1-y0)*i/4):.0f}' stroke='#21262d'/>"
        for i in range(5))
    labels = (f"<text x='8' y='{py(y1):.0f}'>{y1:.0f}</text>"
              f"<text x='8' y='{py(y0):.0f}'>{y0:.0f}</text>"
              f"<text x='40' y='{H-8}'>{datetime.fromtimestamp(x0/1000).strftime('%d.%m')}</text>"
              f"<text x='{W-90}' y='{H-8}'>{datetime.fromtimestamp(x1/1000).strftime('%d.%m')}</text>")
    return (f"<svg width='{W}' height='{H}' style='background:#0d1117;border-radius:8px'>"
            f"{grid}<polyline points='{poly}' fill='none' stroke='{color}' stroke-width='2'/>"
            f"{labels}</svg>")


def main() -> int:
    history = load_history()
    status = {}
    try:
        status = json.loads(STATUS.read_text(encoding="utf-8"))
    except Exception:
        pass

    # series: avg fitness per snapshot
    series = []
    for e in history:
        ts = datetime.fromisoformat(e["when"]).timestamp() * 1000
        skills = e.get("skills", {})
        if skills:
            series.append((ts, sum(skills.values()) / len(skills)))
    chart_pop = svg_line(series, "#7ee787")

    fittest = status.get("fittest", [])[:8]
    rows = "".join(
        f"<tr><td><code>{html.escape(s['name'])}</code></td><td>{s['score']}</td></tr>"
        for s in fittest)

    kept = status.get("autopatch", {}).get("kept", [])
    patch_rows = "".join(
        f"<li><code>{html.escape(k['skill'])}</code>: {k['before']} → <b>{k['after']}</b></li>"
        for k in kept) or "<li class='muted'>no autopatch runs yet</li>"

    trends = status.get("trends", [])[:6]
    trend_rows = "".join(
        f"<li><span class='badge'>{html.escape(t['source'])}</span> "
        f"<a href='{html.escape(t['url'])}'>{html.escape(t['title'])}</a></li>"
        for t in trends) or "<li class='muted'>no trend data</li>"

    updated = status.get("updated", datetime.utcnow().isoformat())
    n_snaps = len(history)

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenAmer — Live Evolution</title>
<style>
  :root {{ --bg:#0d1117; --panel:#161b22; --border:#30363d; --text:#c9d1d9;
          --dim:#8b949e; --green:#7ee787; --blue:#79c0ff; }}
  * {{ margin:0; box-sizing:border-box; }}
  body {{ background:var(--bg); color:var(--text); font-family:-apple-system,'Segoe UI',Roboto,sans-serif;
          line-height:1.6; padding:2rem 1rem; }}
  .wrap {{ max-width:900px; margin:0 auto; }}
  h1 {{ color:var(--green); }} h2 {{ color:var(--blue); margin-top:2rem; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:1rem; margin:1.5rem 0; }}
  .card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:1rem 1.25rem; }}
  .card b {{ font-size:1.6rem; color:var(--green); }}
  table {{ border-collapse:collapse; width:100%; }}
  td, th {{ border:1px solid var(--border); padding:.4rem .8rem; text-align:left; }}
  code {{ color:var(--blue); }}
  a {{ color:var(--blue); }}
  li {{ margin:.3rem 0; }}
  .badge {{ background:#21262d; border-radius:99px; padding:.1rem .6rem; font-size:.75rem; }}
  .muted {{ color:var(--dim); }}
  .foot {{ margin-top:2rem; color:var(--dim); font-size:.85rem; }}
</style></head><body><div class="wrap">
<h1>🧬 OpenAmer Live Evolution</h1>
<p>This page is generated <b>entirely by the agent itself</b> — no human updates it.
Every number comes from real Darwin Engine runs on Damir's machine.</p>

<div class="cards">
  <div class="card"><b>{status.get('population', '—')}</b><br>skills in population</div>
  <div class="card"><b>{status.get('avg_score', '—')}</b><br>avg validator score</div>
  <div class="card"><b>{n_snaps}</b><br>fitness snapshots</div>
  <div class="card"><b>{status.get('species', '—')}</b><br>species installed</div>
</div>

<h2>Population average fitness over time</h2>
{chart_pop}

<h2>Fittest skills (validator, 100 pts)</h2>
<table><tr><th>Skill</th><th>Score</th></tr>{rows}</table>

<h2>Latest AutoPatch — self-repairs, verified</h2>
<ul>{patch_rows}</ul>

<h2>Trend radar → tomorrow's skills</h2>
<ul>{trend_rows}</ul>

<p class="foot">Generated {html.escape(updated)} by <code>darwin_evolution_page.py</code> ·
<a href="https://github.com/openamer/openamer">GitHub</a> ·
First agent-synthesized skill live: <code>agentic-commerce-payments</code> (score 51)</p>
</div></body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"written: {OUT} ({n_snaps} snapshots, {len(series)} chart points)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
