"""Everything this app knows about one point, in one answer.

WHY ONE CALL
------------
The app had six things to say about a place and six places to say it: trails in one file, seasons in
another, a panorama in a third, the duty holder in a fourth, susceptibility in a fifth, buses in a
sixth. A person standing on a road does not want six lookups. This is the screen they actually use,
expressed as an API: give it a coordinate, get the whole picture, offline.

Every field names the file it came from, so a wrong number can be traced to its source rather than
argued about, and every field that could not be resolved says so instead of going missing.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import complaints as C

ROOT = Path(__file__).resolve().parents[2]
D = "web/public/data"


def _load(name: str) -> Any:
    try:
        return json.loads((ROOT / D / name).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


def _m(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(h))


@dataclass
class Place:
    lat: float
    lon: float
    region: dict | None = None
    seasons: list[dict] = field(default_factory=list)
    panorama: str | None = None
    trails: list[dict] = field(default_factory=list)
    duty: dict | None = None
    susceptibility: float | None = None
    bus: dict | None = None
    unresolved: list[str] = field(default_factory=list)
    sources: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], {})}


def place(lat: float, lon: float, *, trail_radius_m: float = 5000.0, limit: int = 5) -> Place:
    p = Place(lat=lat, lon=lon)
    p.sources = {
        "region and seasons": "seasons.json (Open-Meteo ERA5, cross-checked against CHIRPS)",
        "panorama": "panoramas/*.png (rendered from terrain.bin)",
        "trails": "trails.geojson (OpenStreetMap, ODbL)",
        "duty and address": "timeline.json routing key + administration.json",
        "susceptibility": "susceptibility.json (Kincey et al. 2023, CC-BY-4.0)",
        "bus": "bus-parks.geojson (OpenStreetMap, ODbL)",
    }

    seasons = _load("seasons.json")
    if seasons:
        best = min(seasons["regions"], key=lambda r: _m((lat, lon), (r["lat"], r["lon"])))
        p.region = {"key": best["key"], "name": best["name"],
                    "distance_km": round(_m((lat, lon), (best["lat"], best["lon"])) / 1000, 1)}
        p.seasons = best["months"]
        p.panorama = f"/data/panoramas/{best['key']}.png"
    else:
        p.unresolved.append("seasons.json is missing, so there is no guide for this point")

    trails = _load("trails.geojson")
    if trails:
        # EVERY VERTEX, NOT THE FIRST ONE. The first version measured to each trail's opening point,
        # so the whole Annapurna network read as absent from Beni - a town the trail passes through -
        # because no trail HAPPENS to begin within five kilometres. A trail 100 m away whose first
        # node is 20 km up the valley was invisible. Same mistake as the places builder's, one round
        # after I fixed it there.
        import numpy as np
        best: dict[int, float] = {}
        for i, f in enumerate(trails["features"]):
            c = f["geometry"]["coordinates"]
            if not c:
                continue
            a = np.asarray(c, dtype=float)
            dlat = np.radians(a[:, 1] - lat)
            dlon = np.radians(a[:, 0] - lon)
            h = (np.sin(dlat / 2) ** 2
                 + math.cos(math.radians(lat)) * np.cos(np.radians(a[:, 1])) * np.sin(dlon / 2) ** 2)
            d = float((6371000.0 * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))).min())
            if d <= trail_radius_m:
                best[i] = d
        near = [{"name": trails["features"][i]["properties"].get("name"),
                 "distance_m": round(d),
                 "sac": trails["features"][i]["properties"].get("sac_scale")}
                for i, d in sorted(best.items(), key=lambda kv: kv[1])[:limit]]
        p.trails = near
        if not near:
            # AN EMPTY LIST IS NOT AN ANSWER. Beni is the gateway to the Dhaulagiri circuit and this
            # returns nothing, because the Annapurna extract starts at longitude 83.65 and Beni sits
            # at 83.57 - a few kilometres outside it. Reporting "0 trails" reads as "no trails here";
            # what is true is that this repository has not mapped them, and those are different
            # statements with different consequences for somebody planning a walk.
            allbest = 9e9
            for i, f in enumerate(trails["features"]):
                c = f["geometry"]["coordinates"]
                if not c:
                    continue
                a0 = np.asarray(c[0], dtype=float)
                d0 = _m((lat, lon), (a0[1], a0[0]))
                allbest = min(allbest, d0)
            p.unresolved.append(
                f"no mapped trail within {trail_radius_m/1000:.0f} km. The nearest in this bundle is "
                f"{allbest/1000:.0f} km away, which is a gap in the map, not proof that nobody walks "
                f"here - the region extracts have hard edges.")
    else:
        p.unresolved.append("trails.geojson is missing")

    sus = _load("susceptibility.json")
    if sus:
        rows = sus["slopes"]
        if rows:
            # nearest sampled slope is a proxy for the ground underfoot, and it is labelled as one
            tl = _load("timeline.json")
            by_id = {s["id"]: s for s in (tl or {}).get("sites", [])}
            cand = [(abs(_m((lat, lon), (by_id[r["id"]]["lat"], by_id[r["id"]]["lon"]))
                         if r["id"] in by_id else 9e9), r) for r in rows]
            d, r = min(cand, key=lambda x: x[0])
            p.susceptibility = r["value"]
            p.sources["susceptibility"] += f" (nearest sampled slope {d/1000:.1f} km away)"
    else:
        p.unresolved.append("susceptibility.json is missing, so no published class for this ground")

    comp = C.draft(lat, lon, "other")
    if comp.office:
        p.duty = {"slope": comp.slope_title, "distance_m": comp.distance_m,
                  "office": comp.office, "legal_basis": comp.legal_basis,
                  "local_unit": (comp.admin or {}).get("unit"),
                  "district": (comp.admin or {}).get("district"),
                  "website": (comp.admin or {}).get("website")}
    else:
        p.unresolved.append(comp.refused_because or "no duty holder could be resolved")

    bus = _load("bus-parks.geojson")
    if bus:
        best, bd = None, float("inf")
        for f in bus["features"]:
            c = f["geometry"]["coordinates"]
            d = _m((lat, lon), (c[1], c[0]))
            if d < bd:
                best, bd = f, d
        # A BUS STOP THIRTY KILOMETRES AWAY IS NOT A BUS OPTION. The bus file covers three regions,
        # and for anywhere else the "nearest" is a stop in a region the walker is not in - 28.5 km
        # from Beni to an unnamed stop in Pokhara. Reported as unresolved rather than as a walk.
        if best and bd <= 2000.0:
            p.bus = {"stop": best["properties"].get("n"), "distance_m": round(bd),
                     "region": best["properties"].get("r")}
        else:
            p.unresolved.append(
                f"no bus stop within 2 km (nearest is {bd/1000:.1f} km, in another region's data); "
                f"the bus file covers Kathmandu, Pokhara and the Langtang road only")
    else:
        p.unresolved.append("bus-parks.geojson is missing")

    return p
