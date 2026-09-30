#!/usr/bin/env python3
"""Precompute the real advisory for the slopes a presenter would click.

The map shows where the load is. This is what the system would actually SAY about a given
slope - the Nepali advisory, the responsible office, the statutory basis, and the terrain
recommendation - produced by the same code as the agent, not a re-implementation.

Only the routes that matter are precomputed: the top N slopes by rainfall on a chosen day.
The routing here is deterministic (a documented landslide site on a municipal road is a
maintenance duty on a local road), so no model call is needed and all 613 could be done -
but the terrain recommendation costs one DEM read each, so the set is bounded.

    python scripts/build_advisories.py --day 2024-09-28 --top 60
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.advisory.nepali import render, siting_ne
from pahiro.ingest import terrain as terrain_mod
from pahiro.ingest.rainfall import fetch_window_cached, sample_point
from pahiro.ontology import MAINTENANCE, Ontology
from pahiro.siting import advise as siting_advise

ROOT = Path(__file__).resolve().parents[1]
WINDOW_H = ((24, 118.8), (48, 141.9), (72, 157.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2024-09-28")
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--out", default="web/public/data/advisories.json")
    a = ap.parse_args()
    day = date.fromisoformat(a.day)

    tl = json.loads((ROOT / "web/public/data/timeline.json").read_text())
    i = tl["days"].index(a.day)
    ontology = Ontology.load(str(ROOT / "ontology/nepal-slope-routing.json"))
    rule = ontology.lookup("local-road", MAINTENANCE)

    # same multi-window rule as everywhere else
    def loaded(r):
        back = [r[i - k] for k in (0, 1, 2) if i - k >= 0 and r[i - k] is not None]
        if not back:
            return 0.0, 0.0
        sums = [back[0], sum(back[:2]) if len(back) >= 2 else None,
                sum(back[:3]) if len(back) >= 2 else None]
        best = max((sums[w] / WINDOW_H[w][1] for w in range(3) if sums[w] is not None), default=0.0)
        return best, back[0]

    ranked = []
    for s in tl["sites"]:
        ratio, r24 = loaded(s["r"])
        if ratio >= 1.0:
            ranked.append((ratio, r24, s))
    ranked.sort(key=lambda x: -x[1])
    print(f"{len(ranked)} slopes loaded on {a.day}; building advisories for the top {a.top}")

    out = {"day": a.day, "threshold_mm_24h": tl["threshold_mm_24h"], "advisories": {}}
    for n, (ratio, r24, s) in enumerate(ranked[: a.top], 1):
        siting_text, siting_rec = None, None
        try:
            tw = terrain_mod.fetch((s["lon"] - 0.03, s["lat"] - 0.03, s["lon"] + 0.03, s["lat"] + 0.03))
            if tw and tw.usable:
                h, w = tw.elevation.shape
                adv = siting_advise(tw.elevation, tw.transform, h // 2, w // 2, crs=tw.crs)
                siting_text = siting_ne(adv)
                siting_rec = {"recommendation": adv.recommendation,
                              "target_offset_m": adv.target_offset_m,
                              "target_elevation_gain_m": adv.target_elevation_gain_m,
                              "source_distance_m": adv.source_distance_m,
                              "source_slope_deg": adv.source_slope_deg,
                              "caveat": adv.caveats[0]}
        except Exception as exc:
            print(f"    siting failed for {s['id']}: {type(exc).__name__}", file=sys.stderr)

        # EVERY value in Nepali. Passing English strings here produced a notice whose
        # labels were Nepali and whose content was not - the same defect class caught twice
        # earlier in this project, reintroduced by writing a new call site.
        advisory = render(
            location=s["title"] or "अभिलेखित ढलान",
            as_of=a.day,
            what_changed=(f"२४ घण्टामा {r24:.0f} मिमि वर्षा भयो — यो क्षेत्रको "
                          "वर्षा थ्रेसहोल्ड नाघेको छ"),
            evidence_state=("उपग्रह प्रमाण पुरानो छ — अवलोकन अभिलेख हेर्नुहोस्"),
            why_it_matters=("यति भार परेको ढलान खस्न सक्छ, र तलको सडक वा बस्ती "
                            "जोखिममा पर्छ"),
            inspect_first=["यो ढलानको सडक सतह र जल-निकास",
                           "सडक लाइनमाथिको ढलान"],
            recommendation="मर्मत स्वीकृत गर्नुअघि जाँच गर्नुहोस्",
            authority_institution=rule.institution if rule else None,
            legal_basis=rule.legal_basis if rule else None,
            siting=siting_text,
            needs_review=True,
        )
        out["advisories"][s["id"]] = {
            "title": s["title"], "lat": s["lat"], "lon": s["lon"], "r24": round(r24, 1),
            "authority": rule.institution if rule else None,
            "office": rule.office if rule else None,
            "legal_basis": rule.legal_basis if rule else None,
            "advisory_ne": advisory, "siting": siting_rec,
        }
        if n % 10 == 0:
            print(f"  {n}/{min(a.top, len(ranked))}", flush=True)

    path = ROOT / a.out
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {path} ({path.stat().st_size:,} bytes, {len(out['advisories'])} advisories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
