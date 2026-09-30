#!/usr/bin/env python3
"""Plan a walk, offline.

    python scripts/plan_trip.py --near 27.7750 85.3620          # what can I walk from here
    python scripts/plan_trip.py --from 27.8000 85.3790 --to 27.8060 85.3850

Runs off two files that ship with the app - the OSM trail network and the bundled terrain - and
touches nothing else. No network, no API, no key.

Trail data (c) OpenStreetMap contributors, ODbL 1.0.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro import trails                     # noqa: E402
from pahiro.shelter import load_dem           # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--to", dest="to", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--near", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--radius", type=float, default=3000.0, help="metres, for --near")
    ap.add_argument("--limit", type=int, default=8)
    a = ap.parse_args()

    dem = load_dem()
    net = trails.load_default()
    s = net.stats()
    print(f"offline trail network: {s['trails']} trails, {s['nodes']} junctions "
          f"({s['snapped']} gaps snapped to 25 m)")

    if a.near:
        lat, lon = a.near
        got = trails.nearby(net, lon, lat, radius_m=a.radius, limit=a.limit, dem=dem)
        if not got:
            print(f"\nnothing mapped within {a.radius/1000:.1f} km. That means no trail has been "
                  f"drawn here yet - it does not mean there is nothing to walk.")
            return 0
        print(f"\ntrails within {a.radius/1000:.1f} km of {lat:.4f}, {lon:.4f}:")
        for t in got:
            h, m = divmod(t.walk_minutes, 60)
            print(f"  {t.length_m/1000:6.2f} km  +{t.climb_m:4.0f} m  {h}h{m:02d}  "
                  f"{t.distance_to_start_m:4.0f} m away  {t.difficulty:13} {t.name[:40]}")
        print("\nclimb is from a 1.2 km terrain grid: indicative, not surveyed.")
        return 0

    if a.frm and a.to:
        (lat1, lon1), (lat2, lon2) = a.frm, a.to
        p = net.route((lon1, lat1), (lon2, lat2), dem)
        print(f"\n{lat1:.4f},{lon1:.4f} -> {lat2:.4f},{lon2:.4f}")
        print("  " + p.summary())
        if p.ok:
            print(f"  {len(p.points)} points, snapped {p.start_snap_m:.0f} m / "
                  f"{p.end_snap_m:.0f} m to the mapped network")
        for w in p.warnings:
            print("  ! " + w)
        return 0 if p.ok else 1

    ap.error("give --near LAT LON, or --from LAT LON --to LAT LON")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
