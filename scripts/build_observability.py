#!/usr/bin/env python3
"""Rebuild the observability layer the web app serves, from the committed evaluation report.

WHY THIS EXISTS
---------------
Two files the live demo depends on had no committed generator: observability-sites.json and
observability-by-month.json, the measured-observability layer that is beat 5b of the pitch. The
pipeline that produced them was not kept, so they could not be rebuilt or audited line by line.

The measurement code was never lost - src/pahiro/eval/observability.py - and
reports/observability-monsoon.json still holds the 142 site rows it produced. What was missing was
the last step: turning that report into the two files the browser fetches.

    python scripts/build_observability.py

A FIRST ATTEMPT WAS WRONG, AND THE WAY IT WAS WRONG IS THE POINT
----------------------------------------------------------------
An earlier version of this script filtered the rows to 2024, which produced a by_month block of the
wrong size entirely - 37 months instead of 5, with August and September percentages that would have
silently replaced the two figures the whole demo beat turns on. It ran cleanly. Its output looked
plausible. The only thing that caught it was diffing against the committed file.

The correct aggregation is **all years, by calendar month, restricted to the monsoon months**. That
yields 415 / 518 / 518 / 403 / 167 scenes - 2,021 in total, which is the figure the data file itself
states. It is reproduced here exactly, and the script asserts it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "reports/observability-monsoon.json"
SITES_OUT = "web/public/data/observability-sites.json"
MONTH_OUT = "web/public/data/observability-by-month.json"

MONSOON_MONTHS = ("06", "07", "08", "09", "10")
MONTH_NAMES = {"06": "June", "07": "July", "08": "August", "09": "September", "10": "October"}

SITES_NOTE = ("Measured Sentinel-2 usability at each site, in the month it failed. Every point is a "
              "real measurement over 30 days, not a model.")
# The note is the served one, kept verbatim. It is what a reader sees in the app, and rewriting it
# into my own words would change the product to match my script rather than the other way round.
MONTH_NOTE = ("Measured on {scenes:,} Sentinel-2 scenes across {sites} documented failure sites: "
              "the share of scenes with usable clear ground, by calendar month. This is the "
              "counterweight to the replay - a slope can be loaded and invisible at once.")

EXPECTED_SCENES = 2021      # the file's own stated total; see the module docstring


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=SOURCE)
    a = ap.parse_args()

    report = json.loads((ROOT / a.src).read_text(encoding="utf-8"))
    rows = report.get("rows", [])
    if not rows:
        print(f"{a.src} has no rows; nothing to build")
        return 1

    sites = []
    for r in rows:
        scenes = int(r.get("optical_scenes") or 0)
        usable = int(r.get("optical_usable") or 0)
        sites.append({
            "id": str(r["site_id"]),
            "title": r.get("title", ""),
            "lat": round(float(r["lat"]), 6),
            "lon": round(float(r["lon"]), 6),
            "month": str(r.get("event_date", ""))[:7],
            "scenes": scenes,
            "usable": usable,
            "pct": round(usable / scenes * 100, 1) if scenes else 0.0,
            "radar": int(r.get("radar_passes") or 0),
        })

    # ALL YEARS, by calendar month, monsoon months only. This is the aggregation that reproduces
    # the served figures; filtering by year does not.
    by_month: dict[str, dict] = {}
    for s in sites:
        m = s["month"][5:7]
        if m not in MONSOON_MONTHS:
            continue
        acc = by_month.setdefault(m, {"name": MONTH_NAMES[m], "scenes": 0, "usable": 0})
        acc["scenes"] += s["scenes"]
        acc["usable"] += s["usable"]
    for acc in by_month.values():
        acc["pct"] = round(acc["usable"] / acc["scenes"] * 100, 1) if acc["scenes"] else 0.0

    total_scenes = sum(m["scenes"] for m in by_month.values())
    if total_scenes != EXPECTED_SCENES:
        print(f"REFUSING TO WRITE: the monsoon months total {total_scenes} scenes and the served "
              f"data states {EXPECTED_SCENES}. The source report has changed, or this aggregation "
              f"is wrong again - either way, overwriting the demo's figures is not the fix.")
        return 1

    sites_doc = {"_note": SITES_NOTE, "by_month": by_month, "sites": sites}
    # Shape matters as much as figures: the app indexes `months` by month key, and reads the
    # totals from the top level. The first version emitted a list and dropped `sites`/`scenes`,
    # which would have broken the reader while every number in it was correct.
    month_doc = {
        "_note": MONTH_NOTE.format(scenes=total_scenes, sites=len(sites)),
        "sites": len(sites),
        "scenes": total_scenes,
        "months": {m: {"name": v["name"], "scenes": v["scenes"], "usable": v["usable"],
                       "pct": v["pct"]} for m, v in sorted(by_month.items())},
    }

    for rel, doc in ((SITES_OUT, sites_doc), (MONTH_OUT, month_doc)):
        dest = ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  wrote {rel}")

    print(f"  {len(sites)} sites; monsoon months " +
          ", ".join(f"{v['name']} {v['pct']}%" for _, v in sorted(by_month.items())) +
          f"; {total_scenes:,} scenes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
