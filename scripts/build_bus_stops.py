#!/usr/bin/env python3
"""Build the offline bus-stop bundle from the regional OpenStreetMap extracts.

WHY THIS EXISTS
---------------
trails.geojson had a committed generator and bus-parks.geojson did not: it was produced by a
throwaway command typed once into a shell. That made one of the two data files in this repository
reproducible and the other not, which is the difference between data and an artefact somebody
happened to make.

    python scripts/build_bus_stops.py              # from the extracts in evidence/
    python scripts/build_bus_stops.py --fetch      # download them first (~1 MB)

The extracts are not committed - see REGIONS - so a clean clone needs --fetch once.

Bus stop data (c) OpenStreetMap contributors, ODbL 1.0.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "web/public/data/bus-parks.geojson"

# name, extract, bbox, and the one-word region tag written onto every stop.
REGIONS = [
    ("Kathmandu valley", "evidence/bus-stations-valley.json", "27.62,85.20,27.86,85.50"),
    ("Pokhara valley", "evidence/bus-stations-pokhara.json", "28.10,83.85,28.35,84.10"),
    ("Langtang road corridor (Trishuli, Battar, Kutumsang)", "evidence/bus-stations-langtang.json", "27.90,85.10,28.35,85.60"),
]

OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]

NOTE = ("Mapped bus stations and named bus stops, by region. Many are unnamed in OSM, which is "
        "itself information: a stop exists at these coordinates and the map does not say what it "
        "is called. The Langtang corridor is sparse because it is a road with a village on it, "
        "not a city with a stop list - and for Khumbu there are no stops at all, which is the "
        "truth rather than a gap: Namche is two days' walk from the road head.")


def fetch(bbox: str, dest: Path) -> bool:
    query = (f'[out:json][timeout:200];('
             f'node["amenity"="bus_station"]({bbox});'
             f'way["amenity"="bus_station"]({bbox});'
             f'node["highway"="bus_stop"]["name"]({bbox});'
             f');out center tags;')
    for endpoint in OVERPASS:
        try:
            req = urllib.request.Request(
                endpoint, data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": "pahiro-access/1.0"})
            dest.write_bytes(urllib.request.urlopen(req, timeout=260).read())
            return True
        except Exception as exc:                            # noqa: BLE001
            print(f"    {endpoint.split('/')[2]}: {type(exc).__name__}")
            time.sleep(2)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true",
                    help="download the extracts first; they are not committed")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    out = {
        "type": "FeatureCollection",
        "attribution": "\u00a9 OpenStreetMap contributors, ODbL 1.0",
        "source": "openstreetmap.org via Overpass API",
        "regions": [{"name": n, "file": f} for n, f, _ in REGIONS],
        "note": NOTE,
        "features": [],
    }

    for name, rel, bbox in REGIONS:
        path = ROOT / rel
        if not path.exists() and a.fetch:
            print(f"  fetching {name} ...")
            path.parent.mkdir(parents=True, exist_ok=True)
            fetch(bbox, path)
        if not path.exists():
            print(f"  {name}: no extract at {rel} - run with --fetch")
            continue
        # the TAG stays one word even when the display name does not
        tag = name.split()[0].lower()
        got = 0
        for e in json.loads(path.read_text(encoding="utf-8")).get("elements", []):
            tags = e.get("tags") or {}
            lat = e.get("lat") or (e.get("center") or {}).get("lat")
            lon = e.get("lon") or (e.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            stop = tags.get("name")
            props = {"r": tag}
            if stop:
                props["n"] = stop
            out["features"].append({
                "type": "Feature", "properties": props,
                "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            })
            got += 1
        print(f"  {name}: {got} stops")

    dest = ROOT / a.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    named = sum(1 for f in out["features"] if f["properties"].get("n"))
    print(f"wrote {a.out}: {len(out['features'])} stops ({named} named), "
          f"{dest.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
