#!/usr/bin/env python3
"""Build a day-by-day monsoon timeline for all 613 documented slopes.

One compact file, not one file per day: per site, the daily rainfall for the season, plus
the per-site identity (position, title, responsible office). The client computes the state
for any day, so scrubbing is instant and the whole season ships in about a megabyte.

    python scripts/build_timeline.py --from 2024-06-01 --to 2024-10-31 --out web/public/data
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.ingest.rainfall import fetch_window_cached, sample_point
from pahiro.ontology import MAINTENANCE, Ontology
from pahiro.watch import load_sites

ROOT = Path(__file__).resolve().parents[1]


def daterange(a: date, b: date):
    d = a
    while d <= b:
        yield d
        d += timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2024-06-01")
    ap.add_argument("--to", dest="end", default="2024-10-31")
    ap.add_argument("--out", default="web/public/data")
    args = ap.parse_args()

    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    sites = load_sites(str(ROOT / "benchmark/events.csv"))
    ontology = Ontology.load(str(ROOT / "needs-none")) if False else Ontology.load(
        str(ROOT / "ontology/nepal-slope-routing.json"))
    rule = ontology.lookup("local-road", MAINTENANCE)

    days = list(daterange(start, end))
    series: dict[str, list[float | None]] = {str(s["incident_id"]): [] for s in sites}
    got = 0
    for i, day in enumerate(days):
        w = fetch_window_cached(day)
        if w is None:
            for sid in series:
                series[sid].append(None)
            print(f"  [{i+1}/{len(days)}] {day}: unavailable", flush=True)
            continue
        arr, tr = w
        for s in sites:
            v = sample_point(arr, tr, float(s["lon"]), float(s["lat"]))
            series[str(s["incident_id"])].append(round(v, 1) if v == v else None)
        got += 1
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{len(days)}] {day}: ok ({got} days fetched)", flush=True)

    payload = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": [d.isoformat() for d in days],
        "source": "CHIRPS 0.05 deg daily",
        "threshold_mm_24h": 118.8,
        "threshold_name": "Panchpokhari Thangpal, Sindhulchok (published local fit)",
        "sites": [
            {"id": str(s["incident_id"]), "title": (s.get("title") or "").strip()[:90],
             "lat": float(s["lat"]), "lon": float(s["lon"]),
             "authority": rule.institution if rule else None,
             "office": rule.office if rule else None,
             "legal_basis": rule.legal_basis if rule else None,
             "r": series[str(s["incident_id"])]}
            for s in sites
        ],
    }
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    path = out / "timeline.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\n{got}/{len(days)} days fetched")
    print(f"wrote {path}  ({path.stat().st_size:,} bytes) covering {len(days)} days x {len(sites)} slopes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
