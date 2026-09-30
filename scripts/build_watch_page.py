#!/usr/bin/env python3
"""Render the national slope picture as one self-contained interactive page.

Every number and every dot comes from `pahiro.watch`, which reads real CHIRPS rainfall
for the whole country on each date. Switch dates and the country changes.

    python scripts/build_watch_page.py --out reports/watch.html
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.watch import national_status, summarise

ROOT = Path(__file__).resolve().parents[1]

# Westernmost/easternmost and southernmost/northernmost points of the benchmark.
BOUNDS = {"lon0": 80.0, "lon1": 88.5, "lat0": 26.2, "lat1": 30.5}


def build(dates: list[date]) -> dict:
    frames = []
    for d in dates:
        st = national_status(d)
        if not st:
            print(f"  {d}: no rainfall available, skipped", file=sys.stderr)
            continue
        rep = summarise(st)
        frames.append({"date": d.isoformat(), **rep})
        c = rep["counts"]
        print(f"  {d}: {rep['sites']} slopes | above {c['exceeded']} | "
              f"approaching {c['approaching']} | below {c['below']}")
    return {"bounds": BOUNDS, "frames": frames}


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pahiro Watch — every documented slope, one day at a time</title>
<style>
 :root {{ --ink:#0f172a; --muted:#64748b; --line:#e2e8f0; --bg:#f8fafc; }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; background:var(--bg); color:var(--ink);
        font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
 .wrap {{ max-width:1240px; margin:0 auto; padding:34px 22px 70px; }}
 h1 {{ font-size:29px; margin:0 0 4px; letter-spacing:-.02em; }}
 .sub {{ color:var(--muted); margin:0 0 22px; max-width:70ch; }}
 .row {{ display:grid; grid-template-columns:minmax(340px,1fr) minmax(400px,1.25fr); gap:22px; }}
 @media (max-width:960px) {{ .row {{ grid-template-columns:1fr }} }}
 .card {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:20px 22px;
          box-shadow:0 1px 2px rgba(15,23,42,.04); }}
 .dates {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }}
 button {{ font:inherit; font-size:14px; padding:7px 14px; border-radius:999px; cursor:pointer;
           border:1px solid var(--line); background:#fff; color:var(--ink); }}
 button[aria-pressed=true] {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
 .stat {{ display:flex; gap:26px; flex-wrap:wrap; margin:4px 0 16px; }}
 .stat div {{ min-width:104px; }}
 .stat b {{ display:block; font-size:27px; line-height:1.15; letter-spacing:-.02em; }}
 .stat span {{ color:var(--muted); font-size:13px; }}
 .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px;
         vertical-align:middle; }}
 svg {{ width:100%; height:auto; display:block; background:#fff; border-radius:10px; }}
 circle {{ cursor:pointer; }}
 table {{ width:100%; border-collapse:collapse; font-size:14px; }}
 th {{ text-align:left; color:var(--muted); font-weight:600; padding:7px 8px;
       border-bottom:1px solid var(--line); }}
 td {{ padding:7px 8px; border-bottom:1px solid #f1f5f9; }}
 td.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
 .note {{ color:var(--muted); font-size:13.5px; margin-top:14px; }}
 .lbl {{ font-size:12px; fill:var(--muted); }}
</style></head><body><div class="wrap">

<h1>Pahiro Watch</h1>
<p class="sub">Every one of the {n} documented landslide-prone slopes in the benchmark,
evaluated on a single day from one rainfall read covering the whole country — with the
office legally responsible for each. This is not detection. It is the national picture of
which slopes are loaded, and who is on the hook for them.</p>

<div class="dates" id="dates"></div>

<div class="row">
  <div class="card">
    <div id="stats"></div>
    <table><thead><tr><th>Most loaded slopes</th><th class="n">24 h</th></tr></thead>
    <tbody id="top"></tbody></table>
    <p class="note" id="caveat"></p>
  </div>
  <div class="card">
    <div id="map"></div>
    <p class="note">Each dot is a documented slope, positioned by its own coordinates —
    the country's shape is drawn by the data. Hover for the slope and the authority.</p>
  </div>
</div>

<p class="note">Rainfall: CHIRPS 0.05° daily. Threshold: the published
Panchpokhari Thangpal curve, 118.8 mm/24 h — a <b>local</b> fit used here as a national
reference, because no equivalent published curve exists for every district. At 5 km
resolution a convective cell smaller than that is invisible, so this under-counts.
Rendered by <code>scripts/build_watch_page.py</code>.</p>
</div>

<script>
const DATA = {data};
const COLOUR = {{"exceeded":"#dc2626","approaching":"#d97706","below":"#94a3b8"}};
const LABEL = {{"exceeded":"above the threshold","approaching":"approaching","below":"below"}};
const W=760, H=300, PAD=8;

function project(lat, lon, b) {{
  const x = (lon - b.lon0) / (b.lon1 - b.lon0);
  const y = 1 - (lat - b.lat0) / (b.lat1 - b.lat0);
  return [PAD + x * (W - 2*PAD), PAD + y * (H - 2*PAD)];
}}

let current = DATA.frames.length - 1;

function render(i) {{
  current = i;
  const f = DATA.frames[i];
  document.querySelectorAll('#dates button').forEach((b, j) =>
    b.setAttribute('aria-pressed', j === i));

  const c = f.counts;
  document.getElementById('stats').innerHTML = `
    <div class="stat">
      <div><b style="color:#dc2626">${{c.exceeded}}</b><span>${{LABEL.exceeded}}</span></div>
      <div><b style="color:#d97706">${{c.approaching}}</b><span>${{LABEL.approaching}}</span></div>
      <div><b style="color:#64748b">${{c.below}}</b><span>${{LABEL.below}}</span></div>
      <div><b>${{f.worst_r24.toFixed(0)}}<small style="font-size:15px"> mm</small></b><span>worst 24 h</span></div>
    </div>
    <div style="color:#64748b;font-size:14px">${{f.date}} · ${{f.sites}} slopes evaluated ·
    ${{f.with_authority}} with a cited authority</div>`;

  const top = f.rows.filter(r => r.state !== 'below').slice(0, 12);
  document.getElementById('top').innerHTML = top.length
    ? top.map(r => `<tr><td><span class="dot" style="background:${{COLOUR[r.state]}}"></span>${{r.title}}</td>
        <td class="n">${{r.r24_mm.toFixed(0)}}</td></tr>`).join('')
    : '<tr><td colspan="2" style="color:#64748b">No slope is above the threshold on this date.</td></tr>';

  const b = DATA.bounds;
  let dots = '';
  for (const r of f.rows) {{
    const [x, y] = project(r.lat, r.lon, b);
    const rad = r.state === 'below' ? 2.1 : 3.5;
    dots += `<circle cx="${{x.toFixed(1)}}" cy="${{y.toFixed(1)}}" r="${{rad}}" fill="${{COLOUR[r.state]}}"
       fill-opacity="${{r.state === 'below' ? 0.5 : 0.9}}" stroke="#fff" stroke-width="0.4">
       <title>${{r.title}} — ${{r.r24_mm.toFixed(0)}} mm/24h, ${{LABEL[r.state]}}
${{r.authority || 'no cited authority'}}</title></circle>`;
  }}
  document.getElementById('map').innerHTML =
    `<svg viewBox="0 0 ${{W}} ${{H}}" role="img" aria-label="Documented landslide slopes across Nepal, ${{f.date}}">
       <text class="lbl" x="14" y="${{H-6}}">80°E</text>
       <text class="lbl" x="${{W-42}}" y="${{H-6}}">88.5°E</text>
       <text class="lbl" x="14" y="18">30.5°N</text>
       <text class="lbl" x="14" y="${{H-22}}">26.2°N</text>
       ${{dots}}</svg>`;
}}

const dEl = document.getElementById('dates');
DATA.frames.forEach((f, i) => {{
  const b = document.createElement('button');
  const n = f.counts.exceeded;
  b.textContent = f.date + (n ? `  (${{n}} above)` : '');
  b.onclick = () => render(i);
  dEl.appendChild(b);
}});
render(DATA.frames.length - 1);
</script>
</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", default="2026-08-31,2024-09-28,2024-07-06",
                    help="comma-separated; first is the default frame (latest available)")
    ap.add_argument("--out", default="reports/watch.html")
    a = ap.parse_args()
    dates = [date.fromisoformat(x) for x in a.dates.split(",")]
    print("building frames:")
    payload = build(dates)
    if not payload["frames"]:
        print("no frames built", file=sys.stderr)
        return 1
    n = payload["frames"][0]["sites"]
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PAGE.format(n=n, data=json.dumps(payload)), encoding="utf-8")
    print(f"\nwrote {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
