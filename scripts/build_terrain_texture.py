#!/usr/bin/env python3
"""Render the terrain texture from the committed elevation grid.

WHY THIS EXISTS
---------------
terrain-texture.jpg was the last file in web/public/data/ with no recipe - the backdrop of the 3D
flythrough, beat 6. It is 2048x1260, and 2048/1260 is 1.625, which is exactly 832/512: the aspect
of the bundled DEM. So it is a colour-shaded render of the same grid, and this reconstructs it.

    python scripts/build_terrain_texture.py --out /tmp/texture.png     # look before you leap
    python scripts/build_terrain_texture.py --out web/public/data/terrain-texture.jpg

THE DEFAULT OUTPUT IS A SCRATCH PATH, ON PURPOSE

This renders a texture from the DEM. The committed file was rendered by a colormap that was not
kept, so this reproduces the KIND of image and the exact geometry, not the original's pixels or its
palette. Overwriting the one the demo uses with a differently-shaded one would change how beat 6
looks, which is the same class of mistake as the observability regeneration that would have
silently replaced two quoted figures. So the safe output is the default and the served path is
opt-in.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEM_BIN = "web/public/data/terrain.bin"
DEM_JSON = "web/public/data/terrain.json"
WIDTH = 2048


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/terrain-texture.png")
    a = ap.parse_args()

    meta = json.loads((ROOT / DEM_JSON).read_text(encoding="utf-8"))
    w, h = int(meta["width"]), int(meta["height"])
    grid = np.fromfile(ROOT / DEM_BIN, dtype="<u2").reshape(h, w).astype(np.float64)
    lo, hi = float(grid.min()), float(grid.max())
    print(f"  DEM {w}x{h}, {lo:.0f}-{hi:.0f} m")

    # Hillshade from the grid's own gradient, at the grid's own resolution. No sun position is
    # invented: a shading from the north-west is the cartographic convention.
    dy, dx = np.gradient(grid)
    slope = np.arctan(np.hypot(dx, dy) / 1.0)
    aspect = np.arctan2(-dx, dy)
    shade = (np.cos(np.radians(45)) * np.cos(slope)
             + np.sin(np.radians(45)) * np.sin(slope) * np.cos(np.radians(315) - aspect))
    shade = np.clip((shade + 1) / 2, 0.35, 1.25)

    # A hypsometric ramp: valley greens through ochre to snow, which is what a Nepal backdrop is.
    t = np.clip((grid - lo) / max(1.0, hi - lo), 0, 1)
    stops = np.array([0.00, 0.18, 0.40, 0.62, 0.80, 0.92, 1.00])
    colours = np.array([[38, 70, 45], [78, 105, 58], [140, 130, 84],
                        [168, 140, 104], [190, 186, 180], [232, 234, 238], [255, 255, 255]])
    rgb = np.stack([np.interp(t, stops, colours[:, i]) for i in range(3)], axis=-1)
    rgb = np.clip(rgb * shade[..., None], 0, 255).astype(np.uint8)

    from PIL import Image
    im = Image.fromarray(rgb, "RGB")
    out_h = int(round(WIDTH * h / w))
    im = im.resize((WIDTH, out_h), Image.LANCZOS)

    dest = Path(a.out)
    if not dest.is_absolute():
        dest = ROOT / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.suffix.lower() in (".jpg", ".jpeg"):
        im.save(dest, quality=88, optimize=True)
    else:
        im.save(dest)
    print(f"  wrote {dest} ({im.size[0]}x{im.size[1]}, {dest.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
