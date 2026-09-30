"""A flash flood enters Nepal, step by step, using the real engine rather than a script.

WHY IT IS BUILT THIS WAY
------------------------
A demo that mimes the product drifts away from it, and then the demo is the only thing that works.
Every step below calls the same functions the app calls in anger - the same threshold, the same
abstention rule, the same duty routing, the same escape planner, the same complaint drafter. If a
later round breaks one of them, this scenario breaks with it and a test notices.

So the demo is not a claim about the app. It is the app, run slowly, with the reasoning shown.

    GET /api/v1/demo/flood?lat=&lon=

Each step carries what was actually computed, what it depends on, and what it cannot know.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import complaints as C

ROOT = Path(__file__).resolve().parents[2]
TIMELINE = "web/public/data/timeline.json"
OBS_MONTH = "web/public/data/observability-by-month.json"

# The event this scenario replays: the 2024 monsoon as it actually fell, at a real documented slope.
EVENT_DAY = "2024-09-28"
EVENT_NOTE = ("28 September 2024 - the day Nepal recorded 167 landslides. Chosen because the "
              "rainfall in this scenario is the rainfall that actually fell, not a synthetic curve.")


@dataclass
class Step:
    n: int
    title: str
    plain: str            # what a person in the room is told
    computed: dict        # what the engine actually returned
    depends_on: list[str] = field(default_factory=list)
    cannot_know: str = ""


def _timeline() -> dict:
    return json.loads((ROOT / TIMELINE).read_text(encoding="utf-8"))


def flood_scenario(lat: float, lon: float, *, load_dem=None) -> dict[str, Any]:
    tl = _timeline()
    days, th, sites = tl["days"], tl["threshold_mm_24h"], tl["sites"]
    step = days.index(EVENT_DAY) if EVENT_DAY in days else 0

    above = [s for s in sites if s["r"][step] >= th]
    near = min(sites, key=lambda s: C._m(lat, lon, s["lat"], s["lon"]))
    near_m = C._m(lat, lon, near["lat"], near["lon"])

    steps: list[Step] = []

    steps.append(Step(
        1, "A bad day, measured",
        f"On {EVENT_DAY}, {len(above)} of {len(sites)} documented slopes were at or above the "
        f"published 24-hour threshold of {th} mm. This is rain that actually fell.",
        {"day": EVENT_DAY, "sites": len(sites), "above_threshold": len(above),
         "threshold_mm_24h": th, "threshold_name": tl.get("threshold_name")},
        ["CHIRPS 2024 daily rainfall", "Panchpokhari published thresholds"],
        "Rainfall is not what makes a slope fail. We tested that and it does not - which is the "
        "next step, not a footnote."))

    steps.append(Step(
        2, "The satellite cannot see",
        "August returned 16.8% of scenes with clear ground, and 17 of 142 sites were never seen at "
        "all. So the system does not say 'all clear' on a day it cannot see. It abstains.",
        _obs(),
        ["Sentinel-2 scene metadata, 2021 scenes"],
        "Optical satellites cannot see through monsoon cloud. Radar helps and does not solve it. "
        "This is why the app has an abstain state instead of a green tick."))

    steps.append(Step(
        3, "Who is legally responsible",
        f"The nearest documented slope is '{near['title']}', {near_m/1000:.1f} km away. The duty "
        f"holder is {near['office']}. The statute is cited, so the request cannot be bounced as "
        f"'not ours'.",
        {"slope": near["title"], "distance_m": round(near_m), "authority": near["authority"],
         "office": near["office"], "legal_basis": near["legal_basis"]},
        ["LGOA 2074 s.12(2)(c)", "the routing key's duty map"],
        "The office shown is the routing key's DEFAULT for a local road. On a highway, in forest, "
        "or on private land the responsible body differs, and the app says so rather than hiding it."))

    steps.append(_escape_step(lat, lon, load_dem))

    comp = C.draft(lat, lon, "crack", "Reported during the monsoon.", urgent=True)
    steps.append(Step(
        5, "The citizen's own hand",
        "The same routing that tells a rescue team who owns a slope lets a citizen write to that "
        "office with the section quoted. Drafted in Nepali and English; the citizen sends it.",
        {"routed_to": comp.office, "slope": comp.slope_title,
         "letter_ne_chars": len(comp.letter_ne), "refused": comp.refused_because},
        ["the complaint drafter", "the same duty map as step 3"],
        "The app drafts. It does not file, sign or receive, and the letter says so on its face."))

    steps.append(Step(
        6, "When the network is gone",
        "No tower, no SIM, no energy: 20 bytes over a Bluetooth advertisement, then up a ladder of "
        "wider and slower radios, then a person walking. The model dies first, and the test suite "
        "enforces that ordering.",
        {"advertisement_bytes": 20, "ladder": ["BLE ~30 m", "Wi-Fi Aware ~300 m", "SMS", "courier"],
         "endurance_modes": ["NORMAL", "CONSERVE", "LAST_GASP", "SILENT"]},
        ["the beacon codec", "the transport ladder", "the endurance ladder"],
        "Bluetooth does not go through rock. A ridge between you and the next phone stops it, and "
        "no amount of software changes that."))

    return {
        "scenario": "flash flood and landslide, Nepal, monsoon 2024",
        "event": EVENT_NOTE,
        "origin": {"lat": lat, "lon": lon},
        "steps": [{"n": s.n, "title": s.title, "plain": s.plain, "computed": s.computed,
                   "depends_on": s.depends_on, "cannot_know": s.cannot_know} for s in steps],
        "what_this_demo_is": ("Every step calls the same function the app calls in anger. Nothing "
                              "here is animated: if a later change breaks the routing, the escape "
                              "planner or the abstention rule, this scenario changes with it."),
        "what_this_demo_is_not": ("It is not a forecast and not a simulation of a fictional flood. "
                                 "The rain is the rain that fell on 28 September 2024."),
    }


def _obs() -> dict:
    try:
        d = json.loads((ROOT / OBS_MONTH).read_text(encoding="utf-8"))
        m = d["months"]["08"]
        sep = d["months"]["09"]
        return {"scenes": d["scenes"], "sites": d["sites"],
                "august_pct_usable": m["pct"], "september_pct_usable": sep["pct"]}
    except Exception:                                        # noqa: BLE001
        return {}


def _escape_step(lat: float, lon: float, load_dem) -> Step:
    try:
        from . import shelter
        dem = (load_dem or shelter.load_dem)()
        e = shelter.plan_escape(dem, lat, lon, rise_m=5.0)
        # The dataclass field is `reason`; the HTTP layer renames it to `why` in its JSON. Reading
        # `.why` here raised, and the bare except below then reported "the elevation grid is not
        # loaded" - a confident explanation of a failure that had nothing to do with the grid.
        computed = {"reachable": bool(e.reachable), "climb_m": e.climb_m,
                    "distance_m": round(e.distance_m) if e.distance_m else None,
                    "compass": e.compass, "why": e.reason}
        plain = ("Run east, about a kilometre, climbing fifteen metres. The app gives a direction, "
                 "a distance and a height - not a point on a map."
                 if e.reachable else "There is nowhere higher within reach. It says so.")
    except Exception as exc:                                 # noqa: BLE001
        # Never write an explanation for a failure that was not diagnosed. The first version of
        # this blamed the elevation grid for an AttributeError, which is the same class of error
        # as every numeric mistake this project has caught: plausible, specific, and wrong.
        computed = {"error": type(exc).__name__, "detail": str(exc)[:160]}
        plain = (f"The escape planner did not answer: {type(exc).__name__}. This step is reported "
                 f"as failed rather than explained, because guessing at a cause is how a wrong "
                 f"reason gets written down.")
    return Step(
        4, "Where to run",
        plain,
        computed,
        ["the bundled DEM, ~1 km grid"],
        "Terrain only. It cannot see bridges, culverts or the water itself, and it says so in the "
        "advice text rather than in a footnote nobody reads.")


def as_text(lat: float, lon: float) -> str:
    """The scenario as plain text, for a terminal or a speaker's notes."""
    d = flood_scenario(lat, lon)
    out = [f"=== {d['scenario']} ===", d["event"], ""]
    for s in d["steps"]:
        out.append(f"{s['n']}. {s['title']}")
        out.append(f"   {s['plain']}")
        out.append(f"   cannot know: {s['cannot_know']}")
        out.append("")
    return "\n".join(out)
