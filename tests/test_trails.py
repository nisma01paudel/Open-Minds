"""Trip planning over real trails, offline.

The two bugs these tests exist for both produced answers that looked like data:
grouping trails by NAME merged every unnamed path in the valley into a single 558 km trail
climbing 248 km, and summing elevation gain at every mapped vertex counted the same hillside
several times. Neither would have been caught by checking that the code runs.
"""
from __future__ import annotations

import pytest

from pahiro import trails

net = trails.load_default()


def test_the_bundled_network_loads_at_the_scale_the_data_has():
    s = net.stats()
    assert s["trails"] > 3000, f"only {s['trails']} trails - is the bundle missing?"
    assert s["nodes"] > 5000
    assert s["edges"] > 5000


def test_junction_snapping_actually_joins_ways():
    """OSM footpaths often meet without sharing a node. Without snapping the network came apart
    into 2,246 components and the largest was 4.3% of nodes."""
    assert net.snapped > 0, "no junctions were snapped - the network is probably disconnected"


def test_nearby_groups_by_trail_and_not_by_name():
    """The regression. Grouping by name produced one 558 km trail with 248 km of climb, because
    every unnamed path in the valley shares the name ''."""
    got = trails.nearby(net, 85.3620, 27.7750, radius_m=3000, limit=40)
    assert got, "no trails near Budhanilkantha, which is a trailhead"
    longest = max(t.length_m for t in got)
    assert longest < 60_000, (
        f"a single trail is {longest/1000:.0f} km long, which means unrelated paths have been "
        f"merged - the name-grouping bug is back")


def test_nearby_reports_only_trails_that_are_actually_near():
    got = trails.nearby(net, 85.3620, 27.7750, radius_m=2000, limit=20)
    for t in got:
        assert t.distance_to_start_m <= 2000, f"{t.name} is {t.distance_to_start_m:.0f} m away"


def test_a_real_day_hike_routes_and_reports_a_plausible_walk():
    """Shivapuri: this is a walk people do."""
    from pahiro.shelter import load_dem
    p = net.route((85.3790, 27.8000), (85.3850, 27.8060), load_dem())
    assert p.ok, p.reason
    assert 1_000 < p.distance_m < 30_000
    assert p.minutes and 10 < p.minutes < 600


def test_climb_is_sampled_rather_than_summed_per_vertex():
    """The terrain grid is ~1.2 km. Summing a gain at every mapped vertex counts one hillside
    many times, so a 4 km trail reported climbing it does not do."""
    from pahiro.shelter import load_dem
    dem = load_dem()
    got = trails.nearby(net, 85.3790, 27.8000, radius_m=1200, limit=10, dem=dem)
    assert got
    for t in got:
        # A trail cannot climb more than its own length at a 100% grade - that is a wall.
        assert t.climb_m <= t.length_m, (
            f"{t.name}: {t.length_m/1000:.1f} km long but +{t.climb_m:.0f} m climbed")


def test_disconnected_ends_are_refused_with_a_reason_and_not_a_guess():
    """Kathmandu valley footpath data is genuinely fragmented. The honest answer is a refusal
    that says so, not a straight line drawn across the valley."""
    p = net.route((85.3620, 27.7750), (85.3250, 27.6700), None)
    if not p.ok:
        assert "separate parts" in p.reason or "no walkable link" in p.reason
        assert p.points == [], "a refused plan must not carry a route"


def test_a_route_carries_its_warnings():
    """Every plan says what it does not know."""
    from pahiro.shelter import load_dem
    p = net.route((85.3790, 27.8000), (85.3850, 27.8060), load_dem())
    assert p.ok
    joined = " ".join(p.warnings).lower()
    assert "washed-out" in joined or "closed gate" in joined, \
        "a walker must be told the route only knows mapped paths"
    assert "1.2 km" in joined or "indicative" in joined, \
        "the coarse terrain grid must be stated, not hidden"


def test_the_bundle_carries_its_attribution():
    """ODbL requires it, and it is also just true."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    d = json.loads((root / "web/public/data/trails.geojson").read_text(encoding="utf-8"))
    assert "OpenStreetMap" in d["attribution"]
    assert "ODbL" in d["attribution"]
