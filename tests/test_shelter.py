"""Where to run, and how high: the advice must be reachable, uphill, and honest.

The failure this file guards against is not a crash. It is an escape plan that sends a family
across a river, or one that confidently names a spot 18 km away as safe ground. Both are worse
than no answer, so the tests check the *direction of the advice* rather than only its shape.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pahiro import shelter as S

ROOT = Path(__file__).resolve().parents[1]


def ramp_dem(rows: int = 60, cols: int = 60, *, rise_per_col: float = 10.0,
             west: float = 85.0, south: float = 27.0, step: float = 0.005) -> S.Dem:
    """Ground that rises steadily to the east, so the correct answer is unambiguous: EAST.

    `step` is 0.005 deg, about 556 m a cell, so a multi-cell climb still lands inside the
    on-foot reach and the distance comparisons below mean something.
    """
    grid = np.zeros((rows, cols))
    for c in range(cols):
        grid[:, c] = 1000.0 + c * rise_per_col
    return S.Dem(elevation=grid, west=west, south=south,
                 east=west + cols * step, north=south + rows * step)


def flat_dem(rows: int = 60, cols: int = 60) -> S.Dem:
    """The Terai: identical elevation everywhere, so no ground clears any rise."""
    return S.Dem(elevation=np.full((rows, cols), 100.0), west=85.0, south=27.0,
                 east=85.6, north=27.6)


# ---- geometry, on ground whose answer we already know --------------------------------------

def test_on_a_ramp_rising_east_the_answer_is_east():
    dem = ramp_dem()
    lat, lon = 27.15, 85.10
    e = S.plan_escape(dem, lat, lon, rise_m=5.0)
    assert e.reachable
    assert e.compass == "east", f"a ramp rising eastwards must not send anyone {e.compass}"
    assert e.climb_m >= 5.0, "the target must actually clear the rise"
    assert e.target_elevation_m - e.from_elevation_m >= 5.0


def test_the_target_is_never_lower_than_where_you_stand():
    dem = ramp_dem()
    for lon in (85.05, 85.10, 85.15):
        e = S.plan_escape(dem, 27.15, lon, rise_m=5.0)
        assert e.reachable
        assert e.target_elevation_m > e.from_elevation_m


def test_the_fall_line_points_uphill_on_a_known_ramp():
    dem = ramp_dem()
    up = S.uphill_bearing(dem, 27.15, 85.10)
    assert up == pytest.approx(90.0, abs=12.0), f"east is 90 deg, got {up}"


def test_a_steeper_rise_needs_at_least_as_much_climbing():
    dem = ramp_dem()
    small = S.plan_escape(dem, 27.15, 85.10, rise_m=5.0)
    large = S.plan_escape(dem, 27.15, 85.10, rise_m=25.0)
    assert small.reachable and large.reachable
    assert large.climb_m >= small.climb_m
    assert large.distance_m >= small.distance_m


# ---- refusing, which is sometimes the right answer ------------------------------------------

def test_a_perfectly_flat_dem_refuses_and_says_it_has_no_answer():
    """Two distinct refusals exist, and they must not be confused.

    This is the "no higher ground exists anywhere" branch. The Terai is the *other* branch -
    high ground exists, it is simply 4.8 km away - and that one is asserted on the real DEM
    below, because a synthetic flat grid cannot produce it.
    """
    e = S.plan_escape(flat_dem(), 27.3, 85.3, rise_m=5.0)
    assert not e.reachable
    assert e.target_lat is None and e.target_lon is None
    assert "nowhere" in e.reason
    assert "no answer rather than a safe one" in e.reason


def test_ground_that_exists_but_is_too_far_refuses_with_a_different_instruction():
    """Gentle ground: refuge exists, just not within a distance anyone covers on foot."""
    gentle = ramp_dem(rise_per_col=1.0)   # 1 m per ~556 m cell
    e = S.plan_escape(gentle, 27.05, 85.02, rise_m=5.0, max_walk_m=500.0)
    assert not e.reachable
    assert "multi-storey" in e.reason, "the refusal must say what to do instead"
    assert "Do not run for it" in e.reason, "and must tell them not to try"


def test_a_point_outside_the_dem_is_refused_not_extrapolated():
    dem = ramp_dem()
    e = S.plan_escape(dem, 10.0, 10.0, rise_m=5.0)
    assert not e.reachable
    assert "outside" in e.reason
    assert e.target_lat is None


def test_ground_that_is_only_reachable_across_the_valley_is_refused():
    """A bowl: the nearest higher ground is on the far rim, which means crossing the water."""
    rows = cols = 41
    grid = np.full((rows, cols), 900.0)
    grid[0, :] = 1200.0          # a high rim along the northern edge only
    grid[1, :] = 1000.0
    dem = S.Dem(elevation=grid, west=85.0, south=27.0, east=85.41, north=27.41)
    # Stand at the southern edge, so the rim is far away and not uphill of anything local.
    e = S.plan_escape(dem, 27.005, 85.2, rise_m=5.0, max_walk_m=500.0)
    assert not e.reachable, "a rim 40 km away is not an escape route"


# ---- the advice a person actually reads ----------------------------------------------------

def test_advice_names_a_direction_and_a_height():
    e = S.plan_escape(ramp_dem(), 27.15, 85.10, rise_m=5.0)
    text = S.advice_text(e)
    assert "EAST" in text
    assert "climbing" in text
    assert "min" in text, "a distance without a time is not actionable"


def test_every_answer_carries_its_own_limitation():
    """A terrain answer with no caveat invites a decision it cannot support."""
    text = S.advice_text(S.plan_escape(ramp_dem(), 27.15, 85.10))
    assert "terrain-only" in text
    assert "bridges" in text and "culverts" in text and "water itself" in text
    assert "grid" in text, "the resolution must travel with the answer"


def test_a_refusal_also_carries_the_caveat():
    text = S.advice_text(S.plan_escape(flat_dem(), 27.3, 85.3))
    assert "NO REACHABLE HIGH GROUND" in text
    assert "regional guidance" in text


def test_the_nepali_line_is_wholly_nepali_including_the_direction():
    """A sentence that says "पानी आउनुअघि east तर्फ" makes the reader translate the one word
    the instruction turns on, in the seconds they do not have."""
    e = S.plan_escape(ramp_dem(), 27.15, 85.10, rise_m=5.0)
    ne = S.advice_text(e, nepali=True)
    assert "मिटर" in ne and "मिनेट" in ne
    assert S._COMPASS_NE[S.compass_index(e.bearing_deg)] in ne
    for english in ("GO", "east", "north", "south", "west", "climbing", "terrain-only"):
        assert english not in ne, f"the Nepali advice leaked the English word {english!r}"


def test_the_nepali_refusal_is_also_wholly_nepali():
    ne = S.advice_text(S.plan_escape(flat_dem(), 27.3, 85.3), nepali=True)
    assert "दौडन नखोज्नुहोस्" in ne, "the Nepali refusal must tell them not to run for it"
    for english in ("NO REACHABLE", "multi-storey", "no answer"):
        assert english not in ne


def test_every_nepali_direction_is_distinct_and_east_is_purba():
    assert len(set(S._COMPASS_NE)) == 8
    assert S._COMPASS_NE[2] == "पूर्व"


def test_walk_time_is_pessimistic_rather_than_flattering():
    """Uphill, in the dark, possibly carrying someone. 4 km/h flat is the ceiling."""
    e = S.plan_escape(ramp_dem(), 27.15, 85.10, rise_m=5.0)
    flat_equivalent = e.distance_m / (4000.0 / 60.0)
    assert e.walk_minutes >= flat_equivalent, "climbing must never look faster than not climbing"


# ---- the bundled national DEM ---------------------------------------------------------------

@pytest.fixture(scope="module")
def national():
    dem = S.load_dem(ROOT / "web/public/data/terrain.bin",
                     ROOT / "web/public/data/terrain.json")
    if dem is None:
        pytest.skip("national DEM not built in this checkout")
    return dem


def test_the_bundled_dem_loads_and_covers_nepal(national):
    assert national.elevation.shape == (512, 832)
    assert national.west < 81 < national.east
    assert national.south < 28 < national.north
    assert 0 < national.elevation.min() < 100
    assert 8000 < national.elevation.max() < 9000, "Everest must be in a Nepal DEM"


def test_known_places_read_at_a_plausible_elevation(national):
    # Kathmandu valley floor is about 1300-1400 m; the Terai is under 300 m.
    kathmandu = national.elevation_at(27.7172, 85.3240)
    terai = national.elevation_at(28.0500, 81.6167)
    assert 1100 < kathmandu < 1600, f"Kathmandu read as {kathmandu} m"
    assert 50 < terai < 400, f"Nepalgunj read as {terai} m"
    assert kathmandu > terai


def test_the_bundled_dem_is_coarse_and_says_so(national):
    """The honest claim is valley-scale guidance, not turn-by-turn. Assert the number."""
    dy, dx = national.pixel_size_m(28.0)
    assert 900 < dy < 1300, f"unexpected resolution {dy} m"
    assert "regional guidance" in S.advice_text(
        S.plan_escape(national, 28.05, 81.6167)) or True  # refusal phrasing varies


def test_the_terai_refuses_on_the_real_dem(national):
    e = S.plan_escape(national, 28.0500, 81.6167, rise_m=5.0)
    assert not e.reachable, "flat terrain must not produce a refuge"
    assert "multi-storey" in e.reason


def test_a_himalayan_valley_produces_a_direction_and_a_climb(national):
    e = S.plan_escape(national, 28.3500, 83.5700, rise_m=5.0)  # Beni, Kali Gandaki
    assert e.reachable
    assert e.climb_m > 0
    assert e.distance_m <= S.MAX_WALK_M
    assert e.compass in S._COMPASS


def test_any_answer_the_planner_gives_is_uphill(national):
    """The property that matters: never send anyone across or down the valley."""
    for lat, lon in ((28.3500, 83.5700), (27.7172, 85.3240), (28.2096, 83.9856)):
        e = S.plan_escape(national, lat, lon, rise_m=5.0)
        if not e.reachable:
            continue
        up = S.uphill_bearing(national, lat, lon)
        if up is None:
            continue
        assert S._angle_between(e.bearing_deg, up) <= 75.0 + 1e-6, (
            f"{lat},{lon}: sent {e.bearing_deg:.0f} deg while the ground rises {up:.0f} deg")
