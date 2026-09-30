#!/usr/bin/env python3
"""Turn raw OpenStreetMap walkable ways into the offline trail bundle.

WHY THIS EXISTS
---------------
The offline map in this repository was 34 coarse tiles at zoom 5-7 - fine for "where in Nepal",
useless for "which way to the top". A trail is a LINE, not a tile: vector geometry is small, is
correct at every zoom, and needs no network once it is here. So the daily-use half of this app
ships as vectors, and the tiles stay for context.

Source: OSM way["highway"~path|footway|track|steps|bridleway] over the Kathmandu valley
(27.70-27.84 N, 85.22-85.42 E) - the Shivapuri rim, where people actually day-hike.

    python scripts/build_trails.py --in evidence/trails-raw-valley.json

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
    ap.add_argument("--in", dest="src", default="evidence/trails-raw-valley.json")
    ap.add_argument("--out", default="web/public/data/trails.geojson")
    a = ap.parse_args()

    raw = json.loads((ROOT / a.src).read_text(encoding="utf-8"))
    feats, vertices = [], 0
    for el in raw.get("elements", []):
        f = clean(el)
        if f:
            feats.append(f)
            vertices += len(f["geometry"]["coordinates"])

    out = {
        "type": "FeatureCollection",
        "attribution": "© OpenStreetMap contributors, ODbL 1.0",
        "source": "openstreetmap.org via Overpass API",
        "region": "Kathmandu valley and the Shivapuri rim (27.70–27.84 N, 85.22–85.42 E)",
        "note": "Walkable ways. Difficulty from OSM sac_scale, absent where untagged.",
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
