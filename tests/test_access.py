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
    # The valley has around 321 mapped bus stations; the fallback list has 9.
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


# ---- the bus data covers one region; the trails cover four --------------------------------------

def test_a_trailhead_outside_the_stop_data_is_refused_rather_than_given_a_number():
    """The regression, and it was user-facing harm.

    With trails covering four regions and stops covering only the Kathmandu valley, a Namche
    trailhead produced: "bus to mapped stop at 27.7124, 85.4746 (~122.4 km, about Rs 377), then
    122.1 km on foot". Every figure there is invented - there is no 122 km valley bus, and Rs 377
    is a linear extrapolation of a fare table that does not reach that far.

    Telling somebody to walk 122 km is worse than telling them nothing.
    """
    a = access.to_trailhead(27.807, 86.714, 27.807, 86.714)     # Namche Bazaar, Khumbu
    assert not a.ok, "a Khumbu trailhead was given a Kathmandu bus route"
    assert "does not cover this region" in a.reason
    assert "Kathmandu" in a.reason and "Pokhara" in a.reason, \
        "the refusal must name what IS covered, and that changed when Pokhara was added"
    assert a.fare_rs is None, "a refused answer must not carry a fabricated fare"


def test_the_kathmandu_answer_still_works():
    """The refusal must not swallow the case the data actually covers."""
    a = access.to_trailhead(27.8080, 85.3830, 27.7047, 85.3146)
    assert a.ok, a.reason
    assert "Budhanilkantha" in a.park
    assert a.fare_rs and a.fare_rs < 100, "a valley fare must not extrapolate into the hundreds"


def test_the_fare_model_is_not_trusted_beyond_its_range():
    """A linear approximation is fine over a valley and nonsense over a country."""
    assert access.MAX_RIDE_M <= 80_000, \
        "the stop data is one valley; a 100 km 'ride' is not a bus journey"


# ---- a name a person can navigate to -------------------------------------------------------------

def test_a_route_is_not_a_place_to_stand():
    """'Bus to Kathmandu' is a direction, not a stop. Nobody can walk to it."""
    assert not access.is_a_place_name("Bus to Kathmandu")
    assert not access.is_a_place_name("Bus from Pokhara")
    assert not access.is_a_place_name("Stand towards Dhunche")


def test_a_facility_is_not_a_place_to_stand():
    """'Ticket bus counter' names a thing you visit, not a place you arrive at."""
    assert not access.is_a_place_name("Ticket bus counter")
    assert not access.is_a_place_name("Enquiry office")
    assert not access.is_a_place_name("Booking stand")


def test_a_real_name_survives_even_when_it_contains_those_words():
    """The test looks at the SHAPE of a name, not at the presence of a word - which is the whole
    reason it is two patterns rather than a blocklist that grows every time somebody sees a new
    phrasing."""
    for good in ("Battar buspark", "Kutumsang", "Trishuli Bus Station",
                 "Melamchighyang Bus Stop", "Counter Junction", "Gongabu (New Bus Park)",
                 "Machhapokhari"):
        assert access.is_a_place_name(good), f"{good!r} is a real place and was dropped"


def test_the_langtang_prose_names_are_described_by_where_they_are():
    """The regression. These two came out of the OSM data as the destination for a Syaphrubesi
    trailhead, and 'bus to Ticket bus counter' is not an instruction anybody can follow."""
    parks = access.load_parks()
    names = [n for n, _, _ in parks]
    assert not any(n.strip().lower() == "bus to kathmandu" for n in names)
    assert not any(n.strip().lower() == "ticket bus counter" for n in names)
    # and the stop is still there, just described by its position
    assert any(n.startswith("mapped stop at") for n in names)


def test_dropping_a_prose_name_does_not_drop_the_stop():
    """The stop still exists and is still reachable - it has simply lost an unusable label."""
    before = len(access.load_parks())
    assert before >= 335, "the stop list lost entries rather than labels"
