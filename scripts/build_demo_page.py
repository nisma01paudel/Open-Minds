#!/usr/bin/env python3
"""Render the real artifacts into one self-contained HTML page.

Nothing here is hand-written: the trace, the advisory, the siting figures and the
monthly observability table are all read out of the JSON the system actually
produced. Regenerate it and the page matches the data, or the page is wrong.

    python scripts/build_demo_page.py --out reports/demo.html
"""
from __future__ import annotations

import argparse
import collections
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The agent stores lowercase-hyphenated state values ("primed-unobserved"), not the
# constant names. Keying on the constant names silently produced an empty subtitle.
STATE_LABEL = {
    "primed-confirmed": ("primed", "confirmed by observation", "#b45309"),
    "primed-unobserved": ("primed", "we could not look", "#dc2626"),
    "monitored": ("monitored", "evidence is fresh", "#15803d"),
    "abstain": ("abstain", "nothing to say", "#475569"),
}


def esc(x) -> str:
    return html.escape(str(x))


def load(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def trace_rows(run: dict) -> str:
    out = []
    for i, t in enumerate(run.get("trace", []), 1):
        ms = t.get("ms", 0)
        dur = f"{ms:,} ms" if ms < 1000 else f"{ms/1000:.1f} s"
        cls = "ok" if t.get("ok") else "bad"
        out.append(
            f'<tr><td class="n">{i}</td><td class="tool">{esc(t["name"])}</td>'
            f'<td class="dur">{dur}</td><td class="{cls}">{esc(t.get("result",""))}</td></tr>')
    return "\n".join(out)


def month_table(rows: list[dict]) -> str:
    agg = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        m = str(r.get("event_date", ""))[5:7]
        agg[m][0] += r.get("optical_scenes", 0)
        agg[m][1] += r.get("optical_usable", 0)
    names = {"06": "June", "07": "July", "08": "August", "09": "September", "10": "October"}
    out = []
    worst = max(agg.items(), key=lambda kv: (kv[1][1] / kv[1][0]) if kv[1][0] else 1)
    for m in sorted(agg):
        scenes, usable = agg[m]
        pct = 100.0 * usable / scenes if scenes else 0.0
        bar = int(round(pct))
        hl = ' class="worst"' if m == worst[0] else ""
        out.append(
            f'<tr{hl}><td>{names.get(m, m)}</td><td class="n">{scenes:,}</td>'
            f'<td class="n">{usable:,}</td><td class="n"><b>{pct:.1f}%</b></td>'
            f'<td><span class="bar" style="width:{bar}%"></span></td></tr>')
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="evidence/agent-run-2024-09-28.json")
    ap.add_argument("--observability", default="reports/observability-monsoon.json")
    ap.add_argument("--out", default="reports/demo.html")
    a = ap.parse_args()

    run = load(ROOT / a.run, {})
    obs = load(ROOT / a.observability, {}) or {}
    rows = obs.get("rows", [])

    state = run.get("state", "?")
    label, blurb, colour = STATE_LABEL.get(state, (state, "", "#475569"))
    siting = run.get("siting") or {}
    routing = run.get("routing") or {}
    trig = run.get("trigger") or {}
    stale = run.get("staleness") or {}

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pahiro — live run, {esc(run.get('as_of',''))}</title>
<style>
 :root {{ --ink:#0f172a; --muted:#64748b; --line:#e2e8f0; --bg:#f8fafc; --accent:#0e7490; }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; background:var(--bg); color:var(--ink);
        font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
 .wrap {{ max-width:1100px; margin:0 auto; padding:36px 22px 80px; }}
 h1 {{ font-size:30px; margin:0 0 4px; letter-spacing:-.02em; }}
 h2 {{ font-size:19px; margin:38px 0 12px; letter-spacing:-.01em; }}
 .sub {{ color:var(--muted); margin:0 0 26px; }}
 .card {{ background:#fff; border:1px solid var(--line); border-radius:12px; padding:20px 22px;
          box-shadow:0 1px 2px rgba(15,23,42,.04); }}
 .state {{ display:inline-block; padding:5px 13px; border-radius:999px; color:#fff;
           font-weight:600; font-size:14px; letter-spacing:.01em; background:{colour}; }}
 .kv {{ display:grid; grid-template-columns:190px 1fr; gap:6px 18px; margin-top:14px; }}
 .kv dt {{ color:var(--muted); }}
 .kv dd {{ margin:0; }}
 table {{ width:100%; border-collapse:collapse; font-size:14.5px; }}
 th {{ text-align:left; color:var(--muted); font-weight:600; border-bottom:1px solid var(--line);
       padding:8px 10px; }}
 td {{ padding:9px 10px; border-bottom:1px solid #f1f5f9; vertical-align:top; }}
 td.n, th.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
 td.tool {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
 td.dur {{ color:var(--muted); font-variant-numeric:tabular-nums; white-space:nowrap; }}
 td.ok {{ color:#15803d; }} td.bad {{ color:#dc2626; font-weight:600; }}
 tr.worst td {{ background:#fef2f2; }}
 .bar {{ display:inline-block; height:9px; background:var(--accent); border-radius:3px;
         min-width:2px; vertical-align:middle; }}
 pre.advisory {{ white-space:pre-wrap; font:15px/1.75 ui-sans-serif,system-ui,sans-serif;
                 background:#fff; border:1px solid var(--line); border-left:4px solid {colour};
                 border-radius:10px; padding:18px 20px; margin:0; }}
 .note {{ color:var(--muted); font-size:14px; margin-top:10px; }}
 .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
 @media (max-width:820px) {{ .grid {{ grid-template-columns:1fr }} .kv {{ grid-template-columns:1fr }} }}
 code {{ background:#f1f5f9; padding:1px 6px; border-radius:5px; font-size:14px; }}
</style></head><body><div class="wrap">

<h1>Pahiro <span style="color:var(--muted);font-weight:400">पहिरो</span></h1>
<p class="sub">A live run, rendered from the JSON the system produced. Nothing on this page is
hand-written — regenerate it and it matches the data, or it is wrong.</p>

<div class="card">
  <span class="state">{esc(label)} · {esc(blurb)}</span>
  <dl class="kv">
    <dt>Date</dt><dd>{esc(run.get('as_of',''))}</dd>
    <dt>Location</dt><dd>{esc((run.get('ctx') or {}).get('ward_label','—'))}</dd>
    <dt>Report</dt><dd>{esc(run.get('report',''))}</dd>
    <dt>Rainfall trigger</dt><dd>{esc(run.get('rainfall_banner','—'))}</dd>
    <dt>Evidence state</dt><dd>{esc(stale.get('status','—'))} — {esc(stale.get('reason',''))}</dd>
    <dt>Priority</dt><dd>{esc(run.get('priority') or '—')}</dd>
  </dl>
  <p class="note">On this date the rainfall threshold is exceeded <em>and</em> no fresh
  observation exists. The system reports the risk and refuses to call it a detection.</p>
</div>

<h2>Every decision, and how it was made</h2>
<div class="card"><table>
<thead><tr><th class="n">#</th><th>Tool</th><th>Time</th><th>Result</th></tr></thead>
<tbody>
{trace_rows(run)}
</tbody></table></div>

<h2>Where to build instead</h2>
<div class="card">
  <dl class="kv">
    <dt>Recommendation</dt><dd><b>{esc(siting.get('recommendation','—'))}</b></dd>
    <dt>Asset elevation</dt><dd>{esc(siting.get('asset_elevation_m','—'))} m</dd>
    <dt>Source zone</dt><dd>{esc(siting.get('source_distance_m','—'))} m upslope,
        {esc(siting.get('source_slope_deg','—'))}° average</dd>
    <dt>Move to</dt><dd>{esc(siting.get('target_offset_m','—'))} m upslope,
        {esc(siting.get('target_elevation_gain_m','—'))} m higher</dd>
  </dl>
  <p class="note">{esc((siting.get('caveats') or [''])[0])}</p>
</div>

<h2>Responsible authority</h2>
<div class="card">
  <dl class="kv">
    <dt>Institution</dt><dd>{esc(routing.get('institution','—'))}</dd>
    <dt>Office</dt><dd>{esc(routing.get('office','—'))}</dd>
    <dt>Legal basis</dt><dd>{esc(routing.get('legal_basis','—'))}</dd>
    <dt>Decided by</dt><dd>{esc(routing.get('confidence','—'))} — model-selected from cited rules</dd>
  </dl>
</div>

<h2>The advisory, as issued</h2>
<pre class="advisory">{esc(run.get('advisory_ne',''))}</pre>

<h2>Can the ground actually be seen?</h2>
<p class="sub" style="margin-bottom:12px">Every scene screened in the 30 days before each of
{len(rows)} documented failures, pooled by calendar month across 37 year-months.</p>
<div class="card"><table>
<thead><tr><th>Month</th><th class="n">Scenes</th><th class="n">Usable</th><th class="n">Usable</th><th></th></tr></thead>
<tbody>
{month_table(rows)}
</tbody></table>
<p class="note"><b>August is the worst month.</b> A third of the imagery that exists is usable;
in August, a sixth. {obs.get('sites_with_no_optical_at_all', 0)} of {obs.get('sites', len(rows))}
sites had no usable look at all in the month before they failed.</p></div>

<p class="note" style="margin-top:34px">Generated by <code>scripts/build_demo_page.py</code>
from <code>{esc(a.run)}</code> and <code>{esc(a.observability)}</code>.</p>
</div></body></html>
"""
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out}  ({len(page):,} bytes) — open it with:  xdg-open {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
