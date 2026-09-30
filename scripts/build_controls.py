#!/usr/bin/env python3
"""Generate matched control sites for the event benchmark.

    python scripts/build_controls.py --events benchmark/events.csv \
        --all benchmark/events-all.csv --out benchmark/controls.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pahiro.eval.controls import DISCLAIMER, generate_controls, write_csv


def load(path: str) -> list[dict]:
    return [r for r in csv.DictReader(open(path, encoding="utf-8"))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="benchmark/events.csv")
    ap.add_argument("--all", default=None, help="full inventory used to exclude controls")
    ap.add_argument("--out", default="benchmark/controls.csv")
    ap.add_argument("--per-event", type=int, default=3)
    ap.add_argument("--exclusion-km", type=float, default=1.0)
    ap.add_argument("--max-km", type=float, default=12.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit-events", type=int, default=60,
                    help="controls are illustrative of the method; 60 events is plenty "
                         "for the evaluation and keeps the file reviewable")
    a = ap.parse_args()

    events = load(a.events)[: a.limit_events]
    inventory = load(a.all) if a.all else events
    controls = generate_controls(events, per_event=a.per_event, max_km=a.max_km,
                                 exclusion_km=a.exclusion_km, seed=a.seed,
                                 all_events=inventory)
    path = write_csv(controls, a.out)
    nearest = [c.nearest_known_event_km for c in controls]
    print(f"events used            : {len(events)}")
    print(f"controls generated     : {len(controls)}")
    print(f"seed                   : {a.seed}  (reproducible; not re-rolled)")
    print(f"distance to nearest known failure: min {min(nearest):.1f} km, "
          f"median {sorted(nearest)[len(nearest)//2]:.1f} km")
    print(f"exclusion radius       : {a.exclusion_km} km")
    print(f"\nLIMITATION: {DISCLAIMER}")
    print(f"\nwrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
