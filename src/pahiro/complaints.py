"""Turn a citizen's report into a complaint the right office is legally obliged to answer.

WHY THIS IS NOT A CONTACT FORM
------------------------------
Every complaint portal in Nepal routes to a municipality, and a municipality can say "not ours" and
be finished with it. This one resolves the *specific* office that carries the statutory duty for the
ground being reported, and puts the section in the letter. The complaint is addressed to a named
duty-holder under a cited provision, so ignoring it is a decision somebody has to make on paper.

That is the whole dispatch thesis turned around: the same routing that tells a rescue team who owns a
slope tells a citizen who to write to.

WHAT IT DOES NOT DO
-------------------
It does not file anything, sign anything, or claim to have been received. It drafts. The citizen
reads it, sends it, and keeps the receipt. Nothing here has legal effect on its own, and the letter
says so on its face.
"""
from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TIMELINE = "web/public/data/timeline.json"

# How far from a documented slope a report can be and still be routed. Beyond this the office is a
# guess, and a letter to the wrong office is worse than no letter - it teaches the citizen that
# complaining does not work.
MAX_ROUTE_M = 3000.0
ADMIN = "web/public/data/administration.json"

CATEGORIES = {
    "crack": ("A crack has opened", "जमिन चिरा परेको"),
    "slump": ("The ground is moving", "जमिन सर्दै गरेको"),
    "drain": ("Water is not draining", "पानी निकास नभएको"),
    "cut": ("A slope was cut and left unstable", "काटिएको र अस्थिर ढलान"),
    "wall": ("A retaining wall is failing", "संरक्षण पर्खाल भत्कँदै"),
    "other": ("Something else", "अन्य"),
}


def _m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(a))


@dataclass
class Complaint:
    urgent: bool
    lat: float
    lon: float
    category: str
    slope_id: str | None = None
    slope_title: str | None = None
    distance_m: float | None = None
    authority: str | None = None
    office: str | None = None
    legal_basis: str | None = None
    admin: dict | None = None
    refused_because: str | None = None
    letter_ne: str = ""
    letter_en: str = ""
    caveats: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "", [])}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    for drop in (" municipality", " rural municipality", " sub-metropolitan city",
                 " metropolitan city", " nagarpalika", " gaunpalika", ".", ",", "'", "-"):
        s = s.replace(drop, " ")
    return " ".join(s.split())


_ADMIN_CACHE: dict | None = None


