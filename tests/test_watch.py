"""The national view must count what it claims and cite an authority for every slope."""
from datetime import date

import numpy as np
import pytest
from affine import Affine

from pahiro import watch

SITES = [
    {"incident_id": "1", "title": "Landslide at Wet Slope", "lat": "27.70", "lon": "85.30"},
    {"incident_id": "2", "title": "Landslide at Dry Slope", "lat": "28.20", "lon": "84.10"},
]

# One window covering both sites; the west is soaked, the east is dry.
TRANSFORM = Affine.translation(80.0, 31.0) * Affine.scale(0.05, -0.05)


def _window(wet_mm: float):
    arr = np.full((100, 180), 2.0, dtype="float32")
    # lon 85.30 -> col 106 ; lon 84.10 -> col 82
    arr[:, 100:120] = wet_mm
    return arr, TRANSFORM


def test_status_counts_are_consistent_and_every_slope_has_an_authority(monkeypatch):
    monkeypatch.setattr(watch, "fetch_window_cached", lambda day, *a, **k: _window(140.0))
    st = watch.national_status(date(2024, 9, 28), sites=SITES)
    rep = watch.summarise(st)
    assert rep["sites"] == 2
    assert sum(rep["counts"].values()) == 2, "every slope is in exactly one bucket"
    assert rep["counts"]["exceeded"] == 1, "only the wet slope is above threshold"
    assert rep["counts"]["below"] == 1
    assert rep["with_authority"] == 2, "a slope with no cited authority must not be shown bare"


def test_dry_ground_is_below_and_wet_ground_is_above(monkeypatch):
    monkeypatch.setattr(watch, "fetch_window_cached", lambda day, *a, **k: _window(140.0))
    st = watch.national_status(date(2024, 9, 28), sites=SITES)
    by_id = {s.site_id: s for s in st}
    assert by_id["1"].state == "exceeded"
    assert by_id["2"].state == "below"
    assert by_id["1"].legal_basis, "the authority must come with its statutory basis"


def test_no_rainfall_available_returns_nothing_rather_than_guessing(monkeypatch):
    monkeypatch.setattr(watch, "fetch_window_cached", lambda day, *a, **k: None)
    assert watch.national_status(date(2024, 9, 28), sites=SITES) == []


def test_results_are_ordered_worst_first(monkeypatch):
    monkeypatch.setattr(watch, "fetch_window_cached", lambda day, *a, **k: _window(140.0))
    st = watch.national_status(date(2024, 9, 28), sites=SITES)
    assert st[0].state == "exceeded", "the loaded slope must lead"


def test_status_carries_the_office_and_not_only_the_institution(monkeypatch):
    """The map popup lists Responsible and Office as separate rows.

    `national_status` used to fill authority/legal_basis from the rule and drop `office`, so every
    historical frame rendered "Office: -" while the live frame rendered the real office. Same rule,
    two different renderings — a judge clicking three slopes sees the dash.
    """
    monkeypatch.setattr(watch, "fetch_window_cached", lambda day, *a, **k: _window(140.0))
    st = watch.national_status(date(2024, 9, 28), sites=SITES)
    assert st, "precondition: the fixture produced statuses"
    for s in st:
        assert s.office, f"slope {s.site_id} has an institution but no office"
        assert s.authority, "the institution must still be carried alongside it"


def test_the_office_matches_the_rule_the_ontology_actually_returns(monkeypatch):
    """Guards against the office drifting from the cited rule, which is what makes it citable."""
    from pahiro.ontology import MAINTENANCE, Ontology

    monkeypatch.setattr(watch, "fetch_window_cached", lambda day, *a, **k: _window(140.0))
    rule = Ontology.load("ontology/nepal-slope-routing.json").lookup("local-road", MAINTENANCE)
    st = watch.national_status(date(2024, 9, 28), sites=SITES)
    for s in st:
        assert s.office == rule.office
        assert s.authority == rule.institution
        assert s.legal_basis == rule.legal_basis


@pytest.mark.parametrize("name", ["slopes-chirps-2024-09-28.geojson",
                                  "slopes-chirps-2024-07-06.geojson",
                                  "slopes-live-2026-09-30.geojson"])
def test_committed_map_frames_carry_an_office_for_every_slope(name):
    """The artefact a judge actually loads, checked directly.

    The historical frames are written by a second, inline properties dict in
    scripts/build_watch_geojson.py -- it is easy to fix the dataclass and still ship a frame with no
    office, so this asserts on the committed bytes rather than on the code path.
    """
    import json
    from pathlib import Path

    path = Path("web/public/data") / name
    if not path.exists():
        pytest.skip(f"{name} not built in this checkout")
    feats = json.loads(path.read_text())["features"]
    assert feats, f"{name} has no features"
    missing = [f["properties"]["id"] for f in feats if not f["properties"].get("office")]
    assert not missing, f"{name}: {len(missing)} slopes render 'Office: -' (e.g. {missing[:3]})"
