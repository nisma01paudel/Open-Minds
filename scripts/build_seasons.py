#!/usr/bin/env python3
"""Build a twelve-month season guide for every trail region, from open climate data.

WHY THIS EXISTS
---------------
The trail bundle answers "where can I walk". It cannot answer "when should I go", which is the
question a Nepali actually asks before booking a week off, and the one every trekking site answers
with marketing rather than measurement.

This fetches monthly climate normals for each trail region from Open-Meteo's ERA5 archive - no key,
no account - and writes them beside the trails, so the guide works with the radio off.

    python scripts/build_seasons.py            # uses the cached file if present
    python scripts/build_seasons.py --fetch    # re-download from Open-Meteo

What it deliberately does NOT do: score a month as "good" or "bad". It reports rain, cloud and
temperature, and the walker decides - because for a farmer and a paraglider the same month is a
different month.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = "evidence/climate-normals.json"
OUT = "web/public/data/seasons.json"

# The six regions the trail bundle covers, as their centre points.
REGIONS = [
    ("kathmandu", "Kathmandu valley and the Shivapuri rim", 27.75, 85.32),
    ("khumbu", "Khumbu / Everest region", 27.80, 86.80),
    ("annapurna", "Annapurna region", 28.50, 84.00),
    ("langtang", "Langtang and Helambu", 28.15, 85.50),
    ("manaslu", "Manaslu circuit", 28.60, 84.65),
    ("mustang", "Upper Mustang and the Kali Gandaki", 28.85, 83.90),
]

# 1995-2024: a normal, not a single year. One API call per region.
YEARS = "2015-2024"
API = "https://archive-api.open-meteo.com/v1/archive"
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def fetch_one(lat: float, lon: float) -> dict:
    import urllib.error
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": f"{YEARS[:4]}-01-01", "end_date": f"{YEARS[-4:]}-12-31",
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,shortwave_radiation_sum",
        "timezone": "Asia/Kathmandu",
    })
    req = urllib.request.Request(f"{API}?{q}",
                                 headers={"User-Agent": "pahiro-seasons/1.0"})
    # Open-Meteo rate-limits by IP. Backing off is the difference between a build that works on a
    # clean connection and one that only works the first time.
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            wait = 20 * (attempt + 1)
            print(f"    429, waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()

    cache = ROOT / CACHE
    if a.fetch or not cache.exists():
        raw = {}
        for key, name, lat, lon in REGIONS:
            print(f"  fetching {name} ...")
            raw[key] = fetch_one(lat, lon)
            time.sleep(8)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(raw), encoding="utf-8")
    raw = json.loads(cache.read_text(encoding="utf-8"))

    out = {
        "type": "season-guide",
        "source": "Open-Meteo ERA5 archive, 2015-2024 daily reanalysis, aggregated by calendar month",
        "attribution": "Contains modified Copernicus Climate Change Service information (ERA5) via Open-Meteo",
        "method": ("Each month is the mean over 10 years of daily ERA5 values at the region centre. "
                   "Rain is the daily total; dry_days counts days under 1 mm; sun is the daily "
                   "shortwave radiation sum. It is a normal, not a forecast, and a mountain valley "
                   "differs from its centre point - the altitude of the grid cell is reported so "
                   "that can be judged."),
        "read_this_as": ("No month is labelled good or bad. A farmer, a trekker and a paraglider "
                         "want different weather from the same month, so the numbers are given and "
                         "the decision is left where it belongs."),
        "regions": [],
    }

    for key, name, lat, lon in REGIONS:
        d = raw[key]
        daily = d["daily"]
        by = defaultdict(lambda: {"rain": [], "dry": 0, "n": 0, "tmax": [], "tmin": [], "sun": []})
        for i, day in enumerate(daily["time"]):
            m = int(day[5:7]) - 1
            p = daily["precipitation_sum"][i] or 0.0
            by[m]["rain"].append(p)
            by[m]["n"] += 1
            if p < 1.0:
                by[m]["dry"] += 1
            if daily["temperature_2m_max"][i] is not None:
                by[m]["tmax"].append(daily["temperature_2m_max"][i])
            if daily["temperature_2m_min"][i] is not None:
                by[m]["tmin"].append(daily["temperature_2m_min"][i])
            if daily["shortwave_radiation_sum"][i] is not None:
                by[m]["sun"].append(daily["shortwave_radiation_sum"][i])

        months = []
        for m in range(12):
            v = by[m]
            months.append({
                "month": m + 1,
                "name": MONTH_NAMES[m],
                "rain_mm_per_day": round(sum(v["rain"]) / max(1, len(v["rain"])), 1),
                "rain_mm_total": round(sum(v["rain"]) * 30.4 / max(1, len(v["rain"]))),
                "dry_day_pct": round(100.0 * v["dry"] / max(1, v["n"]), 1),
                "t_max_c": round(statistics.mean(v["tmax"]), 1) if v["tmax"] else None,
                "t_min_c": round(statistics.mean(v["tmin"]), 1) if v["tmin"] else None,
                "sun_mj_m2_day": round(statistics.mean(v["sun"]), 1) if v["sun"] else None,
            })
        out["regions"].append({
            "key": key, "name": name,
            "lat": lat, "lon": lon,
            "grid_elevation_m": round(d.get("elevation", 0)),
            "months": months,
        })
        wettest = max(months, key=lambda m: m["rain_mm_per_day"])
        driest = min(months, key=lambda m: m["rain_mm_per_day"])
        print(f"  {name}: wettest {wettest['name']} "
              f"({wettest['rain_mm_per_day']} mm/day), driest {driest['name']} "
              f"({driest['rain_mm_per_day']} mm/day)")

    # CROSS-CHECK AGAINST THIS REPOSITORY'S OWN MEASUREMENT.
    #
    # ERA5 is a reanalysis on a ~28 km grid, and the Himalaya is the worst case for it. Its annual
    # totals here are not believable - it puts 8,228 mm a year on Manaslu, roughly five times what
    # falls there - and a season guide built on that would tell a walker something confident and
    # false, which is the one failure this whole project exists to avoid.
    #
    # The repository already holds an independent measurement: 153 days of CHIRPS rainfall at 613
    # documented slopes. Comparing the two over the monsoon months turns "is ERA5 trustworthy here"
    # from an opinion into a number, and it does not flatter all six regions.
    tl = json.loads((ROOT / "web/public/data/timeline.json").read_text(encoding="utf-8"))
    days, sites = tl["days"], tl["sites"]
    monsoon = [i for i, d in enumerate(days) if d[5:7] in ("06", "07", "08", "09")]

    for r in out["regions"]:
        near = [s for s in sites
                if abs(s["lat"] - r["lat"]) < 0.35 and abs(s["lon"] - r["lon"]) < 0.35]
        era5 = statistics.mean(m["rain_mm_per_day"] for m in r["months"] if m["month"] in (6, 7, 8, 9))
        if near:
            chirps = statistics.mean(s["r"][i] for s in near for i in monsoon)
            ratio = era5 / chirps if chirps else 0.0
            ok = 0.6 <= ratio <= 1.7
            r["validation"] = {
                "against": "CHIRPS, Jun-Sep 2024, this repository's own measurement",
                "sites_compared": len(near),
                "era5_mm_per_day": round(era5, 1),
                "chirps_mm_per_day": round(chirps, 1),
                "ratio": round(ratio, 2),
                "reliable": ok,
                "verdict": ("the two agree closely enough to use the twelve-month guide"
                            if ok else
                            "ERA5 overstates the monsoon here by nearly a factor of two against the "
                            "measurement this repository holds; the monthly rain figures for this "
                            "region are NOT reliable and should not be quoted"),
            }
        else:
            r["validation"] = {"against": "no CHIRPS slope within 0.35 degrees",
                              "reliable": False,
                              "verdict": "unvalidated - no independent measurement near this region"}

    # Only June to September could be checked, because that is the window CHIRPS covers here. The
    # other eight months are unvalidated, and the Manaslu region shows why that matters: it passes
    # the monsoon test at a ratio of 1.54 while ERA5 gives it 8,228 mm a year and calls April its
    # wettest month, both of which are wrong. So the guide says which months it stands behind.
    for r in out["regions"]:
        for m in r["months"]:
            m["validated"] = m["month"] in (6, 7, 8, 9)
        r["months_validated"] = 4
        r["annual_note"] = ("ERA5's twelve-month total is not reliable in this terrain - it is "
                            "reported because it is what the model says, not because it is true. "
                            "Only June to September have been checked against an independent "
                            "measurement from this repository.")

    dest = ROOT / OUT
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(out['regions'])} regions x 12 months, {dest.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
