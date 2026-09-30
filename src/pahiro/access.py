"""Getting to the trailhead: which bus, from where, and roughly what it costs.

THE QUESTION THIS ANSWERS
-------------------------
Every trail app tells you about the mountain. The question that actually stops a walker in
Kathmandu is "which bus do I take, from which park, and what will it cost me" - and if an app
cannot answer that, the trail is a line on a screen rather than a Saturday.

WHAT IS SOURCED AND WHAT IS ESTIMATED
-------------------------------------
Sourced, with a date, because it changes:

    Valley minimum public-transport fare: Rs 24, Bagmati Province adjustment, April 2026.
    Fares are set by the Department of Transport Management (dotm.gov.np) and are revised;
    the figure here is a dated snapshot, not a live feed.

Estimated, and labelled:

    The distance bands above the minimum, and therefore the total. Nepal's fare table is set in
    bands by distance; this uses a linear approximation and will be wrong by a rupee or two on
    a long route in the wrong direction.

NOT KNOWN AT ALL, and said rather than guessed:

    Which specific bus, its schedule, whether it is running today, whether it stops where you
    are, strikes (bandha), and whether a route has changed since this file was written. The
    output names the park and the fare and tells the walker to confirm the route at the park -
    which is what a person does anyway.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .trails import EARTH_R_M, _haversine

# Dated and cited. When DOTM revises fares this number goes stale, and the app says so rather
# than presenting it as current.
FARE_MIN_RS = 24.0
FARE_AS_OF = "April 2026"
FARE_SOURCE = "Department of Transport Management (dotm.gov.np); Bagmati Province adjustment"
FARE_INCLUDED_KM = 5.0          # what the minimum is understood to cover
FARE_PER_KM_RS = 3.0            # linear approximation beyond that

# Fallback parks, used only when the OSM extract is absent. Coordinates are APPROXIMATE - good
# enough to pick the right side of the valley, not good enough to navigate to. The OSM file
# replaces them when present.
# A NAME A PERSON CAN NAVIGATE TO, AND WHY THIS IS TWO PATTERNS RATHER THAN A WORD LIST
#
# OSM bus stops carry three kinds of label: place names ("Battar buspark", "Kutumsang"), generic
# words ("Bus Stop"), and PROSE - "Ticket bus counter", "Bus to Kathmandu". The first is a
# destination. The other two are not: you cannot walk to a counter or to a direction.
#
# The obvious fix is a list of bad words, and a list of bad words is a list of the bad words
# somebody already saw. Two structural tests do better and do not need extending every time a new
# phrasing turns up:
#
#   a ROUTE names a destination:      it contains a preposition of direction - "Bus to Kathmandu"
#   a FACILITY names a function:      it ends in a word for a thing, not a place - "Ticket counter"
#
# Names failing either are described by their coordinates instead, which is worse prose and better
# navigation. This still lets real names through that merely contain such words ("Counter's
# Junction" would pass the first test and is a place), because the tests look at the shape of the
# name rather than at the presence of a word.
GENERIC_NAMES = {"bus stop", "bus park", "bus station", "busstand", "bus stop.", "stop"}

ROUTE_WORDS = (" to ", " from ", " towards ", " via ")
FACILITY_TAILS = ("counter", "office", "ticket", "booking", "enquiry", "inquiry", "shed",
                  "stand", "shelter", "gate")


def is_a_place_name(name: str | None) -> bool:
    """Can somebody be sent to this? Place names yes; routes and facilities no."""
    if not name:
        return False
    low = " " + name.strip().lower() + " "
    if name.strip().lower() in GENERIC_NAMES:
        return False
    if any(w in low for w in ROUTE_WORDS):
        return False
    tail = name.strip().lower().rstrip(".").split()[-1:] or [""]
    if tail[0] in FACILITY_TAILS:
        return False
    return True

FALLBACK_PARKS = [
    ("Ratna Park (Old Bus Park)", 27.7047, 85.3146),
    ("Gongabu (New Bus Park)", 27.7345, 85.3080),
    ("Kalanki", 27.6937, 85.2812),
    ("Koteshwor", 27.6786, 85.3493),
    ("Chabahil", 27.7178, 85.3452),
    ("Balaju", 27.7354, 85.3025),
    ("Lagankhel", 27.6669, 85.3241),
    ("Satdobato", 27.6580, 85.3251),
    ("Jadibuti", 27.6787, 85.3629),
]

BUS_FILE = "web/public/data/bus-parks.geojson"

# WHERE THE BUS DATA STOPS, AND WHY THIS IS A REFUSAL RATHER THAN A NUMBER
#
# The stop dataset covers the Kathmandu and Pokhara valleys. The trail network covers four
# regions of Nepal.
# Those two facts together produced this, for a trailhead at Namche:
#
#     bus to mapped stop at 27.7124, 85.4746 (~122.4 km, about Rs 377),
#     then 122.1 km on foot to the trailhead
#
# Every number in that sentence is fabricated. There is no 122 km valley bus, Rs 377 is a linear
# extrapolation of a fare table that does not extend that far, and telling somebody to walk 122 km
# is worse than telling them nothing. The nearest-stop search cannot know that the reason no stop
# is close is that nobody loaded the stops for that district.
#
# So beyond this radius it says so. A refusal that names the gap is information; a plausible number
# invented to fill it is a lie with units.
MAX_RIDE_M = 60_000.0


@dataclass
class Access:
    """How to get to a trailhead, as far as anyone honest can say offline."""

    ok: bool
    park: str = ""
    park_lat: float | None = None
    park_lon: float | None = None
    ride_m: float | None = None
    fare_rs: float | None = None
    walk_from_park_m: float | None = None
    direct_walk_m: float | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.ok:
            return f"no bus route known: {self.reason}"
        walk = self.walk_from_park_m or 0
        out = (f"bus to {self.park} (~{self.ride_m/1000:.1f} km, "
               f"about Rs {self.fare_rs:.0f})")
        if walk > 200:
            out += f", then {walk/1000:.1f} km on foot to the trailhead"
        else:
            out += ", trailhead at the stop"
        return out


def fare_for(km: float) -> float:
    """An estimate, rounded the way a fare actually is: to the rupee, never below the minimum."""
    if km <= FARE_INCLUDED_KM:
        return FARE_MIN_RS
    raw = FARE_MIN_RS + (km - FARE_INCLUDED_KM) * FARE_PER_KM_RS
    return float(math.ceil(raw))


def load_parks(path: str | Path | None = None) -> list[tuple[str, float, float]]:
    """Real bus stations from OSM when the extract is present, otherwise the fallback list.

    Most mapped stops in the valley are UNNAMED, which is itself information and is passed
    through rather than invented: a stop exists at these coordinates and the map does not say
    what it is called. Naming it would be this program guessing, and a walker sent to the wrong
    "Ratna Park" because we wanted a tidier label is worse than one sent to a point.
    """
    root = Path(__file__).resolve().parents[2]
    p = Path(path) if path else root / BUS_FILE
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out = []
            for f in d.get("features", []):
                geom = f.get("geometry") or {}
                c = geom.get("coordinates")
                if not c:
                    continue
                name = (f.get("properties") or {}).get("n")
                if not is_a_place_name(name):
                    name = None
                if not name:
                    # Describe it by where it is, not by a name we do not have.
                    name = f"mapped stop at {float(c[1]):.4f}, {float(c[0]):.4f}"
                out.append((name, float(c[1]), float(c[0])))
            if out:
                return out
        except (ValueError, KeyError, TypeError):
            pass
    return [(n, lat, lon) for n, lat, lon in FALLBACK_PARKS]


def to_trailhead(trail_lat: float, trail_lon: float, from_lat: float, from_lon: float,
                 parks: list[tuple[str, float, float]] | None = None) -> Access:
    """Which park to leave from, roughly what it costs, and what is left to walk.

    Picks the park that minimises the TOTAL of the ride and the walk at the far end, because the
    nearest park to the trailhead is not always the cheapest way to arrive - a park 2 km further
    but on a direct route beats one that leaves a 5 km walk.
    """
    parks = parks if parks is not None else load_parks()
    if not parks:
        return Access(False, reason="no bus parks are bundled")

    # Before searching: if the trailhead is nowhere near the stop data at all, say that.
    nearest_any = min(_haversine((trail_lon, trail_lat), (plon, plat))
                      for _, plat, plon in parks)
    if nearest_any > MAX_RIDE_M:
        return Access(
            False,
            reason=(f"no bus information for this area. The nearest mapped stop is "
                    f"{nearest_any/1000:.0f} km away, which means the stop data does not cover "
                    f"this region rather than that no bus goes there - the stop list covers the "
                    f"Kathmandu and Pokhara valleys, while the trails cover four regions of Nepal. "
                    f"For some places that gap is the truth: there is no bus to Namche."),
            notes=["Fares and stops are known for the Kathmandu and Pokhara valleys.",
                   "For other regions, ask locally: the district bus park is the usual answer, "
                   "and this app does not know where it is."])

    best = None
    for name, plat, plon in parks:
        ride = _haversine((from_lon, from_lat), (plon, plat))
        walk = _haversine((plon, plat), (trail_lon, trail_lat))
        # The walk after the bus is the part that decides whether this is a real trip, so it is
        # weighted: a metre on foot at the end costs more than a metre on a bus seat.
        score = ride + walk * 1.5
        if best is None or score < best[0]:
            best = (score, name, plat, plon, ride, walk)

    _, name, plat, plon, ride, walk = best
    direct = _haversine((from_lon, from_lat), (trail_lon, trail_lat))

    notes = [
        f"Fare is an estimate from the valley minimum of Rs {FARE_MIN_RS:.0f} "
        f"({FARE_AS_OF}) plus a distance approximation.",
        "Nepal bus routes and fares are set by DOTM and change; confirm the route at the park.",
        "Not known here: schedules, whether the service is running today, bandha, or a route "
        "change since this data was written.",
    ]
    if walk > 3000:
        notes.append(
            f"the nearest park still leaves {walk/1000:.1f} km on foot, so this trailhead is "
            f"not really a bus destination - consider a taxi from the last town, or a different "
            f"trail")
    if ride > MAX_RIDE_M:
        return Access(False, reason=(
            f"the nearest mapped stop is {ride/1000:.0f} km from your start, which is outside the "
            f"area the stop data covers; a fare estimate here would be invented"))

    if direct < ride:
        notes.append("your starting point is closer to the trailhead than any bus park is, so "
                     "the bus is not obviously worth it")

    return Access(True, park=name, park_lat=plat, park_lon=plon, ride_m=ride,
                  fare_rs=fare_for(ride / 1000.0), walk_from_park_m=walk, direct_walk_m=direct,
                  notes=notes)
