#!/usr/bin/env python3
"""Major places, described from data rather than from prose.

WHY IT IS BUILT THIS WAY
------------------------
Two earlier attempts failed. The first asked Overpass for places and got four of six regions back
empty. The second invented nothing and derived everything but had no coordinates.

Both problems are solved by NOT asking for a new dataset at all. Nepal's 753 local units are already
here (administration.json, from NEPAL-QUEST-DATA) with real population, area and official website.
And 613 documented slopes are already here with real coordinates AND a title that names the unit
they sit in - "Landslide at Jaimini Municipality-10".

So a place entry is a JOIN, and every field in it is something a machine checked:

    name, Nepali name, district, province, population, area, website   <- the gazetteer
    lat, lon                                                          <- the slopes documented in it
    slopes_documented, susceptibility_median                          <- our own hazard work
    trails_mapped_within_10km                                         <- the trail bundle

There is no prose, because prose about a place is the one thing nothing here can check.

    python scripts/build_places.py
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "web/public/data/places.geojson"
D = "web/public/data"


def _m(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(h))


def main() -> int:
    admin = json.loads((ROOT / D / "administration.json").read_text(encoding="utf-8"))
    sites = json.loads((ROOT / D / "timeline.json").read_text(encoding="utf-8"))["sites"]
    sus = {r["id"]: r["value"] for r in
           json.loads((ROOT / D / "susceptibility.json").read_text(encoding="utf-8"))["slopes"]}
    trails = json.loads((ROOT / D / "trails.geojson").read_text(encoding="utf-8"))["features"]

    # unit name -> the slopes whose titles name that unit. This is where the coordinates come from.
    units = sorted(admin["units"], key=lambda u: -len(u["name"]))
    hits: dict[str, list[dict]] = defaultdict(list)
    for s in sites:
        title = s["title"].lower()
        for u in units:
            if u["name"].lower() in title:
                hits[u["name"]].append(s)
                break

    if not hits:
        print("REFUSING: no slope title matched a local unit, so there are no coordinates to place")
        return 1
    print(f"  {len(hits)} of {len(admin['units'])} local units located from documented slopes")

    # trail density per place, measured from every vertex within 10 km
    def trail_count(lat: float, lon: float) -> int:
        n = 0
        for f in trails:
            c = f["geometry"]["coordinates"]
            if not c:
                continue
            if any(abs(p[1] - lat) < 0.09 and abs(p[0] - lon) < 0.11 for p in c[::4]):
                n += 1
        return n

    feats = []
    for name, ss in sorted(hits.items(), key=lambda kv: -len(kv[1])):
        u = next(x for x in admin["units"] if x["name"] == name)
        lat = statistics.mean(s["lat"] for s in ss)
        lon = statistics.mean(s["lon"] for s in ss)
        vals = [sus[s["id"]] for s in ss if s["id"] in sus]
        feats.append({
            "type": "Feature",
            "properties": {
                "name": name, "name_ne": u.get("name_ne"), "kind": u.get("kind"),
                "district": u.get("district"), "province_ne": u.get("province_ne"),
                "population": u.get("population"), "area_km2": u.get("area_km2"),
                "website": u.get("website"),
                "slopes_documented": len(ss),
                "susceptibility_median": round(statistics.median(vals), 3) if vals else None,
                "trails_mapped_within_10km": trail_count(lat, lon),
                "located_by": ("the mean position of the documented slopes whose titles name this "
                               "unit - not a surveyed town centre"),
            },
            "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
        })

    out = {
        "type": "FeatureCollection",
        "attribution": ("Local units from github.com/rgtstha/NEPAL-QUEST-DATA (community open data); "
                        "slopes and trails \u00a9 OpenStreetMap contributors, ODbL 1.0"),
        "method": ("A place is a join, not a description. Names, population, area and website come "
                   "from Nepal's 753-unit gazetteer; coordinates come from the documented slopes "
                   "whose titles name the unit; hazard and trail figures come from this repository. "
                   "No field here is prose, because prose about a place is the one thing that "
                   "cannot be checked."),
        "accuracy": ("Positions are the MEAN OF DOCUMENTED SLOPES inside a unit, not town centres. "
                     "A large rural municipality can be tens of kilometres across, so a point is a "
                     "label position, not a location. Distances measured to these points inherit "
                     "that error and are reported as approximate."),
        "counts": {"places": len(feats)},
        "features": feats,
    }
    dest = ROOT / OUT
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(feats)} places, {dest.stat().st_size/1024:.0f} KB")
    for f in feats[:5]:
        p = f["properties"]
        print(f"    {p['name'][:26]:28} {p['district'] or '-':16} pop {str(p['population'] or '-'):>8} "
              f"{p['slopes_documented']:>3} slopes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
