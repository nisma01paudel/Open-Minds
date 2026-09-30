#!/usr/bin/env python3
"""Major places with descriptions that are COMPUTED, not written.

WHY IT IS BUILT THIS WAY
------------------------
A place description copied from a guidebook is prose somebody else wrote. A description invented
here would be prose nobody verified, which is the failure this project keeps catching.

So every field is derived from something checkable: the place comes from OpenStreetMap, its type
and population are OSM tags, its elevation is read from the bundled DEM, and how many of this
repository's own mapped trails begin within five kilometres is counted from the trail network.

That last one is the point. Nothing else in the world tells a walker "this is where the trails
start", because nothing else has both the place list and the trail network in the same offline file.

    python scripts/build_places.py            # from the cache in evidence/
    python scripts/build_places.py --fetch    # download the places first
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = "evidence/places-raw.json"
OUT = "web/public/data/places.geojson"
TRAILS = "web/public/data/trails.geojson"
DEM = "web/public/data/terrain.bin"
DEM_META = "web/public/data/terrain.json"
TRAILHEAD_M = 5000.0

REGIONS = [
    ("kathmandu", "27.55,85.10,27.90,85.55"),
    ("khumbu", "27.55,86.55,28.05,87.05"),
    ("annapurna", "28.15,83.65,28.85,84.35"),
    ("langtang", "27.90,85.15,28.45,85.85"),
    ("manaslu", "28.30,84.30,28.90,85.00"),
    ("mustang", "28.55,83.55,29.20,84.25"),
]

OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]

# Place classes worth carrying. A hamlet is not a place you plan a trip around.
WANTED = {"city", "town", "village", "suburb", "municipality"}


def fetch(bbox: str) -> list[dict]:
    q = (f'[out:json][timeout:180];('
         + "".join(f'node["place"="{p}"]({bbox});' for p in WANTED) +
         f');out center tags;')
    for ep in OVERPASS:
        try:
            req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": "pahiro-places/1.0"})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read()).get("elements", [])
        except Exception as exc:                             # noqa: BLE001
            print(f"    {ep.split('/')[2]}: {type(exc).__name__}")
            time.sleep(3)
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()

    cache = ROOT / CACHE
    if a.fetch or not cache.exists():
        raw = {}
        for key, bbox in REGIONS:
            print(f"  fetching {key} ...")
            raw[key] = fetch(bbox)
            time.sleep(2)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(raw), encoding="utf-8")
    raw = json.loads(cache.read_text(encoding="utf-8"))

    # A region that fetched nothing must stop the build. The first run got two of six regions, and
    # the file it wrote looked complete - it was an Annapurna list presented as a national one.
    empty = [k for k, _ in REGIONS if not raw.get(k)]
    if empty:
        print(f"REFUSING TO WRITE: no places for {', '.join(empty)}. "
              f"The earlier attempt shipped a two-region file as a national gazetteer because "
              f"nothing checked. Re-run with --fetch on a connection that works.")
        return 1

    trails = json.loads((ROOT / TRAILS).read_text(encoding="utf-8"))["features"]
    meta = json.loads((ROOT / DEM_META).read_text(encoding="utf-8"))
    import numpy as np
    dem = np.fromfile(ROOT / DEM, dtype="<u2").reshape(meta["height"], meta["width"])
    # terrain.json stores the corners as flat keys (west/south/east/north), not a bounds array.
    # Reading meta["bounds"] returned None for every place, so all 207 came out with no elevation
    # and nothing failed - a silent None, which is the shape of most of the bugs in this repository.
    bounds = (meta.get("west"), meta.get("south"), meta.get("east"), meta.get("north"))

    def elevation(lat: float, lon: float):
        if any(b is None for b in bounds):
            return None
        w, s, e, n = bounds
        if not (s <= lat <= n and w <= lon <= e):
            return None
        y = int((n - lat) / (n - s) * (meta["height"] - 1))
        x = int((lon - w) / (e - w) * (meta["width"] - 1))
        return int(dem[max(0, min(meta["height"] - 1, y)), max(0, min(meta["width"] - 1, x))])

    # Trailheads: which mapped trails start within 5 km. Computed from the bundle, so it moves when
    # the bundle moves and cannot go stale the way a written description does.
    starts = []
    for f in trails:
        c = f["geometry"]["coordinates"]
        if c:
            starts.append((c[0][1], c[0][0]))

    features, seen = [], set()
    for key, _ in REGIONS:
        for e in raw.get(key, []):
            tags = e.get("tags") or {}
            name = tags.get("name")
            lat = e.get("lat") or (e.get("center") or {}).get("lat")
            lon = e.get("lon") or (e.get("center") or {}).get("lon")
            if not name or lat is None or lon is None or name in seen:
                continue
            seen.add(name)
            near = sum(1 for (slat, slon) in starts
                       if abs(slat - lat) < 0.045 and abs(slon - lon) < 0.05)
            features.append({
                "type": "Feature",
                "properties": {
                    "name": name,
                    "kind": tags.get("place"),
                    "region": key,
                    "population": int(tags["population"]) if str(tags.get("population", "")).isdigit() else None,
                    "district": tags.get("addr:district") or tags.get("is_in:district"),
                    "elevation_m": elevation(lat, lon),
                    # Counted, NOT named. A first version called >=3 trails a "trailhead" and
                    # flagged 207 out of 207 places, because a 5 km box anywhere in the middle
                    # hills contains dozens of the 23,726 mapped trails. The number is a measure of
                    # how densely OSM has mapped that area - which is real information - and it is
                    # not a claim that walking there is good, which the count cannot support.
                    "trails_mapped_within_5km": near,
                },
                "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            })

    heads = sorted(features, key=lambda x: -x["properties"]["trails_mapped_within_5km"])[:5]
    out = {
        "type": "FeatureCollection",
        "attribution": "\u00a9 OpenStreetMap contributors, ODbL 1.0",
        "source": "openstreetmap.org via Overpass API",
        "method": ("Every field is derived, not written: place and population from OSM tags, "
                   "elevation read from this repository's DEM, and trails_within_5km counted from "
                   "the bundled trail network. There is no prose here, because prose about a place "
                   "is the one thing that cannot be checked by a machine."),
        "note_on_density": ("trails_mapped_within_5km counts mapped trails whose first node falls "
                            "inside a five-kilometre box. It measures how well OpenStreetMap has "
                            "covered the area, not how good the walking is, and an area with no "
                            "coverage reads as zero however fine the walking there may be."),
        "feature_count": len(features),
        "reporting": 0,
        "features": features,
    }
    dest = ROOT / OUT
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(features)} places, {dest.stat().st_size/1024:.0f} KB")
    for f in heads:
        p = f["properties"]
        print(f"    {p['name'][:32]:34} {p['trails_mapped_within_5km']:>4} mapped trails  "
              f"{p['elevation_m']} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
