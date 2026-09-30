"""Triage: the ranking has to be explainable, stable and honest about what it cannot see.

The invariant that matters most is `test_every_point_traces_to_a_reason`. A score whose parts do
not add up to the whole is a black box wearing an explanation, and a coordinator cannot argue
with it — which is the entire reason this is deterministic instead of a model.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pahiro import triage as T

NOW = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)


def row(**kw) -> dict:
    base = {
        "device_id": "dev-1",
        "people": 2,
        "created_at": (NOW - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "lat": 28.35,
        "lon": 83.57,
        "accuracy_m": 20.0,
        "battery": 80,
        "reports": 1,
    }
    base.update(kw)
    return base


# ---- the arithmetic is a whole -----------------------------------------------------------------

def test_the_weights_sum_to_one_hundred():
    """So a score reads directly as a percentage of the maximum, which is easy to argue with."""
    total = T.W_PEOPLE + T.W_POSITION + T.W_RECENCY + T.W_BATTERY
    assert total == pytest.approx(100.0), f"weights sum to {total}"


def test_every_point_traces_to_a_reason():
    """The score must be exactly the sum of the factors that claim to produce it."""
    for r in (
        row(),
        row(people=None),
        row(lat=None, lon=None),
        row(battery=5),
        row(battery=None),
        row(people=40, battery=2, located={"search_radius_m": 400}),
        row(located={"search_radius_m": 12}),
    ):
        t = T.triage_row(r, NOW)
        explained = sum(x.points for x in t.reasons)
        assert t.score == pytest.approx(explained, abs=0.01), (
            f"score {t.score} but reasons sum to {explained} for {r}")


def test_the_most_urgent_call_scores_the_maximum_and_bands_critical():
    """Maximum = most people, tightest fix, freshest, and a handset about to die.

    The battery weight is earned by *urgency*, so the top of the range is a dying phone, not a
    fully charged one - which is the whole point of the factor."""
    t = T.triage_row(row(people=T.PEOPLE_CAP, battery=5,
                         located={"search_radius_m": 10}), NOW)
    assert t.score == pytest.approx(100.0, abs=1.0)
    assert t.band == "critical"


def test_a_hopeless_call_scores_low_and_does_not_band_critical():
    t = T.triage_row(row(people=1, lat=None, lon=None, battery=None,
                         created_at=(NOW - timedelta(hours=40)).isoformat()
                         .replace("+00:00", "Z")), NOW)
    assert t.score < 20
    assert t.band == "routine"


# ---- the factors, one at a time ----------------------------------------------------------------

def test_more_people_outranks_fewer_all_else_equal():
    many = T.triage_row(row(people=8), NOW)
    few = T.triage_row(row(people=1), NOW)
    assert many.score > few.score
    # and the panel is told so, with the number
    assert any(x.factor == "people" and "8 people" in x.detail for x in many.reasons)


def test_an_unknown_headcount_is_scored_as_something_not_as_zero():
    """A blank field must not bury a genuine call, and must not outrank a stated group either."""
    unknown = T.triage_row(row(people=None), NOW)
    one = T.triage_row(row(people=1), NOW)
    many = T.triage_row(row(people=8), NOW)
    assert unknown.score > one.score, "unknown must not be treated as nobody"
    assert unknown.score < many.score, "unknown must not outrank a stated group"
    assert any("headcount unknown" in w for w in unknown.warnings)


def test_a_report_with_no_position_is_flagged_as_a_different_task():
    t = T.triage_row(row(lat=None, lon=None), NOW)
    assert any("search task" in w for w in t.warnings)
    assert t.score < T.triage_row(row(), NOW).score


def test_a_tight_circle_beats_a_wide_one():
    tight = T.triage_row(row(located={"search_radius_m": 15}), NOW)
    wide = T.triage_row(row(located={"search_radius_m": 700}), NOW)
    hopeless = T.triage_row(row(located={"search_radius_m": 1200}), NOW)
    assert tight.score > wide.score > hopeless.score
    assert any("700" in x.detail for x in wide.reasons)
    assert any("1200 m circle needs a team" in w for w in hopeless.warnings)


def test_a_fix_without_a_circle_is_accepted_but_not_credited_fully():
    """Half credit: the coordinate is real, the uncertainty is unknown. Say so by scoring it."""
    no_circle = T.triage_row(row(located=None), NOW)
    tight = T.triage_row(row(located={"search_radius_m": 15}), NOW)
    assert no_circle.score < tight.score
    assert no_circle.score > T.triage_row(row(lat=None, lon=None), NOW).score


@pytest.mark.parametrize("hours", [0.5, 6, 20])
def test_recency_decays_and_never_goes_negative(hours):
    fresh = T.triage_row(row(), NOW)
    older = T.triage_row(
        row(created_at=(NOW - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")), NOW)
    assert older.score <= fresh.score
    assert all(x.points >= 0 for x in older.reasons)


def test_a_call_older_than_the_stale_window_scores_no_recency_but_still_says_so():
    """A factor that contributes nothing is still shown, at zero. Hiding it would make the
    panel's arithmetic look wrong to the person reading it."""
    t = T.triage_row(
        row(created_at=(NOW - timedelta(hours=30)).isoformat().replace("+00:00", "Z")), NOW)
    recency = [x for x in t.reasons if x.factor == "recency"]
    assert len(recency) == 1
    assert recency[0].points == 0.0
    assert "30 h ago" in recency[0].detail


