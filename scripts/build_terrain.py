#!/usr/bin/env python3
"""Build a real 3D terrain for Nepal from open elevation tiles.

The web map is flat. This gives an actual mesh: AWS terrarium elevation tiles decoded to
metres, stitched, decimated, and shipped as a raw Int16 grid the browser can turn into
geometry. Satellite imagery is draped over it separately.

Tiles are decoded through ImageMagick rather than a Python imaging library, because
terrarium stores elevation in RGB and ImageMagick can hand us the raw bytes directly:

    elevation_metres = (R * 256 + G + B / 256) - 32768

    python scripts/build_terrain.py --zoom 9 --decimate 4
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TILE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return x, y


def tile_bounds(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    """(west, south, east, north) of a tile."""
    n = 2 ** z

    def lon(xt: float) -> float:
        return xt / n * 360.0 - 180.0

    def lat(yt: float) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yt / n))))

    return lon(x), lat(y + 1), lon(x + 1), lat(y)


def fetch_tile(z: int, x: int, y: int, cache: Path) -> tuple[int, int, np.ndarray] | None:
    png = cache / f"{z}_{x}_{y}.png"
    raw = cache / f"{z}_{x}_{y}.raw"
    if not raw.exists():
        if not png.exists():
            url = TILE.format(z=z, x=x, y=y)
            r = subprocess.run(["curl", "-s", "-f", "-o", str(png), url], capture_output=True)
            if r.returncode != 0:
                return None
        if subprocess.run(["magick", str(png), "-depth", "8", f"rgb:{raw}"],
                          capture_output=True).returncode != 0:
            return None
    try:
        arr = np.fromfile(raw, dtype=np.uint8)
    except Exception:
        return None
    if arr.size != 256 * 256 * 3:
        # terrarium tiles are sometimes 512px; resample to 256 for a uniform grid
        png2 = cache / f"{z}_{x}_{y}_256.png"
        subprocess.run(["magick", str(png), "-resize", "256x256!", "-depth", "8", f"rgb:{raw}"],
                       capture_output=True, check=True)
        arr = np.fromfile(raw, dtype=np.uint8)
        if arr.size != 256 * 256 * 3:
            return None
    return x, y, arr.reshape(256, 256, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default="80.0,26.2,88.5,30.4", help="west,south,east,north")
    ap.add_argument("--zoom", type=int, default=9)
    ap.add_argument("--decimate", type=int, default=4)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="web/public/data")
    args = ap.parse_args()

    w, s, e, n = (float(v) for v in args.bbox.split(","))
    z = args.zoom
    x0f, y0f = lonlat_to_tile(w, n, z)     # top-left
    x1f, y1f = lonlat_to_tile(e, s, z)     # bottom-right
    x0, y0, x1, y1 = int(x0f), int(y0f), int(x1f), int(y1f)
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    print(f"zoom {z}: {nx} x {ny} = {nx*ny} tiles  (~{nx*ny*0.05:.0f} MB)")

    cache = ROOT / "cache" / f"terrain-{z}"
    cache.mkdir(parents=True, exist_ok=True)

    coords = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    mosaic = np.zeros((ny * 256, nx * 256, 3), dtype=np.uint8)
    ok = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for res in pool.map(lambda c: fetch_tile(z, c[0], c[1], cache), coords):
            if res is None:
                continue
            x, y, arr = res
            r, c = (y - y0) * 256, (x - x0) * 256
            mosaic[r:r + 256, c:c + 256] = arr
            ok += 1
    print(f"decoded {ok}/{len(coords)} tiles")
    if ok == 0:
        print("no tiles decoded", file=sys.stderr)
        return 1

    rgb = mosaic.astype(np.float32)
    elev = (rgb[:, :, 0] * 256.0 + rgb[:, :, 1] + rgb[:, :, 2] / 256.0) - 32768.0

    d = max(1, args.decimate)
    elev = elev[::d, ::d]
    h, wpx = elev.shape
    print(f"grid {wpx} x {h}  ({elev.min():.0f} .. {elev.max():.0f} m)")

    # exact geographic bounds of the tile grid, so the browser can place it precisely
    grid_w, grid_s, grid_e, grid_n = tile_bounds(x0, y0, z)
    _, _, _, _ = tile_bounds(x1, y1, z)
    _, grid_s, grid_e, _ = tile_bounds(x1, y1, z)
    meta = {
        "width": wpx, "height": h,
        "west": grid_w, "south": grid_s, "east": grid_e, "north": grid_n,
        "min_m": float(elev.min()), "max_m": float(elev.max()),
        "zoom": z, "decimate": d, "tiles": ok,
        "note": "AWS Terrain Tiles (terrarium). elevation = (R*256 + G + B/256) - 32768",
    }

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "terrain.bin").write_bytes(elev.astype("<i2").tobytes())
    (out / "terrain.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {out/'terrain.bin'} ({(out/'terrain.bin').stat().st_size:,} bytes)")
    print(f"wrote {out/'terrain.json'}  extent {grid_w:.3f},{grid_s:.3f} .. {grid_e:.3f},{grid_n:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
