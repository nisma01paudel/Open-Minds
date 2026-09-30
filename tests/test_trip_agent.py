"""Ask for a walk in your own words.

Three of these tests are regressions for bugs that produced empty or absurd answers while every
line of code was doing exactly what it was told:

  rejecting trails whose difficulty is not recorded made "an easy walk from Kathmandu" come back
  empty while thousands of real easy walks sat in the bundle;

  screening on "has a view" refused everything, because the bundle has no points of interest and
  the coarse terrain grid reports no climb for most valley paths;

  sorting shortest-first answered "a free half day" with a six-minute stroll.
"""
from __future__ import annotations

from pahiro import trip_agent as T

KATHMANDU = (27.7047, 85.3146)      # Ratna Park, where the buses are


def test_the_fallback_reader_understands_a_plain_request_without_a_model():
    q = T._keywords("easy half day walk, view, bus under Rs 50")
    assert q.difficulty == "easy"
    assert q.max_fare_rs == 50
    assert "view" in q.wants


def test_a_negative_phrase_is_not_read_as_its_opposite():
    """'not too hard' contains 'hard', and reading it literally sends people up a mountain."""
    assert T._keywords("nothing too hard please").difficulty == "easy"
    assert T._keywords("a hard steep climb").difficulty == "hard"


def test_hours_and_minutes_are_both_understood():
    assert T._keywords("about 6 hours").max_minutes == 360
    assert T._keywords("90 minutes").max_minutes == 90


def test_a_model_answer_is_validated_before_it_is_used():
    """The model is a suggestion, not an authority. A hallucinated field is dropped."""

    class Lying:
        def available(self): return True

        def decide(self, prompt, schema):
            return {"difficulty": "extreme", "max_minutes": 100000, "max_fare_rs": -5,
                    "wants": ["view", "dinosaurs"]}

    q = T.parse_request("a gentle walk", Lying())
    assert q.difficulty is None or q.difficulty == "easy", "an invalid difficulty was obeyed"
    assert q.max_minutes is None, "a 100000-minute walk was accepted"
    assert q.max_fare_rs is None, "a negative fare was accepted"
    assert q.wants == ["view"], f"an invented want survived: {q.wants}"
    assert q.dropped, "refused fields must be recorded, not silently discarded"


def test_a_broken_model_does_not_break_planning():
    """A capability that only works when a 1.1 GB server is up is not a capability."""

    class Broken:
        def available(self): return True

        def decide(self, prompt, schema):
            raise RuntimeError("model is down")

    q = T.parse_request("easy walk under Rs 40", Broken())
    assert q.difficulty == "easy"
    assert q.max_fare_rs == 40


def test_an_unrecorded_difficulty_does_not_empty_the_answer():
    """The regression. Most Nepali footpaths carry no sac_scale tag."""
    q, opts = T.plan("easy short walk", KATHMANDU)
    assert opts, "an ordinary request returned nothing - the difficulty screen is back"
    assert any("difficulty not recorded" in f for o in opts for f in o.fits)


def test_a_want_ranks_and_never_rejects():
    """There are no points of interest in the bundle, so 'has a view' is not knowable here."""
    q, opts = T.plan("easy walk with a view", KATHMANDU)
    assert opts, "screening on an unverifiable want emptied the answer again"
    assert any("cannot check" in f or "outlook" in f for o in opts for f in o.fits)


def test_short_fragments_are_not_offered_as_a_walk():
    """The first version returned three 500 m stretches of pavement for every request."""
    q, opts = T.plan("anything", KATHMANDU)
    for o in opts:
        assert o.trail.length_m >= 1500, f"{o.trail.name} is only {o.trail.length_m:.0f} m"


def test_a_longer_request_is_answered_with_a_longer_walk():
    """Sorting shortest-first answered 'a free half day' with a six-minute stroll."""
    _, short = T.plan("a 20 minute walk", KATHMANDU)
    _, long = T.plan("a 4 hour walk", KATHMANDU)
    if short and long:
        assert long[0].trail.walk_minutes >= short[0].trail.walk_minutes


def test_every_option_says_how_to_get_there_and_what_it_costs():
    """The bus is the part that decides whether somebody goes."""
    q, opts = T.plan("easy walk", KATHMANDU)
    assert opts
    for o in opts:
        assert o.access.ok, "an option with no way to reach it is not an option"
        assert o.access.fare_rs and o.access.fare_rs >= 24
        assert o.line().count("bus") >= 1


def test_the_understood_request_is_returned_alongside_the_options():
    """Showing what was understood is the difference between a planner and a slot machine."""
    q, _ = T.plan("easy 2 hour walk, bus under Rs 40", KATHMANDU)
    assert "easy" in q.describe()
    assert "Rs 40" in q.describe()
