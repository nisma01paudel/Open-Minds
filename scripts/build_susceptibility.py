#!/usr/bin/env python3
"""Read the peer-reviewed national susceptibility raster at every documented slope.

WHY THIS IS WORTH 688 MB
------------------------
Every hazard judgement in this repository until now was either measured by us or relative to our
own 613 slopes. Both are honest and neither is peer-reviewed. Kincey et al. (2023) published a
national, 30-metre, rainfall-triggered landslide susceptibility surface for Nepal under CC-BY-4.0:

    https://zenodo.org/records/8307964     LandslideSusceptibility30m.zip

Sampling that at our own slope coordinates lets the app say something it could not say before -
"this ground is in the published HIGH susceptibility class" - and cite a source that is not us.

WHAT IT DOES NOT DO
-------------------
It does not replace the measurement. Kincey's surface is a susceptibility model: it says where
failure is more or less likely across the country, not whether a particular slope is moving today.
The two are reported side by side and neither is presented as the other.

    python scripts/build_susceptibility.py --zip evidence/zenodo/susceptibility.zip
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "web/public/data/susceptibility.json"
TIMELINE = "web/public/data/timeline.json"

CITATION = ("Kincey, M. et al. National-scale rainfall-triggered landslide susceptibility and "
            "exposure in Nepal. Zenodo. https://doi.org/10.5281/zenodo.8307964 (CC-BY-4.0)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="evidence/zenodo/susceptibility.zip")
    ap.add_argument("--extract", default="/tmp/kincey")
    a = ap.parse_args()

    zp = ROOT / a.zip
    if not zp.exists():
        print(f"REFUSING: {a.zip} is not here. Download it from the Zenodo record first - it is "
              f"688 MB and this script will not pretend to have read it.")
        return 1

    ex = Path(a.extract)
    ex.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zp) as z:
        tifs = [n for n in z.namelist() if n.lower().endswith((".tif", ".tiff"))]
        if not tifs:
            print("REFUSING: no GeoTIFF inside the archive; the layout changed")
            return 1
        print(f"  {len(tifs)} raster(s) in the archive, extracting ...")
        z.extractall(ex)

    import numpy as np
    import rasterio
    from rasterio.warp import transform as rio_transform

    sites = json.loads((ROOT / TIMELINE).read_text(encoding="utf-8"))["sites"]

    # One raster may cover the country; if several, each point is read from whichever contains it.
    handles = [rasterio.open(ex / t) for t in tifs]
    print(f"  {len(handles)} raster(s) open: {handles[0].crs}, {handles[0].res}")

    # THE RASTER IS NOT IN DEGREES. Kincey's surface is EPSG:32645 (UTM 45N) and our coordinates are
    # WGS84 lat/lon. rasterio.sample() reads its input in the raster's own CRS, so the first run
    # passed degrees as metres, nothing landed inside the bounds, and every point came back missing.
    # The refusal above is the only reason that produced a message instead of a blank file.
    rows, missing = [], 0
    for s in sites:
        val = None
        for h in handles:
            try:
                xs, ys = rio_transform("EPSG:4326", h.crs, [s["lon"]], [s["lat"]])
                x, y = xs[0], ys[0]
            except Exception:                                # noqa: BLE001
                continue
            b = h.bounds
            if b.left <= x <= b.right and b.bottom <= y <= b.top:
                try:
                    v = next(h.sample([(x, y)]))[0]
                    # THE NODATA SENTINEL IS NOT NaN. This raster marks emptiness with the
                    # float32 minimum, -3.4e38, so an isnan test passes it straight through and the
                    # range came out starting at minus three hundred undecillion. Honour the
                    # raster's own nodata, and reject anything outside a plausible susceptibility
                    # range as a second line of defence.
                    if v is None:
                        continue
                    fv = float(v)
                    if h.nodata is not None and abs(fv - float(h.nodata)) < 1e-6:
                        continue
                    if not np.isfinite(fv) or abs(fv) > 1e6:
                        continue
                    val = fv
                except Exception:                            # noqa: BLE001
                    pass
                break
        if val is None:
            missing += 1
            continue
        rows.append({"id": s["id"], "title": s["title"], "value": round(val, 4)})

    if not rows:
        print("REFUSING: not one point fell inside a raster. Check the CRS before trusting a blank.")
        return 1

    for h in handles:
        h.close()

    vals = sorted(r["value"] for r in rows)
    out = {
        "source": CITATION,
        "licence": "CC-BY-4.0",
        "what_it_is": ("A national 30 m rainfall-triggered susceptibility model. It says where "
                       "failure is more or less likely; it does not say whether a slope is moving "
                       "today, and this file is reported beside our own measurements rather than "
                       "instead of them."),
        "sampled": len(rows),
        "unmatched": missing,
        "range": {"min": vals[0], "max": vals[-1],
                  "median": vals[len(vals) // 2],
                  "p90": vals[int(len(vals) * 0.9)]},
        "slopes": rows,
    }
    dest = ROOT / OUT
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(rows)} slopes sampled, {missing} outside the raster, "
          f"range {vals[0]:.3f}-{vals[-1]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
