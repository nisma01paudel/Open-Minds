"""Ask for a walk in your own words; an open-weight model turns it into a plan.

WHY THE MODEL IS HERE, AND WHAT IT IS NOT ALLOWED TO DO
------------------------------------------------------
The trip planning underneath this - which trails are near you, how far, how much climbing, which
bus and what fare - is deterministic and stays that way. The model's job is the part it is
genuinely better at: reading "I've got a free morning from Kathmandu, nothing too brutal, and I'd
rather not spend more than fifty rupees on the bus" and turning that into a structured request.

So the split is:

    the model   reads the request, and later explains the answer
    the engine  decides which trail, which park, what the fare is

and the model's output is VALIDATED AND CLAMPED before the engine ever sees it. A model that
answers "difficulty: extreme" to a request for an easy walk, or "max_minutes: 100000", gets those
fields dropped rather than obeyed. The failure mode this prevents is a language model quietly
sending somebody up a mountain.

WITHOUT THE MODEL IT STILL WORKS. Keyword parsing handles the same requests less gracefully, and
the planner is the same code either way. A capability that only functions when a 1.1 GB server is
running is not a capability for a phone in a valley.

This is the daily-use half of the system talking to the same open-weight model as the disaster
half: one model, one box, no API key.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import access as access_mod
from . import trails as trails_mod

DIFFICULTIES = ("easy", "moderate", "hard", "severe")

# What the request may ask for in words. Deterministic, and used both as the fallback parser and
# as the allowlist that constrains what the model is permitted to return.
WANTS = {
    "view": ("view", "viewpoint", "summit", "peak", "panorama", "drishti", "himal"),
    "forest": ("forest", "jungle", "trees", "woods", "ban", "shade"),
    "water": ("waterfall", "river", "stream", "spring", "jharana", "kuwa", "pokhari", "lake"),
    "temple": ("temple", "monastery", "gompa", "stupa", "mandir", "shrine", "gumba"),
    "village": ("village", "gaun", "settlement", "town"),
    "nature": ("nature", "wildlife", "birds", "birding", "park"),
}

# Upper bounds. Anything beyond these is a parsing error rather than a request: nobody is asking
# for a 40-hour walk or a 900-rupee bus to a day hike.
MAX_MINUTES_CAP = 12 * 60
MAX_FARE_CAP = 2000.0


@dataclass
class TripQuery:
    """What the walker asked for, after validation."""

    raw: str
    difficulty: str | None = None
    max_minutes: int | None = None
    max_fare_rs: float | None = None
    wants: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)   # model fields refused, and why
    inferred: list[str] = field(default_factory=list)  # fields the model added that the words
                                                       # do not support

    def describe(self) -> str:
        bits = []
        if self.difficulty:
            bits.append(self.difficulty)
        if self.max_minutes:
            bits.append(f"under {self.max_minutes // 60}h{self.max_minutes % 60:02d}")
        if self.max_fare_rs:
            bits.append(f"bus under Rs {self.max_fare_rs:.0f}")
        if self.wants:
            bits.append("wants " + ", ".join(self.wants))
        return "; ".join(bits) or "anything walkable"


def _mentions_money(text: str) -> bool:
    low = text.lower()
    return bool(re.search(r"(rs\.?|npr|rupee|रुपैयाँ|\b\d+\s*(rs|rupees?))", low))


def _keywords(text: str) -> TripQuery:
    """The fallback reader, and the baseline the model has to beat."""
    low = text.lower()
    q = TripQuery(raw=text)

    # difficulty: a negated hard is an easy, and "not too hard" literally contains "hard".
    if re.search(r"\b(not|nothing|no)\s+(too\s+|very\s+)?(hard|steep|tough|difficult|long)\b",
                 low):
        q.difficulty = "easy"
    elif re.search(r"\b(easy|gentle|flat|short|light|simple|family|beginner|sajilo)\b", low):
        q.difficulty = "easy"
    elif re.search(r"\b(hard|steep|tough|strenuous|challenging|difficult|kathin)\b", low):
        q.difficulty = "hard"
    elif re.search(r"\b(moderate|medium|some climbing|middling)\b", low):
        q.difficulty = "moderate"

    m = re.search(r"(\d+(?:\.\d+)?)\s*(hour|hr|h|घण्टा)", low)
    if m:
        q.max_minutes = int(float(m.group(1)) * 60)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(minute|min|मिनेट)", low)
    if m:
        q.max_minutes = int(float(m.group(1)))
    m = re.search(r"(?:rs\.?|npr|rupees?|रुपैयाँ)\s*(\d+(?:\.\d+)?)", low) or \
        re.search(r"(\d+(?:\.\d+)?)\s*(?:rs|rupees?|rupee)", low)
    if m:
        q.max_fare_rs = float(m.group(1))

    for want, words in WANTS.items():
        if any(w in low for w in words):
            q.wants.append(want)
    return q


def _span_query() -> dict:
    """The schema the model must fill. Kept small on purpose - every field is one the engine can
    actually use, and a field nobody consumes is a field that only creates ways to be wrong."""
    return {
        "type": "object",
        "properties": {
            "difficulty": {"type": "string", "enum": ["easy", "moderate", "hard", "severe",
                                                      "any"]},
            "max_minutes": {"type": "integer"},
            "max_fare_rs": {"type": "number"},
            "wants": {"type": "array", "items": {"type": "string",
                                                 "enum": sorted(WANTS.keys())}},
        },
        "required": [],
    }


def _prompt(text: str) -> str:
    return (
        "You read a walker's request and return only a JSON object describing it.\n"
        "Fields: difficulty (easy|moderate|hard|severe|any), max_minutes (integer, the total "
        "walk length they want), max_fare_rs (number, the most they will pay for a bus), "
        "wants (array from: " + ", ".join(sorted(WANTS)) + ").\n"
        "Omit any field the request does not state. Do not guess a difficulty the walker did "
        "not imply. Do not add fields.\n"
        "Request: " + text + "\n"
    )


def parse_request(text: str, backend=None) -> TripQuery:
    """Read a request into a validated query.

    The model's answer is treated as a SUGGESTION and every field is checked before it is used.
    An out-of-range or unparseable field is dropped and recorded in `dropped` rather than obeyed,
    because the cost of obeying a hallucinated "max_minutes" is a person on a mountain at dusk.
    """
    base = _keywords(text)
    if backend is None or not backend.available():
        return base

    # Only failures that MEAN "no usable model" fall back. A bare `except Exception` here hid a
    # TypeError in this very file for a whole round: `_span_query` took an argument it never used
    # and was called with none, so every request raised, every request silently used the keyword
    # reader, and the model was never called once. Broad excepts turn bugs into features.
    try:
        prompt, schema = _prompt(text), _span_query()
    except Exception:
        raise                            # a mistake in this file is not a missing model
    try:
        raw = backend.decide(prompt, schema)
    except Exception:
        # Broad HERE and narrow above, which is the whole point: everything inside `decide` is the
        # backend's business - a dead server, a timeout, a malformed response - and the model is
        # optional. Everything above it is this file's business, and a mistake there must be loud.
        return base                      # the model is a convenience, never a dependency
    if not isinstance(raw, dict):
        return base

    q = TripQuery(raw=text)

    d = raw.get("difficulty")
    if isinstance(d, str) and d.lower() in DIFFICULTIES:
        q.difficulty = d.lower()
    elif isinstance(d, str) and d.lower() != "any":
        q.dropped.append(f"difficulty={d!r}")

    m = raw.get("max_minutes")
    if isinstance(m, (int, float)) and 5 <= m <= MAX_MINUTES_CAP:
        q.max_minutes = int(m)
    elif m is not None:
        q.dropped.append(f"max_minutes={m!r}")

    f = raw.get("max_fare_rs")
    if isinstance(f, (int, float)) and 0 < f <= MAX_FARE_CAP:
        q.max_fare_rs = float(f)
    elif f is not None:
        q.dropped.append(f"max_fare_rs={f!r}")

    w = raw.get("wants")
    if isinstance(w, list):
        q.wants = [x for x in w if isinstance(x, str) and x in WANTS]

    # A CONSTRAINT THE WORDS DO NOT SUPPORT IS NOT A CONSTRAINT.
    #
    # Validation checked VALUES - a difficulty outside the enum, an absurd duration - and never
    # checked whether the request had asked for the field at all. So "a hard 6 hour climb" came back
    # as "hard; under 6h00; bus under Rs 100; wants a view": two constraints the model invented, one
    # of which silently removes every trail with a pricier bus.
    #
    # A hallucinated budget is not a cosmetic error - it narrows the answer using something nobody
    # said. So a money constraint has to be grounded in the text, and one that is not is recorded
    # rather than obeyed.
    if q.max_fare_rs is not None and not _mentions_money(text):
        q.inferred.append(f"bus under Rs {q.max_fare_rs:.0f} (no budget was mentioned)")
        q.max_fare_rs = None
    if q.wants and not any(word in text.lower() for w in q.wants for word in WANTS[w]):
        q.inferred.append("wants " + ", ".join(q.wants) + " (not in the request)")
        q.wants = []

    # Anything the model missed, the deterministic reader may have caught; and anything the
    # model invented is not added to it. The union is taken only where they agree or the keyword
    # reader was silent, so a chatty model cannot widen the request.
    if q.difficulty is None:
        q.difficulty = base.difficulty
    if q.max_minutes is None:
        q.max_minutes = base.max_minutes
    elif base.max_minutes and q.max_minutes and \
            max(q.max_minutes, base.max_minutes) / max(1, min(q.max_minutes, base.max_minutes)) > 2:
        # A DISAGREEMENT THIS LARGE MEANS THE MODEL MISREAD A UNIT.
        #
        # "5 घण्टाको पदयात्रा" - five hours - came back as max_minutes 5. The keyword reader had
        # matched the Devanagari unit and read 300. The model's value was perfectly VALID - positive,
        # under the cap - so every check passed and it won, and a Nepali speaker asking for a
        # five-hour walk was offered nothing, because no trail is five minutes long.
        #
        # When the two readers differ by more than a factor of two, the one that matched an explicit
        # unit is the one to believe.
        q.inferred.append(
            f"duration {q.max_minutes} min (the words say {base.max_minutes} min; the unit was "
            f"matched literally, so the literal reading is used)")
        q.max_minutes = base.max_minutes
    if q.max_fare_rs is None:
        q.max_fare_rs = base.max_fare_rs
    if not q.wants:
        q.wants = base.wants
    return q


@dataclass
class TripOption:
    trail: trails_mod.NearbyTrail
    access: access_mod.Access
    fits: list[str] = field(default_factory=list)
    why_not: list[str] = field(default_factory=list)

    def line(self) -> str:
        t = self.trail
        h, m = divmod(t.walk_minutes, 60)
        out = f"{t.name} — {t.length_m/1000:.1f} km, +{t.climb_m:.0f} m, {h}h{m:02d}"
        if self.access.ok:
            out += f"\n    {self.access.summary()}"
        return out


def plan(text: str, origin: tuple[float, float], *, backend=None, limit: int = 3,
         radius_m: float = 8000.0, dem=None, net=None) -> tuple[TripQuery, list[TripOption]]:
    """From a sentence to a short list of walks that actually satisfy it.

    Returns the query alongside the options so the caller can show the walker what was
    understood - which is the difference between a planner and a slot machine.
    """
    q = parse_request(text, backend)
    net = net if net is not None else trails_mod.load_default()
    olat, olon = origin
    # A 500 m fragment of pavement is not a walk, and the first version of this sorted by
    # shortest-first and returned three of them for every request.
    MIN_TRIP_M = 1500.0
    near = trails_mod.nearby(net, olon, olat, radius_m=radius_m, limit=200, dem=dem,
                             min_length_m=MIN_TRIP_M)

    options: list[TripOption] = []
    for t in near:
        fits, why_not = [], []
        if q.difficulty:
            # AN UNRECORDED DIFFICULTY IS A GAP IN THE MAP, NOT A REASON TO SAY NO.
            #
            # Most Nepali footpaths carry no OSM sac_scale tag, so rejecting them made the
            # planner answer "nothing" to "an easy walk from Kathmandu" while thousands of real
            # easy walks sat in the bundle. It is kept and the gap is stated - the same choice the
            # map layer makes when it draws an untagged trail in the neutral colour.
            if t.difficulty in ("not recorded", "", "unknown"):
                fits.append("difficulty not recorded")
            elif q.difficulty == "easy" and t.difficulty not in ("easy",):
                why_not.append(f"{t.difficulty}, and easy was asked")
            elif q.difficulty == "moderate" and t.difficulty == "severe":
                why_not.append(f"{t.difficulty}, and moderate was asked")
            else:
                fits.append(f"difficulty {t.difficulty}")
        if q.max_minutes and t.walk_minutes > q.max_minutes:
            why_not.append(f"{t.walk_minutes} min, over the {q.max_minutes} asked for")
        else:
            fits.append(f"{t.walk_minutes} min")

        # THE WANTS FIELD HAS TO DO SOMETHING, or it is a field nobody consumes.
        #
        # There is no POI data in the bundle, so a want can only be checked against the trail's
        # own name and its shape. Where it cannot be checked, that is said rather than assumed:
        # "a view" is not something this data can confirm.
        # A WANT RANKS. IT DOES NOT REJECT.
        #
        # The first version screened out anything that did not obviously have a view, and since
        # the coarse terrain grid reports no climb for most valley paths, "easy walk with a view"
        # came back empty. The bundle has no points of interest, so whether a trail has an outlook
        # is NOT knowable from this data - and refusing on a criterion you cannot evaluate is
        # pretending to knowledge. It boosts and it warns; it never says no.
        if q.wants:
            name_low = t.name.lower()
            matched = [w for w in q.wants if any(word in name_low for word in WANTS[w])]
            if matched:
                fits.append("name says " + ", ".join(matched))
            elif any(w in ("view", "forest", "water") for w in q.wants):
                if t.climb_m > 150:
                    fits.append("climbs, so an outlook is likely")
                else:
                    fits.append("cannot check this from the map data")

        start = t.points[0]
        ac = access_mod.to_trailhead(start[1], start[0], olat, olon)
        if q.max_fare_rs and ac.ok and ac.fare_rs and ac.fare_rs > q.max_fare_rs:
            why_not.append(f"bus Rs {ac.fare_rs:.0f}, over the Rs {q.max_fare_rs:.0f} asked for")
        elif ac.ok and ac.fare_rs:
            fits.append(f"bus Rs {ac.fare_rs:.0f}")

        # A trail nobody can get to is not an option. The walk from the last stop is part of the
        # trip, and a 12 km walk after the bus is not a half-day out.
        if ac.ok and (ac.walk_from_park_m or 0) > 6000:
            why_not.append(f"{ac.walk_from_park_m/1000:.0f} km on foot past the last stop")

        options.append(TripOption(trail=t, access=ac, fits=fits, why_not=why_not))

    good = [o for o in options if not o.why_not]

    # Rank by how close a walk is to what was ASKED FOR, not by shortness. Sorting
    # shortest-first answered "a free half day" with a six-minute stroll, because that is what
    # "shortest" means. With no duration requested, a longer walk is a better use of a day out.
    def name_match(o: TripOption) -> int:
        low = o.trail.name.lower()
        return sum(1 for w in q.wants if any(word in low for word in WANTS[w]))

    if q.max_minutes:
        good.sort(key=lambda o: (-name_match(o), abs(q.max_minutes - o.trail.walk_minutes),
                                 -o.trail.length_m))
    else:
        good.sort(key=lambda o: (-name_match(o), -o.trail.length_m))
    return q, good[:limit]
