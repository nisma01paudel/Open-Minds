#!/usr/bin/env python3
"""Reproduce the Pahiro data-feasibility finding, using only the standard library.

Answers two questions with live data, no account and no API key:
  1. Can we read free satellite/rainfall data for a Nepal AOI?
  2. How many cloud-free optical scenes does a Nepal slope actually get, by month,
     compared with all-weather radar? (This is the evidence behind contribution C.)

Usage:
    python3 scripts/verify_data_access.py                    # Dhading/Jhyaple Khola, 2019-2025
    python3 scripts/verify_data_access.py --out evidence/monsoon-gap.csv
"""
from __future__ import annotations
import argparse, collections, json, sys, urllib.request

STAC = "https://earth-search.aws.element84.com/v1/search"
DEFAULT_BBOX = [84.95, 27.75, 85.10, 27.90]   # Dhading / Jhyaple Khola corridor, Nepal
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


def search(collection: str, start: str, end: str, bbox, cloud_lt: int | None = None, limit: int = 500):
    body = {"collections": [collection], "bbox": list(bbox),
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": limit}
    if cloud_lt is not None:
        body["query"] = {"eo:cloud_cover": {"lt": cloud_lt}}
    req = urllib.request.Request(STAC, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("features", [])


def monthly(features):
    return collections.Counter(f["properties"]["datetime"][5:7] for f in features)


def row(label, counts):
    return f"{label:<10} " + " ".join(f"{counts.get(f'{i:02d}', 0):>4}" for i in range(1, 13))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", type=float, nargs=4, default=DEFAULT_BBOX)
    ap.add_argument("--from", dest="start", default="2019")
    ap.add_argument("--to", dest="end", default="2025")
    ap.add_argument("--cloud", type=int, default=20, help="max cloud cover %% for optical")
    ap.add_argument("--out", help="write the table to this CSV path")
    a = ap.parse_args()
    years = list(range(int(a.start), int(a.end) + 1))

    print(f"AOI bbox           : {a.bbox}")
    print(f"Optical cloud limit: < {a.cloud}%\n")

    optical, optical_tot = {}, collections.Counter()
    for y in years:
        fs = search("sentinel-2-l2a", f"{y}-01-01", f"{y}-12-31", a.bbox, cloud_lt=a.cloud)
        optical[y] = monthly(fs)
        optical_tot.update(optical[y])

    print("SENTINEL-2 L2A (optical) usable scenes by month")
    print(f"{'year':<10} " + " ".join(f"{m:>4}" for m in MONTHS))
    for y in years:
        print(row(y, optical[y]))
    print(row("TOTAL", optical_tot))

    radar, radar_tot = {}, collections.Counter()
    years_r = years[-3:]
    for y in years_r:
        fs = search("sentinel-1-grd", f"{y}-01-01", f"{y}-12-31", a.bbox)
        radar[y] = monthly(fs)
        radar_tot.update(radar[y])

    print("\nSENTINEL-1 GRD (all-weather radar) scenes by month")
    print(f"{'year':<10} " + " ".join(f"{m:>4}" for m in MONTHS))
    for y in years_r:
        print(row(y, radar[y]))
    print(row("TOTAL", radar_tot))

    monsoon = sum(optical_tot.get(f"{i:02d}", 0) for i in (7, 8))
    print(f"\nFINDING: {monsoon} usable optical scenes in July+August across "
          f"{len(years)} years, versus {sum(radar_tot.get(f'{i:02d}',0) for i in (7,8))} radar scenes "
          f"in the same two months across the last {len(years_r)} years.")
    print("=> Optical-only monitoring is blind in the peak landslide months; radar is the fallback.")

    if a.out:
        with open(a.out, "w") as fh:
            fh.write("source,year," + ",".join(MONTHS) + "\n")
            for y in years:
                fh.write(f"sentinel-2-l2a_cloud_lt{a.cloud},{y}," +
                         ",".join(str(optical[y].get(f"{i:02d}", 0)) for i in range(1, 13)) + "\n")
            fh.write("sentinel-2-l2a_cloud_lt%d,TOTAL," % a.cloud +
                     ",".join(str(optical_tot.get(f"{i:02d}", 0)) for i in range(1, 13)) + "\n")
            for y in years_r:
                fh.write(f"sentinel-1-grd,{y}," +
                         ",".join(str(radar[y].get(f"{i:02d}", 0)) for i in range(1, 13)) + "\n")
            fh.write("sentinel-1-grd,TOTAL," +
                     ",".join(str(radar_tot.get(f"{i:02d}", 0)) for i in range(1, 13)) + "\n")
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