def test_a_dying_handset_raises_urgency_and_says_why():
    """The last chance to hear from a phone is not the least urgent moment; it is the most."""
    low = T.triage_row(row(battery=5), NOW)
    high = T.triage_row(row(battery=95), NOW)
    assert low.score > high.score
    assert any("stop beaconing" in x.detail for x in low.reasons)
    assert any("fix the position now" in w for w in low.warnings)


def test_an_unreported_battery_earns_nothing_and_claims_nothing():
    """Absence of evidence must not read as a full battery, and must not read as a dying one.

    It therefore scores no battery points, takes no low-battery urgency, and says out loud that
    the handset's condition is unknown. A dying handset legitimately outranks it: that one is
    the last chance to hear from the phone.
    """
    unknown = T.triage_row(row(battery=None), NOW)
    healthy = T.triage_row(row(battery=100), NOW)
    dying = T.triage_row(row(battery=1), NOW)

    assert not any(x.factor == "battery" for x in unknown.reasons)
    assert not any("stop beaconing" in x.detail for x in unknown.reasons)
    assert any("battery never reported" in w for w in unknown.warnings)
    assert unknown.score < healthy.score, "unknown is not evidence of a healthy phone"
    assert dying.score > healthy.score, "a dying phone is the most urgent, not the least"


def test_being_heard_repeatedly_is_not_counted_as_more_people():
    """A flood reports the same call by several paths. Three frames is not three people."""
    t = T.triage_row(row(reports=3), NOW)
    assert t.people == 2
    assert any("not 3 people" in w for w in t.warnings)


# ---- clocks and bad input ----------------------------------------------------------------------

def test_a_timestamp_from_the_future_is_flagged_rather_than_trusted():
    t = T.triage_row(
        row(created_at=(NOW + timedelta(hours=3)).isoformat().replace("+00:00", "Z")), NOW)
    assert any("future" in w for w in t.warnings)
    assert not any(x.factor == "recency" for x in t.reasons)


def test_a_missing_or_unparseable_timestamp_is_not_scored_and_is_flagged():
    for created in (None, "", "yesterday", "2026-13-45T99:99:99Z"):
        t = T.triage_row(row(created_at=created), NOW)
        assert not any(x.factor == "recency" for x in t.reasons)
        assert any("timestamp" in w for w in t.warnings)


def test_a_call_with_nothing_but_an_id_does_not_crash():
    t = T.triage_row({"device_id": "lonely"}, NOW)
    assert t.device_id == "lonely"
    assert t.score >= 0


# ---- the board ---------------------------------------------------------------------------------

def test_the_board_is_ordered_worst_first_and_is_deterministic():
    rows = [
        row(device_id="a", people=1, battery=90),
        row(device_id="b", people=8, battery=5, located={"search_radius_m": 12}),
        row(device_id="c", people=4, battery=50),
    ]
    first = T.triage(rows, NOW)
    second = T.triage(list(reversed(rows)), NOW)
    assert [x["device_id"] for x in first["ranked"]] == [x["device_id"] for x in second["ranked"]]
    assert first["ranked"][0]["device_id"] == "b", "the urgent one must lead"


def test_ties_break_on_people_then_reports_never_arbitrarily():
    rows = [
        row(device_id="z", people=2, reports=1, battery=None),
        row(device_id="y", people=6, reports=1, battery=None),
        row(device_id="x", people=6, reports=4, battery=None),
    ]
    order = [r["device_id"] for r in T.triage(rows, NOW)["ranked"]]
    assert order[0] == "x", "same score and same people: the repeatedly-heard one leads"
    assert order[1] == "y"


def test_the_board_reports_bands_the_caveat_and_the_count():
    out = T.triage([row(device_id=str(i)) for i in range(5)], NOW)
    assert out["count"] == 5
    assert sum(out["bands"].values()) == 5
    assert "not a judgement about who matters" in out["not_a_promise"]
    assert "low rank is not a reason to ignore" in out["not_a_promise"]


def test_an_empty_board_is_an_empty_board_not_an_error():
    out = T.triage([], NOW)
    assert out["count"] == 0
    assert out["ranked"] == []
    assert out["bands"] == {"critical": 0, "urgent": 0, "routine": 0}
