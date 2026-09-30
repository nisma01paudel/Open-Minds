"""Getting to the trailhead.

The fare is a dated, sourced estimate and the bus route is not known at all. These tests hold
that line: the output must be useful without pretending to be a timetable.
"""
from __future__ import annotations

from pahiro import access


def test_the_fare_never_goes_below_the_published_minimum():
    """Rs 24 is the Bagmati Province valley minimum as of April 2026. An estimate that dips under
    the legal floor is wrong in the direction that wastes someone's money."""
    for km in (0.0, 0.5, 2.0, 5.0):
        assert access.fare_for(km) >= access.FARE_MIN_RS, f"{km} km gave a fare below the minimum"


def test_the_fare_rises_with_distance():
    fares = [access.fare_for(km) for km in (1, 5, 10, 20, 40)]
    assert fares == sorted(fares), f"fares are not monotonic: {fares}"
    assert fares[-1] > fares[0]


def test_the_fare_carries_its_date_and_source():
    """A fare with no date is a fare that is quietly wrong forever."""
    assert access.FARE_AS_OF, "the fare snapshot has no date"
    assert "dotm" in access.FARE_SOURCE.lower() or "Transport Management" in access.FARE_SOURCE


def test_the_bundled_stops_are_the_real_ones_from_openstreetmap():
    parks = access.load_parks()
    assert len(parks) > 50, f"only {len(parks)} stops bundled"
    # The valley has around 141 mapped bus stations; the fallback list has 9.
    assert len(parks) > 20, "the OSM extract is missing and the fallback list is being used"


def test_an_unnamed_stop_is_described_by_where_it_is_rather_than_invented():
    """Most mapped stops have no name. Inventing one would send a walker to the wrong place."""
    parks = access.load_parks()
    unnamed = [n for n, _, _ in parks if n.startswith("mapped stop at")]
    assert unnamed, "expected some unnamed stops in the OSM extract"
    for n in unnamed[:3]:
        # it must carry coordinates, so a phone can still navigate to it
        assert any(ch.isdigit() for ch in n)


def test_the_answer_names_the_park_a_kathmandu_walker_would_actually_use():
    """Budhanilkantha is the stop for the Shivapuri trailhead. If the planner picks something
    else, the scoring is wrong - the nearest point is not always the right bus."""
    a = access.to_trailhead(27.8080, 85.3830, 27.7047, 85.3146)
    assert a.ok
    assert "Budhanilkantha" in a.park, f"picked {a.park!r} for the Shivapuri trailhead"
    assert a.fare_rs and a.fare_rs >= access.FARE_MIN_RS


def test_it_says_what_it_does_not_know():
    """Schedules, bandha and route changes are unknown, and the output says so rather than
    implying a timetable."""
    a = access.to_trailhead(27.8080, 85.3830, 27.7047, 85.3146)
    joined = " ".join(a.notes).lower()
    assert "schedules" in joined or "bandha" in joined
    assert "dotm" in joined or "confirm" in joined


def test_a_trailhead_no_bus_reaches_is_flagged_as_such():
    """Far out in the hills, the honest answer is that the bus does not go there."""
    a = access.to_trailhead(28.0500, 85.6000, 27.7047, 85.3146)
    assert a.ok
    assert any("on foot" in n for n in a.notes), \
        "a 30 km walk from the last stop must be flagged, not presented as a bus trip"
