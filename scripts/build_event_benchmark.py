#!/usr/bin/env python3
"""Build the event half of the benchmark from BIPAD's landslide incidents.

Two integrity rules, both from a measured property of the data:
1. A coordinate used by many records is an administrative default point, not a
   site. We flag how many records share each coordinate and keep only unique ones.
2. A date carrying many records is a real regional event, and gives many sites
   under one documented date - the only honest way to build a same-date benchmark.

Output: benchmark/events.csv (unique-coordinate sites on multi-site days) and
benchmark/events-all.csv (everything, flagged).

    python scripts/build_event_benchmark.py --out benchmark/events.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.ingest.bipad import BipadClient

MIN_DAY_CLUSTER = 5      # a day with at least this many records is a real event
MAX_COORD_USES = 1       # keep only coordinates that identify a single site


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="benchmark/events.csv")
    ap.add_argument("--min-day-cluster", type=int, default=MIN_DAY_CLUSTER)
    ap.add_argument("--max-coord-uses", type=int, default=MAX_COORD_USES)
    ap.add_argument("--limit", type=int, help="cap records fetched, for a quick run")
    a = ap.parse_args()

    client = BipadClient()
    print("fetching BIPAD landslide incidents ...", file=sys.stderr)
    records = client.landslide_incidents(max_records=a.limit)
    print(f"  {len(records)} records", file=sys.stderr)

    coord_uses = collections.Counter()
    day_uses = collections.Counter()
    rows = []
    for r in records:
        pt = r.get("point") or {}
        coords = pt.get("coordinates") or [None, None]
        lon, lat = (coords + [None, None])[:2] if isinstance(coords, list) else (None, None)
        when = (r.get("incidentOn") or "")[:10]
        if lon is None or lat is None or not when:
            continue
        key = f"{round(lon, 5)},{round(lat, 5)}"
        coord_uses[key] += 1
        day_uses[when] += 1
        rows.append({
            "incident_id": r.get("id"),
            "date": when,
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "coord_key": key,
            "title": (r.get("title") or "").strip(),
            "verified": r.get("verified"),
            "approved": r.get("approved"),
            "source": r.get("source"),
        })

    for r in rows:
        r["coord_uses"] = coord_uses[r["coord_key"]]
        r["day_cluster"] = day_uses[r["date"]]

    out_all = Path(a.out).with_name("events-all.csv")
    out_all.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with open(out_all, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)

    keeps = [r for r in rows
             if r["coord_uses"] <= a.max_coord_uses and r["day_cluster"] >= a.min_day_cluster]
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(keeps)

    print(f"\ndistinct coordinates : {len(coord_uses)} across {len(rows)} records")
    top = coord_uses.most_common(3)
    for k, n in top:
        print(f"  most reused coordinate {k} appears {n} times "
              f"-> an administrative default point, not a site")
    print(f"\nmulti-site days (>= {a.min_day_cluster} records):")
    for d, n in day_uses.most_common(6):
        print(f"  {d}: {n} records")
    print(f"\nkept {len(keeps)} sites with a unique coordinate on a multi-site day")
    print(f"wrote {a.out} and {out_all}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