def resolve_admin(slope_title: str) -> dict | None:
    """Name the local unit a documented slope sits in, and its official website.

    "Ward Committee under the Ward Chair" is a true description of the duty and a useless address.
    Nepal's 753 local units each have a name, a district and an official gov.np site, and the slope
    titles already carry the unit - "Landslide at Jaimini Municipality-10" - so the letter can name
    Jaimini, Baglung, and the page that office actually answers.
    """
    global _ADMIN_CACHE
    if _ADMIN_CACHE is None:
        try:
            _ADMIN_CACHE = json.loads((ROOT / ADMIN).read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            _ADMIN_CACHE = {"units": [], "districts": {}}
    title = _norm(slope_title)
    if not title:
        return None
    units = sorted(_ADMIN_CACHE.get("units", []), key=lambda u: -len(_norm(u["name"])))
    for u in units:
        n = _norm(u["name"])
        if n and n in title:
            d = _ADMIN_CACHE.get("districts", {}).get(_norm(u.get("district") or ""), {})
            return {"unit": u["name"], "unit_ne": u.get("name_ne"), "kind": u.get("kind"),
                    "district": u.get("district") or d.get("district"),
                    "district_ne": d.get("district_ne"), "headquarters": d.get("headquarters"),
                    "province_ne": u.get("province_ne") or d.get("province_ne"),
                    "website": u.get("website") or d.get("website"),
                    "population": u.get("population") or d.get("population")}
    return None


def _load() -> list[dict]:
    return json.loads((ROOT / TIMELINE).read_text(encoding="utf-8"))["sites"]


def nearest(lat: float, lon: float, sites: list[dict] | None = None) -> tuple[dict | None, float]:
    sites = sites if sites is not None else _load()
    best, bd = None, float("inf")
    for s in sites:
        d = _m(lat, lon, s["lat"], s["lon"])
        if d < bd:
            best, bd = s, d
    return best, bd


def _letter_ne(s: dict, c: Complaint, note: str) -> str:
    head = "अत्यावश्यक" if c.urgent else "जरुरी"
    return (
        f"विषय: {c.category} — {s['title']} को जोखिमबारे {head} जानकारी\n\n"
        f"श्रीमान्/श्रीमती प्रमुखज्यू,\n\n"
        f"मैले {s['lat']:.5f}, {s['lon']:.5f} निर्देशांकको ढलानमा "
        f"{CATEGORIES[c.category][1]} देखेको छु। {note}\n\n"
        + (f"यो स्थान {c.admin['unit']}"
           + (f" ({c.admin['unit_ne']})" if c.admin.get('unit_ne') else "")
           + (f", {c.admin['district']} जिल्ला" if c.admin.get('district') else "")
           + f" भित्र पर्छ।\n\n" if c.admin else "")
        + f"स्थानीय सरकार सञ्चालन ऐन, २०७४ को धारा १२(२)(ग) बमोजिम सडकसँग जोडिएको पहिरो "
          f"हटाउने दायित्व {s['office']} को हो।\n\n"
        f"कृपया यो स्थानको निरीक्षण गरी आवश्यक व्यवस्था मिलाउनुहुन अनुरोध गर्दछु। "
        f"यो पत्र स्वचालित रूपमा तयार भएको हो र यसले कुनै कानुनी कारबाही सुरु गर्दैन।\n\n"
        f"भवदीय,\n[तपाईंको नाम]\n[सम्पर्क नम्बर]\n[मिति]\n"
    )


def _letter_en(s: dict, c: Complaint, note: str) -> str:
    head = "URGENT" if c.urgent else "Report"
    return (
        f"Subject: {head} — {CATEGORIES[c.category][0]} at {s['title']}\n\n"
        f"Dear Sir/Madam,\n\n"
        f"I am reporting {CATEGORIES[c.category][0].lower()} at {s['lat']:.5f}, {s['lon']:.5f}. "
        f"{note}\n\n"
        + (f"This location falls in {c.admin['unit']}, "
           f"{c.admin.get('district') or ''} district"
           f"{', ' + c.admin['province_ne'] if c.admin.get('province_ne') else ''}"
           f" ({c.admin['website']}).\n\n" if c.admin else "")
        + f"Under the Local Government Operation Act 2074, s.12(2)(c), the duty to remove landslides "
        f"affecting roads rests with {s['office']}.\n\n"
        f"I request an inspection and appropriate action. This letter was drafted automatically and "
        f"does not by itself start any legal proceeding.\n\n"
        f"Yours faithfully,\n[Your name]\n[Contact number]\n[Date]\n"
    )


def draft(lat: float, lon: float, category: str = "other", note: str = "",
          urgent: bool = False, sites: list[dict] | None = None) -> Complaint:
    """Draft a complaint addressed to the office that holds the statutory duty for this ground."""
    if category not in CATEGORIES:
        category = "other"
    c = Complaint(urgent=urgent, lat=lat, lon=lon, category=category)
    s, d = nearest(lat, lon, sites)
    if s is None or d > MAX_ROUTE_M:
        c.refused_because = (
            f"no documented landslide slope within {MAX_ROUTE_M/1000:.0f} km of this point "
            f"(nearest is {d/1000:.1f} km away)" if s else "no slope data loaded")
        c.caveats.append(
            "A letter to the wrong office teaches the citizen that complaining does not work, so "
            "this refuses rather than guesses. Choose the nearest documented slope, or send it to "
            "the ward office directly.")
        return c

    c.slope_id, c.slope_title, c.distance_m = s["id"], s["title"], round(d)
    c.authority, c.office, c.legal_basis = s["authority"], s["office"], s["legal_basis"]
    c.admin = resolve_admin(s["title"])
    c.letter_ne = _letter_ne(s, c, note)
    c.letter_en = _letter_en(s, c, note)
    c.caveats = [
        "The office shown is the routing key's DEFAULT duty holder for a local road, not a "
        "per-parcel legal determination. Where the slope is on a highway, a forest, or private "
        "land the responsible body differs.",
        ("The local unit was matched from the slope's own title against Nepal's 753 unit "
         "gazetteer, so it is the unit the record names and not a survey of the ground."
         if c.admin else
         "No local unit could be matched from the slope's title, so only the generic duty holder "
         "is named. Address the letter to the ward office directly."),
        "The nearest documented slope may not be the slope you are standing on. Check the "
        "coordinates in the letter before sending it.",
        "Nothing here has been filed, signed, or received. Send it yourself and keep the receipt.",
    ]
    return c
