"""Build an observation series for one area of interest.

Produces the records the staleness gate and the change layer consume: for each
satellite pass, when it was acquired, how much of the patch was actually usable
after cloud masking, and what the index value was.

    python -m pahiro.ingest.series --bbox 84.95 27.75 85.10 27.90 \
        --from 2024-01-01 --to 2024-12-31 --best-per-month --out cache/dhading-2024
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from pahiro.ingest import stac, window


def sample_scenes(scenes: list[stac.Scene], best_per_month: bool, limit: int | None) -> list[stac.Scene]:
    """Pick the least-cloudy scene per month, or just the first N."""
    if best_per_month:
        by_month: dict[tuple[int, int], stac.Scene] = {}
        for s in scenes:
            key = (s.acquired.year, s.acquired.month)
            cur = by_month.get(key)
            cloud = s.cloud_cover if s.cloud_cover is not None else 100.0
            if cur is None or cloud < (cur.cloud_cover if cur.cloud_cover is not None else 100.0):
                by_month[key] = s
        picked = [by_month[k] for k in sorted(by_month)]
    else:
        picked = scenes
    return picked[:limit] if limit else picked


def observe(scene: stac.Scene, bbox, index: str, max_pixels: int = 256) -> dict:
    """One observation record: when, how usable, and what the index says."""
    if scene.is_optical:
        patch = window.index_patch(scene.assets, bbox, kind=index, cloud_mask=True)
        values = patch.values[patch.valid]
        rec = {
            "sensor": stac.OPTICAL,
            "scene_id": scene.id,
            "acquired": scene.acquired.isoformat(),
            "cloud_cover": scene.cloud_cover,
            "usable_fraction": round(patch.valid_fraction, 4),
            "index": index,
            "index_mean": round(float(values.mean()), 4) if values.size else None,
            "index_std": round(float(values.std()), 4) if values.size else None,
            "pixels": int(patch.valid.sum()),
        }
    else:
        band = scene.assets.get("vv") or scene.assets.get("vh") or next(iter(scene.assets.values()), None)
        patch = window.read_band(band, bbox, max_pixels=max_pixels) if band else None
        values = patch.values[patch.valid] if patch is not None else np.array([])
        rec = {
            "sensor": stac.RADAR,
            "scene_id": scene.id,
            "acquired": scene.acquired.isoformat(),
            "cloud_cover": None,
            "usable_fraction": round(patch.valid_fraction, 4) if patch else 0.0,
            "index": "backscatter",
            "index_mean": round(float(values.mean()), 4) if values.size else None,
            "index_std": round(float(values.std()), 4) if values.size else None,
            "pixels": int(values.size),
        }
    return rec


def write_records(records: list[dict], out_base: Path) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    with open(out_base.with_suffix(".jsonl"), "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    fields = ["sensor", "scene_id", "acquired", "cloud_cover", "usable_fraction",
              "index", "index_mean", "index_std", "pixels"]
    with open(out_base.with_suffix(".csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(records)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build an observation series from free satellite data.")
    ap.add_argument("--bbox", type=float, nargs=4, required=True,
                    metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--index", default="ndvi", choices=["ndvi", "ndmi", "ndwi", "bsi"])
    ap.add_argument("--max-cloud", type=float, default=20.0,
                    help="scene-level cloud limit; use 100 to inspect the monsoon")
    ap.add_argument("--best-per-month", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-pixels", type=int, default=256)
    ap.add_argument("--out", required=True, help="output base path, without extension")
    a = ap.parse_args(argv)

    bbox = tuple(a.bbox)
    scenes = stac.search(stac.OPTICAL, bbox, a.start, a.end, cloud_lt=a.max_cloud)
    picked = sample_scenes(scenes, a.best_per_month, a.limit)
    print(f"found {len(scenes)} optical scenes; observing {len(picked)}", file=sys.stderr)

    records: list[dict] = []
    for s in picked:
        try:
            rec = observe(s, bbox, a.index, a.max_pixels)
        except Exception as exc:  # a single unreadable asset must not kill the run
            print(f"  skip {s.id}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        records.append(rec)
        flag = "usable" if rec["usable_fraction"] >= 0.30 else "BLIND"
        print(f"  {rec['acquired']}  usable={rec['usable_fraction']:.3f}  "
              f"{a.index}={rec['index_mean']}  {flag}", file=sys.stderr)

    if not records:
        print("no records produced", file=sys.stderr)
        return 1
    write_records(records, Path(a.out))
    print(f"wrote {a.out}.jsonl and {a.out}.csv ({len(records)} observations)", file=sys.stderr)

    monthly: dict[str, list[float]] = defaultdict(list)
    for r in records:
        monthly[r["acquired"][:7]].append(r["usable_fraction"])
    print("\nusable fraction by month (the monsoon question):", file=sys.stderr)
    for k in sorted(monthly):
        vals = monthly[k]
        print(f"  {k}  mean usable {np.mean(vals):.3f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
