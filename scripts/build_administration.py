#!/usr/bin/env python3
"""Build Nepal's administrative gazetteer, so a complaint can name the office that exists.

WHY THIS EXISTS
---------------
The complaint drafter used to say "Ward Committee under the Ward Chair" - a true description of the
duty and a useless address. A letter nobody can deliver is not a complaint.

Nepal has 77 districts and 753 local units, each with a name, a Nepali name, a district, a province
and an OFFICIAL WEBSITE. That is enough to turn a generic duty into a deliverable address:

    Jaimini Municipality, Myagdi district, Gandaki Province  ->  its own gov.np site

Source: https://github.com/rgtstha/NEPAL-QUEST-DATA (open data, community maintained). Fetched once,
cached in evidence/, and compiled here into one offline file.

    python scripts/build_administration.py

No network: it reads the cache.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "web/public/data/administration.json"

SOURCES = {
    "district": "evidence/admin-districts.json",
    "municipality": "evidence/admin-municipalities.json",
    "rural_municipality": "evidence/admin-rural_municipalities.json",
    "metropolitan": "evidence/admin-metropolitan_cities.json",
    "sub_metropolitan": "evidence/admin-sub_metropolitan_cities.json",
}


def norm(s: str) -> str:
    """Fold a name to something matchable across spelling, case and stray punctuation."""
    s = unicodedata.normalize("NFKD", s or "").lower()
    for drop in (" municipality", " rural municipality", " sub-metropolitan city",
                 " metropolitan city", " nagarpalika", " gaunpalika", ".", ",", "'", "-"):
        s = s.replace(drop, " ")
    return " ".join(s.split())


def main() -> int:
    units, districts = [], {}

    for rec in json.loads((ROOT / SOURCES["district"]).read_text(encoding="utf-8")):
        districts[norm(rec["districts"])] = {
            "district": rec["districts"], "district_ne": rec.get("nepali"),
            "province_ne": rec.get("province"), "headquarters": rec.get("headquarters"),
            "population": rec.get("population20117"), "area_km2": rec.get("areaKm2"),
            "website": rec.get("officialWebsites"),
        }

    for kind, rel in SOURCES.items():
        if kind == "district":
            continue
        for rec in json.loads((ROOT / rel).read_text(encoding="utf-8")):
            name = rec.get("name")
            if not name:
                continue
            units.append({
                "name": name, "name_ne": rec.get("nepali"), "kind": kind,
                "district": rec.get("district"), "province_ne": rec.get("province"),
                "population": rec.get("population"), "area_km2": rec.get("area"),
                "website": rec.get("website"),
            })

    out = {
        "source": "https://github.com/rgtstha/NEPAL-QUEST-DATA (community open data)",
        "note": ("Every local unit and district in Nepal with its official website, so a complaint "
                 "can be addressed to an office that exists and can be looked up. Names contain "
                 "Nepali as well as English, because a letter written in Nepali should name the "
                 "place in Nepali."),
        "districts": districts,
        "units": units,
        "counts": {"districts": len(districts), "units": len(units),
                   "with_website": sum(1 for u in units if u.get("website"))},
    }
    dest = ROOT / OUT
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {out['counts']}, {dest.stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
