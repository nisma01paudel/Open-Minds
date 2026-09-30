"""Spoken guidance: one short line at a time, in Nepali, and correct about the direction.

The dangerous failure here is a navigator that congratulates someone for climbing while they
descend, or that tells a person who has gained 20 m of a 200 m climb that they are failing.
Both are asserted below.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from pahiro import navigate as N
from pahiro import shelter as S

ROOT = Path(__file__).resolve().parents[1]

DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def ramp_dem(rows: int = 40, cols: int = 40, *, rise_per_col: float = 10.0) -> S.Dem:
    grid = np.zeros((rows, cols))
    for c in range(cols):
        grid[:, c] = 1000.0 + c * rise_per_col
    return S.Dem(elevation=grid, west=85.0, south=27.0, east=85.0 + cols * 0.005,
                 north=27.0 + rows * 0.005)


def flat_dem() -> S.Dem:
    return S.Dem(elevation=np.full((40, 40), 100.0), west=85.0, south=27.0,
                 east=85.2, north=27.2)


@pytest.fixture
def plan():
    return S.plan_escape(ramp_dem(), 27.05, 85.02, rise_m=5.0)


# ---- the spoken vocabulary ------------------------------------------------------------------

def test_every_phrase_is_available_in_both_languages():
    assert set(N.PHRASES) == set(N.EN), "a phrase in one language and not the other"
    for key, ne in N.PHRASES.items():
        assert DEVANAGARI.search(ne), f"{key} is not written in Devanagari"
        assert ne.strip(), f"{key} is empty"
        assert N.EN[key].strip()


def test_the_essential_instruction_is_present_and_means_climb():
    """'माथि जानुहोस्' - go up. The one line that has to exist."""
    assert N.PHRASES["go_up"] == "माथि जानुहोस्"
    assert N.EN["go_up"] == "Go up"


def test_no_spoken_line_mixes_english_into_the_nepali():
    """The reader cannot translate the one word the instruction turns on."""
    for key, ne in N.PHRASES.items():
        for english in ("go", "up", "down", "water", "building", "floor", "run"):
            assert english not in ne.lower(), f"{key} leaked {english!r}"


# ---- the briefing ---------------------------------------------------------------------------

def test_the_first_step_sent_anyone_is_away_from_the_water(plan):
    """Even before direction: the stream is what kills, and it is the first thing to leave."""
    s = N.steps(plan)
    assert s[0].ne == N.PHRASES["away_water"]
    assert s[0].kind == "climb"


def test_the_briefing_gives_a_direction_then_a_distance_then_a_height(plan):
    s = N.steps(plan)
    joined_ne = " ".join(x.ne for x in s)
    direction = N._COMPASS_NE[S.compass_index(plan.bearing_deg)]
    assert direction in joined_ne, "the Nepali direction word must appear"
    assert "मिटर" in joined_ne, "a distance must be spoken"
    assert f"{plan.target_elevation_m:.0f}" in joined_ne, "the target height must be spoken"


def test_a_refusal_becomes_instructions_and_not_a_direction(plan):
    steps = N.steps(S.plan_escape(flat_dem(), 27.05, 85.02, rise_m=5.0))
    kinds = {x.kind for x in steps}
    assert kinds == {"unreachable"}
    spoken = " ".join(x.ne for x in steps)
    assert N.PHRASES["tall_building"] in spoken
    assert N.PHRASES["dont_run"] in spoken


def test_the_briefing_is_short_enough_to_say_out_loud():
    steps = N.steps(S.plan_escape(ramp_dem(), 27.05, 85.02), limit=5)
    assert 3 <= len(steps) <= 5, "a briefing nobody can finish is not a briefing"


# ---- live guidance --------------------------------------------------------------------------

def test_walking_uphill_is_confirmed(plan):
    """Still below the target, but higher than a moment ago: that is progress."""
    dem = ramp_dem()   # 10 m per 556 m cell; the plan starts at 1040 m and targets 1050 m
    step = N.update(plan, dem, 27.05, 85.02, started_elevation_m=1000.0,
                    last_elevation_m=1005.0)
    assert step.elevation_now_m == pytest.approx(1040.0)
    assert step.kind == "climb"
    assert step.ne.startswith(N.PHRASES["keep_up"])
    assert step.remaining_m is not None and step.remaining_m > 0


def test_losing_height_is_called_out_immediately(plan):
    """Downhill is easier and faster, which is exactly why a panicking person does it.

    The contradiction to avoid in a fixture: `last_elevation_m` must be higher than the ground
    the person is standing on, or it is not a descent at all.
    """
    dem = ramp_dem()
    step = N.update(plan, dem, 27.05, 85.02, started_elevation_m=1010.0,
                    last_elevation_m=1060.0)   # they were up at 1060 m and are now at 1040 m
    assert step.elevation_now_m == pytest.approx(1040.0)
    assert step.kind == "wrong_way"
    assert N.PHRASES["wrong_way"] in step.ne
    assert N.PHRASES["go_up"] in step.ne, "correcting must include what to do instead"


def test_climbing_part_of_the_way_is_encouraged_not_criticised():
    """Someone who has gained 20 m of a 200 m climb is doing the right thing.

    The check is relative to where they started, never to the summit, or the app would tell a
    person making good progress that they are failing.
    """
    dem = ramp_dem(rise_per_col=5.0)          # 1000, 1005, 1010, 1015 ... per 556 m cell
    e = S.plan_escape(dem, 27.05, 85.01, rise_m=5.0)
    assert e.reachable, "precondition: this ramp must produce a plan"
    assert e.target_elevation_m > 1015.0, "precondition: the summit is still ahead"
    step = N.update(e, dem, 27.05, 85.015, started_elevation_m=1005.0,
                    last_elevation_m=1012.0)   # climbed 1005 -> 1015, summit still ahead
    assert step.elevation_now_m == pytest.approx(1015.0)
    assert step.kind == "climb", "partial progress must not read as failure"
    assert step.remaining_m is not None and step.remaining_m > 0


def test_reaching_the_target_height_says_so(plan):
    dem = ramp_dem()
    step = N.update(plan, dem, 27.05, 85.10, started_elevation_m=1000.0)
    assert step.kind == "arrived"
    assert step.ne == N.PHRASES["arrived"]
    assert step.remaining_m == 0.0


def test_live_guidance_on_an_impossible_escape_sends_you_to_a_building(plan):
    e = S.plan_escape(flat_dem(), 27.05, 85.02, rise_m=5.0)
    step = N.update(e, flat_dem(), 27.05, 85.02)
    assert step.kind == "unreachable"
    assert step.ne == N.PHRASES["tall_building"]


def test_live_guidance_never_returns_an_empty_line(plan):
    dem = ramp_dem()
    for lon in (85.01, 85.02, 85.03, 85.04):
        step = N.update(plan, dem, 27.05, lon, started_elevation_m=1000.0)
        assert step.ne.strip() and step.en.strip()
        assert DEVANAGARI.search(step.ne)


# ---- the serialisable summary the API and client share --------------------------------------

def test_the_plan_summary_carries_both_languages_and_the_steps(plan):
    s = N.plan_summary(plan)
    assert s["reachable"] is True
    assert s["compass_ne"] and DEVANAGARI.search(s["compass_ne"])
    assert s["spoken"]["first_ne"] and s["spoken"]["heading_ne"]
    assert 3 <= len(s["steps"]) <= 5
    for step in s["steps"]:
        assert step["ne"] and step["en"] and step["kind"]


def test_the_summary_is_json_serialisable(plan):
    import json
    json.dumps(N.plan_summary(plan))
    json.dumps(N.plan_summary(S.plan_escape(flat_dem(), 27.05, 85.02)))


def test_the_summary_of_a_refusal_is_also_speakable():
    s = N.plan_summary(S.plan_escape(flat_dem(), 27.05, 85.02, rise_m=5.0))
    assert s["reachable"] is False
    assert s["compass_ne"] is None
    assert all(x["kind"] == "unreachable" for x in s["steps"])


def test_the_api_exposes_the_navigation():
    """A navigator the API never returns is dead code in a client nobody can reach."""
    src = (ROOT / "src/pahiro/api.py").read_text(encoding="utf-8")
    assert "navigate.plan_summary" in src
    assert "/api/v1/escape" in src
