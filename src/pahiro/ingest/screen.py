"""Two-tier screening: decide which scenes are worth downloading, cheaply.

The trap this fixes: Sentinel-2's ``eo:cloud_cover`` describes the whole ~110 km
tile, not your study area. A scene reporting 99.95% cloud can be clear over your
slope, and vice versa. The only honest measure is the scene classification band
(SCL) read over your actual area of interest.

Reading just the SCL window costs ~0.05 MB per scene, so screening the entire
archive for a site is tens of megabytes instead of hundreds of gigabytes of
full tiles.

    python -m pahiro.ingest.screen --bbox 84.95 27.75 85.10 27.90 \
        --from 2024-01-01 --to 2024-12-31 --out evidence/screen-2024
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

CLEAR = np.array(window.CLEAR_SCL)


def screen_scene(scene: stac.Scene, bbox, max_pixels: int = 256) -> dict:
    """Measure how much of the AOI is actually clear ground in this scene."""
    patch = window.read_band(scene.assets["scl"], bbox, max_pixels=max_pixels)
    scl = np.nan_to_num(patch.values, nan=-1).astype("int16")
    total = scl.size
    clear = int(np.isin(scl, CLEAR).sum())
    return {
        "scene_id": scene.id,
        "acquired": scene.acquired.isoformat(),
        "tile_cloud_cover": scene.cloud_cover,
        "aoi_clear_fraction": round(clear / total, 4) if total else 0.0,
        "aoi_pixels": total,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Screen scenes by AOI clear fraction (cheap).")
    ap.add_argument("--bbox", type=float, nargs=4, required=True,
                    metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--max-pixels", type=int, default=256)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", required=True, help="output base path, without extension")
    a = ap.parse_args(argv)

    bbox = tuple(a.bbox)
    # No cloud filter here on purpose: tile cloud is not our cloud.
    # A wide bbox spans several tiles, so page through to collect every scene.
    scenes = stac.search(stac.OPTICAL, bbox, a.start, a.end, cloud_lt=None)
    if a.limit:
        scenes = scenes[: a.limit]
    print(f"screening {len(scenes)} scenes by AOI clear fraction", file=sys.stderr)

    records: list[dict] = []
    for i, s in enumerate(scenes, 1):
        try:
            rec = screen_scene(s, bbox, a.max_pixels)
        except Exception as exc:
            print(f"  [{i}/{len(scenes)}] skip {s.id}: {type(exc).__name__}", file=sys.stderr)
            continue
        records.append(rec)
        if i % 10 == 0 or i == len(scenes):
            print(f"  [{i}/{len(scenes)}] ...", file=sys.stderr)

    if not records:
        print("nothing screened", file=sys.stderr)
        return 1

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out.with_suffix(".jsonl"), "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    with open(out.with_suffix(".csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)

    monthly: dict[str, list[float]] = defaultdict(list)
    for r in records:
        monthly[r["acquired"][:7]].append(r["aoi_clear_fraction"])

    print("\nAOI clear fraction by month (the honest monsoon measure):", file=sys.stderr)
    print(f"{'month':<9}{'scenes':>7}{'median':>9}{'>50%':>7}{'>80%':>7}", file=sys.stderr)
    for k in sorted(monthly):
        v = np.array(monthly[k])
        print(f"{k:<9}{len(v):>7}{np.median(v):>9.2f}"
              f"{100*(v > 0.5).mean():>7.1f}{100*(v > 0.8).mean():>7.1f}", file=sys.stderr)

    jjas = [r["aoi_clear_fraction"] for r in records if r["acquired"][5:7] in ("06", "07", "08", "09")]
    if jjas:
        j = np.array(jjas)
        print(f"\nJJAS pooled: {len(j)} scenes, {100*(j>0.5).mean():.1f}% >50% clear, "
              f"{100*(j>0.8).mean():.1f}% >80% clear", file=sys.stderr)
        for m in ("06", "07", "08", "09"):
            v = np.array([r["aoi_clear_fraction"] for r in records if r["acquired"][5:7] == m])
            if v.size:
                print(f"  month {m}: {v.size} scenes, {100*(v>0.8).mean():.1f}% >80% clear",
                      file=sys.stderr)

    print(f"\nwrote {out}.jsonl / .csv ({len(records)} scenes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
