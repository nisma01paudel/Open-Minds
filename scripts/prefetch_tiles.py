#!/usr/bin/env python3
"""Download the national-view basemap tiles so the map works with the wifi dead.

Why this exists: Demo Day is in person, on unknown wifi. Everything else in this project is
keyless and cached by the service worker, but the BASEMAP comes from third-party tile
servers - and the service worker deliberately ignores cross-origin requests. So with the
network down, the whole map rendered empty while the data behind it was all present. That
is the one failure that would have looked like the project was broken rather than offline.

Only the zooms the presenter actually shows are bundled: the country fits in about eighteen
tiles a level at z5-z7, so this is a couple of megabytes, not a tile server. Deeper zoom
still comes from the live service when there is a connection.

    python scripts/prefetch_tiles.py            # both basemaps, z5-z7
"""
from __future__ import annotations

import argparse
import math
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web/public/tiles"

BASEMAPS = {
    "s2cloudless": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg",
    "esri": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
}

# Nepal, with a little margin so a pan does not run off the edge
BBOX = (79.8, 26.1, 88.5, 30.7)


def deg2tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zooms", default="5,6,7")
    ap.add_argument("--basemaps", default="s2cloudless,esri")
    a = ap.parse_args()
    zooms = [int(z) for z in a.zooms.split(",")]

    total = got = skipped = 0
    bytes_tot = 0
    for name in a.basemaps.split(","):
        tmpl = BASEMAPS[name]
        for z in zooms:
            x0, y0 = deg2tile(BBOX[0], BBOX[3], z)      # north-west
            x1, y1 = deg2tile(BBOX[2], BBOX[1], z)      # south-east
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    total += 1
                    dst = OUT / name / str(z) / str(y) / f"{x}.jpg"
                    if dst.exists() and dst.stat().st_size > 1000:
                        skipped += 1
                        continue
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    url = tmpl.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": "pahiro-prefetch/1.0"})
                        with urllib.request.urlopen(req, timeout=45) as r:
                            body = r.read()
                        if len(body) < 500:
                            print(f"  tiny response for {name} z{z} {x},{y}", file=sys.stderr)
                            continue
                        dst.write_bytes(body)
                        got += 1
                        bytes_tot += len(body)
                    except Exception as exc:
                        print(f"  FAIL {name} z{z} {x},{y}: {type(exc).__name__}", file=sys.stderr)
                    time.sleep(0.05)
        print(f"  {name}: done")

    print(f"\n{got} downloaded, {skipped} already present, {total} considered "
          f"({bytes_tot/1e6:.1f} MB new) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
