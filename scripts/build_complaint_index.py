#!/usr/bin/env python3
"""One small file the phone can carry: who is responsible for the ground near a point.

WHY A DERIVED FILE AND NOT THE TIMELINE
---------------------------------------
timeline.json is the whole 613-slope hazard record with 153 days of rainfall each. The phone needs
one row per slope to answer "who owns this ground", and carrying the rainfall series to answer it
would be 2.5 MB of data that is never read.

So this pre-resolves the duty holder, the local unit, the district and the office's own website for
every slope, and writes those seven fields. The resolution runs once, on a machine with the
gazetteer, instead of on the phone.

    python scripts/build_complaint_index.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = "web/public/data/complaint-index.json"
D = "web/public/data"


def main() -> int:
    from pahiro import complaints as C

    sites = json.loads((ROOT / D / "timeline.json").read_text(encoding="utf-8"))["sites"]
    rows, resolved = [], 0
    for s in sites:
        admin = C.resolve_admin(s["title"])
        if admin:
            resolved += 1
        rows.append({
            "id": s["id"],
            "title": s["title"],
            "lat": round(s["lat"], 5),
            "lon": round(s["lon"], 5),
            "office": s["office"],
            "legal": s["legal_basis"],
            "unit": (admin or {}).get("unit"),
            "district": (admin or {}).get("district"),
            "site": (admin or {}).get("website"),
        })

    if resolved == 0:
        print("REFUSING: not one slope resolved to a local unit. The gazetteer or the titles moved, "
              "and a complaint index with no offices in it is worse than none.")
        return 1

    out = {
        "source": ("Duty holder from this project's routing key; local unit and website from "
                   "github.com/rgtstha/NEPAL-QUEST-DATA"),
        "note": ("Pre-resolved for the phone: seven fields per documented slope instead of the whole "
                 "hazard record. The office named is the routing key's DEFAULT holder for a local "
                 "road, not a per-parcel legal determination."),
        "counts": {"slopes": len(rows), "resolved": resolved},
        "slopes": rows,
    }
    dest = ROOT / OUT
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(rows)} slopes, {resolved} with a named local unit, "
          f"{dest.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
