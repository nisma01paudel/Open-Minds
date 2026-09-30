#!/usr/bin/env python3
"""Emit the national slope picture as GeoJSON frames for the web UI.

Two sources, used for what each is good at:
- Open-Meteo  -> TODAY (keyless, near-real-time), so the map is live
- CHIRPS      -> the long record, so historical event days can be compared

    python scripts/build_watch_geojson.py --out web/public/data
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.ingest.openmeteo import site_series
from pahiro.ontology import MAINTENANCE, Ontology
from pahiro.trigger import APPROACHING, BELOW, EXCEEDED, PANCHPOKHARI, assess
from pahiro.watch import load_sites, national_status

ROOT = Path(__file__).resolve().parents[1]


def feature(site: dict, rule, state: str, r24: float, r72: float, source: str) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [float(site["lon"]), float(site["lat"])]},
        "properties": {
            "id": str(site.get("incident_id", "")),
            "title": (site.get("title") or "").strip(),
            "date": str(site.get("date", "")),
            "state": state,
            "r24": round(r24, 1),
            "r72": round(r72, 1),
            "authority": rule.institution if rule else None,
            "office": rule.office if rule else None,
            "legal_basis": rule.legal_basis if rule else None,
            "source": source,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="web/public/data")
    ap.add_argument("--live", action="store_true", default=True,
                    help="include a today frame from Open-Meteo")
    args = ap.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    sites = load_sites(str(ROOT / "benchmark/events.csv"))
    ontology = Ontology.load(str(ROOT / "ontology/nepal-slope-routing.json"))
    rule = ontology.lookup("local-road", MAINTENANCE)
    frames = []

    # ---- live frame: Open-Meteo, today -------------------------------------
    if args.live:
        pts = [(float(s["lat"]), float(s["lon"])) for s in sites]
        print("fetching Open-Meteo for the live frame ...")
        series = site_series(pts, verbose=True)
        if series:
            last = sorted(series[0])[-1]
            feats = []
            for site, ser in zip(sites, series):
                day_mm = {date.fromisoformat(k): v for k, v in ser.items() if v is not None}
                if not day_mm:
                    continue
                a = assess(day_mm, date.fromisoformat(last), PANCHPOKHARI)
                w24 = next((w for w in a.windows if w.duration_hours == 24), None)
                w72 = next((w for w in a.windows if w.duration_hours == 72), None)
                feats.append(feature(site, rule, a.state,
                                     w24.accumulation_mm if w24 else 0.0,
                                     w72.accumulation_mm if w72 else 0.0, "open-meteo"))
            frames.append({"id": f"live-{last}", "label": f"Live — {last}",
                           "date": last, "source": "open-meteo", "features": feats})
            print(f"  live frame {last}: {len(feats)} slopes")

    # ---- historical frames: CHIRPS ----------------------------------------
    for day in (date(2024, 9, 28), date(2024, 7, 6)):
        st = national_status(day)
        if not st:
            continue
        by_id = {s.site_id: s for s in st}
        feats = []
        for site in sites:
            s = by_id.get(str(site.get("incident_id", "")))
            if not s:
                continue
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point",
                             "coordinates": [s.lon, s.lat]},
                "properties": {"id": s.site_id, "title": s.title, "state": s.state,
                               "r24": s.r24_mm, "r72": s.r72_mm,
                               "authority": s.authority, "office": s.office,
                               "legal_basis": s.legal_basis,
                               "source": "chirps"},
            })
        frames.append({"id": f"chirps-{day}", "label": str(day), "date": str(day),
                       "source": "chirps", "features": feats})
        print(f"  frame {day}: {len(feats)} slopes")

    # ---- write -------------------------------------------------------------
    index = []
    for f in frames:
        path = out_dir / f"slopes-{f['id']}.geojson"
        path.write_text(json.dumps({
            "type": "FeatureCollection",
            "metadata": {k: v for k, v in f.items() if k != "features"},
            "features": f["features"],
        }))
        counts = {}
        for feat in f["features"]:
            counts[feat["properties"]["state"]] = counts.get(feat["properties"]["state"], 0) + 1
        index.append({**{k: v for k, v in f.items() if k != "features"},
                      "file": path.name, "counts": counts,
                      "worst_r24": max((x["properties"]["r24"] for x in f["features"]), default=0)})
        print(f"    wrote {path.name}  ({path.stat().st_size:,} bytes) {counts}")

    (out_dir / "frames.json").write_text(json.dumps(index, indent=2))
    print(f"\nwrote {out_dir/'frames.json'} with {len(index)} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
