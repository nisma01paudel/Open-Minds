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
REGIONS = [
    ("kathmandu", "evidence/trails-raw-valley.json",
     "Kathmandu valley and the Shivapuri rim (27.70-27.84 N, 85.22-85.42 E)"),
    ("khumbu", "evidence/trails-raw-khumbu.json",
     "Khumbu / Everest region (27.55-28.05 N, 86.55-87.05 E)"),
]


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
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=None,
                    help="a single extract; omit to build from every region in REGIONS")
    ap.add_argument("--out", default="web/public/data/trails.geojson")
    a = ap.parse_args()

    feats, vertices, covered = [], 0, []
    sources = REGIONS if a.src is None else [(a.src, a.src, "explicit --in")]
    for region, path, description in sources:
        f_path = ROOT / path
        if not f_path.exists():
            print(f"  {region}: no extract at {path} - skipped")
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
    named = sum(1 for f in feats if "n" in f["properties"])
    print(f"wrote {a.out}: {len(feats)} trails, {vertices} vertices, {mb:.2f} MB, {named} named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
