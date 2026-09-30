#!/usr/bin/env python3
"""Render a 360-degree panorama of the real terrain from the bundled DEM.

WHY
---
"See how the valley actually looks" cannot be answered with a photograph we do not have and must
not fake. It CAN be answered from the elevation grid we already ship: stand at a point, look in
every direction, and ask how high the ground rises along each bearing. That is a horizon, and a
horizon is what a place looks like.

The output is equirectangular - 2:1, the standard panorama projection - so any viewer, any VR headset
browser, or a plain three.js sphere can open it. It is generated offline and needs no network.

    python scripts/render_panorama.py --lat 28.35 --lon 83.57 --out panorama.png

WHAT IT IS NOT
--------------
It is a silhouette from a ~1 km grid: no trees, no buildings, no colour from the ground. The sky is a
gradient, not a photograph. It shows SHAPE, which is the one thing the elevation data actually
knows, and it says so rather than implying more.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEM_BIN = "web/public/data/terrain.bin"
DEM_META = "web/public/data/terrain.json"

WIDTH = 2048                 # equirectangular: width is 360 degrees
RAY_STEPS = 240              # samples along each bearing
MAX_RANGE_M = 60000.0        # how far the eye looks; beyond this a 1 km grid says nothing useful


def load_dem():
    meta = json.loads((ROOT / DEM_META).read_text(encoding="utf-8"))
    grid = np.fromfile(ROOT / DEM_BIN, dtype="<u2").reshape(meta["height"], meta["width"])
    return meta, grid.astype(np.float64)


def horizon_profile(meta: dict, grid: np.ndarray, lat: float, lon: float, n_az: int):
    """The elevation angle of the highest ground along each bearing, in degrees."""
    h, w = grid.shape
    west, south, east, north = meta["west"], meta["south"], meta["east"], meta["north"]
    # metres per degree at this latitude, good enough over a 60 km look
    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * math.cos(math.radians(lat))

    eye_y = int((north - lat) / (north - south) * (h - 1))
    eye_x = int((lon - west) / (east - west) * (w - 1))
    eye_y = max(0, min(h - 1, eye_y)); eye_x = max(0, min(w - 1, eye_x))
    eye_z = float(grid[eye_y, eye_x])

    az = np.radians(np.arange(n_az) * 360.0 / n_az)
    horizon = np.full(n_az, -90.0)
    for step in range(1, RAY_STEPS + 1):
        r = MAX_RANGE_M * (step / RAY_STEPS) ** 1.4      # denser near the viewer
        dlat = (r * np.cos(az)) / m_per_deg_lat
        dlon = (r * np.sin(az)) / m_per_deg_lon
        yy = np.clip(((north - (lat + dlat)) / (north - south) * (h - 1)).astype(int), 0, h - 1)
        xx = np.clip(((lon + dlon - west) / (east - west) * (w - 1)).astype(int), 0, w - 1)
        z = grid[yy, xx]
        ang = np.degrees(np.arctan2(z - eye_z, r))
        horizon = np.maximum(horizon, ang)
    return horizon, eye_z


def render(meta, grid, lat, lon, width=WIDTH, height=None):
    height = height or width // 2
    n_az = width
    horizon, eye_z = horizon_profile(meta, grid, lat, lon, n_az)

    # vertical field of view: +35 degrees up, -25 down, which covers what a horizon needs
    top, bottom = 35.0, -25.0
    rows = np.linspace(top, bottom, height)[:, None]
    sky_h = horizon[None, :]

    horizon_row = (top - horizon) / (top - bottom) * (height - 1)
    yy = np.arange(height)[:, None]
    is_sky = yy < horizon_row[None, :]

    # THE SKY DEPENDS ONLY ON HOW HIGH YOU ARE LOOKING, not on how high the ridge in front of you
    # is. Tying it to the horizon made each column a different brightness and the first render came
    # out with hard vertical stripes across the whole sky - an artefact of the code, presented as
    # if it were the mountain.
    sky_frac = np.clip((rows - top) / (top - bottom), 0, 1)
    sky = np.stack([
        150 - 100 * sky_frac,
        200 - 90 * sky_frac,
        240 - 55 * sky_frac,
    ], axis=-1) * np.ones((1, width, 1))

    # ground: darker with distance below the horizon, warming toward the eye
    depth = np.clip(-(rows - horizon[None, :]) / 25.0, 0, 1)
    ground = np.stack([
        70 - 30 * depth,
        92 - 40 * depth,
        66 - 30 * depth,
    ], axis=-1)

    img = np.where(is_sky[..., None], sky, ground)
    img = np.clip(img, 0, 255).astype(np.uint8)
    return img, horizon, eye_z


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--out", default="/tmp/panorama.png")
    ap.add_argument("--width", type=int, default=WIDTH)
    a = ap.parse_args()

    meta, grid = load_dem()
    img, horizon, eye_z = render(meta, grid, a.lat, a.lon, a.width)

    from PIL import Image
    dest = Path(a.out)
    if not dest.is_absolute():
        dest = ROOT / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img, "RGB").save(dest)

    print(f"  eye {eye_z:.0f} m at {a.lat}, {a.lon}")
    print(f"  horizon {horizon.min():.1f} to {horizon.max():.1f} degrees above level")
    print(f"  highest ground at bearing {int(np.argmax(horizon) * 360 / len(horizon))} degrees")
    print(f"wrote {dest} ({img.shape[1]}x{img.shape[0]}, {dest.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
