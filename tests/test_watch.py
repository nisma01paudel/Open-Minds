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
