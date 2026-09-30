"""Does the rainfall trigger actually discriminate, or does it just fire often?

A trigger that fires everywhere is worthless. The honest test needs a comparison
group, which is what `benchmark/controls.csv` exists for: matched slopes with no
recorded failure, evaluated on the SAME dates as the events they are matched to.

Reported as two rates and their difference. No significance theatre: the sample is
small, the controls are weak by construction (absence of a record is not stability),
and none of that is hidden.

    python -m pahiro.eval.trigger_eval --events benchmark/events.csv \
        --controls benchmark/controls.csv --limit-events 30 --out reports/trigger-discrimination.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from pahiro.ingest.rainfall import fetch_window_cached, sample_point
from pahiro.trigger import PANCHPOKHARI, EXCEEDED, assess


@dataclass
class SiteResult:
    site_id: str
    kind: str                 # 'event' | 'control'
    date: str
    lat: float
    lon: float
    rainfall_24h: float
    rainfall_72h: float
    state: str
    triggered: bool


def _load(path: str) -> list[dict]:
    return [r for r in csv.DictReader(open(path, encoding="utf-8"))]


def evaluate_sites(sites: list[tuple[str, str, dict]], threshold=PANCHPOKHARI,
                   days: int = 4, verbose: bool = False) -> list[SiteResult]:
    """sites: list of (site_id, kind, row) where row has lat, lon and date."""
    by_day: dict[date, list[int]] = defaultdict(list)
    parsed = []
    for idx, (sid, kind, row) in enumerate(sites):
        # events carry `date`, controls carry `event_date` (the date they are matched to)
        raw_date = row.get("date") or row.get("event_date")
        as_of = date.fromisoformat(raw_date)
        parsed.append((sid, kind, row, as_of))
        for back in range(days):
            by_day[as_of - timedelta(days=back)].append(idx)

    samples: dict[tuple[int, date], float] = {}
    for day in sorted(by_day):
        window = fetch_window_cached(day)
        if window is None:
            continue
        arr, transform = window
        for idx in by_day[day]:
            _, _, row, _ = parsed[idx]
            samples[(idx, day)] = sample_point(arr, transform, float(row["lon"]),
                                               float(row["lat"]))
        if verbose:
            print(f"    {day}: sampled {len(by_day[day])} site(s)", file=sys.stderr)

    out: list[SiteResult] = []
    for idx, (sid, kind, row, as_of) in enumerate(parsed):
        series = {as_of - timedelta(days=b): samples.get((idx, as_of - timedelta(days=b)))
                  for b in range(days)}
        series = {d: v for d, v in series.items() if v is not None and v == v}   # drop NaN
        if not series:
            continue
        a = assess(series, as_of, threshold)
        w24 = next((w for w in a.windows if w.duration_hours == 24), None)
        w72 = next((w for w in a.windows if w.duration_hours == 72), None)
        out.append(SiteResult(
            site_id=sid, kind=kind, date=raw_date, lat=float(row["lat"]),
            lon=float(row["lon"]),
            rainfall_24h=round(w24.accumulation_mm, 1) if w24 else 0.0,
            rainfall_72h=round(w72.accumulation_mm, 1) if w72 else 0.0,
            state=a.state, triggered=a.state == EXCEEDED))
    return out


def summarise(results: list[SiteResult]) -> dict:
    events = [r for r in results if r.kind == "event"]
    controls = [r for r in results if r.kind == "control"]

    def rate(rows):
        return round(100.0 * sum(1 for r in rows if r.triggered) / len(rows), 1) if rows else 0.0

    ev, ct = rate(events), rate(controls)
    return {
        "n_events": len(events), "n_controls": len(controls),
        "event_trigger_rate_pct": ev, "control_trigger_rate_pct": ct,
        "difference_pct_points": round(ev - ct, 1),
        "median_rainfall_24h_event": sorted(r.rainfall_24h for r in events)[len(events)//2] if events else None,
        "median_rainfall_24h_control": sorted(r.rainfall_24h for r in controls)[len(controls)//2] if controls else None,
        "limitations": [
            "controls are slopes with no RECORDED failure, not slopes proven stable, so the "
            "control rate is a lower bound and the measured difference is conservative",
            "the sample is small and the sites span several years of one region",
            "this measures the rainfall trigger only, not the whole system",
        ],
        "results": [asdict(r) for r in results],
    }


def markdown(rep: dict) -> str:
    return "\n".join([
        "# Rainfall trigger — does it discriminate?",
        "",
        f"Event sites: **{rep['n_events']}** · matched control sites: **{rep['n_controls']}** "
        "· identical dates, same threshold (Panchpokhari Thangpal, 118.8 mm/24 h)",
        "",
        "| Group | Triggered | Median 24 h rainfall |",
        "|---|---|---|",
        f"| **Recorded landslides** | **{rep['event_trigger_rate_pct']}%** | "
        f"{rep['median_rainfall_24h_event']} mm |",
        f"| Matched controls | {rep['control_trigger_rate_pct']}% | "
        f"{rep['median_rainfall_24h_control']} mm |",
        "",
        f"**Difference: {rep['difference_pct_points']:+} percentage points.**",
        "",
        "## Limitations, stated with the result",
        "",
        *[f"- {x}" for x in rep["limitations"]],
        "",
        "A trigger that fires everywhere would score no difference. This is the smallest "
        "honest test of whether the rainfall layer carries information, and it is reported "
        "with its own weakness attached.",
    ]) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Event vs control trigger discrimination.")
    ap.add_argument("--events", default="benchmark/events.csv")
    ap.add_argument("--controls", default="benchmark/controls.csv")
    ap.add_argument("--limit-events", type=int, default=30)
    ap.add_argument("--days", type=int, default=4)
    ap.add_argument("--out", default="reports/trigger-discrimination.json")
    a = ap.parse_args(argv)

    events = _load(a.events)[: a.limit_events]
    controls = _load(a.controls)
    keep = {str(e.get("incident_id")) for e in events}
    controls = [c for c in controls if c.get("matched_event_id") in keep]

    sites = [(f"evt-{e['incident_id']}", "event", e) for e in events]
    sites += [(f"ctl-{c['control_id']}", "control", c) for c in controls]
    print(f"evaluating {len(events)} events and {len(controls)} controls over {a.days} days",
          file=sys.stderr)

    results = evaluate_sites(sites, days=a.days, verbose=True)
    rep = summarise(results)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n")
    out.with_suffix(".md").write_text(markdown(rep))
    print(f"\nevents triggered:   {rep['event_trigger_rate_pct']}%  "
          f"(n={rep['n_events']})")
    print(f"controls triggered: {rep['control_trigger_rate_pct']}%  "
          f"(n={rep['n_controls']})")
    print(f"difference: {rep['difference_pct_points']:+} points")
    print(f"wrote {out} and {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
