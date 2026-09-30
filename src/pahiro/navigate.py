"""Spoken guidance: "go up from here", in Nepali, while the water is coming.

WHY THIS EXISTS
---------------
`shelter.py` answers *which way and how high* once. That is the briefing. It is not
navigation, and the difference is the whole reason this module exists: a person running in the
dark does not re-read a paragraph, and cannot hold a bearing, a distance and a target elevation
in their head while terrified. What they can follow is one short instruction, repeated, that
changes as they move.

So this turns the plan into a sequence of short imperative steps, and - the part that matters -
into a *live* instruction that updates from the phone's own position:

    माथि जानुहोस्              go up
    अझ माथि जानुहोस्           keep going up
    तल जानुभयो — फर्कनुहोस्     you are going down - turn back
    तपाईं सुरक्षित उचाइमा पुग्नुभयो   you have reached safe height

WHY NEPALI FIRST, AND WHY IT IS SPOKEN
--------------------------------------
The instruction has to arrive in the language the person is thinking in, at the moment they
are not able to translate. Nepali is the primary string here and English is the fallback, which
is the reverse of how the rest of this codebase is written - deliberately, because the reader
of this particular output is a person on a hillside and not a developer.

Speaking it matters for the same reason: their hands are busy and it is dark. The field client
uses the browser's own `speechSynthesis` with `ne-NP`, which means **the voice works with no
network and no API key** - a hosted text-to-speech call is exactly the dependency that fails in
the situation this is built for. Where the handset has no Nepali voice installed, the client
falls back to showing the text large and says so, rather than reading Nepali in an English
voice, which is worse than silence.

WHAT THIS IS NOT
----------------
It is not turn-by-turn street routing. There are no roads in the data - the DEM is a surface,
about a kilometre a cell - so this cannot say "take the second left". It says *up*, *that way*,
*how much further*, and *you have gone the wrong way*, which is what the terrain can honestly
support and what a person in a flood actually needs to hear.

The ascent check is deliberately relative: `update` compares the current elevation with where
the person started, not with the target, because a person who has climbed 20 m and has 200 m
still to go must not be told they are failing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .shelter import (CLIMB_PENALTY, Escape, _COMPASS_NE, compass_index)

# One instruction, in both languages, with the numbers that produced it.
@dataclass(frozen=True)
class Step:
    kind: str            # "start" | "climb" | "hold" | "wrong_way" | "arrived" | "unreachable"
    ne: str              # the spoken line, Nepali first
    en: str
    remaining_m: float | None = None
    elevation_now_m: float | None = None

    def spoken(self, lang: str = "ne") -> str:
        return self.ne if lang == "ne" else self.en


# Short, imperative, and correct. Kept as a table so a native speaker can review the whole
# spoken vocabulary of the app in one place rather than hunting strings through the codebase.
PHRASES = {
    "go_up": "\u092e\u093e\u0925\u093f \u091c\u093e\u0928\u0941\u0939\u094b\u0938\u094d",
    "keep_up": ("\u0905\u091d \u092e\u093e\u0925\u093f \u091c\u093e\u0928\u0941\u0939\u094b\u0938\u094d"),
    "away_water": ("\u092a\u093e\u0928\u0940\u092c\u093e\u091f \u091f\u093e\u0922\u093e "
                   "\u091c\u093e\u0928\u0941\u0939\u094b\u0938\u094d"),
    "wrong_way": ("\u0924\u0932 \u091c\u093e\u0928\u0941\u092d\u092f\u094b \u2014 "
                  "\u092b\u0930\u094d\u0915\u0928\u0941\u0939\u094b\u0938\u094d"),
    "arrived": ("\u0924\u092a\u093e\u0908\u0902 \u0938\u0941\u0930\u0915\u094d\u0937\u093f\u0924 "
                "\u0909\u091a\u093e\u0907\u092e\u093e \u092a\u0941\u0917\u094d\u0928\u0941\u092d\u092f\u094b"),
    "no_ground": ("\u0928\u091c\u093f\u0915\u0948 \u0938\u0941\u0930\u0915\u094d\u0937\u093f\u0924 "
                  "\u0909\u091a\u093e\u0907 \u091b\u0948\u0928"),
    "tall_building": ("\u0905\u0917\u094d\u0932\u094b \u092c\u0939\u0941\u0924\u0932\u0947 "
                      "\u092d\u0935\u0928\u092e\u093e \u091c\u093e\u0928\u0941\u0939\u094b\u0938\u094d"),
    "top_floor": ("\u0938\u0915\u094d\u0926\u094b \u092e\u093e\u0925\u093f\u0932\u094d\u0932\u094b "
                  "\u0924\u0932\u094d\u0932\u093e\u092e\u093e \u091c\u093e\u0928\u0941\u0939\u094b\u0938\u094d"),
    "dont_run": ("\u0926\u094c\u0921\u0928 \u0928\u0916\u094b\u091c\u094d\u0928\u0941\u0939\u094b\u0938\u094d"),
    "hurry_careful": ("\u091b\u093f\u091f\u094b \u0924\u0930 \u0938\u093e\u0935\u0927\u093e\u0928"),
}

EN = {
    "go_up": "Go up",
    "keep_up": "Keep going up",
    "away_water": "Get away from the water",
    "wrong_way": "You are going down - turn back",
    "arrived": "You have reached safe height",
    "no_ground": "There is no safe high ground nearby",
    "tall_building": "Get to a tall building",
    "top_floor": "Go to the highest floor you can reach",
    "dont_run": "Do not run for it",
    "hurry_careful": "Quickly, but carefully",
}


def _metres(step_lat: float, step_lon: float, lat: float, lon: float) -> float:
    dy = (lat - step_lat) * 111_320.0
    dx = (lon - step_lon) * 111_320.0 * math.cos(math.radians(lat))
    return math.hypot(dy, dx)


def steps(e: Escape, *, limit: int = 5) -> list[Step]:
    """The briefing, broken into short spoken instructions, most urgent first.

    Ordered so that the first line is the one to say even if nothing else is heard.
    """
    out: list[Step] = []

    if not e.reachable:
        out.append(Step("unreachable", PHRASES["no_ground"], EN["no_ground"]))
        out.append(Step("unreachable", PHRASES["dont_run"], EN["dont_run"]))
        out.append(Step("unreachable", PHRASES["tall_building"], EN["tall_building"]))
        out.append(Step("unreachable", PHRASES["top_floor"], EN["top_floor"]))
        return out[:limit]

    direction_ne = _COMPASS_NE[compass_index(e.bearing_deg)]
    direction_en = e.compass
    out.append(Step("climb", PHRASES["away_water"], EN["away_water"]))
    out.append(Step(
        "climb",
        f"{direction_ne} \u0924\u0930\u094d\u092b \u091c\u093e\u0928\u0941\u0939\u094b\u0938\u094d",
        f"Head {direction_en}",
        remaining_m=e.distance_m,
        elevation_now_m=e.from_elevation_m,
    ))
    out.append(Step(
        "climb",
        f"{PHRASES['keep_up']} \u2014 \u0915\u0930\u093f\u092c {e.distance_m:.0f} "
        f"\u092e\u093f\u091f\u0930",
        f"{EN['keep_up']} - about {e.distance_m:.0f} m",
        remaining_m=e.distance_m,
    ))
    out.append(Step(
        "climb",
        f"\u0915\u092e\u094d\u0924\u0940\u092e\u093e {e.target_elevation_m:.0f} "
        f"\u092e\u093f\u091f\u0930 \u0909\u091a\u093e\u0907\u092e\u093e \u092a\u0941\u0917\u094d\u0928\u0941\u0939\u094b\u0938\u094d",
        f"Reach at least {e.target_elevation_m:.0f} m elevation",
    ))
    out.append(Step("climb", PHRASES["hurry_careful"], EN["hurry_careful"]))
    return out[:limit]


def update(e: Escape, dem, lat: float, lon: float, *, started_elevation_m: float | None = None,
           last_elevation_m: float | None = None, arrived_slack_m: float = 1.0) -> Step:
    """The one line to say right now, from where the phone says the person is.

    `started_elevation_m` is where they began, so the climb check is relative to their own
    progress rather than to the summit: someone who has gained 20 m of a 200 m climb is doing
    the right thing and must be told so.
    """
    now = float(dem.elevation_at(lat, lon))
    start = now if started_elevation_m is None else started_elevation_m

    if not e.reachable:
        return Step("unreachable", PHRASES["tall_building"], EN["tall_building"],
                    elevation_now_m=now)

    if e.target_elevation_m is not None and now >= e.target_elevation_m - arrived_slack_m:
        return Step("arrived", PHRASES["arrived"], EN["arrived"],
                    elevation_now_m=now, remaining_m=0.0)

    remaining = _metres(e.target_lat, e.target_lon, lat, lon)

    # Losing height is the dangerous direction, and it is the one a panicking person does
    # without noticing, because downhill is easier and faster.
    reference = start if last_elevation_m is None else last_elevation_m
    if now < reference - 2.0:
        return Step(
            "wrong_way",
            f"{PHRASES['wrong_way']} \u2014 {PHRASES['go_up']}",
            f"{EN['wrong_way']} - go up",
            remaining_m=remaining, elevation_now_m=now,
        )

    if now > reference + 1.0:
        return Step(
            "climb",
            f"{PHRASES['keep_up']} \u2014 \u0915\u0930\u093f\u092c {remaining:.0f} "
            f"\u092e\u093f\u091f\u0930",
            f"{EN['keep_up']} - about {remaining:.0f} m to go",
            remaining_m=remaining, elevation_now_m=now,
        )

    return Step(
        "hold",
        f"{PHRASES['go_up']} \u2014 {remaining:.0f} \u092e\u093f\u091f\u0930",
        f"{EN['go_up']} - {remaining:.0f} m",
        remaining_m=remaining, elevation_now_m=now,
    )


def plan_summary(e: Escape, *, steps_limit: int = 5) -> dict:
    """The whole navigator as one serialisable object, for the API and the client."""
    s = steps(e, limit=steps_limit)
    return {
        "reachable": e.reachable,
        "compass": e.compass,
        "compass_ne": (_COMPASS_NE[compass_index(e.bearing_deg)]
                       if e.reachable and e.bearing_deg is not None else None),
        "distance_m": None if e.distance_m is None else round(e.distance_m, 1),
        "climb_m": None if e.climb_m is None else round(e.climb_m, 1),
        "walk_minutes": None if e.walk_minutes is None else round(e.walk_minutes, 1),
        "target_elevation_m": (None if e.target_elevation_m is None
                               else round(e.target_elevation_m, 1)),
        "from_elevation_m": round(e.from_elevation_m, 1),
        "spoken": {
            "heading_ne": s[1].ne if len(s) > 1 else (s[0].ne if s else ""),
            "heading_en": s[1].en if len(s) > 1 else (s[0].en if s else ""),
            "first_ne": s[0].ne if s else "",
            "first_en": s[0].en if s else "",
        },
        "steps": [{"kind": x.kind, "ne": x.ne, "en": x.en,
                   "remaining_m": None if x.remaining_m is None else round(x.remaining_m, 1),
                   "elevation_now_m": (None if x.elevation_now_m is None
                                       else round(x.elevation_now_m, 1))}
                  for x in s],
        "climb_penalty_note": ("walk time treats one metre of climbing as "
                               f"{CLIMB_PENALTY:.0f} m of walking"),
    }
