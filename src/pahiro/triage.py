"""Which call to answer first, and the reason for every point of the decision.

WHY THIS EXISTS
---------------
A board of distress calls is not a plan. A coordinator with a dozen rows has to decide who to
send where first, and the honest answer is that the *order* is a judgement. This makes that
judgement explicit, consistent and arguable. It is the one thing the field API cannot do for
itself: `FieldStore.trapped()` orders rows, but ordering by one key at a time is not triage.

WHY IT IS NOT A MODEL
---------------------
Deliberately deterministic, and that is the design rather than a limitation. A rescue
coordinator must be able to ask "why is this one first" and get an answer they can disagree
with. A language model's ranking cannot be audited in the minute available, cannot be
reproduced in a review, and would be the only part of this system that nobody could check. Every
point below traces to a named factor with the number that produced it, so two people reading the
same board reach the same order and can argue about the *weights* instead of the output.

WHAT IT IS NOT
--------------
It is **not** a claim about who deserves rescue. It ranks *search order* from a radio and a
timestamp, and it knows nothing about the person. A report it ranks low is not a report to
ignore, and the top of the list is not a promise. This is stated in the output and on the panel,
because a ranking of human beings that is not labelled as a heuristic will be read as one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Weights. Chosen so that the *ordering* is defensible and the arithmetic is easy to argue with
# in a corridor: they sum to 100, so a score reads directly as a percentage of the maximum.
W_PEOPLE = 35.0        # how many people are calling
W_POSITION = 25.0      # split between having a fix and how tight it is
W_RECENCY = 20.0       # a call from ten minutes ago is actionable, one from ten hours is history
W_BATTERY = 20.0       # a dying handset is the last chance to hear from it

# People are capped here for scoring, so a report claiming 40 people cannot drown out the rest.
PEOPLE_CAP = 10

# Unknown people is scored as this. Conservative in both directions: not zero (which would bury
# a genuine call) and not high (which would let a blank field outrank a stated group).
UNKNOWN_PEOPLE_EQUIVALENT = 2

# A radius at or below this is as good as a point; above the far bound it is a sweep.
RADIUS_GOOD_M = 15.0
RADIUS_POOR_M = 900.0

# Battery at or below this is the last chance to hear from the handset.
LOW_BATTERY_PCT = 15

# A healthy handset earns this fraction of the battery weight, not all of it.
#
# The first version gave a full battery the whole weight and a dying one the whole weight too, so
# the two scored IDENTICALLY - the urgency reward for a dying phone exactly cancelled the health
# credit for a full one, and the factor could not tell "about to die" from "fine". It is one axis,
# not two: the battery factor measures **urgency from the handset's power state**. A full battery
# is not urgent and earns partial credit; a dying one is maximally urgent and earns all of it.
BATTERY_HEALTHY_FRACTION = 0.6

# A call older than this has stopped being a lead and become a record.
STALE_AFTER_HOURS = 24.0


@dataclass
class Reason:
    factor: str
    points: float
    detail: str


@dataclass
class Triaged:
    device_id: str
    score: float
    band: str
    people: int | None
    reasons: list[Reason] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "score": round(self.score, 1),
            "band": self.band,
            "people": self.people,
            "reasons": [{"factor": r.factor, "points": round(r.points, 1), "detail": r.detail}
                        for r in self.reasons],
            "warnings": self.warnings,
        }


def _band(score: float) -> str:
    if score >= 70:
        return "critical"
    if score >= 45:
        return "urgent"
    return "routine"


def _hours_since(created_at: str | None, now: datetime) -> float | None:
    if not created_at:
        return None
    try:
        stamp = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (now - stamp).total_seconds() / 3600.0


def _position_factor(row: dict, reasons: list[Reason], warnings: list[str]) -> float:
    """A coordinate can be dispatched to. A report without one is a different task.

    Two separate reasons rather than one: *having* a fix and *how tight* it is are different
    facts, and a coordinator may trust one and not the other. Both always emit a reason, so the
    points on the panel add up to the score - a factor that silently contributes is exactly the
    black box this module exists to avoid.
    """
    lat, lon = row.get("lat"), row.get("lon")
    half = W_POSITION / 2.0

    if lat is None or lon is None:
        reasons.append(Reason("position", 0.0, "no position fix"))
        warnings.append("no position fix - this is a search task, not a dispatch")
        return 0.0

    reasons.append(Reason("position", half, f"fix at {lat:.4f}, {lon:.4f}"))

    located = row.get("located") or {}
    radius = located.get("search_radius_m") or located.get("radius_m")
    if radius is None:
        # The coordinate is real; the uncertainty is unknown. Say so by scoring nothing for it
        # rather than by inventing a circle.
        reasons.append(Reason("tightness", 0.0, "no radio circle - accuracy unknown"))
        return half

    if radius <= RADIUS_GOOD_M:
        reasons.append(Reason("tightness", half, f"radio fix within {radius:.0f} m"))
        return W_POSITION

    tightness = max(0.0, min(1.0, (RADIUS_POOR_M - radius) / (RADIUS_POOR_M - RADIUS_GOOD_M)))
    reasons.append(Reason("tightness", half * tightness,
                          f"search circle {radius:.0f} m across"))
    if radius > RADIUS_POOR_M:
        warnings.append(f"a {radius:.0f} m circle needs a team, not a walk")
    return half + half * tightness


def triage_row(row: dict, now: datetime | None = None) -> Triaged:
    """Score one call. Every point traces to a factor, and every factor names its number."""
    now = now or datetime.now(timezone.utc)
    reasons: list[Reason] = []
    warnings: list[str] = []
    score = 0.0

    # ---- people: the question triage is actually about
    people = row.get("people")
    if people is None or people == 0:
        effective = UNKNOWN_PEOPLE_EQUIVALENT
        warnings.append("headcount unknown - scored as "
                        f"{UNKNOWN_PEOPLE_EQUIVALENT}, not as zero")
        detail = f"headcount unknown (scored as {UNKNOWN_PEOPLE_EQUIVALENT})"
    else:
        effective = min(int(people), PEOPLE_CAP)
        detail = f"{people} people" + (f" (capped at {PEOPLE_CAP})" if people > PEOPLE_CAP else "")
    points = W_PEOPLE * (effective / PEOPLE_CAP)
    reasons.append(Reason("people", points, detail))
    score += points

    # ---- position and its uncertainty
    score += _position_factor(row, reasons, warnings)

    # ---- recency
    hours = _hours_since(row.get("created_at"), now)
    if hours is None:
        warnings.append("no usable timestamp - recency not scored")
    elif hours < 0:
        warnings.append("timestamp is in the future - check the handset clock")
    else:
        # Linear decay to zero at STALE_AFTER_HOURS. A curve would be prettier and harder to
        # argue with, which is the wrong trade here.
        freshness = max(0.0, 1.0 - (hours / STALE_AFTER_HOURS))
        points = W_RECENCY * freshness
        reasons.append(Reason("recency", points,
                              f"{hours:.1f} h ago" if hours < 1 else f"{hours:.0f} h ago"))
        score += points

    # ---- battery: a dying handset is the last chance to hear from it
    battery = row.get("battery")
    if battery is None:
        # Not scored, and said out loud. Absence of evidence is not evidence of a full battery,
        # so this neither earns the healthy credit nor claims the handset is dying.
        warnings.append("battery never reported - the handset's condition is unknown")
    elif int(battery) <= LOW_BATTERY_PCT:
        reasons.append(Reason("battery", W_BATTERY,
                              f"{int(battery)}% - this handset will stop beaconing soon"))
        score += W_BATTERY
        warnings.append("expect the signal to stop; fix the position now, not later")
    else:
        points = W_BATTERY * BATTERY_HEALTHY_FRACTION * (int(battery) / 100.0)
        reasons.append(Reason("battery", points,
                              f"{int(battery)}% - no power urgency"))
        score += points

    # ---- repeated reports: the same person heard again is a stronger signal, not a louder one
    reports = int(row.get("reports") or 1)
    if reports > 1:
        warnings.append(f"heard {reports} times - deduplicated, not {reports} people")

    return Triaged(device_id=str(row.get("device_id", "?")), score=score, band=_band(score),
                   people=people, reasons=reasons, warnings=warnings)


def triage(rows: list[dict], now: datetime | None = None) -> dict:
    """Rank a board. Ties break on people, then recency, so the order is never arbitrary."""
    now = now or datetime.now(timezone.utc)
    scored = [triage_row(r, now) for r in rows]
    by_id = {str(r.get("device_id", "?")): r for r in rows}
    scored.sort(key=lambda t: (
        -t.score,
        -(by_id[t.device_id].get("people") or 0),
        -(by_id[t.device_id].get("reports") or 0),
        t.device_id,
    ))
    return {
        "count": len(scored),
        "bands": {b: sum(1 for t in scored if t.band == b)
                  for b in ("critical", "urgent", "routine")},
        "ranked": [t.as_dict() for t in scored],
        "not_a_promise": (
            "This ranks search order from a radio and a timestamp. It is not a judgement about "
            "who matters, it cannot see the person, and a low rank is not a reason to ignore a "
            "report."
        ),
    }
