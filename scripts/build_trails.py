#!/usr/bin/env python3
"""Turn raw OpenStreetMap walkable ways into the offline trail bundle.

WHY THIS EXISTS
---------------
The offline map in this repository was 34 coarse tiles at zoom 5-7 - fine for "where in Nepal",
useless for "which way to the top". A trail is a LINE, not a tile: vector geometry is small, is
correct at every zoom, and needs no network once it is here. So the daily-use half of this app
ships as vectors, and the tiles stay for context.

Source: OSM way["highway"~path|footway|track|steps|bridleway] over the regions listed in
REGIONS. Nepal has far more walking than one city, so the bundle is built from several extracts
and the region name travels on every trail - a walk in Khumbu is not offered to somebody standing
in Kathmandu, and the point of naming the region is that a reader can tell which parts of the
country are actually covered and which simply have not been fetched yet.

    python scripts/build_trails.py                      # every region present in evidence/

Coordinates are rounded to 5 decimals (about 1 m) because nobody navigates a footpath to the
centimetre and the file ships to phones.

ODbL: OpenStreetMap contributors. Attribution is in the output's `attribution` field and must
stay there - the licence requires it, and it is also just true.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Difficulty, in the order a walker meets it. OSM's sac_scale, mapped to words rather than
# left as a tag nobody can read.
SAC_WORDS = {
    "hiking": "easy",
    "mountain_hiking": "moderate",
    "demanding_mountain_hiking": "hard",
    "alpine_hiking": "hard",
    "demanding_alpine_hiking": "severe",
    "difficult_alpine_hiking": "severe",
}
WALKABLE = {"path", "footway", "track", "steps", "bridleway"}

# One extract per region. Adding a region is a data change: fetch it, save it, add a line here.
# name, the raw extract, the bbox to fetch it, and what it covers.
#
# THE RAW EXTRACTS ARE NOT COMMITTED. They are 27 MB of machine-generated OSM that anyone can
# re-fetch in one command, and the bundle they produce - 4.5 MB - IS committed, so the app works
# from a clone without them. Carrying the inputs as well made the repository 102 MB for no reader's
# benefit; this project has already had one 353 MB bloat problem and does not need a second.
REGIONS = [
    ("kathmandu", "evidence/trails-raw-valley.json", "27.70,85.22,27.84,85.42",
     "Kathmandu valley and the Shivapuri rim"),
    ("khumbu", "evidence/trails-raw-khumbu.json", "27.55,86.55,28.05,87.05",
     "Khumbu / Everest region"),
    ("annapurna", "evidence/trails-raw-annapurna.json", "28.15,83.65,28.85,84.35",
     "Annapurna region"),
    ("langtang", "evidence/trails-raw-langtang.json", "27.90,85.15,28.45,85.85",
     "Langtang and Helambu"),
]

OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]


def fetch_regions() -> int:
    """Download every region's extract from Overpass. One command, no key, ~27 MB.

    This is what replaces committing the raw data: the bundle is in the repository, the recipe to
    rebuild it is in this function, and the intermediate files are not shipped twice.
    """
    import time
    import urllib.parse
    import urllib.request

    ok = 0
    for name, path, bbox, description in REGIONS:
        dest = ROOT / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        query = (f'[out:json][timeout:280];'
                 f'way["highway"~"^(path|footway|track|steps|bridleway)$"]({bbox});out geom;')
        for endpoint in OVERPASS:
            try:
                req = urllib.request.Request(
                    endpoint, data=urllib.parse.urlencode({"data": query}).encode(),
                    headers={"User-Agent": "pahiro-trails/1.0"})
                data = urllib.request.urlopen(req, timeout=300).read()
                dest.write_bytes(data)
                ways = data.count(b'"type":"way"')
                print(f"  {name}: {ways} ways -> {path}")
                ok += 1
                break
            except Exception as exc:                       # noqa: BLE001
                print(f"  {name}: {endpoint.split('/')[2]} failed ({type(exc).__name__})")
                time.sleep(2)
        else:
            print(f"  {name}: could not fetch - {description}")
    return ok

# GEOMETRY IS SIMPLIFIED, and this is a deliberate trade rather than a shortcut.
#
# Four regions at full OSM precision is about 520,000 vertices and a 13 MB bundle. That is a real
# cost: it is precached for offline use, so a walker pays it in mobile data, and it ships inside the
# APK. Douglas-Peucker at this tolerance removes the vertices that carry no shape - the ones
# recorded by a GPS trace wobbling along a straight path - and keeps every bend a person would
# notice. The distance figure moves by a fraction of a per cent, and the output reports both
# numbers so the trade is visible instead of asserted.
SIMPLIFY_M = 10.0


def _perpendicular_m(pt, a, b) -> float:
    """Distance from a point to the segment ab, in metres, on a local flat approximation."""
    lat0 = (a[1] + b[1]) / 2.0
    kx = 111_320.0 * math.cos(math.radians(lat0))
    ky = 111_320.0
    px, py = (pt[0] - a[0]) * kx, (pt[1] - a[1]) * ky
    bx, by = (b[0] - a[0]) * kx, (b[1] - a[1]) * ky
    seg2 = bx * bx + by * by
    if seg2 == 0:
        return math.hypot(px, py)
    t = max(0.0, min(1.0, (px * bx + py * by) / seg2))
    return math.hypot(px - t * bx, py - t * by)


def simplify(coords, tolerance_m: float = SIMPLIFY_M):
    """Douglas-Peucker. Ramer's algorithm, unchanged since 1972, which is why it is the right one:
    it is the standard, it is exact, and nobody has to review it."""
    if len(coords) < 3:
        return coords
    keep = [False] * len(coords)
    keep[0] = keep[-1] = True
    stack = [(0, len(coords) - 1)]
    while stack:
        i, j = stack.pop()
        worst, idx = 0.0, -1
        for k in range(i + 1, j):
            d = _perpendicular_m(coords[k], coords[i], coords[j])
            if d > worst:
                worst, idx = d, k
        if idx != -1 and worst > tolerance_m:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [c for c, k in zip(coords, keep) if k]


def clean(way: dict) -> dict | None:
    geom = way.get("geometry") or []
    if len(geom) < 2:
        return None
    tags = way.get("tags") or {}
    hw = tags.get("highway")
    if hw not in WALKABLE:
        return None
    props = {"h": hw}
    if tags.get("name"):
        # Names are often long and often duplicated; 80 chars is plenty for a label.
        props["n"] = tags["name"][:80]
    sac = tags.get("sac_scale")
    if sac:
        props["d"] = SAC_WORDS.get(sac, sac)
    # `steps` and `bridleway` matter to a walker deciding whether to take it.
    coords = [[round(p["lon"], 5), round(p["lat"], 5)] for p in geom
              if p and p.get("lon") is not None and p.get("lat") is not None]
    if len(coords) < 2:
        return None
    coords = simplify(coords)
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=None,
                    help="a single extract; omit to build from every region in REGIONS")
    ap.add_argument("--out", default="web/public/data/trails.geojson")
    ap.add_argument("--fetch", action="store_true",
                    help="download the regional extracts from Overpass first (they are not "
                         "committed: 27 MB of machine-generated data)")
    a = ap.parse_args()

    if a.fetch:
        print("fetching regional extracts from OpenStreetMap ...")
        got = fetch_regions()
        if not got:
            return 1

    feats, vertices, raw_vertices, covered = [], 0, 0, []
    sources = REGIONS if a.src is None else [(a.src, a.src, "explicit --in")]
    for region, path, *rest in [(s[0], s[1]) for s in sources] if a.src else REGIONS:
        description = rest[0] if rest else "explicit --in"
        f_path = ROOT / path
        if not f_path.exists():
            print(f"  {region}: no extract at {path} - run with --fetch to download it")
            continue
        raw = json.loads(f_path.read_text(encoding="utf-8"))
        got = 0
        for el in raw.get("elements", []):
            f = clean(el)
            if f:
                # The region travels with the trail so a walk in Khumbu is never offered to
                # somebody standing in Kathmandu.
                f["properties"]["r"] = region
                feats.append(f)
                vertices += len(f["geometry"]["coordinates"])
                raw_vertices += len([p for p in (el.get("geometry") or []) if p.get("lon")])
                got += 1
        covered.append(description)
        print(f"  {region}: {got} ways")

    out = {
        "type": "FeatureCollection",
        "attribution": "© OpenStreetMap contributors, ODbL 1.0",
        "source": "openstreetmap.org via Overpass API",
        "regions": covered,
        "note": ("Walkable ways, by region. Difficulty from OSM sac_scale, absent where untagged. "
                 "Nepal has far more walking than this: a region missing here is one nobody has "
                 "fetched yet, not one without trails."),
        "features": feats,
    }
    dest = ROOT / a.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    mb = dest.stat().st_size / 1_048_576
    kept = vertices / raw_vertices * 100 if raw_vertices else 100.0
    print(f"  geometry: {raw_vertices} vertices -> {vertices} kept ({kept:.0f}% at "
          f"{SIMPLIFY_M:.0f} m tolerance)")
    named = sum(1 for f in feats if "n" in f["properties"])
    print(f"wrote {a.out}: {len(feats)} trails, {vertices} vertices, {mb:.2f} MB, {named} named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
